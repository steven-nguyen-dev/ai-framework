---
name: write-analysis
description: Write the claim library, mapping spec, requirements spec and ticket summary that form the contract implementation follows for one requirement, from its Jira ticket or brief, every party's API documentation, and the repository it runs in. Use on "write the analysis", "analyse this ticket", "write the mapping spec", "write the requirements spec", "amend the contract", or when a Jira ticket or brief needs its analysis documents before implementation.
version: 0.7.0
disable-model-invocation: false
---

# write-analysis

Four documents for one requirement, into `<repo-root>/.scratchpads/<KEY>/`. Together they are the
**contract**: implementation builds what they state, and is done when the summary's definition of
done holds.

| # | Output | Template | States |
|---|---|---|---|
| 0 | `<KEY>-<topic>-library.md` | `templates/claim-library-template.md` | Where every claim comes from |
| 1 | `<KEY>-<topic>-mapping-spec.md` | `templates/integration-mapping-spec-template.md` | Per endpoint, how each property transforms and why |
| 2 | `<KEY>-<target-system>-<topic>-requirements-spec.md` | `templates/system-requirements-spec-template.md` | Per endpoint, what the target system changes, and what holds when it is built |
| 3 | `<KEY>-<topic>-summary.md` | `templates/ticket-summary-template.md` | At a high level, what logic changes, and the definition of done |

Every line of the contract states what holds when the work is done. The summary carries the
definition of done for all four; each spec carries the acceptance lines the summary cites.

The endpoint is the unit of grouping in documents 1 and 2. Systems here meet over REST, so a change
lands on an endpoint, and the reader arrives holding one.

Each template carries its own writing rules and deletes them on publication. The claim library
states the citation rule the other three follow.

## Steps

### 1. Gather the inputs

- **Requirement** — a Jira key or URL with its comments and attachments, or a written brief with
  everything it links. Capture its definition of done verbatim, one library row per item.
- **API documentation** — one specification per party the data crosses: the external partner, the
  source channel, each internal target system. Name what you hold for each party, and ask for the
  rest in one message.
- **Codebase** — the repository this change lands in. Started outside one, ask the user to start
  again from inside it.

**Completion:** every party is named with the specification held for it, the repository root and
commit are written down, and every definition-of-done item the requirement states sits in the
library in the requirement's own words.

### 2. Open the library

Copy `templates/claim-library-template.md` to `<KEY>-<topic>-library.md` and fill its keys table.
Append to it as you gather, through every step below.

**Completion:** the library exists at its path, and every long path the work uses has a key.

### 3. Write the mapping spec

One section per endpoint that carries data, in the order the flow calls them. Under each, one row
per property: the source path, the target property, the transformation, and one clause saying why
the target property needs that value.

**Completion:** every property the requirement names sits under the endpoint that carries it, and
every row holds a transformation, a reason of one clause, and an `L-n`.

### 4. Write the requirements spec

The same endpoints, in the same order, read from the target system's side. Under each, one row per
property with its change status: `ADD`, `UPDATE`, `REMOVE` or `REUSE`, settled against that system's
data model. Each endpoint carries its own payload diff. Close with the acceptance lines: each states
what holds on this system when the work is built, and carries an `A-n`.

**Completion:** every mapping-spec row appears here under exactly one endpoint with exactly one
change status, every `ADD` and `UPDATE` row names what the receiving team builds, and every §2 and
§3 row is covered by an `A-n`.

### 5. Write the summary

Conclusions, at the level a reader decides scope from. Every item starts with a verb and names the
system it lands in.

**Completion:** every item in the changes section starts with a verb, names its system, carries an
`L-n`, and states a conclusion the specs hold the rows for.

### 6. Write the definition of done

The summary's §3 table. One `D-n` row per item of the requirement's own definition of done, in the
requirement's words, cited to its library row. Add a `D-n` for each thing this analysis settles that
the requirement leaves unstated. Every row names where it is checked: an `A-n` of the requirements
spec, a section of the mapping spec, or a test the repository holds.

**Completion:** every definition-of-done item the requirement states carries a `D-n` in the
requirement's words with its `L-n`, and every `D-n` names the acceptance line or section that checks
it.

### 7. Self-check

Every bar line binds every instance. For each, write two counts: instances in the document, and
instances that satisfy it. Where the counts differ, fix the instances the gap names and count again.

**Completion:** every bar line carries two equal counts, and each template's writing-rules block is
deleted.

## Amending the contract

Implementation reads the contract and finds it wrong: edit the contract, at the row, line or `D-n`
the finding lands on, so it states what holds now.

- Keep every `L-n`, `A-n`, `C-n`, `CR-n` and `D-n` number. A superseded claim keeps its number, and
  its library row carries the locator and words that hold now.
- Where the finding changes what done means, edit the `D-n` it lands on, and the `A-n` that checks
  it.
- Hand back the list of edited identifiers, in chat.

The published contract states one thing: what holds now.

## Naming

- `<KEY>` — the Jira key in the case Jira writes it, `IA-5109`. With no ticket, use a kebab-case
  name from the brief in every slot `<KEY>` fills, the folder included.
- `<topic>` — two to four lower-kebab-case words naming *that document's* subject:
  `product-types`, `amz-oms-cancellation`, `oms-taxonomy`. The mapping spec and the requirements
  spec often carry different subjects. The summary carries the ticket's own subject, and the library
  carries the summary's, because the library covers all three.
- `<target-system>` — the internal system the requirements spec is written against, lowercase:
  `oms`, `wms`, `oxm`, `pt`.
- Before writing, list the sibling ticket folders under `.scratchpads/` and read their filenames.
  Where a sibling's convention differs from the rows above, follow the sibling — one shape per
  repository beats this table. Say which convention you followed, and why, when you hand the
  documents over.
- Filenames are fixed at creation. On a rename request, grep the repository for the old names and
  report the count of references first.

## The bar

**Citation**

- Every claim in the three documents carries an `L-n`, and every `L-n` resolves to a library row
  whose locator matches the form its kind states.
- An absence carries a library row of its own, with the file and the term that returned nothing.
- Every `Used in` cell resolves to a `##` section that exists in the document it names.
- Every requirement in the documents restates a line of the requirement material.

**Mapping spec**

- Every section is headed by one endpoint, and every property row sits under the endpoint that
  carries it.
- Every row holds a transformation and a reason of one clause naming why the target property needs
  that value.

**Requirements spec**

- Every section is headed by one endpoint or flow, and carries its change rows and its payload diff
  together.
- Every payload diff is fenced `jsonc`, holds the endpoint's whole request body, and carries one
  trailing comment per line: a status, and for `ADD` and `UPDATE` an `L-n` and one clause. The
  comments are the note.
- Every mapping row appears under exactly one status, settled against the target system's data
  model.
- Every `ADD` and `UPDATE` row states what the receiving team builds, in that team's own terms.
- Every acceptance line states a condition that holds when the work is built, and names the rows it
  covers.

**Summary**

- Every changes item starts with a verb and names the system it lands in.
- The summary states conclusions and points to the specs for detail.

**Definition of done**

- Every definition-of-done item the requirement states carries a `D-n` row in the requirement's own
  words, with the `L-n` that resolves it.
- Every `D-n` names where it is checked: an `A-n`, a spec section, or a test path.
- Every decision the contract still needs carries a precondition row naming its owner and the
  section it gates.

**Contract**

- Every line states what holds when the work is done, in the present tense.
