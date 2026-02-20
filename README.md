# analyzeMail

Analyze Gmail Takeout `.mbox` exports locally and generate conservative cleanup candidates.

## What it does

- Parses Gmail Takeout mbox data on your machine.
- Identifies conservative candidate messages older than a threshold.
- Estimates thread-level storage impact.
- Exports actionable reports:
  - `summary.txt`
  - `candidate_senders.csv`
  - `candidate_messages.csv`
  - `candidate_threads.csv`
  - `gmail_filters.txt`

The tool does **not** call Gmail APIs and does **not** delete anything.

## Requirements

- Python 3.10+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
analyzemail scan \
  --mbox /path/to/Takeout/Mail/All\ mail\ Including\ Spam\ and\ Trash.mbox \
  --out-dir reports \
  --min-age-days 365 \
  --max-senders-per-filter 25
```

By default, scan runs in `lightweight` mode to reduce memory usage on large mbox files. It streams sender/message outputs and leaves `candidate_threads.csv` as header-only.

Use full in-memory thread analysis when needed:

```bash
analyzemail scan --mbox /path/to/file.mbox --detail-level full
```

Optional deterministic timestamp for reproducible output:

```bash
analyzemail scan --mbox /path/to/file.mbox --now 2026-02-20T00:00:00+00:00
```

## Running tests

```bash
pytest
```

## Notes on Gmail filters

`gmail_filters.txt` contains copy/paste Gmail queries for high-confidence sender groups only, with conservative exclusions like `-in:sent -in:chat`.
Always review sampled messages before mass deletion.
