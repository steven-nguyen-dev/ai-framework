---
name: write-analysis
description: Write the claim library, mapping spec, requirements spec and ticket summary for one requirement, from its Jira ticket or brief, every party's API documentation, and the repository it runs in.
version: 0.4.0
disable-model-invocation: true
---

# write-analysis

Four documents for one requirement, into `<repo-root>/.scratchpads/<KEY>/`.

| # | Output | Template | Answers |
|---|---|---|---|
| 0 | `<KEY>-<topic>-library.md` | `templates/claim-library-template.md` | Where every claim comes from |
| 1 | `<KEY>-<topic>-mapping-spec.md` | `templates/integration-mapping-spec-template.md` | Per endpoint, how each property transforms and why |
| 2 | `<KEY>-<target-system>-<topic>-requirements-spec.md` | `templates/system-requirements-spec-template.md` | Per endpoint, what the target system changes |
| 3 | `<KEY>-<topic>-summary.md` | `templates/ticket-summary-template.md` | At a high level, what logic changes |

The endpoint is the unit of grouping in documents 1 and 2. Systems here meet over REST, so a change
lands on an endpoint, and the reader arrives holding one.

Each template carries its own writing rules and deletes them on publication. The claim library
states the citation rule the other three follow.

## Steps

### 1. Gather the inputs

- **Requirement** — a Jira key or URL with its comments and attachments, or a written brief with
  everything it links.
- **API documentation** — one specification per party the data crosses: the external partner, the
  source channel, each internal target system. Name what you hold for each party, and ask for the
  rest in one message.
- **Codebase** — the repository this change lands in. Started outside one, ask the user to start
  again from inside it.

**Completion:** every party is named with the specification held for it, and the repository root and
commit are written down.

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
data model. Each endpoint carries its own payload diff.

**Completion:** every mapping-spec row appears here under exactly one endpoint with exactly one
change status, and every `ADD` and `UPDATE` row names what the receiving team builds.

### 5. Write the summary

Conclusions, at the level a reader decides scope from. Every item starts with a verb and names the
system it lands in.

**Completion:** every item in the changes section starts with a verb, names its system, and carries
an `L-n`; nothing in it restates a mapping row.

### 6. Self-check

Quote the line of each document that satisfies each bar line below.

**Completion:** every bar line is quoted against, and each template's writing-rules block is
deleted.

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
- Every search that returned nothing carries a row in the library's stopped-search register.
- Every requirement in the documents restates a line of the requirement material.

**Mapping spec**

- Every section is headed by one endpoint, and every property row sits under the endpoint that
  carries it.
- Every row holds a transformation and a reason of one clause naming why the target property needs
  that value.

**Requirements spec**

- Every section is headed by one endpoint or flow, and carries its change rows and its payload diff
  together.
- Every mapping row appears under exactly one status, settled against the target system's data
  model.
- Every `ADD` and `UPDATE` row states what the receiving team builds, in that team's own terms.

**Summary**

- Every changes item starts with a verb and names the system it lands in.
- The summary states conclusions and points to the specs for detail.
