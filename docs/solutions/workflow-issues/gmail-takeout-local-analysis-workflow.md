---
module: Email Processing
date: 2026-02-20
problem_type: workflow_issue
component: tooling
symptoms:
  - "Mailbox cleanup required manual Gmail searching and could not estimate storage impact safely"
  - "No local workflow existed to turn Gmail Takeout mbox data into conservative delete candidates"
  - "Risk of over-deletion without auditable sender/message/thread reports"
root_cause: missing_tooling
resolution_type: tooling_addition
severity: medium
tags: [gmail-takeout, mbox, cli-tooling, email-cleanup, conservative-filters]
---

# Troubleshooting: Build A Safe Local Gmail Takeout Cleanup Workflow

## Problem
A long-lived Gmail account accumulated enough data to approach storage limits, but cleanup via the Gmail UI alone was too manual and risky. The team needed a local, auditable workflow that suggests conservative deletion candidates without automating deletion.

## Environment
- Module: Email Processing
- Affected Component: Tooling (local CLI)
- Date Solved: 2026-02-20
- Platforms: macOS and Linux

## Symptoms
- No existing command-line workflow for analyzing Gmail Takeout `.mbox` archives.
- No sender-level or thread-level storage estimates for prioritizing cleanup.
- No generated Gmail search filters scoped to high-confidence candidates.
- No repo-level agent standards for maintaining safety constraints over time.

## What Didn't Work

**Attempted Solution 1:** Manual cleanup in Gmail web UI with ad-hoc search queries.
- **Why it failed:** Not scalable for years of mail and did not provide consistent, auditable criteria.

**Attempted Solution 2:** Immediate storage expansion purchase.
- **Why it failed:** Avoids root workflow gap and does not create reusable cleanup tooling.

## Solution
Implemented a Python CLI tool (`analyzemail`) that processes Takeout mbox files locally and emits conservative recommendations plus review artifacts.

### Key implementation pieces
- `analyzemail/parser.py`: Streams mbox messages and normalizes key headers (`Message-ID`, `References`, list headers, Gmail labels, date, size).
- `analyzemail/classify.py`: Applies conservative classification rules, age thresholds, and exclusion logic for risky categories.
- `analyzemail/threads.py`: Builds thread estimates using reference chains with subject fallback.
- `analyzemail/reports.py`: Writes `summary.txt`, CSV exports, and batched Gmail filter queries.
- `analyzemail/cli.py`: Exposes `analyzemail scan` with `--mbox`, `--out-dir`, `--min-age-days`, `--max-senders-per-filter`, and deterministic `--now`.
- `AGENTS.md`: Enforces safety and quality constraints (no auto-delete behavior, test requirements, conservative defaults).

### Example command
```bash
python -m analyzemail.cli scan \
  --mbox tests/fixtures/sample_takeout.mbox \
  --out-dir /tmp/analyzemail_reports \
  --now 2026-02-20T00:00:00+00:00
```

### Output artifacts
- `summary.txt`
- `candidate_senders.csv`
- `candidate_messages.csv`
- `candidate_threads.csv`
- `gmail_filters.txt`

## Why This Works
1. Root cause was missing tooling, not missing data. The new CLI introduces a repeatable local workflow for mailbox triage.
2. Conservative classification reduces deletion risk by requiring bulk-like signals and excluding sensitive/personal patterns.
3. Generated artifacts provide auditability and manual review checkpoints before any Gmail-side delete action.
4. `AGENTS.md` preserves safety expectations for future contributors and agents.

## Prevention
- Maintain conservative defaults and never add direct delete automation.
- Require regression tests whenever classifier or threading logic changes.
- Keep deterministic output support (`--now`) to stabilize CI and review diffs.
- Track review findings in `todos/` for known correctness and scale risks before broadening usage.

## Related Issues
No related issues documented yet.
