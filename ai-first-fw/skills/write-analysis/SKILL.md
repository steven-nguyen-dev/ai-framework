---
name: write-analysis
description: Write the mapping spec, requirements spec and ticket summary for one requirement, from its Jira ticket or brief, every party's API documentation, and the repository it runs in.
version: 0.1.0
disable-model-invocation: true
---

# write-analysis

Three documents for one requirement, in this order, into `<repo-root>/.scratchpads/<slug>/`. Slug:
the Jira key lowercased, or a kebab-case name from the brief.

| # | Output | Template |
|---|---|---|
| 1 | `<slug>-mapping-spec.md` | `templates/integration-mapping-spec-template.md` |
| 2 | `<target-system>-<slug>-requirements-spec.md` | `templates/system-requirements-spec-template.md` |
| 3 | `<slug>-summary.md` | `templates/ticket-summary-template.md` |

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
