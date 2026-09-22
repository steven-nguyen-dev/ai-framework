# The quality bar

What an implementation plan clears before G2. `implementation-planner` Step 3 hands this file and a
feature folder path to a sub-agent, which holds the plan against every line here and reports what
fails.

## The stance

- **Cold** — read the folder on disk and the files its citations name. Use nothing from the
  invoking conversation.
- **Contamination abort** — where the planning conversation, the interview or an earlier round is
  present in context, report that instead of reviewing.
- **Diagnostic** — name what is wrong, where it is, and what it contradicts. Write no rewrites and
  no suggested wording, edit no file, and leave `raw-context.md` §0 exactly as found.
- **Document-only** — no codebase survey, no sibling search. Open a cited `file · Class.method` far
  enough to see the symbol, and go no further.

## What it reads

| File | For |
|---|---|
| `raw-context.md` §0 | Read first — the state, and whether the plan exists |
| `implementation-plan.md` | The artifact under the bar |
| `business-requirements.md` | The authority on what should happen |
| `raw-context.md` §1 | The log — every `SRC`, `FACT`, `DEC`, `GAP` and `TD` |
| `mapping-plan.md` and the spec files it names | The boundary contract, where the area has one |

A missing `raw-context.md`, `implementation-plan.md` or `business-requirements.md` stops the review
and is itself the finding. So does a `raw-context.md` carrying no §0.

## Evidence

- Every `file · Class.method` and `package.ClassName#member` citation opens, and the symbol is found
  in it.
- Every current-behaviour claim carries a citation or the word `unverified`.
- Every `SRC` cited in a requirements `Source` column has a log line, and every path that line names
  opens on disk.
- Every `SRC` line carries a fitness verdict.
- A claim citing a `refined/` extract rather than the source operation, schema path or field is a
  finding.
- A `Source` reading `<who>, <date>` for something a supplied material already states is untraced.
- Every `[NEW]` in the file tree (plan §1) names the `FACT` holding its search miss, and that `FACT`
  names the scopes searched.
- Hand-authored test data presented as observed production data is a finding.

## Brief

The plan implements `business-requirements.md` — all of it, and nothing more.

- The test plan (§4) carries the blanket statement that phase 1 covers every `AC` (requirements §3)
  and every `NFR` (§4) needing a test.
- An `AC` a spec covers instead of a test is named individually in §4, citing its spec file and its
  `MAP` — the blanket statement does not carry it.
- Phase 1 restates no scenario. A Given / When / Then in the plan is a copy of requirements §3, and
  a copy drifts.
- Phase 2 names at least one target class or method, or states in one line why it has none, and
  every target traces to a file plan §1 creates or changes.
- Every `NFR` is addressed by phase 1, a phase 2 target, or an explicit plan note.
- Everything the plan builds traces to an `AC` or an `NFR`. The rest is scope creep.
- Where specs exist, plan §1 carries a `Covered by specs` list, every entry names a spec file that
  exists, and no §1 file change re-implements what that list delegates.

## Coherence

The plan contradicts neither itself nor the record.

- The file tree (§1) against the test plan (§4): every non-test file is a phase 2 target or carries
  a stated reason for needing none.
- Governance (§3) against the file changes (§1).
- The §1 `Sequencing constraints` line states a constraint the file list does not imply, or reads
  `none`.
- No section contradicts a `DEC` in the log.
- Every `DEC` line carries its reason, what lost, and the parent it hangs off. A parent naming an ID
  that does not exist is a finding.
- Every ID was minted in the document that owns it (`SKILL.md` · The IDs), and none was renumbered.
- No `AC` or `NFR` names wire-format detail — an endpoint, a field name, a status code.
- Every `TD` states what would settle it.
- Every gap §0 lists as open carries an owner and a search record in the log, and is surfaced in the
  gate request rather than left for the human to find.
- The writing rules (`SKILL.md` · Writing a line) hold: sentences short and active, the actor named,
  every name meaning something, evidence copied rather than paraphrased.
- Every diagram renders. Where the machine has no renderer, the finding says the diagram is
  unverified rather than passing it.

## Mapping — where `mapping-plan.md` exists

- Every mapping row carries a `MAP` ID, a stated reason and a confidence grade.
- Every boundary field the partner document defines appears in the mapping plan.
- A mapping that would fail silently — wrong key or identifier, SKU, money, state — carries all four
  of: the target's business purpose, its contract placement, its near-miss field or `none`, and the
  business consequence of getting it wrong. Any one blank is a finding.
- Every value set names what closed it — a schema, an enumeration, a partner document. A sample
  payload closes nothing.
- Every fallback is a decision, never a language default standing in for one — `0`, `false`, `""`.
- Every cardinality mismatch carries a rule or a `GAP`.
- Null and absent are answered separately.
- A target with no source, and a dropped inbound field, are each stated. Silence is a finding.
- A transformation the plan describes that the mapping plan does not reflect, or a mapping whose
  rule the plan contradicts, is a finding.

## What a finding is

Four things, and no more:

1. **What is wrong** — one sentence.
2. **Where** — the section, and the line quoted from it.
3. **What it contradicts** — the `AC`, `NFR`, `DEC`, `FACT`, the citation that did not resolve, or
   the other section of the plan.
4. **Severity** — `blocker` (the gate must not pass), `defect` (fix before the gate, or take a
   disposition like a gap), or `note`.

Report to the calling agent, opening on `blockers: n · defects: n · notes: n`, then the findings
grouped under Evidence, Brief, Coherence and Mapping. A heading with nothing under it reads
`0 findings`. Write no file.
