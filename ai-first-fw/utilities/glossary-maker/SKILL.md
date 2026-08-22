---
name: glossary-maker
description: Scan a repository and write GLOSSARY.md — its terminology in ISO 704:2022 form.
disable-model-invocation: true
version: 0.0.2
---

# glossary-maker

Harvest a repository's working vocabulary into `GLOSSARY.md`: one concept per entry, numbered so
any entry can be cited.

Admission turns on one thing — the **collision**. A designation is admitted where a reader meeting
it cold, or carrying its sense from another project, lands on the wrong code. A designation the
class settles keeps its ordinary meaning and stays out.

Three disciplines hold across all six steps:

- **Drift.** Code, config and manifests settle a characteristic; a README, a Javadoc paragraph or
  an HLD makes a claim. Where a claim contradicts the code, the entry follows the code and the
  contradiction ships in the handover as drift.
- **Declared silence.** A characteristic no consulted source settles takes a `GAP` line, so the
  next reader inherits the question rather than an invention.
- **Delegated reading.** Each harvest lane is a sub-agent returning one line per candidate:
  designation, lane, and evidence as `file:line` or `file · Class.method`. That return is the
  lane's whole deliverable, so the code behind it stays out of this context.

## Step 1 — Frame the corpus

1. **Name the target** — the repo, or the module the user named. A monorepo with no named target
   takes one question, then proceeds.
2. **Choose the mode.** `GLOSSARY.md` at the repo root means **refresh**; its absence means
   **create**.
3. **Bound the corpus** as an include list and an exclude list. Generated Javadoc under
   `target/site/apidocs` renders the source — read the source it renders.
4. **In refresh mode, read the existing glossary in full** before any harvest. Its numbers are live
   citations and Step 4 keeps them.

Completion: target named; mode chosen; both path lists written; in refresh mode, every existing
headword listed with its number.

## Step 2 — Harvest

**One sub-agent per lane, run concurrently.** Each returns its candidate list and nothing besides.

| Lane | Where it looks | What it yields |
|---|---|---|
| **Enum & constant** | `enum E*`, `public static final`, annotation types | closed value sets — the *values* are designations, not only the type |
| **Config key** | `application*.{yml,properties}`, `@Value("${…}")`, `@ConfigurationProperties` | property names whose letters lie about what they hold |
| **Module & package** | aggregator poms (`<modules>`), Gradle includes, root directories, package roots | suffix conventions, deployable names, and directories no aggregator lists |
| **Wire name** | topic and queue names, REST path prefixes, table and column names, headers | cross-team shorthand that reaches nobody through prose |
| **Javadoc & comment** | class and method Javadoc, `TODO` / `NOTE` / `XXX` | the term a developer had to stop and explain in place |
| **Prose** | `*.md`, HLDs, ADRs, handover notes, README, exported wiki pages | business vocabulary carrying no identifier — order stages, document names, roles |
| **Collision** | across every lane above | the four shapes below |

The **collision** lane pays for the run. It hunts four shapes:

- One designation, two referents — the same word declared in unrelated packages, or naming a module
  in one document and a team in another.
- Two designations, one referent — synonyms in circulation, of which one wins.
- An abbreviation expanded two ways, or expanded nowhere on disk.
- Identifiers one edit apart where both are live (`nexusPath` beside `nexxusPath`) — a misspelling
  the code reads is a designation.

Completion: every candidate carries a lane and at least one evidence citation; the collision lane
has reported on all four shapes, naming the shape as absent where it found none.

## Step 3 — Admit

Hold every candidate against the collision test. Each takes one verdict with its deciding reason:

| Verdict | When |
|---|---|
| `admit` | the designation collides |
| `reject` | opening the class settles it, or it carries its ordinary meaning |
| `defer` | admission turns on a fact no source settles — carries the question |

A term is admitted for its collision, never for its importance: general programming vocabulary
stays out however heavily the project uses it.

Completion: every candidate carries a verdict and its reason; every `defer` carries a question.

## Step 4 — Write

Group admitted concepts into five to eight sections named after the reader's question rather than
the code layout. *The layer*, *Flows and messaging*, *Modules and code*, *Products and platforms*,
*Business vocabulary*, *Auth, config and infrastructure*, *Shorthand designations* is a set that has
worked. Number sections `## N` and entries `**N.M designation**`.

Open the file with the header below, then write every entry to the rules that header states. The
header is the output's own instructions: a later reader extends the file from it without this skill.

````markdown
Concept system for <the thing>. This file is the layer-wide language: the concepts that exist here,
the one designation to use for each, and the designations that must not be used.

Written to ISO 704:2022. Entry layout follows ISO 10241-1.

## Scope

An entry belongs here when a reader who resolves the designation from ordinary language, or from
another context in this organisation, arrives at the wrong code. A designation resolved by opening
the class does not belong here. Anything unlisted carries its ordinary meaning.

## How to read an entry

```
**1.2 term ‹subject field›**
ADMITTED: alternative designation for this same concept
DEPRECATED: designation for this same concept that must not be used

definition — one substitutable noun phrase, no closing period

NOTE 1  true of the concept but not part of its definition
EXAMPLE  an instance of the concept
CONFUSABLE  a designation naming a DIFFERENT concept
BROADER / NARROWER / PART OF / PARTS / COORDINATE / RELATED  concept relations
GAP  what no consulted source states
```

`DEPRECATED` and `CONFUSABLE` are different fields and never merge. A deprecated designation is the
wrong word for **this** concept. A confusable designation is the right word for **another** concept.
Merging them makes the file harmful: a reader told to avoid a word substitutes this headword for it,
and a reference to the other concept silently becomes a reference to this one.

## Rules for adding or editing an entry

1. **One concept, one entry.** A designation with two senses gets two entries, each with a subject
   field in ‹guillemets›, each listing the others under `CONFUSABLE`.
2. **Intensional definition.** Superordinate concept first, then only the characteristics that
   delimit this concept from its coordinates.
3. **Substitution test.** The definition replaces the term in a running sentence and leaves it true
   and readable. What fails this is a note.
4. **No circularity.** A definition opens with something other than its own term, and two
   definitions never define each other.
5. **State what the concept is.** "Not X" belongs on a `CONFUSABLE` line.
6. **Part of speech is preserved.** A noun term takes a noun-phrase definition; an adjectival term
   takes a subject field of the form ‹of a …› and an adjectival definition.
7. **Notes carry the rest.** Implementation, history, warnings, spelling traps — all notes.
8. **Silence is declared.** Write a `GAP` line where no consulted source settles a characteristic.

## Numbers are stable

An entry keeps its number for life. New concepts append within their section. A concept that no
longer exists keeps its number and moves to `## Retired` at the foot with one line saying what
replaced it, because a reused number rewrites every citation that pointed at the old one.
````

Completion: every admitted concept has an entry; every homonym carries a subject field and lists its
siblings as `CONFUSABLE`; every deferred candidate appears as a `GAP` line or is dropped with its
reason recorded; in refresh mode, every pre-existing number still means what it meant.

## Step 5 — Gate

```bash
python3 scripts/validate_glossary.py GLOSSARY.md
```

The gate passes on exit 0. Fix what it names and run it again.

It carries the cross-entry rules a reading pass cannot: every deprecated designation resolved
against every headword, every homonym group cross-referenced both ways, every taxonomic relation
resolved to a real entry. On a hundred-entry file that is thousands of comparisons. `--help` lists
the rest.

Warnings pass the gate. Fix each one, or answer it in the handover with the reason it stands.

Completion: the validator exits 0; its output recorded; every warning fixed or answered.

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
- `GLOSSARY.md` — before using or interpreting any project term.
  Cite by term *and* number — "connector (1.3)". The file is the source; memory is not.

@GLOSSARY.md
```

Completion: all four report sections delivered; the pointer offered, and written into `CLAUDE.md` or
`AGENTS.md` on the user's word.
