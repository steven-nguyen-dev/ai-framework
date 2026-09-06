# [INTEGRATION_NAME] Data Mapping Specification

**Document Identifier:** `[KEY]-[TOPIC]-mapping.md`
**Requirement:** `[KEY]` — *[Feature / Initiative Title]*
**Source System / Origin:** `[SOURCE_SYSTEM]` — [its tier, in the word the context files give]
**Target System:** `[TARGET_SYSTEM]` — [its tier, in the word the context files give]
**Target Interface Spec:** `[TARGET_INTERFACE_REFERENCE]` (OpenAPI, AsyncAPI, Protobuf, GraphQL)
**Claim library:** `[KEY]-[TOPIC]-library.md` — every `L-n` in this document resolves there
**Author / Team:** `[Author / Team Name]`
**Target Release / Version:** `[vX.Y.Z / Sprint N]`

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **mapping**. It states one thing per property: what value reaches the target, and
why that property needs it. Implementation builds what these rows state.

It carries the same shape as the change requests — scope, then one section per endpoint holding a
table and a payload sample, then acceptance — so a reader moving between the two reads one format.
Sections 5 to 8 are this document's own: the rules a per-property comment is too short to hold.

It stands alone as far as a document with rules can. A reader holding this file builds the mapping
from it, and reaches the claim library only to check a source. Where a decision this mapping needs
is still open, the specs' Notes section carries it, and section 8 names the note.

**Writing rules.**

- `references/writing-limits.md` states the character, paragraph, list and column limits every unit
  here holds.
- Name each system, party, key and wire field in the word the repository's context files give, and
  name the context file that owns a term two files share.
- Fill the wire identity from the context files before you write a property row.
- Group by endpoint. One `###` section per endpoint that carries data, in the order the flow calls
  them, headed `[source]` or `[target]` then the method and path — `source` reaches the system the
  data comes from, `target` reaches the system it lands in.
- **Transformation** states the operation on the value: direct map, cast, parse, enum lookup,
  concatenate, inject from context.
- **Reason** is one clause naming why the target property needs that value. "Enum lookup, section 5"
  is a transformation; "the target routes work on this status" is a reason.
- Every row carries an `L-n`. The claim library states the citation rule and holds every locator.
- Use pure Markdown headings and links, and keep the sections this requirement uses.

**The payload sample comment.** Every sample is the endpoint's whole request body, fenced `jsonc`,
with the trailing comments aligned on one column. Every mapped line carries a comment holding the
origin of the value and its `L-n`, so the sample alone states where each value comes from:

```text
// <property> of <object> in the <SOURCE_SYSTEM> <resource> payload · L-n
// computed: <the operation, in words> · L-n
// injected: <the connection setting or constant> · L-n
```

Name the source resource, not only the property — `sellerSku` of `listingItem` in the Amazon
Listings Items payload. A value the source does not carry names what produces it: the computation,
the enum lookup and its section, the connection setting, the constant. Shorten a long value, keep
every line.

---

## 1. Scope

* **Problem statement:** [What business process this integration automates.] `L-n`
* **In scope:** [The data flows this document covers, in each direction.]
* **Out of scope:** [What a reader might expect here and will not find, and where it lives instead.]
* **Communication pattern:** [Synchronous request/response | Asynchronous job and poll | Event-driven or webhook | Scheduled file or batch] `L-n`

**Wire identity**

State each row in the word the context files give, and name the file that owns a term two files
share.

| | Value | Claim |
| :--- | :--- | :--- |
| Family | `[the family of integration this change lands in]` | `L-n` |
| Routing key | `[the key that resolves the destination, and the wire field carrying it]` | `L-n` |
| Identity scope | `[the party hierarchy this data is scoped by, tier by tier]` | `L-n` |
| Direction | `[the direction sense the context file names, and what it emits]` | `L-n` |
| Stream derivation | `[how the stream or topic name is derived, and what prefixes it]` | `L-n` |

**Endpoints this mapping covers**

| Endpoint | Section | Rows |
| :--- | :--- | :-: |
| `[target]` `[POST /path/to/target_endpoint]` | 4.1 | [n] |
| `[target]` `[POST /path/to/other_endpoint]` | 4.2 | [n] |

---

## 2. Entity alignment

How the source hierarchy lands on the target hierarchy. One row per level.

| Level | `[SOURCE_SYSTEM]` concept | `[TARGET_SYSTEM]` component | Cardinality | Alignment rationale |
| :--- | :--- | :--- | :-: | :--- |
| Scope | `[source scope identifier]` | `[target scope identifier]` | 1-to-1 | Isolates one account's data |
| Primary entity | `[source parent / header]` | `[target master / header record]` | 1-to-1 | Main entity container |
| Child entity | `[source line / child item]` | `[target child / line item]` | 1-to-many | [Why the child is separate] |
| Dynamic attributes | `[source custom fields]` | `[target dynamic attributes]` | 1-to-many | [Why these are not columns] |

---

## 3. Flows

One block per flow. Name the endpoints it calls, in order, so a reader reaches the right section of
section 4. Each flow here is the unit the mock run in the specs' definition of done exercises, and
the specs draw it as a sequence.

### Flow 1: [Name, e.g. Initial synchronisation]

**Trigger:** [Manual, connection setup, schedule, webhook.] `L-n`

1. `[GET /path/on/source]` — [what it returns]
2. `[POST /path/on/target]` — [what it persists]

### Flow 2: [Name, e.g. Delta maintenance]

**Trigger:** [Webhook or version check.] `L-n`

1. `[POST /path/on/source]` — [what it returns]
2. `[POST /path/on/target]` — [what it upserts]

---

## 4. Field mapping, by endpoint

### 4.1 `[target]` `[POST /path/to/target_endpoint]`

* **Spec:** `[KEY]` → `[operationId or json.pointer.path]`
* **Called by:** Flow 1, step 2 · Flow 2, step 2
* **Source object:** `[source_payload.header_object]`
* **Target DTO:** `[TARGET_SYSTEM] / [TargetModelDTO]`
* **Rate limit:** `[e.g. 5 req/sec]` `L-n`

| Source field path | Target property | Transformation | Reason | Claim |
| :--- | :--- | :--- | :--- | :--- |
| `$.source_id` | `code` | Cast to string, trim | Primary key of the target record | `L-1` |
| `$.source_name` | `name` | Direct map | Display label in the target UI | `L-2` |
| `$.status_code` | `status` | Enum lookup, section 5 | The target routes work on this state | `L-3` |
| `$.timestamps.created` | `created_at` | Parse ISO 8601 to UTC | Orders records when events arrive late | `L-4` |
| `[Context]` | `[scope_key]` | Inject scope identifier | Scopes the record to one account | `L-5` |

**Child rows: `[TargetChildDTO[]]`** — source node `[source_payload.line_items[]]`

| Source field path | Target property | Transformation | Reason | Claim |
| :--- | :--- | :--- | :--- | :--- |
| `$.line_items[*].item_id` | `line_item_code` | Direct map | Identifies the line within the parent | `L-6` |
| `$.line_items[*].quantity` | `qty` | Parse integer, default 0 | The target deducts stock on this number | `L-7` |

**Request payload sample**

```jsonc
{
  "code": "ID_00123",                         // source_id of [header_object] in the [SOURCE_SYSTEM] [resource] payload · L-1
  "name": "Standard Name",                    // source_name of [header_object] in the same payload · L-2
  "status": "ACTIVE",                         // computed: enum lookup of status_code, section 5 · L-3
  "created_at": "2026-08-26T10:00:00Z",       // timestamps.created of [header_object], parsed to UTC · L-4
  "[scope_key]": "SCOPE_0001",                // injected: the connection's scope identifier · L-5
  "line_items": [
    {
      "line_item_code": "LINE_01",            // line_items[*].item_id of [header_object] · L-6
      "qty": 5                                // line_items[*].quantity, integer, 0 when absent · L-7
    }
  ]
}
```

### 4.2 `[target]` `[POST /path/to/other_endpoint]`

* **Spec:** `[KEY]` → `[operationId or json.pointer.path]`
* **Called by:** Flow 2, step 1
* **Source object:** `[source_payload.custom_attributes]`
* **Target DTO:** `[AttributeListDTO]`

| Source field path | Target property | Transformation | Reason | Claim |
| :--- | :--- | :--- | :--- | :--- |
| `$.attributes.[key_a]` | `field_code: "[key_a]"` | Map allowed values to `field_values[]` | The target renders a dropdown from these | `L-8` |
| `$.attributes.[key_b]` | `field_code: "[key_b]"` | Flatten object, append unit | The target holds no numeric-with-unit type | `L-9` |

**Request payload sample**

```jsonc
{
  "field_code": "[key_a]",                    // the attribute key of attributes.[key_a] in the [SOURCE_SYSTEM] [resource] payload · L-8
  "field_values": [
    { "name": "Red", "value": "red" }         // computed: each allowed value of attributes.[key_a] becomes one name/value pair · L-8
  ],
  "text_value": "10 cm"                       // computed: attributes.[key_b].w and .u concatenated; the target holds no unit type · L-9
}
```

---

## 5. Enum translation

One row per source value. State the fallback where the source can send a value this table omits.

| Property | Source value (`[SOURCE_SYSTEM]`) | Target value (`[TARGET_SYSTEM]`) | Fallback | Claim |
| :--- | :--- | :--- | :--- | :--- |
| `status` | `"PENDING_APPROVAL"`, `"IN_REVIEW"` | `"under_review"` | `"draft"` on an unlisted value | `L-n` |
| `status` | `"PUBLISHED"`, `"ACTIVE"`, `"1"` | `"active"` | — | `L-n` |
| `status` | `"ARCHIVED"`, `"DELETED"`, `"0"` | `"inactive"` | — | `L-n` |
| `[property]` | `"[SOURCE_VALUE]"` | `"[target_value]"` | `"[default]"` on an unlisted value | `L-n` |

---

## 6. Uniqueness and ordering

What this integration settles. Each line states the behaviour that holds.

* **Composite key:** `[SCOPE_KEY] + [PRIMARY_ENTITY_CODE]` `L-n`
* **Delivery guarantee:** [at-most-once | at-least-once], set by `[the transport]`. [What the handler does when the broker redelivers.] `L-n`
* **Repeat delivery:** [What a second copy of the same payload does to the stored record.] `L-n`
* **Out-of-order events:** [The property compared, and what happens when the arriving value is older.] `L-n`
* **Records absent from a full sync:** [What the integration does with them.] `L-n`
* **Record-level failure in a batch:** [What is logged, and what happens to the rest of the batch.] `L-n`
* **Masked properties:** [The personal-data properties this flow carries, and the declaration each side holds.] `L-n`

---

## 7. Acceptance

Each line states what holds once the mapping is built. Keep the lines this requirement carries.

| # | Holds when | Covers |
| :-- | :--- | :--- |
| A-1 | Every row of section 4 has a mapper that produces its target property. | 4 |
| A-2 | Every enum in section 5 maps to its target value, and an unlisted value takes the fallback. | 5 |
| A-3 | A repeated payload leaves the record count unchanged, per section 6. | 6 |
| A-4 | An out-of-order event leaves the stored record at the state section 6 names. | 6 |
| A-5 | Every flow in section 3 runs end to end against the mocks at `[path/to/mock/suite]`. | 3 |

---

## 8. Notes carried by the specs

*(Delete this section when the mapping needs no open decision. A row here names a decision the
specs' Notes section holds, so this document states which of its rows waits on it.)*

| Note | Waits on | Gates |
| :--- | :--- | :--- |
| `N-1` | [The decision, in one clause.] | 4.2 · 6 |
