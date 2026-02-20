import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_takeout.mbox"


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
