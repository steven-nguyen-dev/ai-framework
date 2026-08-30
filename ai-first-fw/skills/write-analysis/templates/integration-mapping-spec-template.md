# [INTEGRATION_NAME] Data Mapping & Technical Specification Template

**Document Identifier:** `[PROJECT_CODE]-[INTEGRATION_NAME]-mapping-spec.md`  
**Reference Tracking:** `[JIRA_ISSUE_KEY]` — *[Feature / Initiative Title]*  
**Source System / Origin:** `[SOURCE_SYSTEM]` (e.g. Marketplace, Carrier, ERP, POS, 3PL, Custom Channel)  
**Target Internal System:** `[TARGET_SYSTEM]` (e.g. OMS, WMS, OXM, PT, Inventory Core)  
**Target Interface Spec:** `[TARGET_INTERFACE_REFERENCE]` (e.g. OpenAPI / Swagger, AsyncAPI, Protobuf, GraphQL)  
**Document Author / Team:** `[Author / Team Name]`  
**Target Release / Version:** `[vX.Y.Z / Sprint N]`  

---

## 1. Executive Summary & Architectural Scope

### 1.1 Integration Objective
* **Problem Statement:** Briefly describe what business process is being automated or integrated.
* **Scope Boundary:** Specify what data flows in-scope (Ingress / Egress) and what is explicitly out-of-scope.

### 1.2 Communication & Protocol Pattern
*(Select the active pattern and remove unused ones)*
* **Pattern A: Synchronous REST / GraphQL** (Real-time HTTP Request/Response)
* **Pattern B: Asynchronous Job / Polling** (Trigger Request $\rightarrow$ Poll Status $\rightarrow$ Fetch Result Document)
* **Pattern C: Event-Driven / Webhooks** (Pub/Sub, Kafka, Webhook payloads, Message Queues)
* **Pattern D: Scheduled File / Batch** (SFTP, S3, CSV, XML, EDI)

---

## 2. Structural Archetype & Hierarchy Alignment

Choose the structural topology of the data being mapped:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DATA TOPOLOGY SELECTION (Choose applicable archetype)                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ • ARCHETYPE 1: Flat / Key-Value (e.g. Inventory counts, Price tiers, Tracking numbers) │
│ • ARCHETYPE 2: Header-Detail / Master-Child (e.g. Orders + Items, ASNs + Lines)        │
│ • ARCHETYPE 3: Hierarchical / Tree / Graph (e.g. Categories, Warehouse Bins, BOM Kits) │
│ • ARCHETYPE 4: Dynamic / Extensible EAV (e.g. Custom fields, Dynamic product schemas)  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Entity Level / Component Alignment Matrix

| Level / Layer | `[SOURCE_SYSTEM]` Source Concept | `[TARGET_SYSTEM]` Target Component | Structural Archetype | Alignment Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Scope / Tenant** | `[Source Account / Market ID]` | `[Tenant / Store / Channel Code]` | Context Header | Enforces multi-tenant isolation |
| **Primary Entity** | `[Source Parent / Header]` | `[Target Master / Header Record]` | Flat / Header | Main entity container |
| **Nested Sub-Entity** | `[Source Line / Child Item]` | `[Target Child / Line Item / Sub-Node]` | Child / Array | 1-to-many relationship |
| **Dynamic Attributes** | `[Source Custom Fields / Schema]` | `[Target Dynamic Attributes / EAV]` | Dynamic (Key-Value) | Variable metadata fields |

---

## 3. Endpoints & Interface Inventory

### 3.1 `[SOURCE_SYSTEM]` Interfaces (Source of Truth)
| # | Interface / Method & Path | Invocation Trigger | Payload Format | Throttling / Rate Limits |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `[POST /path/to/source]` | User Action / Event / Cron | `JSON / XML / CSV` | `[e.g. 5 req/sec]` |
| 2 | `[GET /path/to/source/{id}]` | Status Check / Fetch | `JSON / XML / Stream` | `[e.g. 10 req/sec]` |

### 3.2 `[TARGET_SYSTEM]` Interfaces (Consumer / Persistence)
| # | Interface / Method & Path | Operation Mode | Payload DTO / Schema | Persistence Action |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `[POST /rest/v1/bulk_endpoint]` | Bulk / Batch Ingestion | `[BulkRequestDTO]` | Idempotent Upsert |
| 2 | `[POST /rest/v1/single_endpoint]` | Single / Delta Update | `[SingleRequestDTO]` | Create / Update |

---

## 4. End-to-End Operational Workflows

### Flow 1: Full / Initial Synchronization Flow
```
[Trigger: Manual / Connection Setup] ──► [1. Fetch Source Data] ──► [2. Transform & Validate] ──► [3. Push to Target]
```
1. **Trigger & Fetch:** Initiates request to `[SOURCE_SYSTEM]` (sync request, async report, or batch export).
2. **Transform & Normalize:** Parses source format (XML/JSON/CSV), maps fields, handles data type casting.
3. **Ingest & Persist:** Calls `[TARGET_SYSTEM]` bulk endpoint; records transaction logs and entity mappings.

### Flow 2: Delta / Event-Driven Maintenance Flow
```
[Trigger: Webhook / Version Check] ──► [1. Filter Delta Changes] ──► [2. Target Upsert (No Full Sync)]
```
1. Detects delta via webhook or checksum/version hash comparison.
2. Updates only changed records in `[TARGET_SYSTEM]` without repeating the full data dump.

### Flow 3: Downstream Business Flow
Describes how downstream transactional processes (e.g. order fulfillment, stock deduction, price computation) consume the stored data without querying the external source API at runtime.

---

## 5. Field Mapping & Transformation Specification

### 5.1 Primary / Header Entity Mapping
* **Source Object / Node:** `[source_payload.header_object]`
* **Target Interface / Model:** `[TARGET_SYSTEM] / [TargetModelDTO]`

| # | `[SOURCE_SYSTEM]` Field Path | `[TARGET_SYSTEM]` Property | Data Type | Transformation & Business Logic | Nullable? | Example Value |
| :-: | :--- | :--- | :--- | :--- | :-: | :--- |
| 1 | `$.source_id` | `code` / `id` | `string` | Cast to string, trim whitespace | No | `"ID_00123"` |
| 2 | `$.source_name` | `name` | `string` | Direct map | No | `"Standard Name"` |
| 3 | `$.status_code` | `status` | `string` | Enum mapping (see Section 6) | No | `"ACTIVE"` |
| 4 | `$.timestamps.created` | `created_at` | `date-time` | Parse ISO 8601 UTC string | Yes | `"2026-08-26T10:00:00Z"` |
| 5 | `[Context / Environment]` | `channel_code` | `string` | Injected store/tenant identifier | No | `"STORE_US_01"` |

---

### 5.2 Child / Nested Entity / Line Items Mapping
* **Source Object / Node:** `[source_payload.line_items[]]`
* **Target Interface / Model:** `[TARGET_SYSTEM] / [TargetChildDTO[]]`

| # | `[SOURCE_SYSTEM]` Field Path | `[TARGET_SYSTEM]` Property | Data Type | Transformation & Business Logic | Nullable? | Example Value |
| :-: | :--- | :--- | :--- | :--- | :-: | :--- |
| 1 | `$.line_items[*].item_id` | `line_item_code` | `string` | Unique child entity reference | No | `"LINE_01"` |
| 2 | `$.line_items[*].quantity` | `qty` | `integer` | Parse integer, default to 0 | No | `5` |
| 3 | `$.line_items[*].unit_price`| `price` | `number` | Numeric decimal value | No | `29.99` |
| 4 | `$.line_items[*].parent_ref`| `parent_code` | `string` | Link to parent entity code | Yes | `"ID_00123"` |

---

### 5.3 Dynamic Attributes / Metadata / Custom Fields Mapping (If applicable)
* **Source Object / Node:** `[source_payload.custom_attributes{}]`
* **Target Interface / Model:** `[TARGET_SYSTEM] / [AttributeListDTO]`

| # | Source Property Key | Target Attribute Field | Target Data Type | Transformation Rule | Example Source $\rightarrow$ Target |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 1 | `$.attributes.color` | `field_code: "color"` | `singleSelect` | Map allowed values to `field_values[]` | `"red"` $\rightarrow$ `{"name": "Red", "value": "red"}` |
| 2 | `$.attributes.dimensions` | `field_code: "dim"` | `textField` | Flatten nested object or capture unit | `{"w": 10, "u": "cm"}` $\rightarrow$ `"10 cm"` |

---

## 6. Enum & Value Translation Matrix

| Domain Property | Source Value (`[SOURCE_SYSTEM]`) | Target Value (`[TARGET_SYSTEM]`) | Fallback / Default Behavior |
| :--- | :--- | :--- | :--- |
| **Status / State** | `"PENDING_APPROVAL"`, `"IN_REVIEW"` | `"under_review"` | Default to `"draft"` if unknown |
| **Status / State** | `"PUBLISHED"`, `"ACTIVE"`, `"1"` | `"active"` | — |
| **Status / State** | `"ARCHIVED"`, `"DELETED"`, `"0"` | `"inactive"` | — |
| **Type Classification** | `"STANDARD_ITEM"` | `"simple"` | Default to `"simple"` |
| **Type Classification** | `"KIT_OR_BUNDLE"` | `"kit"` | — |

---

## 7. Data Type & Formatting Standards

| Source Construct | Target API Data Type | Target UI / Processing Behavior | Transformation Rule |
| :--- | :--- | :--- | :--- |
| `String with Enum / Options` | `singleSelect` / `COMBO_BOX` | Single-choice Dropdown | Populates `field_values: [{name, value}]` |
| `Array of Strings / Enums` | `multiSelect` | Multi-select Checkbox / Tags | Populates array of values |
| `Open Text (unbounded)` | `textField` / `string` | Standard Text Input Box | Direct string transfer |
| `Large / Multiline Text` | `richText` / `text` | Multiline Textarea / Editor | Preserves safe HTML/Markdown |
| `Numeric / Floating Point` | `number` / `integer` | Numeric Validation Box | Apply min/max boundary constraints |
| `ISO 8601 Timestamp` | `datefield` / `date-time` | Date/Time Picker | Standardize to UTC `YYYY-MM-DDTHH:mm:ssZ` |
| `Nested Key-Value Object` | `treeSelect` / `json` | Structured Sub-form | Flatten with dot notation or store raw JSON |

---

## 8. Multi-Tenancy, Idempotency & Error Handling

1. **Composite Uniqueness Key:** Define the unique composite key: `[TENANT_ID / CHANNEL_CODE] + [PRIMARY_ENTITY_CODE]`.
2. **Idempotency Strategy:** Repeated payloads must update existing records without creating duplicates or duplicating sub-items.
3. **Out-of-Order Events:** If using webhooks or queues, compare event timestamps / version hashes (`version_timestamp >= stored_timestamp`).
4. **Soft Deletion / Reconciliation:** Missing records from full synchronization dumps must be flagged as `inactive` or `archived`, never hard-deleted.
5. **Partial Failures & Circuit Breaking:** Record-level failures in batch payloads must be logged with source request ID, error code, and retry eligibility without failing the entire batch.
