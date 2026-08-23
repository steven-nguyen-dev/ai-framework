---
name: glossary-maker
description: Scan a repository and write GLOSSARY.md — its terminology in ISO 704:2022 form.
disable-model-invocation: true
version: 0.2.0
---

# glossary-maker

Harvest a repository's working vocabulary into `GLOSSARY.md`: one concept per entry, numbered so any
entry can be cited.

Admission turns on one thing — the **collision**. A designation is admitted where a reader meeting
it cold, or carrying its sense from another project, lands on the wrong code. A designation the
class settles keeps its ordinary meaning and stays out. Admission is never for importance: general
programming vocabulary stays out however heavily the project uses it.

**Drift** holds across every step. Code, config and manifests settle a characteristic; a README, a
Javadoc paragraph or an HLD makes a claim. Where a claim contradicts the code, the entry follows the
code and the contradiction ships in the handover as drift.

## Step 1 — Frame the corpus

1. **Name the target** — the repo, or the module the user named. A monorepo with no named target
   takes one question, then proceeds.
2. **Choose the mode.** `GLOSSARY.md` at the repo root means **refresh**; its absence means
   **create**.
3. **Open `GLOSSARY-HEADER.md`**, beside this file. It is the output's opening, copied verbatim with
   `<the thing>` filled in, and its Legend is what each field means — this skill carries only the
   tests a writer applies on top.
4. **Bound the corpus** as an include list and an exclude list. Generated Javadoc under
   `target/site/apidocs` renders the source — read the source it renders.
5. **In refresh mode, read the existing glossary in full** before any harvest, and keep an untouched
   copy aside — its numbers are live citations that Step 4 keeps and Step 5 checks against.

Completion: target named; mode chosen; header template open; both path lists written; in refresh
mode, every existing headword listed with its number and the pre-refresh copy set aside.

## Step 2 — Harvest

**One sub-agent per lane, run concurrently.** Each returns one line per candidate — designation,
lane, and evidence as `file:line` or `file · Class.method` — plus any **drift** it met: a document
sentence the code contradicts, with a citation on each side. Nothing besides, so the code behind it
stays out of this context.

| Lane | Where it looks | What it yields |
|---|---|---|
| **Enum & constant** | `enum E*`, `public static final`, annotation types | closed value sets — the *values* are designations, not only the type |
| **Config key** | `application*.{yml,properties}`, `@Value("${…}")`, `@ConfigurationProperties` | property names whose letters lie about what they hold |
| **Module & package** | aggregator poms (`<modules>`), Gradle includes, root directories, package roots | suffix conventions, deployable names, and directories no aggregator lists |
| **Wire name** | topic and queue names, REST path prefixes, table and column names, headers | cross-team shorthand that reaches nobody through prose |
| **Javadoc & comment** | class and method Javadoc, `TODO` / `NOTE` / `XXX` | the term a developer had to stop and explain in place |
| **Prose** | `*.md`, HLDs, ADRs, handover notes, README, exported wiki pages | business vocabulary carrying no identifier — order stages, document names, roles |
| **Collision** | across every lane above | the shapes below |

The **collision** lane pays for the run. It hunts four shapes:

- One designation, two referents — the same word declared in unrelated packages, or naming a module
  in one document and a team in another.
- Two designations, one referent — synonyms in circulation, of which one wins.
- An abbreviation expanded two ways, or expanded nowhere on disk.
- Identifiers one edit apart where both are live (`nexusPath` beside `nexxusPath`) — a misspelling
  the code reads is a designation.

Completion: every candidate carries a lane and at least one evidence citation; every lane has
returned its drift, reporting none where it found none; the collision lane has reported on all four
shapes, naming the shape as absent where it found none.

## Step 3 — Admit

Hold every candidate against the collision test. Each takes one verdict with its deciding reason:

| Verdict | When |
|---|---|
| `admit` | the designation collides |
| `reject` | opening the class settles it, or it carries its ordinary meaning |
| `defer` | admission turns on a fact no source settles — carries the question |

Completion: every candidate carries a verdict and its reason; every `defer` carries a question.

## Step 4 — Write

Open the file with the header template, then group admitted concepts into five to eight sections
named after the reader's question rather than the code layout. *The layer*, *Flows and messaging*,
*Modules and code*, *Products and platforms*, *Business vocabulary*, *Auth, config and
infrastructure*, *Shorthand designations* is a set that has worked.

### One field, one test

The Legend says what each field carries. A field earns its content by one further test:
**delete-and-check** — omit the line, ask what lookup now returns the wrong answer, and keep it only
if there is one. Content that fails its own field's test moves to the field whose test it passes;
content that passes none is deleted. The definition's test is stricter: it substitutes for the term
in a running sentence and leaves it true.

`NOTE` is the residue, and keeps only what delete-and-check keeps: it is the last field to try, not
the first. `GAP` is the one field that earns content by absence — a characteristic the reader will
need that no consulted source settles. It takes a `GAP` line so the next reader inherits the
question rather than an invention.

### The gate resolves, the writer judges

Step 5 resolves designations against each other across the whole file — that is all it does, and it
is the one pass a reader cannot do reliably. Everything visible inside a single entry is yours:

- **A definition stands on its own terms.** It opens with something other than its own term, no two
  definitions define each other, it runs to one sentence, and it closes without a full stop.
- **A list of one drops its numbering.** One note is `NOTE`, not `NOTE 1`.
- **Field text identical across set members** sits on the `SET` line, once.

Three of these turn on judgement no checker could reach:

1. **Intensional definition.** Superordinate concept first, then only the characteristics that
   delimit this concept from its coordinates.
2. **A delimiting negative is definitional.** "which speaks the Anchanto product's contract and
   never calls a partner" is one sentence and belongs in the definition. A contrast with a *named
   neighbour* is what goes to `CONFUSABLE` — the distinction the gate cannot make for you. Carry the
   negative on a verb, as that example does; a definition opening `not …` or `is not …` trips the
   gate's negative-definition error however delimiting it is.
3. **Part of speech is preserved.** A noun term takes a noun-phrase definition; an adjectival term
   takes a subject field of the form ‹of a …› and an adjectival definition.

### Three forms

**A table, where a section is uniform.** Entries carrying a definition and nothing else are rows.
The number stays in the row, so citations survive.

```markdown
| # | designation | definition |
|---|---|---|
| 7.1 | `CONN` | an area's connector deployable, `connector/<area>-connector` |
| 7.2 | `AREACORE` | an area's core module |
```

**A full entry, where the concept carries a gotcha.** Pull these out of the table — they are what a
reader came for.

**A `SET` line, where one designation has several senses.** One line names the whole set, and each
member carries its own subject field. Field text identical across members sits on the set line,
once.

```markdown
SET write-back ‹result leg› ‹partner direction› ‹credential refresh›
```

Resolve every `defer` from Step 3 here: it becomes a `GAP` line carrying its question, or it is
dropped with the reason recorded for the handover.

### Numbers

Sections are `## N`, entries `N.M`. An entry keeps its number for life: new concepts append within
their section, and a concept that no longer exists keeps its number and moves to `## Retired` at the
foot with one line saying what replaced it. A reused number rewrites every citation that pointed at
the old one.

Completion: every admitted concept has an entry, row or set member; every field in the file has been
put to its own test and the result recorded, field by field rather than asserted in aggregate; every
deferred candidate is a `GAP` line or is dropped with its reason recorded; in refresh mode, every
pre-existing number still means what it meant.

## Step 5 — Gate

```bash
python3 <this skill>/scripts/resolve_glossary.py <target repo>/GLOSSARY.md
```

The script sits beside this file; `GLOSSARY.md` sits in the target repo. Resolve both paths before
running — a bare `scripts/…` resolves against the target repo and finds nothing.

It resolves every designation against every headword: a `DEPRECATED` that names a live entry, a
relation pointing nowhere, a homonym set that disagrees with its members, a number used twice. On a
hundred-entry file that is thousands of comparisons, and the errors are the harmful kind — a reader
who avoids a deprecated word substitutes this headword for it, so a `DEPRECATED` that really names
another concept quietly redirects them.

In refresh mode, pass the previous revision so numbering is held to its promise:

```bash
python3 <this skill>/scripts/resolve_glossary.py GLOSSARY.md --against <the pre-refresh copy>
```

Every finding is an unresolved reference, so every finding is a fix — there is nothing here to
argue with and no warning tier to triage.

Completion: the resolver exits 0, run with `--against` in refresh mode; its output recorded.

## Step 6 — Hand over

Report, in this order:

1. **Drift** — each document sentence the code contradicted, with both citations. The run's most
   valuable output.
2. **Counts** — entries and sections, split into new, changed and untouched.
3. **GAPs** — every unsettled characteristic, written as a question someone can answer.
4. **Rejects worth arguing about** — candidates a reader expects to find, and why they are out.

Then offer the pointer, because a glossary nothing loads is a glossary nothing reads:

```markdown
## Read before acting
- `GLOSSARY.md` — read before using or interpreting any project term. Cite by designation and
  number — "connector (1.3)". The file is the source; memory is not.
```

The pointer is the always-loaded index and the file is fetched on demand. Add `@GLOSSARY.md` beneath
it only for a glossary small enough — roughly a thousand tokens — that paying it on every turn and
every sub-agent dispatch beats one read. Report the file's size so the user can make that call.

Completion: all four report sections delivered; the file's token size reported; the pointer offered,
and written into `CLAUDE.md` or `AGENTS.md` on the user's word.
