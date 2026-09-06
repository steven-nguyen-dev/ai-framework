---
name: write-analysis
description: Write the four-document contract — claim library, mapping spec, requirements spec and summary — that implementation follows for one requirement, from its Jira issue or brief, every party's documentation, and the repository's own code and context files. Use on "write the analysis", "analyse this ticket", "write the mapping spec", "write the requirements spec", "write the definition of done", "amend the contract", or when a requirement needs its contract before implementation.
version: 1.2.0
disable-model-invocation: false
---

# write-analysis

Four documents for one requirement, into the repository's analysis folder. Together they are the
**contract**: implementation builds what the contract states, and the work is done when the
contract's definition of done holds.

| # | Output | Template | States |
|---|---|---|---|
| 0 | `<KEY>-<topic>-library.md` | `templates/claim-library-template.md` | Where every claim comes from |
| 1 | `<KEY>-<topic>-mapping-spec.md` | `templates/integration-mapping-spec-template.md` | Per endpoint, how each property transforms and why |
| 2 | `<KEY>-<target-system>-<topic>-requirements-spec.md` | `templates/system-requirements-spec-template.md` | Per endpoint, what the receiving system changes, and what holds once it is built |
| 3 | `<KEY>-<topic>-summary.md` | `templates/ticket-summary-template.md` | What logic changes, and the definition of done |

Every line of the contract states what holds when the work is done. The summary carries the
definition of done for all four; each spec carries the acceptance lines the summary cites. Each
template carries its own writing rules and deletes them on publication, and the claim library states
the citation rule the other three follow.

`references/contract-tiers.md` carries the tier test, the order the work moves in, the evidence
order between code and documents, and what reaches the preconditions table.

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

## Step 3 — Write the mapping spec

Open with the wire identity: the family, the routing key, the identity scope, the direction and the
stream derivation, each in the word the context files give. Then one section per endpoint that
carries data, in the order the flow calls them. Under each, one row per property: the source path,
the target property, the transformation, and one clause saying why the target property needs that
value.

**Completion:** every wire-identity row carries a value and an `L-n`, every property the requirement
names sits under the endpoint that carries it, and every row holds a transformation, a reason of one
clause, and an `L-n`.

## Step 4 — Write the requirements spec

The same endpoints, in the same order, read from the receiving system's side. Under each, one row
per property with its change status: `ADD`, `UPDATE`, `REMOVE` or `REUSE`, settled against that
system's data model. Each endpoint carries its own payload diff. Close with the acceptance lines:
each states what holds on that system once the work is built, and carries an `A-n`.

**Completion:** every mapping-spec row appears here under exactly one endpoint with exactly one
change status, every `ADD` and `UPDATE` row names what the receiving team builds, and every change
row is covered by an `A-n`.

## Step 5 — Write the summary

Conclusions, at the level a reader settles scope from. Group the changes by the team that builds it,
then by endpoint, flow or domain inside each team, using the same units in the same order the
mapping spec and the requirements spec use. Every item starts with a verb and names the system it
lands in; each team section carries its tier. An `integration` or `internal` gap is an item this
codebase builds, and the `internal` item names the item on this side that is reachable first. An
`external` limit is a precondition.

**Completion:** every changes item sits under one team and one endpoint, flow or domain, in the
order the specs use; every item starts with a verb, names its system, carries an `L-n`, and states a
conclusion the specs hold the rows for; every team section carries its tier; every `internal` item
names the item on this side that precedes it; every precondition row names an `external` limit or a
decision a named person settles.

## Step 6 — Write the definition of done

The summary's definition-of-done table. One `D-n` per item of the requirement's stated definition of
done, in the requirement's words, cited to its library row. Add a `D-n` for each state this analysis
settles that the requirement leaves unstated. Every row carries its tier and names where it is
checked: an `A-n` of the requirements spec, a section of the mapping spec, or a test the repository
holds.

Two rows stand in every contract: this side's surface is callable and documented, and every flow the
mapping spec names runs end to end against the repository's mocks.

**Completion:** every item of the stated definition of done carries a `D-n` in the requirement's
words with its `L-n`, every `D-n` carries a tier and names what checks it, and the reachable-surface
and mock-run rows are present.

## Step 7 — Self-check

Every bar line binds every instance. For each, write two counts: instances in the documents, and
instances that satisfy it. Where the counts differ, edit the instances the gap names and count
again.

**Completion:** every bar line carries two equal counts, and each template's writing-rules block is
deleted.

## Amending the contract

Implementation reads the contract and finds it wrong: edit the contract, at the row, line or `D-n`
the finding lands on, so it states what holds now.

- Keep every `L-n`, `A-n`, `C-n`, `CR-n`, `D-n` and `P-n`. A superseded claim keeps its number, and
  its library row is written over with the claim, locator and quote that hold now — the row states
  the current fact and its source, and the chat carries what changed.
- Where the code states one thing and a `doc` or `url` row another, the code's locator and words go
  into that row, and the contract is edited to match the code.
- Where the finding changes what done means, edit the `D-n` it lands on and the `A-n` that checks it.
- Where an `integration` or `internal` gap sits in the preconditions table, move it into the changes
  section as the item this codebase builds, with the `D-n` that closes it.
- Hand back the list of edited identifiers, in chat.

The published contract states one thing: what holds now.

## Naming

- `<KEY>` — the requirement's own key, in the case its tracker writes it. With no tracker, use a
  kebab-case name from the brief in every slot `<KEY>` fills, the folder included.
- `<topic>` — two to four lower-kebab-case words naming *that document's* subject. The mapping spec
  and the requirements spec often carry different subjects. The summary carries the requirement's
  own subject, and the library carries the summary's, because the library covers all three.
- `<target-system>` — the receiving system the requirements spec is written against, in the word the
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

**Definition of done**

- Every item of the requirement's stated definition of done carries a `D-n` row in the requirement's
  own words, with the `L-n` that resolves it.
- Every `D-n` names what checks it: an `A-n`, a spec section, or a test path.
- A `D-n` states this side's surface is callable and documented, and a `D-n` states every flow the
  mapping spec names runs end to end against the repository's mocks.
- Every precondition row names an `external` limit, or a decision a named person settles.

**Citation**

- Every claim in the three documents carries an `L-n`, and every `L-n` resolves to a library row
  whose locator matches the form its kind states.
- Every claim about this codebase's behaviour carries kind `code`. Every claim about a party outside
  the organisation carries kind `url` or `doc`, citing that party's own published page.
- Every `Used in` cell resolves to a `##` section that exists in the document it names.
- Every requirement in the documents restates a line of the requirement material.

**Claim library**

- The document opens on its metadata block and runs to section 1, and every word in it sits in a
  table row.
- Every row carries one atomic fact: one declarative sentence of 25 words or fewer.
- Every `Locator` names exactly one target, in the form its kind states. A fact resting on two places
  carries two rows.
- Every `Says` carries the source's own words inside quotes, 25 words or fewer. An absence carries
  `0 occurrences of [term]`.
- Every row states the claim, locator and quote that hold now.

**Vocabulary**

- Every system, party, key and wire field appears in the word the context files give, and each one
  names the context file that owns a term two files share.
- Every term the context files mark as a collision carries the sense this contract uses.

**Mapping spec**

- Every wire-identity row carries its value and its `L-n`.
- Every section is headed by one endpoint, and every property row sits under the endpoint that
  carries it.
- Every row holds a transformation and a reason of one clause naming why the target property needs
  that value.

**Requirements spec**

- Every section is headed by one endpoint or flow, and carries its change rows and its payload diff
  together.
- Every payload diff is fenced `jsonc`, holds the endpoint's whole request body, and carries one
  trailing comment per line: a status, and for `ADD` and `UPDATE` an `L-n` and one clause.
- Every mapping row appears under exactly one status, settled against the receiving system's data
  model.
- Every `ADD` and `UPDATE` row states what the receiving team builds, in that team's own terms.
- Every acceptance line states a condition that holds once the work is built, and names the rows it
  covers.

**Summary**

- Every changes item starts with a verb and names the system it lands in.
- Every changes item sits under one team, then under one endpoint, flow or domain; every team
  section carries its tier.
- Every inner group is headed by the same unit, in the same order, that the mapping spec and the
  requirements spec use.
- The summary states conclusions and points to the specs for detail.

