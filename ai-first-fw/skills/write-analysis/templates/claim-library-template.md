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
documents is written. It resolves any claim in any of the three documents to the material behind it,
so a reader checks the contract against its sources in one action.

**The citation rule.** The mapping spec, the requirements spec and the summary follow it. Every
claim in those documents carries an `L-n` that resolves to a row of §3 here. Those documents cite;
this document holds the locator and the words.

**Writing rules.**

- One row per claim. A claim used by two documents keeps one row and one `L-n`.
- `L-n` is permanent. A superseded claim keeps its number, and its row carries the locator and the
  words that hold now.
- Write the locator so a reader opens the material in one action, with no search: a path a file tool
  reads, a URL a fetch tool loads, a Jira key and field, or a named person.
- `Says` carries the material's own words, quoted, up to about 25 of them. Where a quote does not
  carry it, write the tight paraphrase a reader acts on. Keep your reasoning in the document that
  cites the row.
- An absence is a claim. Give it a row whose locator names the file and the term, and whose `Says`
  records the count as `0 occurrences`.
- Give every item of the ticket's definition of done its own row, in the ticket's words, used in
  `summary 3`.
- `Used in` names the document and its `##` section only — `mapping §4`, `requirements §2`,
  `summary 2`. Subsection numbers move while this library is open; top-level numbers do not.
- Every kind is one of `code`, `url`, `doc`, `jira`, `user`. §2 states the locator form for each.
- Use pure Markdown headings and links.

---

## 1. Keys

Short keys stand in for long paths. Expand each one here, once. Every expansion begins with `/` or
`[K-REPO]`, so a file tool opens it as written.

| Key | Expands to |
| :--- | :--- |
| `K-REPO` | `[/absolute/path/to/repository-root]` |
| `[KEY_A]` | `[/absolute/path/to/partner-openapi.json]` |
| `[KEY_B]` | `[K-REPO]/[path/to/target-system-swagger.json]` |
| `[KEY_C]` | `[K-REPO]/[path/to/requirements-doc.md]` |

All other paths are relative to `[K-REPO]`. Class names are given without their package where the
name is unique in the repository.

---

## 2. Locator forms

The form each kind takes. A row whose locator does not match its form is not yet a citation.

| Kind | Locator form | Example |
| :--- | :--- | :--- |
| `code` | `path/to/File.ext:START-END` for a range, `path/to/File.ext#memberName` for a class or method, `path — [term], [n] occurrences` for an absence | `src/main/java/com/x/ProductSync.java:118-146` |
| `url` | Full URL, then `(fetched YYYY-MM-DD)` — the page moves and the date says which version you read | `https://partner.dev/docs/catalog#status (fetched 2026-08-26)` |
| `doc` | `document.md` §N, or `[KEY]` → `[json.pointer.path]` for a specification file | `[KEY_A]` → `components.schemas.Product.properties.status` |
| `jira` | `KEY` + the field: `description`, `comment by [author] YYYY-MM-DD`, or `attachment [filename]` | `IA-5105 comment by J. Tan 2026-08-20` |
| `user` | `[name]`, `[YYYY-MM-DD]` — Says carries the decision in their words | `Steve, 2026-08-25` |

---

## 3. Claims

Every claim behind the three documents. Append as you write, and keep every number fixed.

| # | Claim | Kind | Locator | Says | Used in |
| :-- | :--- | :--- | :--- | :--- | :--- |
| L-1 | [The claim, in one sentence.] | `code` | `[path/to/File.ext:START-END]` | "[what the material says]" | mapping §5 |
| L-2 | [The claim.] | `doc` | `[KEY_A]` → `[json.pointer.path]` | [tight paraphrase] | mapping §6 · requirements §3 |
| L-3 | [The claim.] | `url` | `[https://…]` (fetched `[YYYY-MM-DD]`) | "[quote]" | summary 2 |
| L-4 | [The claim.] | `jira` | `[KEY] comment by [author] [YYYY-MM-DD]` | "[quote]" | summary 2 |
| L-5 | [The decision.] | `user` | `[name]`, `[YYYY-MM-DD]` | "[their words]" | summary 2 |
| L-6 | `[field_name]` appears nowhere in `[KEY_B]`. | `doc` | `[KEY_B]` — `[field_name]`, 0 occurrences | An absence. The file is where a reader re-checks it. | requirements §4 |
| L-7 | The ticket's definition of done, item [n]. | `jira` | `[KEY]` description — definition of done | "[the item, in the ticket's words]" | summary 3 |
