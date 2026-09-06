# [TARGET_SYSTEM] Change Requests — [Short Feature Title]

**Document Identifier:** `[KEY]-[TARGET_SYSTEM]-[TOPIC]-change-requests.md`
**Requirement:** `[KEY]` — *[Feature / User Story Title]*
**Target System:** `[TARGET_SYSTEM]` — [the system this document asks to change]
**Source System:** `[SOURCE_SYSTEM]` — [the external system whose payload the new values come from]
**Author / Team:** `[Author / Team Name]`
**Target Release / Sprint:** `[vX.Y.Z / Sprint N]`

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **change requests**. This is the document that leaves this repository: the team that
owns `[TARGET_SYSTEM]` receives this file on its own and builds from it. So it stands alone. It
names every term it uses, states every source it maps from in its own words, and carries no `L-n`
and no pointer to another document of the contract. A reader holding this file alone builds the
change.

**Writing rules.**

- `references/writing-limits.md` states the character, paragraph, list and column limits every unit
  here holds.
- Name each system, party, key and wire field in the word the repository's context files give, and
  expand it on first use, because the reader holds no context file.
- Group by endpoint. One `###` section per endpoint or flow, headed by the method and path. Its
  change table and its payload sample sit together in that section.
- Give every property one change status: `ADD`, `UPDATE`, `REMOVE` or `REUSE`, settled against
  `[TARGET_SYSTEM]`'s own data model.
- Reuse first. Before you write `ADD`, look for a property already in the model carrying the same
  business meaning, and write the result as a `REUSE` row.
- Write each `ADD` and `UPDATE` requirement in the receiving team's own terms — the property, the
  column, the validation — starting with a verb.
- Section 4 carries one `A-n` per condition that holds once the work is built, and every change row
  is covered by an `A-n`.
- Use pure Markdown headings and links, and write counts as numbers.
- Keep the endpoints this requirement touches and delete the rest.

**The payload sample comment.** Every sample is the endpoint's whole request body, fenced `jsonc`,
with the trailing comments aligned on one column. A line whose property is `ADD`, `UPDATE` or
`REMOVE` carries a comment; a `REUSE` line carries none, and its silence marks it unchanged. Each
comment holds the status, then the mapping in plain words, so the comment alone explains where the
value comes from:

```text
// [ADD] <property> of <object> in the <SOURCE_SYSTEM> <resource> payload
```

Name the property, the object that holds it and the payload it arrives in — `sellerSku` of
`listingItem` in the Amazon Listings Items payload, not `sellerSku` and not `L-4`. Where the value
comes from no source property, name what produces it: the connection setting, the constant, the
computation. Shorten a long value, keep every line.

---

## 1. Scope

This document states the schema, payload, migration and validation changes `[TARGET_SYSTEM]` makes
to support `[FEATURE_NAME]`. `[SOURCE_SYSTEM]` is [one sentence naming what it is and what it sends].

**Counts**

| Status | On an endpoint | On no endpoint | Engineering action |
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
* **Carries:** [The flow this endpoint serves, and the `[SOURCE_SYSTEM]` data it receives.]

| Property path | Type | Status | Persistence impact | Requirement |
| :--- | :--- | :---: | :--- | :--- |
| `$.[new_property_1]` | `[type]` | ADD | New column `[col_name]` | [Verb-led statement of what to build, and why no existing property carries it.] |
| `$.[new_property_2]` | `[type]` | ADD | New column `[col_name]`, indexed | [Statement.] |
| `$.[existing_property]` | `[type]` | UPDATE | Alter column `[col_name]` | [The validation or type change, stated as the new rule.] |
| `$.[legacy_property]` | `[type]` | REMOVE | Drop column `[col_name]` | [What replaces it.] |
| `$.code` | `string` | REUSE | None | Already the unique primary identifier. |

**Request payload sample**

```jsonc
{
  "existing_field_id": "ID_001",
  "existing_field_name": "Standard Name",
  "new_property_1": "sample_new_value",       // [ADD] [property] of [object] in the [SOURCE_SYSTEM] [resource] payload
  "new_property_2": true,                     // [ADD] derived from [property] of [object]; indexed for [what reads it]
  "existing_property": true                   // [UPDATE] [old rule] → [new rule]; [SOURCE_SYSTEM] sends a strict boolean
}
```

### 2.2 `[POST /path/to/endpoint_b]`

* **Interface:** `[REST | GraphQL | Event topic]`
* **Target DTO:** `[MetadataDTO]`
* **Persistence target:** `[Database table or collection]`
* **Carries:** [The flow this endpoint serves, and the `[SOURCE_SYSTEM]` data it receives.]

| Property path | Type | Status | Persistence impact | Requirement |
| :--- | :--- | :---: | :--- | :--- |
| `$.[raw_payload_blob]` | `string / json` | ADD | New column `[col_name]`, JSON | Store the source payload verbatim so a replay reprocesses without a refetch. |
| `$.[version_checksum]` | `string` | ADD | New column `[col_name]`, indexed | Detect upstream change without comparing every property. |
| `$.[mandatory_flag]` | `boolean` | UPDATE | Constraint update | Accept booleans only. |
| `$.field_code` | `string` | REUSE | None | Already the attribute key. |

**Request payload sample**

```jsonc
{
  "entity_code": "CODE_123",
  "version_checksum": "V_ABC987",             // [ADD] hash of the whole [object] payload from [SOURCE_SYSTEM]; indexed
  "raw_payload_blob": "{...source_json...}",  // [ADD] the [SOURCE_SYSTEM] [resource] response body, unedited
  "attributes": [
    {
      "attribute_code": "[key]",
      "mandatory": true,                      // [UPDATE] "Y"/"N" string → boolean; [property] of [object] sends true/false
      "unit_options": ["cm", "inches"]        // [ADD] [property] of [object] in the [SOURCE_SYSTEM] [resource] payload
    }
  ]
}
```

### 2.3 `[GET /path/to/endpoint_c]`

* **Interface:** Query / read
* **Target DTO:** `[TargetResponseDTO]`
* **Carries:** [Which consumer reads this, and what it does with the new property.]

| Property path | Type | Status | Persistence impact | Requirement |
| :--- | :--- | :---: | :--- | :--- |
| `$.response.[new_property]` | `[type]` | ADD | Read from `[col_name]` | Return the newly ingested property so `[consumer]` renders it. |
| `$.query.[legacy_param]` | `[type]` | DEPRECATE | None | Return a `Sunset` header on this parameter; `[replacement]` supersedes it. |

**Response payload sample**

```jsonc
{
  "code": "ID_00123",
  "new_property": "sample_new_value"          // [ADD] read from [col_name]; [consumer] renders it on [screen]
}
```

---

## 3. Changes that land on no endpoint

Flows, components and assumptions this requirement adds, changes or retires. Same four statuses as
section 2.

| Workflow, component or assumption | Status | Action |
| :--- | :---: | :--- |
| `[Token mint / counter / sequencing gate]` | ADD | [Verb-led statement of the capability to build.] |
| `[Legacy manual file upload]` | REMOVE | Retire the upload screen and its worker; `[endpoint]` replaces it. |
| `[Single-scope assumption]` | REMOVE | Scope every record operation by the scope key. |
| `[Unused legacy endpoint]` | DEPRECATE | Return a `Sunset` header, and remove after `[release]`. |

---

## 4. Acceptance

Each line states what holds on `[TARGET_SYSTEM]` once the work is built. Keep the lines whose rows
this requirement carries and delete the rest.

| # | Holds when | Covers |
| :-- | :--- | :--- |
| A-1 | A migration exists and has run for every `ADD` column. | 2, ADD rows |
| A-2 | Every column the tables mark indexed carries its index. | 2, ADD rows |
| A-3 | Every `ADD` and `UPDATE` property carries its serialisation annotation on the DTO. | 2 |
| A-4 | Validators enforce the rule each `UPDATE` row states. | 2, UPDATE rows |
| A-5 | A repeated payload updates the existing record, and the record count stays the same. | 2 |
| A-6 | Every endpoint operating on a `REUSE` property passes its existing tests unchanged. | 2, REUSE rows |
| A-7 | Every `DEPRECATE` parameter returns its response, with the `Sunset` header. | 2 |
| A-8 | Every new mapper and validation class carries tests at the coverage `[TARGET_SYSTEM]` requires. | 2, 3 |
| A-9 | `[This endpoint or operation]` is callable and documented at `[path]`. | 2 |
| A-10 | [The capability section 3 adds behaves as section 3 states, checked at [where].] | 3 rows |

---

## 5. Glossary

Every term this document uses that the receiving team does not already hold. This section is what
lets the file travel alone.

| Term | Means |
| :--- | :--- |
| `[SOURCE_SYSTEM]` | [What it is, and what it sends.] |
| `[source resource name]` | [The source endpoint or payload the change rows map from.] |
| `[domain term]` | [Its meaning in this change request.] |
