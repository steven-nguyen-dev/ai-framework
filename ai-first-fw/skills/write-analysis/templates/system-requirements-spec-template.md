# [TARGET_SYSTEM] Requirements — [Short Feature Title]

**Document Identifier:** `[KEY]-[TARGET_SYSTEM]-[TOPIC]-requirements-spec.md`
**Requirement:** `[KEY]` — *[Feature / User Story Title]*
**Target System:** `[TARGET_SYSTEM]` — [the word the context files give]
**Tier:** `[integration | internal]` — [the context file that places this system at that level]
**System Specification Reference:** `[TARGET_SYSTEM] data model / API spec` (`[spec-file]`)
**Counterparty / Context:** `[SOURCE_SYSTEM]` — [its tier]
**Claim library:** `[KEY]-[TOPIC]-library.md` — every `L-n` in this document resolves there
**Author / Team:** `[Author / Team Name]`
**Target Release / Sprint:** `[vX.Y.Z / Sprint N]`

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **requirements spec**. Its reader owns `[TARGET_SYSTEM]` and arrives holding one
endpoint. It states what changes on that endpoint, and what holds once the change is built.

**Writing rules.**

- Use the word the repository's context files give for every system, party, key and wire field, and
  name the context file that owns a term two files share.
- Group by endpoint. One `###` section per endpoint or flow, headed by the method and path. Its
  change rows and its payload diff sit together in that section, stated once.
- Every payload diff is the endpoint's whole request body, fenced `jsonc`. Every line carries a
  trailing comment: `// [REUSE]` alone, or `// [ADD]` / `// [UPDATE]` / `// [REMOVE]` with an `L-n`
  and one clause. Shorten a long value; keep every line. The comments are the note.
- Align the trailing comments of one diff on the same column, so the statuses read as a column.
- Every property carries one change status: `ADD`, `UPDATE`, `REMOVE` or `REUSE`. Settle it against
  the target system's data model before you write the row.
- Reuse first. Before you write `ADD`, check whether a property already in the model carries the
  same business meaning, and record the result as a `REUSE` row, or as a claim stating the absence.
- Write each `ADD` and `UPDATE` requirement in the receiving team's own terms: the property, the
  column, the validation. Start it with a verb.
- Section 4 carries one `A-n` per condition that holds once the work is built. Every change row is
  covered by an `A-n`, and the summary's definition of done cites them.
- Every row carries an `L-n`. The claim library states the citation rule and holds every locator.
- Use pure Markdown headings and links. Write counts as numbers.
- Keep the endpoints this requirement touches and delete the rest.

---

## 1. Scope

This specification states the schema, payload, migration and validation changes `[TARGET_SYSTEM]`
makes to support `[FEATURE_NAME]`.

| Status | On an endpoint (2) | On no endpoint (3) | Engineering action |
| :--- | :-: | :-: | :--- |
| ADD | [n] | [n] | New property, column and migration |
| UPDATE | [n] | [n] | Validation, type or mapping change on an existing property |
| REMOVE / DEPRECATE | [n] | [n] | Phase out a legacy property, endpoint or flow |
| REUSE | [n] | [n] | No work; the property already carries this meaning |

**Endpoints this requirement changes**

| Endpoint / topic | Section | Changes |
| :--- | :--- | :--- |
| `[POST /path/to/endpoint_a]` | 2.1 | [n] ADD, [n] UPDATE |
| `[POST /path/to/endpoint_b]` | 2.2 | [n] ADD |
| `[GET /path/to/endpoint_c]` | 2.3 | [n] ADD, [n] DEPRECATE |

---

## 2. Changes, by endpoint

### 2.1 `[POST /path/to/endpoint_a]`

* **Interface:** `[REST | GraphQL | Event topic]`
* **Target DTO:** `[TargetRequestDTO]`
* **Persistence target:** `[Database table or collection]`
* **Carries:** [The flow and the source data this endpoint receives.] `L-n`

| Property path | Type | Status | Example | Persistence impact | Requirement | Claim |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `$.[new_property_1]` | `[type]` | ADD | `"[example]"` | New column `[col_name]` | [Verb-led statement of what to build, and why no existing property carries it.] | `L-n` |
| `$.[new_property_2]` | `[type]` | ADD | `[example]` | New column `[col_name]`, indexed | [Statement.] | `L-n` |
| `$.[existing_property]` | `[type]` | UPDATE | `[example]` | Alter column `[col_name]` | [The validation or type change, stated as the new rule.] | `L-n` |
| `$.[legacy_property]` | `[type]` | REMOVE | — | Drop column `[col_name]` | [What replaces it.] | `L-n` |
| `$.code` | `string` | REUSE | `"ID_00123"` | None | Already the unique primary identifier. | `L-n` |
| `$.name` | `string` | REUSE | `"Standard Name"` | None | Already the human-readable display label. | `L-n` |
| `$.[scope_key]` | `string` | REUSE | `"SCOPE_0001"` | None | Already isolates one account's data. | `L-n` |

**Request payload diff**

```jsonc
{
  "existing_field_id": "ID_001",                 // [REUSE]
  "existing_field_name": "Standard Name",        // [REUSE]
  "new_property_1": "sample_new_value",          // [ADD]    L-n  [why no existing property carries it]
  "new_property_2": true,                        // [ADD]    L-n  indexed; [what reads it]
  "existing_property": true                      // [UPDATE] L-n  [old type or rule] → [new type or rule]
}
```

### 2.2 `[POST /path/to/endpoint_b]`

* **Interface:** `[REST | GraphQL | Event topic]`
* **Target DTO:** `[MetadataDTO]`
* **Persistence target:** `[Database table or collection]`
* **Carries:** [The flow and the source data this endpoint receives.] `L-n`

| Property path | Type | Status | Example | Persistence impact | Requirement | Claim |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `$.[raw_payload_blob]` | `string / json` | ADD | `"{...}"` | New column `[col_name]`, JSON | Store the source payload verbatim so a replay reprocesses without a refetch. | `L-n` |
| `$.[version_checksum]` | `string` | ADD | `"[hash]"` | New column `[col_name]`, indexed | Detect upstream change without comparing every field. | `L-n` |
| `$.[mandatory_flag]` | `boolean` | UPDATE | `true` | Constraint update | Accept booleans only; the source sends a strict boolean. | `L-n` |
| `$.field_code` | `string` | REUSE | `"[key]"` | None | Already the attribute key. | `L-n` |
| `$.field_values[]` | `array` | REUSE | `[{"name":"Red","value":"red"}]` | None | Already holds the selectable option pairs. | `L-n` |

**Request payload diff**

```jsonc
{
  "entity_code": "CODE_123",                     // [REUSE]
  "version_checksum": "V_ABC987",                // [ADD]    L-n  indexed; detects upstream change
  "raw_payload_blob": "{...unedited_json...}",   // [ADD]    L-n  verbatim source, replayable
  "attributes": [
    {
      "attribute_code": "[key]",                 // [REUSE]
      "mandatory": true,                         // [UPDATE] L-n  "Y"/"N" string → strict boolean
      "unit_options": ["cm", "inches"]           // [ADD]    L-n  [which consumer needs the units]
    }
  ]
}
```

### 2.3 `[GET /path/to/endpoint_c]`

* **Interface:** Query / read
* **Target DTO:** `[TargetResponseDTO]`
* **Carries:** [Which consumer reads this, and what it does with the new field.] `L-n`

| Property path | Type | Status | Example | Requirement | Claim |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `$.response.[new_field]` | `[type]` | ADD | `"[example]"` | Return the newly ingested property so `[consumer]` renders it. | `L-n` |
| `$.query.[legacy_param]` | `[type]` | DEPRECATE | `false` | Return a `Sunset` header on this parameter; `[replacement]` supersedes it. | `L-n` |

---

## 3. Changes that land on no endpoint

Flows, components and assumptions this requirement adds, changes or retires. Same four statuses as
section 2.

| Workflow, component or assumption | Status | Action | Claim |
| :--- | :---: | :--- | :--- |
| `[Token mint / counter / sequencing gate]` | ADD | [Verb-led statement of the capability to build.] | `L-n` |
| `[Legacy manual file upload]` | REMOVE | Retire the upload screen and its worker; `[endpoint]` replaces it. | `L-n` |
| `[Single-scope assumption]` | REMOVE | Scope every record operation by the scope key. | `L-n` |
| `[Unused legacy endpoint]` | DEPRECATE | Return a `Sunset` header, and remove after `[release]`. | `L-n` |

---

## 4. Acceptance

Each line states what holds on `[TARGET_SYSTEM]` once the work is built. The summary's definition of
done cites these lines by `A-n`. Keep the lines whose rows this requirement carries and delete the
rest.

| # | Holds when | Covers |
| :-- | :--- | :--- |
| A-1 | A migration exists and has run for every `ADD` column. | 2, ADD rows |
| A-2 | Every column the tables mark indexed carries its index. | 2, ADD rows |
| A-3 | Every `ADD` and `UPDATE` property carries its serialisation annotation on the DTO. | 2, ADD and UPDATE rows |
| A-4 | Validators enforce the rule each `UPDATE` row states. | 2, UPDATE rows |
| A-5 | A repeated payload updates the existing record, and the record count stays the same. | 2, mapping section 6 |
| A-6 | Records absent from a full sync hold the state the mapping spec section 6 names. | mapping section 6 |
| A-7 | Every endpoint operating on a `REUSE` property passes its existing tests unchanged. | 2, REUSE rows |
| A-8 | Every `DEPRECATE` parameter returns its response, with the `Sunset` header. | 2, DEPRECATE rows |
| A-9 | Every new mapper and validation class carries tests at the coverage this repository requires. | 2, 3 |
| A-10 | Every flow the mapping spec section 3 names runs end to end against the mocks at `[path/to/mock/suite]`. | mapping section 3 |
| A-11 | `[This side's endpoint or operation]` is callable and documented at `[path]`. | 2 |
| A-12 | [The capability section 3 adds behaves as section 3 states, checked at [where].] | 3 rows |
