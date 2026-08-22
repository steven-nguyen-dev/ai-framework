<!-- The state and the record. SKILL.md · "The log" states how to fill this file, and this comment
     stays because that section is short and this file is never the artifact under review.
     §0 is rewritten in place on the way out of every step. §1 is appended to and never edited. -->

# Raw context: `<feature name>`

## 0. State

| | |
|---|---|
| **State** | `<one rung from the ladder>` |
| **Since** | `<YYYY-MM-DD>` — `<the log line that moved it>` |
| **Waiting on** | `<the human / nothing>` |
| **Next action** | `<the next move, including any invocation to be typed>` |
| **Open gaps** | `<GAP-n name · GAP-n name>`, or `none` |
| **Baseline** | `<branch commit SHA at the last gate approval; at G2 also one git hash-object per planning artifact>` |

### The ladder

| # | State | Reached when |
|---|---|---|
| 0 | `awaiting source material` | The demand for material went out, unanswered |
| 1 | `intake complete` | Every artifact has an `SRC` line and a verdict |
| 2 | `interviewed` | The agent read the rule set back. The human confirmed it |
| 3 | `requirements generated` | `business-requirements.md` is complete. The agent requested G1 |
| 4 | `requirements approved` | The human ticked G1. Every gap carries a disposition |
| 5 | `codebase read` | Every unverifiable fact is settled, and the tests are demonstrably runnable |
| 6 | `specs generated` | `specs-builder` wrote `mapping-plan.md` and filled the spec folder |
| 7 | `plan generated` | `implementation-plan.md` is complete |
| 8 | `plan approved` | The human ticked G2. *Nothing in production changed before this* |
| 9 | `code generated` | Phase 1 tests ran red, the code compiles, phase 2 tests exist, the suite runs green |
| 10 | `code reviewed` | The cold review is on disk and every gap is dispositioned |
| 11 | `closed` | Promoted, de-referenced, retained |

**Rung 6 is skipped when no specs are generated** — the work moves rung 5 to rung 7. **Rungs 4, 8
and 10 are never skipped.** A review is not a rung: it does not advance the state and does not hold
it.

---

## 1. Log

*One line per event, appended in time order. Delete the three lines below before the first real one.*

- `<YYYY-MM-DD>` · `SRC-n` · `<short name>` · `<the document, its verdict, what it is used for>`
- `<YYYY-MM-DD>` · `GAP-n` · `<short name>` · `<the precise question. Owner: <owner>. Searched: <what, and the result>>`
- `<YYYY-MM-DD>` · `DEC-n` · `<short name>` · `<what was decided. Because <reason>. Rejected: <what lost>. Hangs off: root>`
