from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import replace
from datetime import datetime, timezone

from analyzemail.classify import SenderAggregator, classify_message
from analyzemail.models import ClassificationResult, ParseStats
from analyzemail.parser import iter_parsed_mbox
from analyzemail.reports import (
    build_summary_text_from_totals,
    create_report_paths,
    write_candidate_senders_report,
    write_candidate_threads_report,
    write_empty_candidate_threads,
    write_gmail_filters_report,
)
from analyzemail.threads import build_threads


def _parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyzemail",
        description="Analyze Gmail Takeout mbox files and generate conservative cleanup reports.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan an mbox file and generate reports")
    scan_parser.add_argument("--mbox", required=True, help="Path to Gmail Takeout .mbox file")
    scan_parser.add_argument("--out-dir", default="reports", help="Directory where scan output folders are created")
    scan_parser.add_argument(
        "--min-age-days",
        type=int,
        default=365,
        help="Minimum age in days for deletion candidates (default: 365)",
    )
    scan_parser.add_argument(
        "--max-senders-per-filter",
        type=int,
        default=25,
        help="Maximum sender addresses per generated Gmail filter query (default: 25)",
    )
    scan_parser.add_argument(
        "--now",
        default=None,
        help="Override current time in ISO8601 format for deterministic output",
    )
    scan_parser.add_argument(
        "--detail-level",
        choices=["lightweight", "full"],
        default="lightweight",
        help="lightweight streams sender/message outputs with lower memory; full includes thread graph analysis",
    )

    return parser


def _write_candidate_messages_header(writer: csv.writer) -> None:
    writer.writerow(
        [
            "message_index",
            "message_id",
            "date_utc",
            "from_address",
            "subject",
            "age_days",
            "size_bytes",
            "confidence",
            "strong_signals",
            "weak_signals",
        ]
    )


def _write_candidate_message_row(writer: csv.writer, result: ClassificationResult) -> None:
    writer.writerow(
        [
            result.message.index,
            result.message.message_id or "",
            result.message.date_utc.isoformat() if result.message.date_utc else "",
            result.message.from_address,
            result.message.subject,
            result.age_days if result.age_days is not None else "",
            result.message.size_bytes,
            result.confidence,
            "|".join(result.strong_signals),
            "|".join(result.weak_signals),
        ]
    )


def _run_scan(args: argparse.Namespace) -> int:
    if args.min_age_days <= 0:
        print("error: --min-age-days must be > 0", file=sys.stderr)
        return 2
    if args.max_senders_per_filter <= 0:
        print("error: --max-senders-per-filter must be > 0", file=sys.stderr)
        return 2

    now = _parse_now(args.now)
    report_paths = create_report_paths(out_dir=args.out_dir, now=now)

    sender_aggregator = SenderAggregator()
    full_results: list[ClassificationResult] = []

    total_messages = 0
    parsed_messages = 0
    skipped_messages = 0
    warning_count = 0
    total_bytes = 0
    candidate_bytes = 0
    candidate_count = 0

    with report_paths.candidate_messages_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        _write_candidate_messages_header(writer)

        for parsed_message, parse_warnings in iter_parsed_mbox(args.mbox):
            total_messages += 1
            warning_count += len(parse_warnings)
            if parsed_message is None:
                skipped_messages += 1
                continue

            indexed_message = replace(parsed_message, index=parsed_messages)
            parsed_messages += 1
            total_bytes += indexed_message.size_bytes

            classification = classify_message(indexed_message, min_age_days=args.min_age_days, now=now)
            sender_aggregator.add(classification)

            if classification.is_candidate:
                candidate_count += 1
                candidate_bytes += classification.message.size_bytes
                _write_candidate_message_row(writer, classification)

            if args.detail_level == "full":
                full_results.append(classification)

    parse_stats = ParseStats(
        total_messages=total_messages,
        parsed_messages=parsed_messages,
        skipped_messages=skipped_messages,
    )

    senders = sender_aggregator.finalize()
    if args.detail_level == "full":
        threads = build_threads(tuple(full_results))
        write_candidate_threads_report(report_paths.candidate_threads_path, threads)
    else:
        threads = ()
        write_empty_candidate_threads(report_paths.candidate_threads_path)

    write_candidate_senders_report(report_paths.candidate_senders_path, senders)
    write_gmail_filters_report(
        report_paths.gmail_filters_path,
        senders,
        min_age_days=args.min_age_days,
        max_senders_per_filter=args.max_senders_per_filter,
    )

    report_paths.summary_path.write_text(
        build_summary_text_from_totals(
            parse_stats=parse_stats,
            total_bytes=total_bytes,
            candidate_message_count=candidate_count,
            candidate_bytes=candidate_bytes,
            senders=senders,
            threads=threads,
            warning_count=warning_count,
        ),
        encoding="utf-8",
    )

    print(f"Scan complete. Output directory: {report_paths.output_dir}")
    print("\nSummary:\n")
    print(report_paths.summary_path.read_text(encoding="utf-8"), end="")
    print(f"Gmail filters: {report_paths.gmail_filters_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            return _run_scan(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: scan failed: {exc}", file=sys.stderr)
        return 1

    print("error: unsupported command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
