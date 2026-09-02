# [TICKET_KEY] Claim Library — [Short Feature Title]

**Document Identifier:** `[JIRA_ISSUE_KEY]-[TOPIC]-library.md` (e.g. `IA-5105-product-types-library.md`)
**Ticket:** `[JIRA_ISSUE_KEY]` — *[Feature / Initiative Title]*
**Covers:** `[JIRA_ISSUE_KEY]-[TOPIC]-mapping-spec.md` · `[JIRA_ISSUE_KEY]-[TARGET_SYSTEM_LOWER]-[TOPIC]-requirements-spec.md` · `[JIRA_ISSUE_KEY]-[TOPIC]-summary.md`
**Repository:** `[repository-name]` @ `[branch]` — commit `[short-sha]`
**Author / Team:** `[Author / Team Name]`
**Last appended:** `[YYYY-MM-DD]`

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **library**. One per ticket. It is opened first and appended to as each of the three
documents is written. Its reader is the next agent session on this ticket: it exists so that session
resolves any claim in any of the three documents to the material behind it, and spends its searches
on ground this session left uncovered.

**The citation rule.** The mapping spec, the requirements spec and the summary follow it. Every
claim in those documents carries an `L-n` that resolves to a row of §3 here. Those documents cite;
this document holds the locator, the quote and the searches that stopped.

**Writing rules.**

- One row per claim. A claim used by two documents keeps one row and one `L-n`.
- `L-n` is permanent. A superseded claim keeps its number and moves to §4 with what replaced it.
- Write the locator so the next session opens the material in one action, with no search:
  a path a file tool reads, a URL a fetch tool loads, a Jira key and field, or a named person.
- `Says` carries the material's own words, quoted, up to about 25 of them. Where a quote does not
  carry it, write the tight paraphrase the next session acts on. Keep your reasoning in the
  document that cites the row.
- A search that found nothing is a claim. Record it in §4, so the next session searches new ground.
- Every kind is one of `code`, `url`, `doc`, `jira`, `user`. §2 states the locator form for each.
- Use pure Markdown headings and links.

---

## 1. Keys

Short keys stand in for long paths. Expand each one here, once.

| Key | Expands to |
| :--- | :--- |
| `[KEY_A]` | `[full/path/to/partner-openapi.json]` |
| `[KEY_B]` | `[full/path/to/target-system-swagger.json]` |
| `[KEY_C]` | `[full/path/to/requirements-doc.md]` |

All other paths are relative to the `[repository-name]` root. Class names are given without their
package where the name is unique in the repository.

---

## 2. Locator forms

The form each kind takes. A row whose locator does not match its form is not yet a citation.

| Kind | Locator form | Example |
| :--- | :--- | :--- |
| `code` | `path/to/File.ext:START-END` for a range, `path/to/File.ext#memberName` for a class or method | `src/main/java/com/x/ProductSync.java:118-146` |
| `url` | Full URL, then `(fetched YYYY-MM-DD)` — the page moves and the date says which version you read | `https://partner.dev/docs/catalog#status (fetched 2026-08-26)` |
| `doc` | `document.md` §N, or `[KEY]` → `[json.pointer.path]` for a specification file | `[KEY_A]` → `components.schemas.Product.properties.status` |
| `jira` | `KEY` + the field: `description`, `comment by [author] YYYY-MM-DD`, or `attachment [filename]` | `IA-5105 comment by J. Tan 2026-08-20` |
| `user` | `[name]`, `[YYYY-MM-DD]`, and the decision in their words | `Steve, 2026-08-25, "we ship the DTO before OMS confirms"` |

---

## 3. Claims

Every claim behind the three documents. Append as you write, and keep every number fixed.

| # | Claim | Kind | Locator | Says | Used in |
| :-- | :--- | :--- | :--- | :--- | :--- |
| L-1 | [The claim, in one sentence.] | `code` | `[path/to/File.ext:START-END]` | "[what the material says]" | mapping §5.1 |
| L-2 | [The claim.] | `doc` | `[KEY_A]` → `[json.pointer.path]` | [tight paraphrase] | mapping §6 · requirements §3 |
| L-3 | [The claim.] | `url` | `[https://…]` (fetched `[YYYY-MM-DD]`) | "[quote]" | summary 2.3 |
| L-4 | [The claim.] | `jira` | `[KEY] comment by [author] [YYYY-MM-DD]` | "[quote]" | summary 2.1 |
| L-5 | [The decision.] | `user` | `[name]`, `[YYYY-MM-DD]` | "[their words]" | summary 2.2 |
| L-6 | `[field_name]` appears nowhere in `[KEY_B]`. | `doc` | `[KEY_B]` — `[field_name]`, 0 occurrences | An absence. The file is where the next session re-checks it. | requirements §4 |

---

## 4. Searches that stopped

What this session looked for and did not find, and where the looking stopped. A row here saves the
next session the same search.

| # | Looked for | Where | Result |
| :-- | :--- | :--- | :--- |
| S-1 | [What you were trying to establish.] | [The files, endpoints or pages searched, and the query.] | not found by this search — [what would answer it] |
| S-2 | [What you were trying to establish.] | [Where.] | found, superseded by `L-n` — [what replaced it] |

---

## 5. Open at the time of writing

Claims the three documents rest on that no source settles yet. Each names what would settle it.

- **L-[n]** — [the claim] rests on [assumption]. *To settle: [ask X / read Y / audit Z].*
