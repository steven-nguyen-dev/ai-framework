---
name: write-analysis
description: Write the mapping spec, requirements spec and ticket summary for one requirement, from its Jira ticket or brief, every party's API documentation, and the repository it runs in.
version: 0.2.0
disable-model-invocation: true
---

# write-analysis

Three documents for one requirement, in this order, into `<repo-root>/.scratchpads/<KEY>/`.

| # | Output | Template |
|---|---|---|
| 1 | `<KEY>-<topic>-mapping-spec.md` | `templates/integration-mapping-spec-template.md` |
| 2 | `<KEY>-<target-system>-<topic>-requirements-spec.md` | `templates/system-requirements-spec-template.md` |
| 3 | `<KEY>-<topic>-summary.md` | `templates/ticket-summary-template.md` |

## Naming

- `<KEY>` — the Jira key in the case Jira writes it, `IA-5109`. No ticket, a kebab-case name from
  the brief in its place, in every slot `<KEY>` fills including the folder.
- `<topic>` — two to four lower-kebab-case words naming *that document's* subject, not the ticket
  title: `product-types`, `amz-oms-cancellation`, `oms-taxonomy`. All three documents carry one —
  the mapping spec's subject and the requirements spec's subject differ often enough to name apart,
  and the summary's is the ticket's own subject, the one thing all three documents are about.
  `IA-5109-product-types-summary.md`.
- `<target-system>` — the internal system the requirements spec is written against, lowercase:
  `oms`, `wms`, `oxm`, `pt`.
- Before writing, list the sibling ticket folders under `.scratchpads/` and read their filenames.
  Where a sibling's convention contradicts the rows above, the sibling wins — one shape per
  repository beats this table. Say which one you followed, and why, in the message that hands the
  documents over.
- Filenames are fixed at creation. Renaming later breaks every cross-reference a sibling ticket
  holds; if the user asks for a rename, grep the repository for the old names first and report the
  count of references before touching anything.

## Inputs

All three in hand before the mapping spec.

- **Requirement** — a Jira key or URL, with its comments and attachments; or a written brief, with
  everything it links.
- **API documentation** — one specification per party the data crosses: the external partner, the
  source channel, each internal target system. Name what you hold for each party, ask for the rest
  in one message.
- **Codebase** — the repository this runs inside. Started outside one, ask the user to start again
  from inside the repository the change lands in.

## The bar

- Every claim carries its source, in the form its template states.
- Every requirement in the documents restates a line of the requirement material.
- Every mapping row appears in the requirements spec under exactly one status, settled against the
  target system's data model.
