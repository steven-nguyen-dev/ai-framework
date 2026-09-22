# [KEY] Claim Library — [Short Feature Title]

**Document Identifier:** `[KEY]-[TOPIC]-library.md`
**Requirement:** `[KEY]` — *[Feature / Initiative Title]*
**Covers:** `[KEY]-[TOPIC]-mapping.md` · `[KEY]-[TOPIC]-specs.md`
**Repository:** `[repository-name]` @ `[branch]` — commit `[short-sha]`
**Author / Team:** `[Author / Team Name]`
**Date:** `[YYYY-MM-DD]`

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **library**. One per requirement. It is opened first and appended to as the mapping
and the specs are written. It resolves any claim in those two documents to the material behind it,
so a reader checks the contract against its sources in one action.

The change requests cite nothing here. That document travels to the receiving team on its own, and
each of its payload comments states its source in words, so it reads with this library absent. Every
claim behind a change request row still takes a row here, because the analysis rests on it.

**The citation rule.** The mapping and the specs follow it. Every claim in those two documents
carries an `L-n` that resolves to a row of section 3 here. Those documents cite; this document holds
the locator and the words.

**Writing rules.**

- `references/writing-limits.md` reaches this repository's unit limits and wording rules, which
  every unit and every sentence here holds.
- The document opens on its metadata block and runs straight to section 1. Every word in it sits in
  a table row.
- **One row, one atomic fact.** `Claim` is a single declarative sentence. Design rationale, deduction
  and synthesis live in the mapping and the specs, which cite this row.
- **One row, one locator.** `Locator` names exactly one target, in the form its kind states. Where a
  fact rests on two places, write two rows, each with its own number and its own target.
- **One row, one verbatim quote.** `Says` carries the source's own words inside `"` quotes: the exact
  line for `code`, the exact sentence for `doc`, `jira`, `url` and `user`. An absence carries
  `0 occurrences of [term]`.
- One row per claim. A claim used by two documents keeps one row and one `L-n`.
- `L-n` is permanent. A superseded claim keeps its number, and its row is written over with the
  claim, locator and quote that hold now — the row states the current fact and its source.
- A claim about this codebase's behaviour carries kind `code`. A claim about a party outside the
  organisation carries kind `url` or `doc`, citing that party's own published page.
- Where the code states one thing and a document another, the code's locator and quote go into the
  row, and the document is corrected to match.
- Give every item of the requirement's stated definition of done its own row, in the requirement's
  words, used in `specs 5`.
- `Used in` names the document and its `##` section only — `mapping 4`, `specs 4`. Subsection
  numbers move while this library is open; top-level numbers hold. A claim the change requests rest
  on carries `change requests` and its section, and that document carries no `L-n` in return.
- Every kind is one of `code`, `url`, `doc`, `jira`, `user`. Section 2 states the locator form for
  each.

---

## 1. Keys

Short keys stand in for long paths. Expand each one here, once. Every expansion begins with `/` or
`[K-REPO]`, so a file tool opens it as written.

| Key | Expands to |
| :--- | :--- |
| `K-REPO` | `[/absolute/path/to/repository-root]` |
| `K-REQ` | `[the requirement's key or the brief's path]` |
| `[KEY_A]` | `[/absolute/path/to/party-openapi.json]` |
| `[KEY_B]` | `[K-REPO]/[path/to/target-system-spec.json]` |
| `[KEY_C]` | `[K-REPO]/[path/to/context-file.md]` |

All other paths are relative to `[K-REPO]`. Class names are given without their package where the
name is unique in the repository.

---

## 2. Locator forms

The form each kind takes. Every row's locator names one target in the form its kind states, so a
reader opens it in one action with no search.

| Kind | Locator form | Example |
| :--- | :--- | :--- |
| `code` | `[K-REPO]/path/to/File.ext:START-END` for a range, `[K-REPO]/path/to/File.ext#memberName` for a class or method, `[K-REPO]/path/to/File.ext — [term], 0 occurrences` for an absence | `[K-REPO]/[path]/[File].[ext]:118-146` |
| `url` | Full URL with its anchor, then `(fetched YYYY-MM-DD)` — the page moves and the date says which version you read | `https://[party]/docs/[page]#[anchor] (fetched YYYY-MM-DD)` |
| `doc` | `[KEY]` → `[json.pointer.path]` for a specification file, or `[KEY]` section N for prose | `[KEY_A]` → `components.schemas.[Entity].properties.[field]` |
| `jira` | `K-REQ` + the exact place: section N paired with its requirement key, `comment by [author] YYYY-MM-DD`, or `attachment [filename]` | `K-REQ` section 15 (`FR-22`) |
| `user` | `[name]`, `[YYYY-MM-DD]` — Says carries the decision in their words | `[name], [YYYY-MM-DD]` |

---

## 3. Claims

Every claim behind the mapping and the specs, and behind every change request row. Append as you write, and keep every number fixed.

| # | Claim | Kind | Locator | Says | Used in |
| :-- | :--- | :--- | :--- | :--- | :--- |
| L-1 | The line item quantity serialises under the wire key `[wire_key]`. | `code` | `[K-REPO]/[path]/[Entity]DTO.[ext]:23` | `"@JsonProperty(\"[wire_key]\") private Integer [field];"` | mapping 4 |
| L-2 | `[field]` is mandatory before `[operation]` is called. | `jira` | `K-REQ` section 15 (`FR-22`) | `"[the requirement's exact sentence]"` | change requests 2 |
| L-3 | `[operation]` returns HTTP 204 with no content. | `doc` | `[KEY_A]` → `paths./[path].post.responses` | `"204": { "description": "Success." }` | mapping 1 |
| L-4 | `[the party's rule]`. | `url` | `https://[party]/docs/[page]#[anchor]` (fetched `[YYYY-MM-DD]`) | `"[the page's exact sentence]"` | specs 4 |
| L-5 | `[the decision]`. | `user` | `[name]`, `[YYYY-MM-DD]` | `"[their exact words]"` | specs 4 |
| L-6 | `[field_name]` appears nowhere in `[KEY_B]`. | `doc` | `[KEY_B]` — `[field_name]`, 0 occurrences | `0 occurrences of [field_name]` | change requests 2 |
| L-7 | The requirement's stated definition of done, item [n]. | `jira` | `K-REQ` description — definition of done, item [n] | `"[the item's exact words]"` | specs 5 |
| L-8 | `[term]` names `[what it resolves to]` in this contract. | `doc` | `[KEY_C]` → `[term]` | `"[the context file's exact definition]"` | mapping 1 |
