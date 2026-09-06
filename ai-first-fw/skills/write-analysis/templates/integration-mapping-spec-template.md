# [INTEGRATION_NAME] Data Mapping Specification

**Document Identifier:** `[JIRA_ISSUE_KEY]-[TOPIC]-mapping-spec.md` (e.g. `IA-5105-product-types-mapping-spec.md`)
**Reference Tracking:** `[JIRA_ISSUE_KEY]` — *[Feature / Initiative Title]*
**Source System / Origin:** `[SOURCE_SYSTEM]` (e.g. Marketplace, Carrier, ERP, POS, 3PL, Custom Channel)
**Target Internal System:** `[TARGET_SYSTEM]` (e.g. OMS, WMS, OXM, PT, Inventory Core)
**Target Interface Spec:** `[TARGET_INTERFACE_REFERENCE]` (e.g. OpenAPI / Swagger, AsyncAPI, Protobuf, GraphQL)
**Claim library:** `[JIRA_ISSUE_KEY]-[TOPIC]-library.md` — every `L-n` in this document resolves there
**Author / Team:** `[Author / Team Name]`
**Target Release / Version:** `[vX.Y.Z / Sprint N]`

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **mapping spec**. It answers one question per property: what value reaches the target,
and why that property needs it.

**Writing rules.**

- Group by endpoint. One `###` section per endpoint that carries data, in the order the flow calls
  them, headed `[in]` or `[out]` then the method and path — `in` reaches the source system, `out`
  reaches the target. A property row sits under the endpoint that carries it.
- **Transformation** states the operation on the value: direct map, cast, parse, enum lookup,
  concatenate, inject from context.
- **Reason** is one clause naming why the target property needs that value. Keep it under about
  twelve words. "Enum lookup, see §5" is a transformation; "OMS routes on this status" is a reason.
- Where one property carries a rule too long for a clause, write the clause here and the rule in the
  enum matrix or a numbered note below the table.
- Every row carries an `L-n`. The claim library states the citation rule and holds every locator.
- Use pure Markdown headings and links.
- Keep the sections this ticket uses and delete the rest.

---

## 1. Scope

* **Problem statement:** [What business process this integration automates.] `L-n`
* **In scope:** [The data flows this document covers, ingress and egress.]
* **Out of scope:** [What a reader might expect here and will not find, and where it lives instead.]
* **Communication pattern:** [Synchronous REST | Asynchronous job and poll | Event-driven or webhook | Scheduled file or batch] `L-n`

---

## 2. Entity alignment

How the source hierarchy lands on the target hierarchy. One row per level.

| Level | `[SOURCE_SYSTEM]` concept | `[TARGET_SYSTEM]` component | Cardinality | Alignment rationale |
| :--- | :--- | :--- | :--- | :--- |
| Scope / tenant | `[Source account / market ID]` | `[Tenant / store / channel code]` | 1-to-1 | Multi-tenant isolation |
| Primary entity | `[Source parent / header]` | `[Target master / header record]` | 1-to-1 | Main entity container |
| Child entity | `[Source line / child item]` | `[Target child / line item]` | 1-to-many | [Why the child is separate] |
| Dynamic attributes | `[Source custom fields]` | `[Target dynamic attributes / EAV]` | 1-to-many | [Why these are not columns] |

---

## 3. Flows

One block per flow. Name the endpoints it calls, in order, so a reader reaches the right section
of §4.

### Flow 1: [Name, e.g. Initial synchronisation]

**Trigger:** [Manual, connection setup, cron, webhook.] `L-n`

1. `[GET /path/on/source]` — [what it returns]
2. `[POST /rest/v1/target_endpoint]` — [what it persists]

### Flow 2: [Name, e.g. Delta maintenance]

**Trigger:** [Webhook or version check.] `L-n`

1. `[POST /path/on/source]` — [what it returns]
2. `[POST /rest/v1/target_endpoint]` — [what it upserts]

---

## 4. Field mapping, by endpoint

### 4.1 `[out]` `[POST /rest/v1/target_endpoint]`

* **Spec:** `[KEY]` → `[operationId or json.pointer.path]`
* **Called by:** Flow 1, step 2 · Flow 2, step 2
* **Source object:** `[source_payload.header_object]`
* **Target DTO:** `[TARGET_SYSTEM] / [TargetModelDTO]`
* **Rate limit:** `[e.g. 5 req/sec]` `L-n`

| # | Source field path | Target property | Type | Transformation | Reason | Nullable | Example | Claim |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :--- |
| 1 | `$.source_id` | `code` | `string` | Cast to string, trim | Primary key of the target record | No | `"ID_00123"` | `L-1` |
| 2 | `$.source_name` | `name` | `string` | Direct map | Display label in the target UI | No | `"Standard Name"` | `L-2` |
| 3 | `$.status_code` | `status` | `string` | Enum lookup, §5 | Target routes work on this state | No | `"ACTIVE"` | `L-3` |
| 4 | `$.timestamps.created` | `created_at` | `date-time` | Parse ISO 8601 to UTC | Orders records when events arrive late | Yes | `"2026-08-26T10:00:00Z"` | `L-4` |
| 5 | `[Context]` | `channel_code` | `string` | Inject tenant identifier | Scopes the record to one store | No | `"STORE_US_01"` | `L-5` |

**Child rows: `[TargetChildDTO[]]`** — source node `[source_payload.line_items[]]`

| # | Source field path | Target property | Type | Transformation | Reason | Nullable | Example | Claim |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :--- |
| 6 | `$.line_items[*].item_id` | `line_item_code` | `string` | Direct map | Identifies the line within the parent | No | `"LINE_01"` | `L-6` |
| 7 | `$.line_items[*].quantity` | `qty` | `integer` | Parse integer, default 0 | Target deducts stock on this number | No | `5` | `L-7` |

### 4.2 `[out]` `[POST /rest/v1/other_endpoint]`

* **Spec:** `[KEY]` → `[operationId or json.pointer.path]`
* **Called by:** Flow 2, step 1
* **Source object:** `[source_payload.custom_attributes]`
* **Target DTO:** `[AttributeListDTO]`

| # | Source field path | Target property | Type | Transformation | Reason | Nullable | Example | Claim |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :--- |
| 1 | `$.attributes.color` | `field_code: "color"` | `singleSelect` | Map allowed values to `field_values[]` | Target renders a dropdown from these | Yes | `"red"` to `{"name": "Red", "value": "red"}` | `L-8` |
| 2 | `$.attributes.dimensions` | `field_code: "dim"` | `textField` | Flatten object, append unit | Target holds no numeric-with-unit type | Yes | `{"w": 10, "u": "cm"}` to `"10 cm"` | `L-9` |

---

## 5. Enum translation

One row per source value. State the fallback where the source can send a value this table omits.

| Property | Source value (`[SOURCE_SYSTEM]`) | Target value (`[TARGET_SYSTEM]`) | Fallback | Claim |
| :--- | :--- | :--- | :--- | :--- |
| `status` | `"PENDING_APPROVAL"`, `"IN_REVIEW"` | `"under_review"` | `"draft"` on an unlisted value | `L-n` |
| `status` | `"PUBLISHED"`, `"ACTIVE"`, `"1"` | `"active"` | — | `L-n` |
| `status` | `"ARCHIVED"`, `"DELETED"`, `"0"` | `"inactive"` | — | `L-n` |
| `type` | `"KIT_OR_BUNDLE"` | `"kit"` | `"simple"` on an unlisted value | `L-n` |

---

## 6. Uniqueness and ordering

State what this integration settles. Where the answer is not settled, name it in the summary's open
questions instead of writing a default here.

* **Composite key:** `[TENANT_ID or CHANNEL_CODE] + [PRIMARY_ENTITY_CODE]` `L-n`
* **Repeat delivery:** [What a second copy of the same payload does to the stored record.] `L-n`
* **Out-of-order events:** [The field compared, and what happens when the arriving value is older.] `L-n`
* **Records absent from a full sync:** [What the integration does with them.] `L-n`
* **Record-level failure in a batch:** [What is logged, and what happens to the rest of the batch.] `L-n`
