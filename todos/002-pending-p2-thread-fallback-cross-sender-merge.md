---
status: pending
priority: p2
issue_id: "002"
tags: [code-review, architecture, quality]
dependencies: []
---

# Prevent Cross-Sender Thread Merging In Subject Fallback

Refine thread fallback grouping so unrelated messages from different senders are not merged solely because they share a subject within the same week.

## Problem Statement

`build_threads` performs fallback grouping using `(normalized_subject, week_bucket)` for singleton messages. This can merge unrelated emails (for example, different newsletter providers using common subjects like "Weekly digest") into a single thread.

The merge inflates thread-level size estimates and can mislead prioritization in thread reports.

## Findings

- `analyzemail/threads.py:70` defines singleton group keys as `tuple[str, int]`.
- `analyzemail/threads.py:82` uses only `(subject_key, week_bucket)` as the grouping key.
- Sender identity (or domain/list metadata) is not part of fallback linkage criteria.

## Proposed Solutions

### Option 1: Add Sender Domain To Fallback Key

**Approach:** Group by `(normalized_subject, week_bucket, from_domain)` instead of subject/week only.

**Pros:**
- Significant reduction in accidental cross-sender merges.
- Small code change with straightforward tests.

**Cons:**
- Legitimate cross-domain thread continuity remains split.

**Effort:** Small

**Risk:** Low

---

### Option 2: Require Additional Similarity Signal Before Merging

**Approach:** Keep subject/week as a prefilter, then require at least one of: same sender, same list-id, same reply prefix pattern.

**Pros:**
- Better precision than domain-only grouping.
- More resilient to subject collisions.

**Cons:**
- More logic complexity and broader test matrix.

**Effort:** Medium

**Risk:** Medium

---

### Option 3: Disable Subject-Based Fallback

**Approach:** Only thread using `Message-ID`/`References` graph links.

**Pros:**
- Eliminates accidental fallback merges.

**Cons:**
- Under-groups messages missing reference headers.
- Reduces usefulness of thread impact estimates.

**Effort:** Small

**Risk:** Medium

## Recommended Action


## Technical Details

**Affected files:**
- `analyzemail/threads.py:70`
- `analyzemail/threads.py:82`
- `tests/test_threads.py` (add regression case for same-subject/different-sender)

**Related components:**
- Thread ranking in `analyzemail/reports.py`
- Summary output thread impact in `summary.txt`

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- **PR:** https://github.com/jmonschke/analyzeMail/pull/1
- **Review context:** workflows-review run on branch `feat/gmail-takeout-analyzer`

## Acceptance Criteria

- [ ] Fallback thread grouping no longer merges same-subject messages from different senders by default
- [ ] Thread-level candidate byte totals remain stable for explicit reply/reference chains
- [ ] Tests include cross-sender, same-subject fixtures validating no false merges
- [ ] Existing threading tests continue to pass

## Work Log

### 2026-02-20 - Initial Discovery

**By:** Codex

**Actions:**
- Reviewed fallback grouping logic in `analyzemail/threads.py`
- Traced group key construction and edge-link behavior
- Drafted implementation alternatives and acceptance criteria

**Learnings:**
- Subject-only fallback is useful but needs tighter identity constraints for reliable thread impact reporting

## Notes

- Maintain deterministic ordering and output behavior after fallback logic change.
