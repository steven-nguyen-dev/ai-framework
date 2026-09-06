# [TARGET_SYSTEM] Requirements — [Short Feature Title]

**Document Identifier:** `[JIRA_ISSUE_KEY]-[TARGET_SYSTEM_LOWER]-[TOPIC]-requirements-spec.md` (e.g. `IA-5105-oms-taxonomy-requirements-spec.md`)
**Reference Tracking:** `[JIRA_ISSUE_KEY]` — *[Feature / User Story Title]*
**Target Internal System:** `[TARGET_SYSTEM]` (e.g. OMS, WMS, OXM, PT, Core Billing, Routing Engine)
**System Specification Reference:** `[TARGET_SYSTEM] Data Model / API Spec` (e.g. `[service]-swagger.json`, `schema.proto`, `models.ts`)
**External Integration / Context:** `[SOURCE_SYSTEM / CHANNEL]` (e.g. Marketplace, Carrier, ERP, Pricing Feed)
**Claim library:** `[JIRA_ISSUE_KEY]-[TOPIC]-library.md` — every `L-n` in this document resolves there
**Author / Team:** `[Author / Team Name]`
**Target Release / Sprint:** `[vX.Y.Z / Sprint N]`

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **requirements spec**. Its reader owns `[TARGET_SYSTEM]` and arrives holding one
endpoint. It tells that reader what changes on that endpoint.

**Writing rules.**

- Group by endpoint. One `###` section per endpoint or flow, headed by the method and path. Its
  change rows and its payload diff sit together in that section, stated once.
- Every payload diff is the endpoint's whole request body, fenced `jsonc`. Every line carries a
  trailing comment: `// [REUSE]` alone, or `// [ADD]` / `// [UPDATE]` / `// [REMOVE]` with an `L-n`
  and one clause. Shorten a long value; keep every line. The comments are the note.
- Align the trailing comments of one diff on the same column, so the statuses read as a column.
- Every property carries one change status: `ADD`, `UPDATE`, `REMOVE` or `REUSE`. Settle it against
  the target system's data model before you write the row.
- Reuse first. Before you write `ADD`, check whether a property already in the model carries the
  same business meaning, and record the check as a `REUSE` row or a stopped search.
- Write each `ADD` and `UPDATE` requirement in the receiving team's own terms: the property, the
  column, the validation. Start it with a verb.
- Every row carries an `L-n`. The claim library states the citation rule and holds every locator.
- Use pure Markdown headings and links. Write counts as numbers.
- Keep the endpoints this ticket touches and delete the rest.

---

## 1. Scope

This specification states the schema, payload, migration and validation changes `[TARGET_SYSTEM]`
makes to support `[FEATURE_NAME]`.

| Status | On an endpoint (§2) | On no endpoint (§3) | Engineering action |
| :--- | :-: | :-: | :--- |
| ADD | [n] | [n] | New property, column and migration |
| UPDATE | [n] | [n] | Validation, type or mapping change on an existing property |
| REMOVE / DEPRECATE | [n] | [n] | Phase out a legacy property, endpoint or flow |
| REUSE | [n] | [n] | No work; the property already carries this meaning |

**Endpoints this ticket changes**

| Endpoint / topic | Section | Changes |
| :--- | :--- | :--- |
| `[POST /rest/v1/endpoint_a]` | 2.1 | [n] ADD, [n] UPDATE |
| `[POST /rest/v1/endpoint_b]` | 2.2 | [n] ADD |
| `[GET /rest/v1/endpoint_c]` | 2.3 | [n] ADD, [n] DEPRECATE |

---

## 2. Changes, by endpoint

### 2.1 `[POST /rest/v1/endpoint_a]`

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
| `$.channel_code` | `string` | REUSE | `"STORE_US_01"` | None | Already provides multi-tenant isolation. | `L-n` |

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

### 2.2 `[POST /rest/v1/endpoint_b]`

* **Interface:** `[REST | GraphQL | Event topic]`
* **Target DTO:** `[MetadataDTO]`
* **Persistence target:** `[Database table or collection]`
* **Carries:** [The flow and the source data this endpoint receives.] `L-n`

| Property path | Type | Status | Example | Persistence impact | Requirement | Claim |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `$.[raw_payload_blob]` | `string / json` | ADD | `"{...}"` | New column `[col_name]`, JSON | Store the external payload verbatim so a replay reprocesses without a refetch. | `L-n` |
| `$.[version_checksum]` | `string` | ADD | `"[hash]"` | New column `[col_name]`, indexed | Detect upstream change without comparing every field. | `L-n` |
| `$.[mandatory_flag]` | `boolean` | UPDATE | `true` | Constraint update | Accept booleans only; the source sends a strict boolean. | `L-n` |
| `$.field_code` | `string` | REUSE | `"color"` | None | Already the attribute key. | `L-n` |
| `$.field_values[]` | `array` | REUSE | `[{"name":"Red","value":"red"}]` | None | Already holds the selectable option pairs. | `L-n` |

**Request payload diff**

```jsonc
{
  "entity_code": "CODE_123",                     // [REUSE]
  "version_checksum": "V_ABC987",                // [ADD]    L-n  indexed; detects upstream change
  "raw_payload_blob": "{...unedited_json...}",   // [ADD]    L-n  verbatim source, replayable
  "attributes": [
    {
      "attribute_code": "color",                 // [REUSE]
      "mandatory": true,                         // [UPDATE] L-n  "Y"/"N" string → strict boolean
      "unit_options": ["cm", "inches"]           // [ADD]    L-n  [which consumer needs the units]
    }
  ]
}
```

### 2.3 `[GET /rest/v1/endpoint_c]`

* **Interface:** Query / read
* **Target DTO:** `[TargetResponseDTO]`
* **Carries:** [Which consumer reads this, and what it does with the new field.] `L-n`

| Property path | Type | Status | Example | Requirement | Claim |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `$.response.[new_field]` | `[type]` | ADD | `"[example]"` | Return the newly ingested property so `[consumer]` renders it. | `L-n` |
| `$.query.[legacy_param]` | `[type]` | DEPRECATE | `false` | Return a `Sunset` header on this parameter; `[replacement]` supersedes it. | `L-n` |

---

## 3. Changes that land on no endpoint

Flows, components and assumptions this ticket adds, changes or retires. Same four statuses as §2.

| Workflow, component or assumption | Status | Action | Claim |
| :--- | :---: | :--- | :--- |
| `[Token mint / counter / sequencing gate]` | ADD | [Verb-led statement of the capability to build.] | `L-n` |
| `[Legacy manual file upload]` | REMOVE | Retire the upload screen and its worker; `[endpoint]` replaces it. | `L-n` |
| `[Single-tenant assumption]` | REMOVE | Scope every record operation by the tenant key. | `L-n` |
| `[Unused legacy endpoint]` | DEPRECATE | Return a `Sunset` header, and remove after `[release]`. | `L-n` |

---

## 4. Verification gate

Each line below checks a row of section 2. Delete a line whose rows this ticket does not carry.

**Schema**

- [ ] Migration script written and run for every `ADD` column.
- [ ] Index created on every column the tables mark indexed.
- [ ] DTO classes updated with serialisation annotations for every `ADD` and `UPDATE` property.

**Logic**

- [ ] Validators enforce the rule stated in every `UPDATE` row.
- [ ] A repeated payload updates the existing record and creates no duplicate.
- [ ] Records absent from a full sync take the state section 6 of the mapping spec names.

**Compatibility**

- [ ] Every endpoint operating on a `REUSE` property passes its existing tests unchanged.
- [ ] Every `DEPRECATE` parameter still returns a response, with its `Sunset` header.
- [ ] New mapper and validation classes carry tests at the coverage this repository requires.
