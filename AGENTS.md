# AGENTS.md

## Purpose

This repository analyzes Gmail Takeout mbox exports and produces conservative cleanup guidance. Agents must preserve safety-first behavior.

## Environment Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Canonical Commands

- Run tests: `pytest`
- Run a local scan:
  - `analyzemail scan --mbox /path/to/file.mbox --out-dir reports`

## Coding Standards

- Keep defaults conservative. Do not broaden deletion recommendations without explicit rationale and tests.
- Do not silently swallow parse failures. Count and report warnings.
- Keep scan output deterministic when `--now` is provided.
- Use small, reviewable patches and clear naming.
- Use ASCII unless the target file already requires Unicode.

## Safety Constraints

- Never add automatic deletion behavior.
- Recommendations must remain reviewable and export-backed (`summary.txt`, CSV files, and `gmail_filters.txt`).
- Keep high-confidence filtering strict; avoid introducing risky sender matching shortcuts.

## Test Requirements

- Add or update tests for every classifier rule change.
- Add CLI/integration coverage when changing flags or report formats.
- Ensure fixture-based tests cover parser, classifier, threading, and filter generation.

## Documentation Requirements

- If CLI flags or report files change, update `README.md` in the same change.
