from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ParsedMessage:
    index: int
    message_id: str | None
    in_reply_to: str | None
    references: tuple[str, ...]
    date_utc: datetime | None
    from_address: str
    from_domain: str
    subject: str
    list_id: str | None
    list_unsubscribe: str | None
    precedence: str | None
    auto_submitted: str | None
    x_gmail_labels: str | None
    size_bytes: int


@dataclass(frozen=True)
class ParseStats:
    total_messages: int = 0
    parsed_messages: int = 0
    skipped_messages: int = 0


@dataclass(frozen=True)
class ClassificationResult:
    message: ParsedMessage
    age_days: int | None
    strong_signals: tuple[str, ...]
    weak_signals: tuple[str, ...]
    excluded_reasons: tuple[str, ...]
    is_candidate: bool
    confidence: str


@dataclass(frozen=True)
class ThreadSummary:
    thread_id: str
    message_indices: tuple[int, ...]
    message_count: int
    estimated_bytes: int
    candidate_message_count: int
    candidate_estimated_bytes: int
    dominant_sender: str
    confidence: str


@dataclass(frozen=True)
class SenderSummary:
    sender: str
    domain: str
    message_count: int
    candidate_message_count: int
    estimated_bytes: int
    candidate_estimated_bytes: int
    first_seen: datetime | None
    last_seen: datetime | None
    confidence: str


@dataclass(frozen=True)
class ScanResult:
    parse_stats: ParseStats
    classifications: tuple[ClassificationResult, ...]
    threads: tuple[ThreadSummary, ...]
    senders: tuple[SenderSummary, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
