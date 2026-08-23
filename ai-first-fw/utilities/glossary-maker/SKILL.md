---
name: glossary-maker
description: Harvest a repository once and write two documents — GLOSSARY.md, its terminology in ISO 704:2022 form, and a GOTCHAS file per partition, the behaviours no single file states.
disable-model-invocation: true
version: 0.7.1
---

# glossary-maker

One harvest of a repository, two documents.

| Output | Carries | Found by |
|---|---|---|
| `GLOSSARY.md` | what a designation means here | reading what is **declared** |
| `GOTCHAS-<partition>.md` | what no single file states | **reasoning** over what the harvest read |

The six steps are a floor: add lanes, passes and shards where the target warrants them.

**Drift** holds across every step: where code, config or a manifest contradicts a prose claim, the
entry follows the code and the contradiction ships as drift with both citations.

## Step 1 — Frame

1. **Target** — the repo, or the module the user named. A monorepo with no named target costs one
   question.
2. **Mode** — `GLOSSARY.md` at the repo root means refresh, its absence create. The glossary sets the
   mode; gotchas files follow it.
3. **Formats** — open [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md) and
   [GOTCHAS-FORMAT.md](./GOTCHAS-FORMAT.md) now, before the harvest.
4. **Corpus** — an include list and an exclude list. Generated documentation renders source: read the
   source it renders.
5. **Partition** — take the target's own term for it: area, service, bounded context, package root.
   One gotchas file per partition that earns one, plus `GOTCHAS-shared.md`.
6. **Refresh only** — read every existing document in full before any harvest and set an untouched
   copy of each aside. Their numbers are live citations.

Completion: target, mode, both path lists and the partition's source named, both format files read;
in refresh mode every existing headword and trap listed with its number, and a pre-refresh copy of each document aside.

## Step 2 — Harvest

**Load the corpus once and run every lane over it as a pass.** A lane is a question asked of a load:
each corpus is read a single time and every lane it can answer runs against that one read. Each lane
is stated by what it is — derive the search patterns from the stack you find.

Take the loads in this order: **source** — everything compiled or interpreted; **manifest** — build
graph, property and settings files, environment bindings, directory tree; **prose** — `*.md`, HLDs,
ADRs, handover notes, README, wiki exports.

The lanes, each with the yield a reader misses:

- **Closed value set** — enumerated types, symbolic constants, annotation or attribute types. The
  *values* are designations, not only the type.
- **Configuration key** — property and settings files, environment bindings, injected values, flags.
  The manifest declares the key, the source reads it, and a key whose letters lie about what it holds
  is visible only with both halves in hand: settle this lane after both loads.
- **Deployable boundary** — build-graph members, root directories, package roots, service names.
  Suffix conventions, and directories no build graph lists.
- **Wire name** — topics, queues, path prefixes, tables, columns, headers. Cross-team shorthand
  prose never carries.
- **In-place explanation** — doc comments, `TODO` / `NOTE` / `XXX`. The term a developer stopped to
  explain in place.
- **Prose** — business vocabulary carrying no identifier.

Record one line per candidate: designation or trap, its lane, evidence as `file:line` or
`file · Class.method`, and any drift met, cited on both sides.

**Traps come from reasoning, not a lane.** A trap is a contradiction between two or more separate
places, each of which reads correctly on its own — which is why no search finds one, and why a reader
who opens the class still misses it. **Take a partition whole**: a contradiction between two of its
entries is invisible from either one. Where a human had to settle it, record what you tried before
asking, because the next reader stops in the same place; where nobody can answer, it is a `GAP` and
ships as a question.

**Collision pass, last, over the candidates in hand. Four collisions:**

- one designation, two referents — the same word declared in unrelated packages, or naming a module
  in one document and a team in another
- two designations, one referent — synonyms in circulation, of which one wins
- an abbreviation expanded two ways, or expanded nowhere on disk
- identifiers one edit apart where both are live (`nexusPath` beside `nexxusPath`) — a misspelling
  the code reads is a designation

**Sharding.** Where a load or a partition exceeds one context, split by directory and dispatch one
sub-agent per shard, each running every lane its shard can answer and returning candidate lines only. Record the boundaries: a finding whose halves came back from two
shards is settled after the shards return, on the collision pass's terms.

Completion: every designation candidate carries its lane and at least one citation, and every trap
candidate a citation for each of the places whose contradiction produced it; every lane has reported
its drift lane by lane, naming none where it found none; the configuration key settled against both
loads; every question put to a human logged with what was tried first; the collision pass has
reported on all four collisions, naming any it found absent; every shard boundary recorded and every
cross-shard finding settled.

## Step 3 — Admit

Two tests, run separately. These are the authority; each format file restates its own for that document's reader.

**Glossary — collision.** Admit a designation where a reader meeting it cold, or carrying its sense
from another project, lands on the wrong code. Never for importance: general programming vocabulary
stays out however heavily the project uses it.

| Verdict | When |
|---|---|
| `admit` | the designation collides |
| `reject` | opening the class settles it, or it carries its ordinary meaning |
| `defer` | admission turns on a fact no source settles — carries the question |

**Gotcha — surprise, search, cost.** All three, or it is a `reject` naming the test it failed.

- **Surprise** — a competent reader reaches the wrong conclusion, or none. If opening the file
  settles it, it is not this.
- **Search** — it names a behaviour. A thing search finds is a glossary entry.
- **Cost** — a wrong conclusion, or time.

**Routing:**

| Finding | Goes to |
|---|---|
| a designation that collides | the glossary |
| evidence inside one partition | that partition's gotchas file |
| evidence in two or more partitions, or under all of them | `GOTCHAS-shared.md`, as one finding with its exceptions |
| both a word and a behaviour | both — the glossary carries the definition, the gotcha the `Do:` |

Completion: every candidate carries a verdict, its deciding reason and its destination; every `defer`
carries a question; every gotcha `reject` names the test it failed; every both-files finding appears
once per file.

## Step 4 — Write

**Close the glossary before opening the first gotchas file** — gotchas cite glossary terms and each
alias table extends the glossary's shorthand section; written concurrently they disagree.

Number and cite by the contract in [AUDIT-BRIEF.md](./AUDIT-BRIEF.md). Section the glossary by the
rule in [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md). Write one gotchas file per partition that earned
one, plus the shared file; a partition with no admitted finding gets no file.

Resolve every `defer` from Step 3 here: it becomes a `GAP` line carrying its question, or it is
dropped with the reason recorded for the handover.

Completion: every admitted concept has an entry, row or set member, and every admitted trap a
numbered entry with a `Do:`; every `defer` is a `GAP` line or a recorded drop; the glossary was closed
before the first gotchas file was opened; in refresh mode every pre-existing number in every document
still means what it meant.

## Step 5 — Gate

The script resolves across documents, a reader judges inside entries — in that order.

### 5a — Resolve

```bash
python3 <this skill>/scripts/resolve.py <target>/GLOSSARY.md <target>/GOTCHAS-*.md
```

Glossary first, gotchas files after. In refresh mode add one `--against <pre-refresh document>` per
document, paired positionally. Clear every finding before 5b.

### 5b — Judge

**Dispatch one sub-agent over the written documents**, with [AUDIT-BRIEF.md](./AUDIT-BRIEF.md) as its
instructions. Its grant is exactly four things — the documents, both format files, and `AUDIT-BRIEF.md`:
**no target repo and no access to this file**, withheld as tools rather than as instruction. One agent
for every document together, since consistency across them is part of the subject.

Apply its `fix` findings, settle every `cannot judge without the code` yourself, then re-run 5a.

Completion: 5a exits 0 over every document written, with one `--against` per document in refresh
mode; a verdict returned for every entry in every document; every `fix` applied and every `cannot
judge without the code` settled by the author; 5a re-run clean after the fixes; both outputs
recorded.

## Step 6 — Hand over

Report, in this order:

1. **Drift** — each prose sentence the code contradicted, with both citations.
2. **Counts** — entries and sections per document: new, changed, untouched.
3. **Asked a human** — every question the code could not answer, with what was tried first.
4. **GAPs** — every question left unanswered, glossary characteristic and behaviour alike.
5. **Rejects worth arguing about** — candidates a reader expects to find, naming the test each failed.

Then offer the pointer:

```markdown
## Read before acting
- `GLOSSARY.md` — read before using or interpreting any project term. Cite by designation and
  number — "<designation> (1.3)". The file is the source; memory is not.
- `GOTCHAS-<partition>.md` — read before changing that partition, and `GOTCHAS-shared.md` before
  changing anything. Cite by file and number.
```

Report each file's size. Add `@GLOSSARY.md` beneath the pointer only for a glossary of roughly a
thousand tokens or less, where paying it on every turn and every sub-agent dispatch beats one read.

Completion: all five report sections delivered; every document's size reported; the pointer offered,
and written into `CLAUDE.md` or `AGENTS.md` on the user's word.
