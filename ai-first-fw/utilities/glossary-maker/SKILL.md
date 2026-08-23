---
name: glossary-maker
description: Harvest a repository once and write two documents — GLOSSARY.md, its terminology in ISO 704:2022 form, and a GOTCHAS file per partition, the behaviours no single file states.
disable-model-invocation: true
version: 0.3.0
---

# glossary-maker

One harvest, two outputs, split by whether the reader needs a **word** or a **behaviour**.

| Output | Answers | Found by |
|---|---|---|
| `GLOSSARY.md` | what this designation means here | reading **what is written** |
| `GOTCHAS-<partition>.md` | what happens that no file admits | walking **what happens** |

A designation is declared somewhere, so a lane harvests it. A **trap** is declared nowhere: it is
true only across two or more hops, which is why grep finds none of them and why a reader who opens
the class still misses it. Hence two lane families (Step 2), two admission tests (Step 3), and a
routing table in place of judgement.

**Drift** holds across every step. Code, config and manifests settle a characteristic; prose makes a
claim. Where they disagree the entry follows the code and the contradiction ships as drift.

The six steps are a floor. Add lanes, passes and sub-agents where the target warrants them; every
added step states its own completion criterion in the same form.

## Step 1 — Frame

1. **Target** — the repo, or the module the user named. A monorepo with no named target takes one
   question, then proceeds.
2. **Mode** — `GLOSSARY.md` at the repo root means **refresh**, its absence **create**. The glossary
   sets the mode; gotchas files follow it.
3. **Open both format files** beside this one — `GLOSSARY-FORMAT.md`, `GOTCHAS-FORMAT.md`. They
   carry the opening to copy and every rule for what you write; this file carries the process.
4. **Corpus** — an include list and an exclude list. Generated documentation renders source: read
   the source it renders.
5. **Partition** — area, service, bounded context, package root. Take the target's own term for it.
   The output is one gotchas file per partition that earns one, plus `GOTCHAS-shared.md`.
6. **In refresh mode**, read every existing document in full before any harvest and set an untouched
   copy of each aside. Their numbers are live citations Step 4 keeps and Step 5 checks against.

Completion: target, mode, both path lists and the partition's source named; in refresh mode every
existing headword and trap listed with its number, and a pre-refresh copy of each document aside.

## Step 2 — Harvest

**One sub-agent per declaration lane, one per entry point for the flow lane**, run concurrently.
Each returns one line per candidate — designation or trap, lane, and evidence as `file:line` or
`file · Class.method` — plus any drift it met, cited on both sides. Nothing besides, so the code
behind it stays out of this context.

### Declaration lanes → the glossary

Each lane is stated by what it **is**; derive the search patterns from the stack you find.

| Lane | What it is | What it yields |
|---|---|---|
| **Closed value set** | enumerated types, symbolic constants, annotation or attribute types | the *values* are designations, not only the type |
| **Configuration key** | property and settings files, environment bindings, injected values, flags | names whose letters lie about what they hold |
| **Deployable boundary** | build-graph members, root directories, package roots, service names | suffix conventions, and directories no build graph lists |
| **Wire name** | topics, queues, path prefixes, tables, columns, headers | cross-team shorthand prose never carries |
| **In-place explanation** | doc comments on a type or an operation, `TODO` / `NOTE` / `XXX` | the term a developer stopped to explain in place |
| **Prose** | `*.md`, HLDs, ADRs, handover notes, README, wiki exports | business vocabulary carrying no identifier |
| **Collision** | across every lane above | the four shapes below |

The **collision** lane pays for the run:

- one designation, two referents — the same word declared in unrelated packages, or naming a module
  in one document and a team in another
- two designations, one referent — synonyms in circulation, of which one wins
- an abbreviation expanded two ways, or expanded nowhere on disk
- identifiers one edit apart where both are live (`nexusPath` beside `nexxusPath`) — a misspelling
  the code reads is a designation

### Flow lane → the gotchas

Every flow has the same spine:

```text
entry → admission → transformation → [persistence] → emission → terminus
```

Two invariants hold across it, and every trap violates one. **Data enters on a request** — a call, a
message, a timer, a file appearing, a lifecycle hook. **Data must leave**: persistence is optional,
emission is not, and a datum that arrives nowhere is a trap not yet found.

**The walk.** Enumerate every entry, including what no route table lists — subscribers, scheduled
work, lifecycle hooks, file watchers, framework callbacks, reflective dispatch; an entry nothing
points at is already a finding. Pick **one real field** per entry, never a concept — `weight`, not
"the shipment", because a concept can be reasoned about where a field has to be found. Walk hop by
hop, recording four facts and only these: what the datum is **called** here, its **shape** (type,
unit, nullability), whether the path can **end here** while the caller is told nothing, and whether
the hop is **reachable by search** or only by execution. Name the terminus — the response, the row,
the outbound call, the file; where you cannot, that is the finding. Check persistence separately:
the write key, the read key, and whether they resolve to each other. Log every stuck point.

**The six shapes**, found at the joints rather than inside the files:

| Shape | Asks | Signature at the joint |
|---|---|---|
| **Silent stop** | the caller was told it worked — did it? | swallowed error, fall-through default, dropped message, guard returning nothing, success acknowledged before the work runs |
| **Invisible hop** | how did control get here? | annotation-driven schedule, lifecycle hook, reflective or dynamic dispatch, convention wiring, config-selected implementation |
| **Identity change** | is this still the same datum? | one datum under two names, keys or types across hops; two datums sharing one name; a live misspelling |
| **Phantom capability** | does the declared thing run? | stubbed implementation of a real interface, constant nobody reads, disabled schedule, error never raised, build tree that never compiles |
| **Double run** | did one input run twice? | one stimulus, two executions; a "refresh" that destroys and recreates; a retry that is not idempotent |
| **Human-only knowledge** | why did the code not tell me? | you followed code and flow, got stuck, and a person had to say which way it goes |

Shape 6 is the most valuable and the easiest to lose. A question you had to ask a human is a fact the
code does not carry, and the next reader stops at exactly the same joint — so record what you tried
before asking. Where nobody could answer, it is a `GAP` and ships as a question.

Completion: every candidate carries a lane and at least one citation; every lane has returned its
drift, reporting none where it found none; the collision lane has reported on all four shapes,
naming any it found absent; every entry point is walked to a named terminus or a recorded finding,
every hop on it carrying its four facts; every stuck point logged with what was tried.

## Step 3 — Admit

Two tests, run separately — each candidate meets the test for the output it is bound for. They are
written down separately because otherwise gotchas become the bucket for whatever the glossary
rejected.

**The glossary test — collision.** A designation is admitted where a reader meeting it cold, or
carrying its sense from another project, lands on the wrong code. Admission is never for importance:
general programming vocabulary stays out however heavily the project uses it.

| Verdict | When |
|---|---|
| `admit` | the designation collides |
| `reject` | opening the class settles it, or it carries its ordinary meaning |
| `defer` | admission turns on a fact no source settles — carries the question |

**The gotcha test — surprise, search, cost.** All three are required; any one failing is a `reject`
naming that test.

- **Surprise** — a competent reader following the code reaches the wrong conclusion, or none. If
  opening the file settles it, it belongs elsewhere.
- **Search** — the finding names a behaviour. A thing search can find is a glossary entry.
- **Cost** — a wrong conclusion, or time. Neither, and it is dropped.

**Routing**, mechanical:

| Finding | Goes to |
|---|---|
| a designation that collides | the glossary |
| evidence inside one partition | that partition's gotchas file |
| evidence in two or more partitions | the shared file, as one shape with its exceptions |
| evidence on the transport or platform under every partition | the shared file |
| both a word and a behaviour | **both** — the glossary carries the definition, the gotcha the `Do:` |

Completion: every candidate carries a verdict, its deciding reason and its destination file; every
`defer` carries a question; every gotcha `reject` names the test it failed; every both-files finding
appears once per file.

## Step 4 — Write

**Close the glossary before opening the first gotchas file.** Gotchas cite glossary terms and each
partition's alias table extends the glossary's shorthand section; written concurrently they
disagree. Read the format file for the document in hand before its first entry.

Group the glossary's admitted concepts into five to eight sections named after the reader's question
rather than the code layout. *The layer*, *Flows and messaging*, *Modules and code*, *Products and
platforms*, *Business vocabulary*, *Auth, config and infrastructure*, *Shorthand designations* is a
set that has worked. Then write one gotchas file per partition that earned one, plus the shared
file; a partition with no admitted finding gets no file.

Resolve every `defer` from Step 3 here: it becomes a `GAP` line carrying its question, or it is
dropped with the reason recorded for the handover.

**Numbers, one contract for both documents.** Sections are `## N`, entries `N.M`, numbered per file.
An entry keeps its number for life: new entries append within their section, and one that no longer
holds keeps its number and moves to `## Retired` at the foot with one line saying what replaced it.
A reused number rewrites every citation that pointed at the old one. Cite a glossary entry by
designation and number — "connector (1.3)"; cite a trap by file and number — "the swallowed dispatch
(GOTCHAS-oms 4.2)".

Completion: every admitted concept has an entry, row or set member, and every admitted trap a
numbered entry with a `Do:`; every glossary field has been put to its own test and the result
recorded field by field rather than asserted in aggregate; every deferred candidate is a `GAP` line
or dropped with its reason recorded; the glossary was closed before the first gotchas file was
opened; in refresh mode every pre-existing number in every document still means what it meant.

## Step 5 — Gate

```bash
python3 <this skill>/scripts/resolve.py <target>/GLOSSARY.md <target>/GOTCHAS-*.md
```

The script sits beside this file and the documents sit in the target repo, so resolve both paths
before running. The glossary is the first argument; every gotchas file follows it. Its module
docstring states what it resolves — designations, citations and aliases across every document, and
nothing visible inside a single entry.

In refresh mode pass the previous revision of every document, paired positionally:

```bash
python3 <this skill>/scripts/resolve.py GLOSSARY.md GOTCHAS-oms.md \
  --against <pre-refresh GLOSSARY.md> --against <pre-refresh GOTCHAS-oms.md>
```

Every finding is an unresolved reference, so every finding is a fix — nothing here to argue with and
no warning tier to triage.

Completion: the resolver exits 0, run over every document written and with one `--against` per
document in refresh mode; its output recorded.

## Step 6 — Hand over

Report, in this order:

1. **Drift** — each prose sentence the code contradicted, with both citations. The run's most
   valuable output.
2. **Counts** — entries and sections per document, split into new, changed and untouched.
3. **Asked a human** — every question the code could not answer, with what was tried first. These
   became shape-6 entries, and they are why a second run beats the first.
4. **Could not resolve** — walked and still unknown, written as questions.
5. **GAPs** — every unsettled glossary characteristic, written as a question someone can answer.
6. **Rejects worth arguing about** — candidates a reader expects to find, naming the test each
   failed.

Then offer the pointer, because a document nothing loads is a document nothing reads:

```markdown
## Read before acting
- `GLOSSARY.md` — read before using or interpreting any project term. Cite by designation and
  number — "connector (1.3)". The file is the source; memory is not.
- `GOTCHAS-<partition>.md` — read before changing a flow in that partition, and
  `GOTCHAS-shared.md` before changing anything. Cite by file and number.
```

Add `@GLOSSARY.md` beneath it only for a glossary of roughly a thousand tokens or less, where paying
it on every turn and every sub-agent dispatch beats one read. Gotchas files are read at the moment a
flow is touched. Report each file's size so the user can make that call.

Completion: all six report sections delivered; every document's size reported; the pointer offered,
and written into `CLAUDE.md` or `AGENTS.md` on the user's word.
