---
status: complete
priority: p2
issue_id: "001"
tags: [code-review, quality, classification]
dependencies: []
---

# Fix Sent Label Detection False Positives

Exclude messages from deletion candidates only when they are truly in sent-mail labels, not when a custom label merely contains the substring `sent`.

## Problem Statement

`classify_messages` currently marks a message as sent mail when the raw labels string contains the substring `sent`. This can incorrectly exclude valid cleanup candidates when users have custom labels like `consent`, `presentations`, or other values containing `sent`.

This causes false negatives in candidate detection and underestimates reclaimable space.

## Findings

- `analyzemail/classify.py:109` lowercases the raw `X-Gmail-Labels` string.
- `analyzemail/classify.py:110` uses `if "sent" in labels`, which is substring-based rather than token/exact-match based.
- The current implementation has no parsing of comma-separated label tokens or canonical Gmail sent-label variants.

## Proposed Solutions

### Option 1: Parse Labels Into Tokens And Match Exact Sent Labels

**Approach:** Split the labels header into normalized tokens and match against a canonical set (`sent`, `sent mail`, `\\sent`).

**Pros:**
- Removes substring false positives.
- Keeps behavior deterministic and easy to test.

**Cons:**
- Requires maintaining a small canonical label set.

**Effort:** Small

**Risk:** Low

---

### Option 2: Match Whole-Word Boundaries In Raw String

**Approach:** Use regex word boundaries around `sent` in the raw label string.

**Pros:**
- Minimal code change.

**Cons:**
- Still brittle for quoted labels and provider-specific label formats.

**Effort:** Small

**Risk:** Medium

---

### Option 3: Remove Sent-Label Exclusion Entirely

**Approach:** Drop the `sent_mail` exclusion and rely on `-in:sent` in generated filter queries.

**Pros:**
- Simplifies classifier logic.

**Cons:**
- Candidate exports become less accurate and may include sent items in CSV summaries.

**Effort:** Small

**Risk:** Medium

## Recommended Action

Implement Option 1: parse `X-Gmail-Labels` into normalized tokens and match only canonical sent labels (`sent`, `sent mail`, `\\sent`). Add regression tests covering false-positive custom labels and canonical sent labels.

## Technical Details

**Affected files:**
- `analyzemail/classify.py:109`
- `analyzemail/classify.py:110`
- `tests/test_classify.py` (add regression coverage)

**Related components:**
- Sender summaries and confidence scoring in `analyzemail/classify.py`
- Filter generation input in `analyzemail/reports.py`

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- **PR:** https://github.com/jmonschke/analyzeMail/pull/1
- **Review context:** workflows-review run on branch `feat/gmail-takeout-analyzer`

## Acceptance Criteria

- [x] Sent-mail detection uses exact label-token matching, not substring matching
- [x] Messages with non-sent labels containing `sent` are not excluded
- [x] Unit tests cover canonical sent labels and false-positive custom labels
- [x] Existing classifier tests still pass

## Work Log

### 2026-02-20 - Implementation

**By:** Codex

**Actions:**
- Updated sent-mail exclusion logic in `analyzemail/classify.py` to parse label tokens and match exact canonical sent labels
- Added regression test `test_sent_label_detection_uses_exact_tokens` in `tests/test_classify.py`
- Ran full test suite: `9 passed`

**Learnings:**
- Gmail label handling should be tokenized before classification checks; substring matching is too broad for user/custom labels

### 2026-02-20 - Initial Discovery

**By:** Codex

**Actions:**
- Reviewed classifier exclusion logic in `analyzemail/classify.py`
- Identified substring-based sent-label check as root cause
- Drafted solution options and acceptance criteria

**Learnings:**
- Conservative filtering is appropriate, but sent-mail detection needs token-level precision to avoid false negatives

## Notes

- Keep default behavior conservative while improving correctness.
