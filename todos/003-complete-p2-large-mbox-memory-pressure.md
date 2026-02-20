---
status: complete
priority: p2
issue_id: "003"
tags: [code-review, performance, scalability]
dependencies: []
---

# Reduce Memory Pressure For Large Mbox Scans

Refactor scan pipeline to avoid full in-memory retention of all parsed messages and derived structures for very large Gmail Takeout exports.

## Problem Statement

The current implementation reads all parsed messages into memory, then creates additional full-size derived collections for classifications and thread adjacency. For very large Takeout files, this can cause high memory usage or process termination before producing reports.

Given the primary use case is large inbox cleanup, this is a significant scalability risk.

## Findings

- `analyzemail/parser.py:63` initializes `parsed_messages` as an in-memory list and appends every message.
- `analyzemail/parser.py:118` returns all messages as a tuple.
- `analyzemail/classify.py:78` materializes all classification results in memory.
- `analyzemail/threads.py:53` allocates graph adjacency for all messages simultaneously.

## Proposed Solutions

### Option 1: Two-Pass Streaming Aggregation + Optional Detailed Mode

**Approach:** First pass computes sender-level and coarse stats in streaming mode; second optional pass builds message/thread detail only when needed.

**Pros:**
- Handles very large mbox files with bounded memory in default mode.
- Preserves detailed outputs via explicit opt-in.

**Cons:**
- Increases implementation complexity and scan duration (two passes).

**Effort:** Medium

**Risk:** Medium

---

### Option 2: Spill Intermediate Records To Disk

**Approach:** Write parsed/classification intermediates to temporary files (CSV/SQLite) and process incrementally.

**Pros:**
- Strong memory control while preserving rich outputs.
- Supports resumable workflows.

**Cons:**
- Adds I/O overhead and temp-file lifecycle complexity.

**Effort:** Medium

**Risk:** Medium

---

### Option 3: Keep In-Memory Model But Add Hard Limits And Early Warnings

**Approach:** Keep architecture unchanged, add message-count/byte thresholds and explicit warnings or aborts.

**Pros:**
- Fastest implementation.

**Cons:**
- Does not solve scaling; only makes failure modes explicit.

**Effort:** Small

**Risk:** High

## Recommended Action

Implement a lightweight default scan mode that streams parsing and classification, writes candidate message rows directly to disk, and aggregates sender stats incrementally. Keep full thread-graph analysis as explicit opt-in (`--detail-level full`) for cases where thread ranking is needed.

## Technical Details

**Affected files:**
- `analyzemail/parser.py:63`
- `analyzemail/parser.py:118`
- `analyzemail/classify.py:78`
- `analyzemail/threads.py:53`
- `analyzemail/cli.py` (scan mode flags if introducing lightweight/default mode)

**Related components:**
- Report generation and deterministic output contracts in `analyzemail/reports.py`
- Test fixtures and integration tests for large-file behavior

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- **PR:** https://github.com/jmonschke/analyzeMail/pull/1
- **Review context:** workflows-review run on branch `feat/gmail-takeout-analyzer`

## Acceptance Criteria

- [x] Default scan mode avoids O(n) in-memory retention of full message bodies/records
- [x] Tool completes a large synthetic mbox scan without OOM in constrained memory environments
- [x] Reports remain functionally equivalent for existing fixture-based tests
- [x] New tests cover large-input behavior and memory-safe pipeline assumptions

## Work Log

### 2026-02-20 - Implementation

**By:** Codex

**Actions:**
- Added iterator-based parsing in `analyzemail/parser.py` via `iter_parsed_mbox`
- Refactored classification to support streaming one-message evaluation and incremental sender aggregation in `analyzemail/classify.py`
- Reworked CLI scan flow in `analyzemail/cli.py`:
  - default `--detail-level lightweight` streaming mode
  - opt-in `--detail-level full` for in-memory thread graph analysis
  - streamed `candidate_messages.csv` writing to avoid retaining all message/classification rows
- Added reporting helpers in `analyzemail/reports.py` for streaming scan outputs
- Added CLI tests in `tests/test_cli.py` to verify lightweight vs full behavior
- Updated `README.md` with the new `--detail-level` mode documentation
- Ran full test suite: `11 passed`

**Learnings:**
- Separating default scan behavior from thread-heavy analysis is a practical way to preserve functionality while reducing baseline memory pressure on large archives

### 2026-02-20 - Initial Discovery

**By:** Codex

**Actions:**
- Traced data lifecycle from parser through classifier and thread builder
- Identified full-materialization points and compounding memory growth
- Documented scalable implementation options with tradeoffs

**Learnings:**
- Current architecture is clean for small inputs but needs streaming/spooling strategy for real-world Gmail archive sizes

## Notes

- Keep conservative safety semantics unchanged while addressing scale.
