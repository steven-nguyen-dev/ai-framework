<!-- HOW TO FILL THIS FILE

     THIS FILE IS THE DESIGN A REVIEWER HOLDS AGAINST THE REQUIREMENTS. Write it so every claim can
     be refuted in one line: cite `file · Class.method` for current behaviour, and cite AC, NFR,
     GAP, DEC, FACT, SRC or MAP rather than restating what they say.

     Four sections, filled in this order, and there is no fifth:
       §1 file changes → §2 technical debt → §3 governance → §4 test plan.

     THIS FILE MINTS NOTHING. Every ID in it was minted elsewhere and is cited here.

     THREE THINGS HAVE A HOME ELSEWHERE:
       - The business flow — business-requirements.md §2, approved at G1. No flow section here.
       - Revision history — the log in raw-context.md. This file states the current design only.
       - A decision still open at a gate — a GAP line in raw-context.md, where the gate can see it.

     REUSE FIRST. Every [NEW] carries a recorded search miss: search this module, then domain
     siblings, then shared platform libraries, and log the result as a FACT line. "Nothing exists"
     is a result, written down so a reviewer can refute it in one line. The only other admissible
     reason for [NEW] is that reuse would break API backwards compatibility.

     SIBLING CONFORMANCE. Implementation and tests follow the nearest working sibling in the same
     module — logger builder patterns, exception handling, DTO mapping; and for tests, the sibling
     mocking, assertion, setup and naming conventions. Name that sibling in §4 before the tables.

     CITATIONS. First mention uses the bare fully-qualified symbol — `file · Class.method`; a
     property cites as well as a method. NO LINE NUMBERS: they do not survive the next merge from
     master. External contract claims carry their location in that contract — schema path,
     operation, field. Plain text, never a file:// link.
     A REFINED FILE IS NOT A CITATION TARGET. Where a large artifact was read through an extract,
     the claim cites the operation, schema path and field in the SOURCE. The extract is how it was
     read; the source is what it says.

     THE FILE CHANGES (§1) OPEN WITH SEQUENCING CONSTRAINTS — a build, migration, cutover or
     deadline order the file list does not imply, or `none`. WRITE THE CONSTRAINT, NOT A
     WALKTHROUGH. The implementation step derives its order from the file changes (§1) and the
     test plan (§4), so a step-by-step retelling here is a second source of truth for the same
     order.

     PLAN BOUNDARIES. Where specs were generated, this plan covers only what the .spec.yaml files
     do not. No overlapping plans. The file changes (§1) carry a `Covered by specs` list, after
     the sequencing constraints, naming what is delegated and to which spec file, so the seam is
     written down rather than inferred from an absence.

     DONE WHEN — checked against the other files, never recalled from memory:
       - the test plan (§4) states, in prose, that phase 1 covers every AC (business-requirements.md
         §3) and every NFR (§4) that needs a test — a blanket claim, not a row per criterion. It
         never covers a spec-covered AC by that blanket: a spec-covered AC is still named
         individually, citing its spec file and MAP, because it has no test of its own and the
         blanket claim would otherwise misstate that it does;
       - every `file · Class.method` cited here opens, and the symbol is found in it;
       - where mapping-plan.md exists, the file changes (§1) carry a non-empty `Covered by specs`
         list, and every spec-covered AC named in §4 cites a live MAP;
       - every [NEW] names the FACT holding its search miss;
       - the test plan's phase 2 (§4) names at least one target, or says in one line why it has
         none;
       - every <placeholder> is replaced, and every example row is deleted;
       - after the strip, the file holds no <!-- at all.

     ESTABLISH EACH CLAIM BY OPENING FILES, never by recalling what this session did. A count you
     did not enumerate is a guess.

     STRIP THIS COMMENT AND THE ONE BELOW at the end of Step 3, before the quality-bar review and G2. A
     reviewer judges the result, not the method. -->

<!-- WRITING RULES

     Altitude. This file is the developer's document, so a class, a method and a file are all in
     scope — unlike the requirements. What is out of scope is restating business intent: that was
     settled at G1 and is cited, not re-argued.

     Sentences and evidence. The writing-a-line rules (SKILL.md · The log) bind every sentence and
     every quote here too. Literal plain words and consistent terms — the same component keeps the
     name business-requirements.md gave it.

     A file description is a code comment, not an essay — the same javadoc convention this repo's
     own coding standard states (`CODING-GUIDELINES.md`): two lines on WHAT the change does; HOW,
     only when what won't stand alone; WHY, by exception — a design that departs from the obvious
     (an anti-pattern avoided, a workaround, an unusual reuse or type choice), never a restated
     rationale for an ordinary one. Do not narrate the reasoning that led there — that is a decision
     line in raw-context.md, cited, not repeated. -->

# Implementation plan: `<feature name>`

## 1. File changes

**Sequencing constraints:** `<a build, migration, cutover or deadline order the file list does not imply — or `none`>`

**Covered by specs:** `<what this plan delegates>` → `<area>/specs/<code>/<spec file>`
*(One line per delegated area of work. Everything below this list is what the plan itself builds.
Delete this line if no specs were generated.)*

```text
<module>/
├── <source root, per this project>/
│   ├── <Existing><Thing>            UPDATE
│   └── <New><Thing>                 NEW — search miss: FACT-n
```

### `<File name 1>`
`<What the change does and why.>`

### `<File name 2>`
`<What the change does and why.>`

---

## 2. Technical debt

*The IDs this plan carries. Substance and settlement condition live in the `raw-context.md` log.*

| Debt | Title |
|---|---|
| TD-n | `<one line>` |

---

## 3. Governance

*The named documents this change must conform to — coding standard, area spec or harness, migration
or deployment guide. A reviewer holds the diff against exactly this list, so a governing document
omitted here is an undeclared departure.*

- `<Document name 1>`
- `<Document name 2>`

---

## 4. Test plan

**Conventions:** the sibling this feature follows is `<Class>`; the naming pattern is
`<MethodName_Condition_ExpectedResult>`; it registers `<extensions>`. `<FACT-n>`

Two phases, in prose — no per-`AC` table; which method or class each criterion belongs to already
follows from §1's file descriptions, and re-listing it here is the same fact twice.

**Phase 1**, written before the implementation, covers every acceptance criterion
(`business-requirements.md` §3) and every technical constraint (§4) that needs a test — say so as
one blanket statement. The one exception: an `AC` delegated to a spec is named individually, citing
its spec file and `MAP`, because it has no test of its own and the blanket statement must not imply
otherwise.

**Phase 2** names targets, not cases — the tests against them are written only after the
implementation compiles, when the branches exist, and a case list written now is a guess about code
that does not exist. Scope is the major exception paths, boundary values and interactions the file
changes (§1) create or change; say in one line if there are none.
