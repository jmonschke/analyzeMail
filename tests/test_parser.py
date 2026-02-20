from pathlib import Path

import pytest

from analyzemail.parser import parse_mbox


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_takeout.mbox"


def test_parse_mbox_counts_and_core_fields() -> None:
    messages, stats, warnings = parse_mbox(str(_fixture_path()))

    assert stats.total_messages == 8
    assert stats.parsed_messages == 8
    assert stats.skipped_messages == 0
    assert warnings == ()

    first = messages[0]
    assert first.from_address == "deals@example.com"
    assert first.from_domain == "example.com"
    assert first.message_id == "m0@example.com"
    assert first.list_unsubscribe is not None

    reply_message = messages[6]
    assert reply_message.in_reply_to == "thread-1@example.com"
    assert "thread-1@example.com" in reply_message.references


def test_parse_mbox_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        parse_mbox("/tmp/this-does-not-exist-xyz.mbox")
