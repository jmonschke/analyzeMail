from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from analyzemail.models import ClassificationResult, ParseStats, SenderSummary, ThreadSummary


@dataclass(frozen=True)
class ReportPaths:
    output_dir: Path
    summary_path: Path
    candidate_senders_path: Path
    candidate_messages_path: Path
    candidate_threads_path: Path
    gmail_filters_path: Path


def create_report_paths(out_dir: str, now: datetime) -> ReportPaths:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    base_dir = Path(out_dir)
    output_dir = base_dir / f"scan_{now.strftime('%Y%m%d_%H%M%SZ')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    return ReportPaths(
        output_dir=output_dir,
        summary_path=output_dir / "summary.txt",
        candidate_senders_path=output_dir / "candidate_senders.csv",
        candidate_messages_path=output_dir / "candidate_messages.csv",
        candidate_threads_path=output_dir / "candidate_threads.csv",
        gmail_filters_path=output_dir / "gmail_filters.txt",
    )


def _format_age_filter(min_age_days: int) -> str:
    if min_age_days % 365 == 0:
        return f"older_than:{min_age_days // 365}y"
    if min_age_days % 30 == 0:
        return f"older_than:{min_age_days // 30}m"
    return f"older_than:{min_age_days}d"


def _format_bytes(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size_bytes} B"


def _iso_or_empty(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def _build_summary_text(
    parse_stats: ParseStats,
    classifications: tuple[ClassificationResult, ...],
    senders: tuple[SenderSummary, ...],
    threads: tuple[ThreadSummary, ...],
    warnings: tuple[str, ...],
) -> str:
    total_bytes = sum(item.message.size_bytes for item in classifications)
    candidate_messages = [item for item in classifications if item.is_candidate]
    candidate_bytes = sum(item.message.size_bytes for item in candidate_messages)

    top_senders = [sender for sender in senders if sender.candidate_message_count > 0][:10]
    top_threads = [thread for thread in threads if thread.candidate_message_count > 0][:10]

    lines = [
        "analyzemail scan summary",
        "",
        f"total_messages_scanned: {parse_stats.total_messages}",
        f"messages_parsed: {parse_stats.parsed_messages}",
        f"messages_skipped: {parse_stats.skipped_messages}",
        f"total_estimated_bytes: {total_bytes} ({_format_bytes(total_bytes)})",
        f"candidate_messages: {len(candidate_messages)}",
        f"candidate_estimated_bytes: {candidate_bytes} ({_format_bytes(candidate_bytes)})",
        f"warnings: {len(warnings)}",
        "",
        "top_candidate_senders_by_bytes:",
    ]

    if not top_senders:
        lines.append("- none")
    else:
        for sender in top_senders:
            lines.append(
                "- "
                f"{sender.sender} | candidate_bytes={sender.candidate_estimated_bytes} "
                f"({_format_bytes(sender.candidate_estimated_bytes)}) "
                f"candidate_messages={sender.candidate_message_count} "
                f"confidence={sender.confidence}"
            )

    lines.append("")
    lines.append("top_candidate_threads_by_bytes:")
    if not top_threads:
        lines.append("- none")
    else:
        for thread in top_threads:
            lines.append(
                "- "
                f"{thread.thread_id} | candidate_bytes={thread.candidate_estimated_bytes} "
                f"({_format_bytes(thread.candidate_estimated_bytes)}) "
                f"candidate_messages={thread.candidate_message_count} "
                f"dominant_sender={thread.dominant_sender} "
                f"confidence={thread.confidence}"
            )

    return "\n".join(lines) + "\n"


def build_summary_text_from_totals(
    parse_stats: ParseStats,
    total_bytes: int,
    candidate_message_count: int,
    candidate_bytes: int,
    senders: tuple[SenderSummary, ...],
    threads: tuple[ThreadSummary, ...],
    warning_count: int,
) -> str:
    top_senders = [sender for sender in senders if sender.candidate_message_count > 0][:10]
    top_threads = [thread for thread in threads if thread.candidate_message_count > 0][:10]

    lines = [
        "analyzemail scan summary",
        "",
        f"total_messages_scanned: {parse_stats.total_messages}",
        f"messages_parsed: {parse_stats.parsed_messages}",
        f"messages_skipped: {parse_stats.skipped_messages}",
        f"total_estimated_bytes: {total_bytes} ({_format_bytes(total_bytes)})",
        f"candidate_messages: {candidate_message_count}",
        f"candidate_estimated_bytes: {candidate_bytes} ({_format_bytes(candidate_bytes)})",
        f"warnings: {warning_count}",
        "",
        "top_candidate_senders_by_bytes:",
    ]

    if not top_senders:
        lines.append("- none")
    else:
        for sender in top_senders:
            lines.append(
                "- "
                f"{sender.sender} | candidate_bytes={sender.candidate_estimated_bytes} "
                f"({_format_bytes(sender.candidate_estimated_bytes)}) "
                f"candidate_messages={sender.candidate_message_count} "
                f"confidence={sender.confidence}"
            )

    lines.append("")
    lines.append("top_candidate_threads_by_bytes:")
    if not top_threads:
        lines.append("- none")
    else:
        for thread in top_threads:
            lines.append(
                "- "
                f"{thread.thread_id} | candidate_bytes={thread.candidate_estimated_bytes} "
                f"({_format_bytes(thread.candidate_estimated_bytes)}) "
                f"candidate_messages={thread.candidate_message_count} "
                f"dominant_sender={thread.dominant_sender} "
                f"confidence={thread.confidence}"
            )

    return "\n".join(lines) + "\n"


def _write_candidate_senders(path: Path, senders: tuple[SenderSummary, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sender",
                "domain",
                "message_count",
                "candidate_message_count",
                "estimated_bytes",
                "candidate_estimated_bytes",
                "first_seen_utc",
                "last_seen_utc",
                "confidence",
            ]
        )
        for sender in senders:
            if sender.candidate_message_count == 0:
                continue
            writer.writerow(
                [
                    sender.sender,
                    sender.domain,
                    sender.message_count,
                    sender.candidate_message_count,
                    sender.estimated_bytes,
                    sender.candidate_estimated_bytes,
                    _iso_or_empty(sender.first_seen),
                    _iso_or_empty(sender.last_seen),
                    sender.confidence,
                ]
            )


def _write_candidate_messages(path: Path, classifications: tuple[ClassificationResult, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
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

        for item in classifications:
            if not item.is_candidate:
                continue
            writer.writerow(
                [
                    item.message.index,
                    item.message.message_id or "",
                    _iso_or_empty(item.message.date_utc),
                    item.message.from_address,
                    item.message.subject,
                    item.age_days if item.age_days is not None else "",
                    item.message.size_bytes,
                    item.confidence,
                    "|".join(item.strong_signals),
                    "|".join(item.weak_signals),
                ]
            )


def _write_candidate_threads(path: Path, threads: tuple[ThreadSummary, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "thread_id",
                "message_count",
                "estimated_bytes",
                "candidate_message_count",
                "candidate_estimated_bytes",
                "dominant_sender",
                "confidence",
                "message_indices",
            ]
        )
        for thread in threads:
            if thread.candidate_message_count == 0:
                continue
            writer.writerow(
                [
                    thread.thread_id,
                    thread.message_count,
                    thread.estimated_bytes,
                    thread.candidate_message_count,
                    thread.candidate_estimated_bytes,
                    thread.dominant_sender,
                    thread.confidence,
                    "|".join(str(idx) for idx in thread.message_indices),
                ]
            )


def _batch(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _write_gmail_filters(
    path: Path,
    senders: tuple[SenderSummary, ...],
    min_age_days: int,
    max_senders_per_filter: int,
) -> None:
    age_filter = _format_age_filter(min_age_days)
    eligible = [
        sender.sender
        for sender in senders
        if sender.candidate_message_count > 0 and sender.confidence == "high" and sender.sender != "<unknown>"
    ]

    with path.open("w", encoding="utf-8") as handle:
        handle.write("# Review carefully before deleting mail.\n")
        handle.write("# Queries target conservative, high-confidence sender candidates only.\n\n")

        if not eligible:
            handle.write("# No high-confidence sender filters were generated.\n")
            return

        for idx, sender_batch in enumerate(_batch(eligible, max_senders_per_filter), start=1):
            joined = " OR ".join(sender_batch)
            query = f"from:({joined}) {age_filter} -in:sent -in:chat"
            handle.write(f"# Filter batch {idx}\n")
            handle.write(query)
            handle.write("\n\n")


def write_candidate_senders_report(path: Path, senders: tuple[SenderSummary, ...]) -> None:
    _write_candidate_senders(path, senders)


def write_candidate_threads_report(path: Path, threads: tuple[ThreadSummary, ...]) -> None:
    _write_candidate_threads(path, threads)


def write_gmail_filters_report(
    path: Path,
    senders: tuple[SenderSummary, ...],
    min_age_days: int,
    max_senders_per_filter: int,
) -> None:
    _write_gmail_filters(
        path,
        senders,
        min_age_days=min_age_days,
        max_senders_per_filter=max_senders_per_filter,
    )


def write_empty_candidate_threads(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "thread_id",
                "message_count",
                "estimated_bytes",
                "candidate_message_count",
                "candidate_estimated_bytes",
                "dominant_sender",
                "confidence",
                "message_indices",
            ]
        )


def write_reports(
    parse_stats: ParseStats,
    classifications: tuple[ClassificationResult, ...],
    senders: tuple[SenderSummary, ...],
    threads: tuple[ThreadSummary, ...],
    warnings: tuple[str, ...],
    out_dir: str,
    now: datetime,
    min_age_days: int,
    max_senders_per_filter: int,
) -> ReportPaths:
    paths = create_report_paths(out_dir=out_dir, now=now)

    paths.summary_path.write_text(
        _build_summary_text(
            parse_stats=parse_stats,
            classifications=classifications,
            senders=senders,
            threads=threads,
            warnings=warnings,
        ),
        encoding="utf-8",
    )
    _write_candidate_senders(paths.candidate_senders_path, senders)
    _write_candidate_messages(paths.candidate_messages_path, classifications)
    _write_candidate_threads(paths.candidate_threads_path, threads)
    _write_gmail_filters(
        paths.gmail_filters_path,
        senders,
        min_age_days=min_age_days,
        max_senders_per_filter=max_senders_per_filter,
    )

    return paths
