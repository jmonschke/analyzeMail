import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_takeout.mbox"


def _write_synthetic_mbox(path: Path, message_count: int) -> None:
    chunks: list[str] = []
    for idx in range(message_count):
        chunks.append(
            "\n".join(
                [
                    f"From sender{idx}@example.com Sat Jan  1 00:00:00 2022",
                    "Date: Sat, 01 Jan 2022 10:00:00 +0000",
                    f"From: Sender {idx} <sender{idx}@example.com>",
                    "To: user@example.net",
                    f"Subject: Weekly digest {idx}",
                    f"Message-ID: <synthetic-{idx}@example.com>",
                    "List-Unsubscribe: <mailto:unsubscribe@example.com>",
                    "",
                    f"Synthetic body {idx}",
                    "",
                ]
            )
        )
    path.write_text("".join(chunks), encoding="utf-8")


def test_cli_scan_generates_reports(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "analyzemail.cli",
        "scan",
        "--mbox",
        str(_fixture_path()),
        "--out-dir",
        str(tmp_path),
        "--now",
        "2026-02-20T00:00:00+00:00",
    ]
    result = subprocess.run(cmd, cwd=_project_root(), capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    scan_dir = tmp_path / "scan_20260220_000000Z"
    assert scan_dir.exists()

    summary = (scan_dir / "summary.txt").read_text(encoding="utf-8")
    assert "candidate_messages: 5" in summary

    gmail_filters = (scan_dir / "gmail_filters.txt").read_text(encoding="utf-8")
    assert "older_than:1y" in gmail_filters
    assert "threadpromo@example.com" in gmail_filters

    candidate_threads = (scan_dir / "candidate_threads.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(candidate_threads) == 1


def test_cli_scan_full_detail_generates_thread_rows(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "analyzemail.cli",
        "scan",
        "--mbox",
        str(_fixture_path()),
        "--out-dir",
        str(tmp_path),
        "--now",
        "2026-02-20T00:00:00+00:00",
        "--detail-level",
        "full",
    ]
    result = subprocess.run(cmd, cwd=_project_root(), capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    scan_dir = tmp_path / "scan_20260220_000000Z"
    candidate_threads = (scan_dir / "candidate_threads.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(candidate_threads) > 1


def test_cli_scan_handles_missing_file(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "analyzemail.cli",
        "scan",
        "--mbox",
        str(tmp_path / "missing.mbox"),
        "--out-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=_project_root(), capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_cli_lightweight_handles_large_synthetic_mbox(tmp_path: Path) -> None:
    synthetic_path = tmp_path / "large.mbox"
    _write_synthetic_mbox(synthetic_path, message_count=2000)

    cmd = [
        sys.executable,
        "-m",
        "analyzemail.cli",
        "scan",
        "--mbox",
        str(synthetic_path),
        "--out-dir",
        str(tmp_path),
        "--now",
        "2026-02-20T00:00:00+00:00",
    ]
    result = subprocess.run(cmd, cwd=_project_root(), capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    summary = (tmp_path / "scan_20260220_000000Z" / "summary.txt").read_text(encoding="utf-8")
    assert "total_messages_scanned: 2000" in summary
