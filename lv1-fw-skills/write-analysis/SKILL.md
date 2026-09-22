---
name: write-analysis
description: Write the four-document contract — claim library, mapping, change requests and specs — that implementation follows for one requirement, from its Jira issue or brief, every party's documentation, and the repository's own code and context files. Use on "write the analysis", "analyse this ticket", "write the mapping", "write the change requests", "write the specs", "write the scope", "write the definition of done", "amend the contract", or when a requirement needs its contract before implementation.
version: 2.2.0
disable-model-invocation: false
---

# write-analysis

Four documents for one requirement, into the repository's analysis folder. Together they are the
**contract**: implementation builds what the contract states, and the work is done when the
contract's definition of done holds.

| # | Output | Template | States |
|---|---|---|---|
| 0 | `<KEY>-<topic>-library.md` | `templates/claim-library-template.md` | Where every claim comes from |
| 1 | `<KEY>-<topic>-mapping.md` | `templates/mapping-template.md` | Per endpoint, how each property transforms and why |
| 2 | `<KEY>-<target-system>-<topic>-change-requests.md` | `templates/change-requests-template.md` | Per endpoint, what the receiving system changes, and what holds once it is built |
| 3 | `<KEY>-<topic>-specs.md` | `templates/specs-template.md` | What the work covers, what logic changes, the definition of done, and the notes development starts with |

Every line of the contract states what holds when the work is done. The specs carry the definition
of done for all four, and the mapping and the change requests each carry the acceptance lines the
specs cite. Each template carries its own writing rules and deletes them on publication, and the
claim library states the citation rule the mapping and the specs follow.

The mapping and the change requests carry **one format**: scope, then one section per endpoint
holding a change table and a payload sample, then acceptance. They differ in who reads them, and
that settles the rest.

| | Mapping | Change requests |
|---|---|---|
| Reader | This codebase's implementer | The team that owns the receiving system |
| Travels | With the contract | Alone — this file is what that team receives |
| Payload comment | Every mapped line: the source resource, or the computation, and its `L-n` | The `ADD`, `UPDATE` and `REMOVE` lines: which property of which object of the source payload |
| Citation | `L-n` into the library | None — each comment states its source in words |
| Own sections | Entity alignment, flows, enum translation, uniqueness and ordering | Glossary |

`references/writing-limits.md` reaches the `make-it-short` unit limits and wording rules every
document holds, and carries the column set and the split letter the contract adds on top.
`references/contract-tiers.md` carries the tier test, the order the work moves in,
the evidence order between code and documents, and what reaches the preconditions table.

## Inputs

- **Requirement** — the Jira issue: its description, its comments and its attachments, read through
  the Jira tooling this session offers. This is the first intake of every analysis. A written brief
  with everything it links stands in where the work carries no issue.
- **Stated definition of done** — the requirement's own, captured word for word from wherever the
  requirement states it.
- **Party documentation** — one specification per party the data crosses, held as a file or a URL.
- **Repository** — the codebase this change lands in, at a named commit. Started outside one, ask
  the user to start again from inside it.
- **Context files** — the repository's context file set and the collision rules its map states. Every
  system, party, key and wire field the contract writes takes its word from here.

## Tiers

Every contract a change crosses sits between two systems, and the tier that owns it settles whether
a gap in it is work or a limit.

| Tier | A gap in it is |
|---|---|
| `external` | A limit the contract adapts to |
| `internal` | Work this codebase starts, and tells that team about |
| `integration` | Work this codebase does |

Every change item and every `D-n` carries its tier. `references/contract-tiers.md` settles which
tier a contract falls in.

## Step 1 — Take the intake

Read the Jira issue, its comments and its attachments. Name every party the data crosses, give each
one its tier, and name the specification held for it, asking for the rest in one message. Read every
context file the map names. Write the requirement's own definition of done into the library, one row
per item, in the requirement's words.

**Completion:** every party is named with its tier and its specification, the repository root and
commit are written down, every item of the stated definition of done sits in the library in the
requirement's own words, and every context file the map names is read.

## Step 2 — Open the library

Copy `templates/claim-library-template.md` to `<KEY>-<topic>-library.md` and fill its keys table.
Append to it through every step below, one row per atomic fact, each with one locator and one
verbatim quote.

**Completion:** the library exists at its path, every long path the work uses has a key, and the
document runs from its metadata block to section 1 with every word in a table row.

## Step 3 — Write the mapping

Open with the wire identity: the family, the routing key, the identity scope, the direction and the
stream derivation, each in the word the context files give. Then one section per endpoint that
carries data, in the order the flow calls them. Under each, the change table — source path, target
property, transformation, one clause of reason, `L-n` — then the payload sample, whose every mapped
line names the source resource the value comes from, or the computation that produces it, and its
`L-n`.

**Completion:** every wire-identity row carries a value and an `L-n`, every property the requirement
names sits under the endpoint that carries it, every table row holds a transformation, a reason of
one clause and an `L-n`, and every mapped line of every payload sample names its source resource or
its computation.

## Step 4 — Write the change requests

The same endpoints, in the same order, read from the receiving system's side. Under each, the change
table — property path, type, status of `ADD`, `UPDATE`, `REMOVE` or `REUSE` settled against that
system's data model, persistence impact, requirement — then the payload sample.

Each `ADD`, `UPDATE` and `REMOVE` line carries a comment naming which property of which object of
the source system's payload the value comes from, or what produces it where the source carries none;
a `REUSE` line carries no comment.

Fill the glossary with every term the receiving team does not already hold, close with the
acceptance lines, and write the whole document so it reads with every other document of the contract
absent.

**Completion:** every mapping row appears here under exactly one endpoint with exactly one
change status, every `ADD` and `UPDATE` row names what the receiving team builds, every `ADD`,
`UPDATE` and `REMOVE` line of every payload sample names its source property and the object holding
it, every term the document uses outside the receiving team's own vocabulary sits in the glossary,
every change row is covered by an `A-n`, and the document holds no `L-n` and no reference to another
document of the contract.

## Step 5 — Write the scope

The specs' Scope section, which is the boundary of the work. In scope: one line per flow and per
endpoint the mapping carries, in the mapping's order, each naming that flow or endpoint. Out of
scope: one line per subject the requirement raises that this contract does not carry, each naming
the requirement, document or team that carries it instead, or stating that none does.

A line whose boundary comes from the requirement rather than the mapping carries its `L-n`.

**Completion:** every flow and every endpoint of the mapping appears in one in-scope line naming it;
every subject the requirement raises that no mapping row, change request row or precondition covers
appears in one out-of-scope line naming where it lives instead or that no document carries it; and
every line whose boundary comes from the requirement carries an `L-n`.

## Step 6 — Write the specs

Conclusions, at the level a reader settles the work from. Group the changes by the team that builds
it, then by endpoint, flow or domain inside each team, using the same units in the same order the
mapping and the change requests use. Every item starts with a verb and names the system it lands in;
each team section carries its tier.

An `integration` or `internal` gap is an item this codebase builds, and the `internal` item names
the item on this side that is reachable first. An `external` limit is a precondition.

**Completion:** every changes item sits under one team and one endpoint, flow or domain, in the
order the specs use; every item starts with a verb, names its system, carries an `L-n`, and states a
conclusion the specs hold the rows for; every team section carries its tier; every `internal` item
names the item on this side that precedes it; every precondition row names an `external` limit or a
decision a named person settles.

## Step 7 — Draw the flows

The specs' Flows section. One Mermaid `sequenceDiagram` per flow of the mapping, in the mapping's
order, under that flow's name and trigger. Give every participant a component a reader names, and
hold each diagram inside the participant limit `references/writing-limits.md` states, by the moves
that file gives. Label every message with the operation the mapping names for that hop. The
`draw-diagram` skill holds the palette and the sequence recipe, and parses each block.

**Completion:** every flow of the mapping carries one diagram in the specs, every diagram parses and
holds its participant count at or under the limit, every participant is a component named in the
mapping or the change requests, every message carries the mapping's own operation for that hop, and
every grouped boundary names what it holds.

## Step 8 — Write the definition of done

The specs' definition-of-done table. One `D-n` per item of the requirement's stated definition of
done, in the requirement's words, cited to its library row. Add a `D-n` for each state this analysis
settles that the requirement leaves unstated. Every row carries its tier and names where it is
checked: an `A-n` of the mapping or the change requests, or a test the repository holds.

Two rows stand in every contract: this side's surface is callable and documented, and every flow the
mapping names runs end to end against the repository's mocks.

**Completion:** every item of the stated definition of done carries a `D-n` in the requirement's
words with its `L-n`, every `D-n` carries a tier and names what checks it, and the reachable-surface
and mock-run rows are present.

## Step 9 — Write the notes

The specs' Notes section, which is what development starts holding. One `N-n` per open question
this analysis reached and could not close, per gap in the material it looked for and did not find,
and per assumption it took as true to write a row. Each note names its kind, the section it gates,
and who or what settles it. Where a mapping row waits on a note, the mapping's own notes section
names the `N-n`.

**Completion:** every question this analysis left open, every gap in the material, and every
assumption behind a row carries an `N-n` with its kind, the section it gates and what settles it;
every mapping row waiting on a decision names its `N-n`; and every note that blocks the start
of development also carries a precondition row.

## Step 10 — Self-check

Every bar line binds every instance. For each, write two counts: instances in the documents, and
instances that satisfy it. Where the counts differ, edit the instances the gap names and count
again.

**Completion:** every bar line carries two equal counts, and each template's writing-rules block is
deleted.

## Amending the contract

Implementation reads the contract and finds it wrong: edit the contract, at the row, line or `D-n`
the finding lands on, so it states what holds now.

- Keep every `L-n`, `A-n`, `C-n`, `CR-n`, `D-n`, `N-n` and `P-n`. A superseded claim keeps its
  number, and its library row is written over with the claim, locator and quote that hold now — the
  row states the current fact and its source, and the chat carries what changed.
- Where the code states one thing and a `doc` or `url` row another, the code's locator and words go
  into that row, and the contract is edited to match the code.
- Where the finding changes what done means, edit the `D-n` it lands on and the `A-n` that checks it.
- Where an `integration` or `internal` gap sits in the preconditions table, move it into the changes
  section as the item this codebase builds, with the `D-n` that closes it.
- Where a note is answered, fold the answer into the section it gates and write `settled — [the
  answer]` in its row.
- Hand back the list of edited identifiers, in chat. Where the edit lands in the change requests,
  say so, because that document has already travelled to the receiving team.

The published contract states one thing: what holds now.

## Naming

- `<KEY>` — the requirement's own key, in the case its tracker writes it. With no tracker, use a
  kebab-case name from the brief in every slot `<KEY>` fills, the folder included.
- `<topic>` — two to four lower-kebab-case words naming *that document's* subject. The mapping and
  the change requests often carry different subjects. The specs carry the requirement's own subject,
  and the library carries the specs', because the library covers the rest.
- `<target-system>` — the receiving system the change requests are written against, in the word the
  context files give, lowercase.
- Before writing, list the sibling folders in the repository's analysis folder and read their
  filenames. Where a sibling's convention differs from the rows above, follow the sibling — one
  shape per repository beats this table. Say which convention you followed, and why, when you hand
  the documents over.
- Filenames are fixed at creation. On a rename request, grep the repository for the old names and
  report the count of references first.

## The bar

**Contract**

- Every line states what holds when the work is done, in the present tense.
- Every change item and every `D-n` carries one of `external`, `internal` or `integration`.
- Every `internal` item names the item on this side that is reachable before it.

**Writing limits**

- Every unit holds the limit the `make-it-short` unit table states for it, counted against the
  published document, and every sentence holds that skill's wording rules.
- Every bullet list that passed its limit carries its items in groups with a heading each, or in a
  table.

**Definition of done**

- Every item of the requirement's stated definition of done carries a `D-n` row in the requirement's
  own words, with the `L-n` that resolves it.
- Every `D-n` names what checks it: an `A-n`, a mapping section, or a test path.
- A `D-n` states this side's surface is callable and documented, and a `D-n` states every flow the
  mapping names runs end to end against the repository's mocks.
- Every precondition row names an `external` limit, or a decision a named person settles.

**Notes**

- Every open question, gap and assumption this analysis carries holds an `N-n` with its kind, the
  section it gates and what settles it.
- Every mapping row that waits on a decision names the `N-n` that holds it.
- Every note that blocks the start of development also holds a precondition row.

**Citation**

- Every claim in the mapping and the specs carries an `L-n`, and every `L-n` resolves to a
  library row whose locator matches the form its kind states.
- Every claim about this codebase's behaviour carries kind `code`. Every claim about a party outside
  the organisation carries kind `url` or `doc`, citing that party's own published page.
- Every `Used in` cell resolves to a `##` section that exists in the document it names.
- Every requirement in the documents restates a line of the requirement material.

**Claim library**

- The document opens on its metadata block and runs to section 1, and every word in it sits in a
  table row.
- Every row carries one atomic fact, as one declarative sentence.
- Every `Locator` names exactly one target, in the form its kind states. A fact resting on two places
  carries two rows.
- Every `Says` carries the source's own words inside quotes. An absence carries
  `0 occurrences of [term]`.
- Every row states the claim, locator and quote that hold now.

**Vocabulary**

- Every system, party, key and wire field appears in the word the context files give, and each one
  names the context file that owns a term two files share.
- Every term the context files mark as a collision carries the sense this contract uses.

**Mapping and change requests**

- Every section is headed by one endpoint or flow, and carries its change table and its payload
  sample together.
- Every payload sample is fenced `jsonc`, holds the endpoint's whole body, and aligns its trailing
  comments on one column.
- Every property row sits under the endpoint that carries it.

**Mapping**

- Every wire-identity row carries its value and its `L-n`.
- Every table row holds a transformation and a reason of one clause naming why the target property
  needs that value.
- Every mapped line of every payload sample names the source resource the value comes from, or the
  computation that produces it, and carries its `L-n`.
- Every enum, uniqueness and ordering rule sits in the section that owns it, and the row that points
  at it names that section.

**Change requests**

- Every mapping row appears under exactly one status, settled against the receiving system's data
  model.
- Every `ADD` and `UPDATE` row states what the receiving team builds, in that team's own terms.
- Every `ADD`, `UPDATE` and `REMOVE` line of every payload sample names which property of which
  object of the source payload the value comes from, or what produces it; every `REUSE` line carries
  no comment.
- Every term the document uses outside the receiving team's own vocabulary sits in the glossary.
- The document holds no `L-n` and no reference to another document of the contract, and reads
  complete with every other document absent.
- Every acceptance line states a condition that holds once the work is built, and names the rows it
  covers.

**Specs**

- Every flow and every endpoint of the mapping carries one in-scope line naming it.
- Every out-of-scope line names the requirement, document or team that carries its subject instead,
  or states that no document carries it.
- Every changes item starts with a verb and names the system it lands in.
- Every changes item sits under one team, then under one endpoint, flow or domain; every team
  section carries its tier.
- Every inner group is headed by the same unit, in the same order, that the mapping and the change
  requests use.
- Every flow of the mapping carries one `sequenceDiagram` in the specs, in the mapping's order,
  within the participant limit, each participant a named component.
- Every message of every diagram carries the operation the mapping names for that hop, and every
  grouped boundary names what it holds.
- The specs state conclusions and point to the mapping and the change requests for detail.
