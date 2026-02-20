from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from analyzemail.models import ClassificationResult, ParsedMessage, SenderSummary

_PROMO_SUBJECT_MARKERS = (
    "sale",
    "discount",
    "offer",
    "deal",
    "newsletter",
    "promo",
    "promotion",
)

_NOTIFICATION_MARKERS = (
    "notification",
    "digest",
    "weekly update",
    "daily update",
)

_SECURITY_FINANCE_MARKERS = (
    "verification code",
    "otp",
    "password",
    "security alert",
    "two-factor",
    "2fa",
    "statement",
    "invoice",
    "receipt",
    "bank",
)

_SENT_LABEL_TOKENS = {"sent", "sent mail", "\\sent"}


@dataclass
class _SenderAggregate:
    sender: str
    domain: str
    message_count: int = 0
    candidate_message_count: int = 0
    estimated_bytes: int = 0
    candidate_estimated_bytes: int = 0
    high_candidate_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None


def _age_days(message: ParsedMessage, now: datetime) -> int | None:
    if message.date_utc is None:
        return None
    delta = now - message.date_utc
    return max(delta.days, 0)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lower_text = text.lower()
    return any(marker in lower_text for marker in markers)


def _is_likely_no_reply_sender(address: str) -> bool:
    local = address.split("@", 1)[0].lower()
    return local.startswith(("noreply", "no-reply", "do-not-reply", "notifications"))


def _label_tokens(labels: str | None) -> set[str]:
    if not labels:
        return set()
    tokens = set()
    for token in labels.split(","):
        normalized = token.strip().lower()
        if normalized:
            tokens.add(normalized)
    return tokens


def classify_messages(
    messages: tuple[ParsedMessage, ...],
    min_age_days: int,
    now: datetime,
) -> tuple[ClassificationResult, ...]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    results: list[ClassificationResult] = []

    for message in messages:
        age_days = _age_days(message, now)
        subject_lower = message.subject.lower()
        strong_signals: list[str] = []
        weak_signals: list[str] = []
        excluded_reasons: list[str] = []

        if message.list_unsubscribe:
            strong_signals.append("list_unsubscribe")
        if message.list_id:
            strong_signals.append("list_id")
        if message.precedence in {"bulk", "list", "junk"}:
            strong_signals.append("precedence_bulk")

        if _contains_any(subject_lower, _PROMO_SUBJECT_MARKERS):
            weak_signals.append("promo_subject")
        if _contains_any(subject_lower, _NOTIFICATION_MARKERS):
            weak_signals.append("notification_subject")
        if message.auto_submitted and message.auto_submitted != "no":
            weak_signals.append("auto_submitted")
        if _is_likely_no_reply_sender(message.from_address):
            weak_signals.append("no_reply_sender")

        if age_days is None or age_days < min_age_days:
            excluded_reasons.append("too_new_or_unknown_age")

        if _contains_any(subject_lower, _SECURITY_FINANCE_MARKERS):
            excluded_reasons.append("security_or_finance")

        labels = _label_tokens(message.x_gmail_labels)
        if labels.intersection(_SENT_LABEL_TOKENS):
            excluded_reasons.append("sent_mail")

        is_replyish = bool(message.in_reply_to or message.references or subject_lower.startswith("re:"))
        if is_replyish and not strong_signals:
            excluded_reasons.append("likely_personal_thread")

        has_bulk_signals = bool(strong_signals) or len(weak_signals) >= 2
        is_candidate = has_bulk_signals and not excluded_reasons

        if is_candidate and strong_signals:
            confidence = "high"
        elif is_candidate:
            confidence = "medium"
        else:
            confidence = "low"

        results.append(
            ClassificationResult(
                message=message,
                age_days=age_days,
                strong_signals=tuple(strong_signals),
                weak_signals=tuple(weak_signals),
                excluded_reasons=tuple(excluded_reasons),
                is_candidate=is_candidate,
                confidence=confidence,
            )
        )

    return tuple(results)


def summarize_senders(classifications: tuple[ClassificationResult, ...]) -> tuple[SenderSummary, ...]:
    aggregates: dict[str, _SenderAggregate] = {}

    for result in classifications:
        message = result.message
        sender_key = message.from_address or "<unknown>"
        aggregate = aggregates.get(sender_key)
        if aggregate is None:
            aggregate = _SenderAggregate(sender=sender_key, domain=message.from_domain)
            aggregates[sender_key] = aggregate

        aggregate.message_count += 1
        aggregate.estimated_bytes += message.size_bytes

        if result.is_candidate:
            aggregate.candidate_message_count += 1
            aggregate.candidate_estimated_bytes += message.size_bytes
        if result.confidence == "high" and result.is_candidate:
            aggregate.high_candidate_count += 1

        if message.date_utc is not None:
            if aggregate.first_seen is None or message.date_utc < aggregate.first_seen:
                aggregate.first_seen = message.date_utc
            if aggregate.last_seen is None or message.date_utc > aggregate.last_seen:
                aggregate.last_seen = message.date_utc

    summaries: list[SenderSummary] = []
    for sender, aggregate in aggregates.items():
        if aggregate.candidate_message_count == 0:
            confidence = "low"
        else:
            high_ratio = aggregate.high_candidate_count / aggregate.candidate_message_count
            if high_ratio >= 0.8:
                confidence = "high"
            elif high_ratio >= 0.5:
                confidence = "medium"
            else:
                confidence = "low"

        summaries.append(
            SenderSummary(
                sender=sender,
                domain=aggregate.domain,
                message_count=aggregate.message_count,
                candidate_message_count=aggregate.candidate_message_count,
                estimated_bytes=aggregate.estimated_bytes,
                candidate_estimated_bytes=aggregate.candidate_estimated_bytes,
                first_seen=aggregate.first_seen,
                last_seen=aggregate.last_seen,
                confidence=confidence,
            )
        )

    summaries.sort(
        key=lambda item: (
            item.candidate_estimated_bytes,
            item.candidate_message_count,
            item.estimated_bytes,
        ),
        reverse=True,
    )

    return tuple(summaries)
