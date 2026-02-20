from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from analyzemail.classify import classify_messages, summarize_senders
from analyzemail.parser import parse_mbox
from analyzemail.reports import write_reports
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

    return parser


def _run_scan(args: argparse.Namespace) -> int:
    if args.min_age_days <= 0:
        print("error: --min-age-days must be > 0", file=sys.stderr)
        return 2
    if args.max_senders_per_filter <= 0:
        print("error: --max-senders-per-filter must be > 0", file=sys.stderr)
        return 2

    now = _parse_now(args.now)

    messages, parse_stats, parse_warnings = parse_mbox(args.mbox)
    classifications = classify_messages(messages, min_age_days=args.min_age_days, now=now)
    threads = build_threads(classifications)
    senders = summarize_senders(classifications)

    report_paths = write_reports(
        parse_stats=parse_stats,
        classifications=classifications,
        senders=senders,
        threads=threads,
        warnings=parse_warnings,
        out_dir=args.out_dir,
        now=now,
        min_age_days=args.min_age_days,
        max_senders_per_filter=args.max_senders_per_filter,
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
