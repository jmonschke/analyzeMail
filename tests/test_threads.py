from datetime import datetime, timezone
from pathlib import Path

from analyzemail.classify import classify_messages
from analyzemail.models import ClassificationResult, ParsedMessage
from analyzemail.parser import parse_mbox
from analyzemail.threads import build_threads


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_takeout.mbox"


def test_build_threads_links_reference_chains() -> None:
    messages, _stats, _warnings = parse_mbox(str(_fixture_path()))
    now = datetime(2026, 2, 20, tzinfo=timezone.utc)
    classifications = classify_messages(messages, min_age_days=365, now=now)

    threads = build_threads(classifications)

    thread_with_two = [thread for thread in threads if thread.message_count == 2]
    assert len(thread_with_two) >= 1
    assert any(thread.candidate_message_count == 2 and thread.confidence == "high" for thread in thread_with_two)


def test_build_threads_fallback_subject_grouping() -> None:
    first = ParsedMessage(
        index=0,
        message_id="a@example.com",
        in_reply_to=None,
        references=(),
        date_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        from_address="alerts@example.com",
        from_domain="example.com",
        subject="Weekly digest",
        list_id=None,
        list_unsubscribe=None,
        precedence=None,
        auto_submitted=None,
        x_gmail_labels=None,
        size_bytes=100,
    )
    second = ParsedMessage(
        index=1,
        message_id="b@example.com",
        in_reply_to=None,
        references=(),
        date_utc=datetime(2026, 1, 3, tzinfo=timezone.utc),
        from_address="alerts@example.com",
        from_domain="example.com",
        subject="Re: Weekly digest",
        list_id=None,
        list_unsubscribe=None,
        precedence=None,
        auto_submitted=None,
        x_gmail_labels=None,
        size_bytes=200,
    )

    classifications = (
        ClassificationResult(first, 400, (), ("notification_subject", "no_reply_sender"), (), True, "medium"),
        ClassificationResult(second, 399, (), ("notification_subject", "no_reply_sender"), (), True, "medium"),
    )

    threads = build_threads(classifications)
    assert len(threads) == 1
    assert threads[0].message_count == 2
    assert threads[0].candidate_estimated_bytes == 300


def test_build_threads_fallback_does_not_merge_different_senders() -> None:
    first = ParsedMessage(
        index=0,
        message_id="a@example.com",
        in_reply_to=None,
        references=(),
        date_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        from_address="alerts-a@example.com",
        from_domain="example.com",
        subject="Weekly digest",
        list_id=None,
        list_unsubscribe=None,
        precedence=None,
        auto_submitted=None,
        x_gmail_labels=None,
        size_bytes=100,
    )
    second = ParsedMessage(
        index=1,
        message_id="b@example.com",
        in_reply_to=None,
        references=(),
        date_utc=datetime(2026, 1, 3, tzinfo=timezone.utc),
        from_address="alerts-b@example.com",
        from_domain="example.com",
        subject="Re: Weekly digest",
        list_id=None,
        list_unsubscribe=None,
        precedence=None,
        auto_submitted=None,
        x_gmail_labels=None,
        size_bytes=200,
    )

    classifications = (
        ClassificationResult(first, 400, (), ("notification_subject", "no_reply_sender"), (), True, "medium"),
        ClassificationResult(second, 399, (), ("notification_subject", "no_reply_sender"), (), True, "medium"),
    )

    threads = build_threads(classifications)
    assert len(threads) == 2
    assert all(thread.message_count == 1 for thread in threads)
