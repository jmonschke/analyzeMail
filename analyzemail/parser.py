from __future__ import annotations

import mailbox
import os
import re
from datetime import timezone
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime

from analyzemail.models import ParseStats, ParsedMessage

_MESSAGE_ID_RE = re.compile(r"<[^>]+>")


def _normalize_message_id(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1].strip().lower() or None
    return value.strip().lower() or None


def _extract_references(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    ids = []
    for match in _MESSAGE_ID_RE.findall(value):
        normalized = _normalize_message_id(match)
        if normalized:
            ids.append(normalized)
    if not ids:
        for part in value.split():
            normalized = _normalize_message_id(part)
            if normalized:
                ids.append(normalized)
    return tuple(dict.fromkeys(ids))


def _parse_date(value: str | None):
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _message_size_bytes(message: Message) -> int:
    try:
        return len(message.as_bytes())
    except Exception:
        return len(str(message))


def parse_mbox(path: str) -> tuple[tuple[ParsedMessage, ...], ParseStats, tuple[str, ...]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"mbox path does not exist: {path}")

    warnings: list[str] = []
    parsed_messages: list[ParsedMessage] = []
    total_messages = 0
    skipped_messages = 0

    mbox = mailbox.mbox(path)
    try:
        for key in mbox.iterkeys():
            total_messages += 1
            try:
                message = mbox.get_message(key)
                if message is None:
                    skipped_messages += 1
                    warnings.append(f"Message key {key}: empty message")
                    continue

                date_utc = None
                raw_date = message.get("Date")
                if raw_date:
                    try:
                        date_utc = _parse_date(raw_date)
                    except Exception as exc:
                        warnings.append(f"Message key {key}: invalid date '{raw_date}': {exc}")

                from_address = parseaddr(message.get("From", ""))[1].strip().lower()
                from_domain = from_address.split("@", 1)[1] if "@" in from_address else ""

                parsed_messages.append(
                    ParsedMessage(
                        index=len(parsed_messages),
                        message_id=_normalize_message_id(message.get("Message-ID")),
                        in_reply_to=_normalize_message_id(message.get("In-Reply-To")),
                        references=_extract_references(message.get("References")),
                        date_utc=date_utc,
                        from_address=from_address,
                        from_domain=from_domain,
                        subject=message.get("Subject", "").strip(),
                        list_id=message.get("List-Id"),
                        list_unsubscribe=message.get("List-Unsubscribe"),
                        precedence=(message.get("Precedence") or "").strip().lower() or None,
                        auto_submitted=(message.get("Auto-Submitted") or "").strip().lower() or None,
                        x_gmail_labels=message.get("X-Gmail-Labels"),
                        size_bytes=_message_size_bytes(message),
                    )
                )
            except Exception as exc:
                skipped_messages += 1
                warnings.append(f"Message key {key}: parse error: {exc}")
    finally:
        mbox.close()

    stats = ParseStats(
        total_messages=total_messages,
        parsed_messages=len(parsed_messages),
        skipped_messages=skipped_messages,
    )
    return tuple(parsed_messages), stats, tuple(warnings)
