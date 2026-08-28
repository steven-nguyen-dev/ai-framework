# unslop change log, lv1-doc-writer 0.0.1 → 0.0.2

Rules from `unslop` 0.1.1. Input md5 `49db9f414be6c5ffc9bbf605c456a3e8`, 139 lines.

## Passes

| Pass | Applied | Result |
|---|---|---|
| 1 Mechanical | M1-M6 | 0 hits. No curly quotes, no title-case heading, no emoji, no fancy synonym, no filler opener, no chatbot residue |
| 2 Sentence | S7, S8, S9, S10, S11, punctuation | 14 edits |
| 3 Structure | T3, T6 | 2 edits |

## Pass 2, edits

| Rule | Before | After |
|---|---|---|
| S8 passive | "A paragraph is allowed only when" | "Write a paragraph only when" |
| S8 | "Wire-format facts are quoted, never inferred" | "Quote wire-format facts, never infer them" |
| S8 | "Sections compiled from other documents are declared as second-hand" | "Declare sections compiled from other documents as second-hand" |
| S8 | "A pointer to a file that no longer exists is deleted, not carried forward" | "Delete a pointer to a file that no longer exists, do not carry it forward" |
| S8 | "Detail that fails this test is not deleted — it moves to" | "Do not delete detail that fails this test. Move it to" |
| S8 | "Exceptions to a flow are stated with the flow, not buried in an area" | "State exceptions with the flow, do not bury them in an area" |
| S8 | "The first colour scheme was defended by a passing validator and was still wrong" | "A passing validator defended the first colour scheme. It was still wrong" |
| S8 | "They are not covered here and are not to be guessed at" | "This document does not cover them. Do not guess" |
| S8, A4 row 6 | "Section numbers: checked who cites" | "Checked who cites" (also removed a mid-sentence colon) |
| S9 adverb | "apply it absolutely" | "apply it to every document in the set" |
| S9 | "say so explicitly rather than omitting it silently" | "say so rather than omit it" |
| S11 hedge | "a reader should finish able to draw" | "A reader finishes able to draw" |
| S10 dense | "The cost is real: two documents at adjacent levels will state the same summary twice." | split into two sentences, colon dropped |
| S7 feeling | "The taxonomy is the spine." | "The taxonomy is fixed." |

## Pass 2, punctuation

| Location | Was | Now |
|---|---|---|
| B2, white-box bullet | 2 em dashes in one paragraph, over the 1-per-paragraph cap | "holding exactly three components (connector, bus, integration service)" |
| A1, scope bullet | "it states scope — not a hook" | "it states scope, not a hook" |
| B3, naming bullet | "labels are inconsistent — but record the collision" | "labels are inconsistent, but record the collision" |
| B4, flaw-location bullet | "a flaw of — not in a global appendix" | "a flaw of, not in a global appendix" |

Em dashes went from 14 to 8. The 8 kept are one per paragraph and separate a list item from its gloss, which A1 requires.

## Pass 3, edits

| Rule | Change |
|---|---|
| T3 | "**The completion test:** a reader should..." became "**The completion test.** A reader..." Bold label plus mid-sentence colon restating the line |
| T6 | Reading-guide table said `B1–B4`. Sections run B1 to B5. Corrected to `B1–B5` |

## Cut for lacking a source

None. Every claim in the input names its source or its example.

## Ship checklist, §4

| # | Check | Result |
|---|---|---|
| 1 | Code, identifiers and quoted text byte-identical | pass. `local-library/.manuscript/`, `N.1 Design`, `<doc> §N`, "inbound", "outbound", "82 partner modules", "Acknowledges, then processes" all unchanged |
| 2 | No fact, number, date or name absent from the input | pass. Nothing added |
| 3 | Every cut claim listed | pass. None cut |
| 4 | Each surviving sentence carries its original meaning | pass |
| 5 | Headings sentence case, quotes straight | pass |
| 6 | Em dash at most 1 per paragraph, no mid-sentence colon | pass |
| 7 | Domain terms kept, not swapped | pass. white box, black box, bus, HLD, taxonomy, flaw ID kept |

## Rule defect found

`unslop` §0 declared frontmatter keys and values untouchable, which blocked the `version` bump the
repo's Versioning Policy requires on any change. Amended in `unslop` 0.1.1: `version` is the one
frontmatter value a pass may edit, and it must be bumped.
