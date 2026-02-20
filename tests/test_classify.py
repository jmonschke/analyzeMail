from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

from analyzemail.classify import classify_messages, summarize_senders
from analyzemail.parser import parse_mbox


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_takeout.mbox"


def test_classification_conservative_rules() -> None:
    messages, _stats, _warnings = parse_mbox(str(_fixture_path()))
    now = datetime(2026, 2, 20, tzinfo=timezone.utc)

    results = classify_messages(messages, min_age_days=365, now=now)

    candidates = [result for result in results if result.is_candidate]
    assert len(candidates) == 5

    by_id = {result.message.message_id: result for result in results}
    assert by_id["m3@example.org"].is_candidate is False
    assert "security_or_finance" in by_id["m3@example.org"].excluded_reasons

    assert by_id["m2@example.org"].is_candidate is False
    assert "likely_personal_thread" in by_id["m2@example.org"].excluded_reasons

    assert by_id["m5@example.com"].is_candidate is False
    assert "too_new_or_unknown_age" in by_id["m5@example.com"].excluded_reasons

    assert by_id["m4@example.org"].is_candidate is True
    assert by_id["m4@example.org"].confidence == "medium"


def test_sender_confidence_for_filtering() -> None:
    messages, _stats, _warnings = parse_mbox(str(_fixture_path()))
    now = datetime(2026, 2, 20, tzinfo=timezone.utc)

    classifications = classify_messages(messages, min_age_days=365, now=now)
    senders = summarize_senders(classifications)

    sender_map = {sender.sender: sender for sender in senders}
    assert sender_map["threadpromo@example.com"].confidence == "high"
    assert sender_map["no-reply@updates.example"].confidence == "low"


def test_sent_label_detection_uses_exact_tokens() -> None:
    messages, _stats, _warnings = parse_mbox(str(_fixture_path()))
    now = datetime(2026, 2, 20, tzinfo=timezone.utc)

    baseline = messages[0]
    not_sent_label = replace(baseline, x_gmail_labels="consent, archive")
    sent_label = replace(baseline, x_gmail_labels="\\Sent, archive")

    results = classify_messages((not_sent_label, sent_label), min_age_days=365, now=now)

    non_sent_result = results[0]
    assert non_sent_result.is_candidate is True
    assert "sent_mail" not in non_sent_result.excluded_reasons

    sent_result = results[1]
    assert sent_result.is_candidate is False
    assert "sent_mail" in sent_result.excluded_reasons
