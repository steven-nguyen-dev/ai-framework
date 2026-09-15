# IA-5105-US1 — the test-suite rewrite plan

Target tree: `/Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-test-servers/amazon/IA-5105-US1/`

Authority (wiki `plan/amazon-test-suites#00-authority`): the IA-5105 deliverables override the Jira
ticket. Where a deliverable and a producer disagree, **assert the deliverable and let the case fail
red**. Never soften an assertion, never edit a mock so a case passes.

**This plan is executable without reading the deliverables: every expected value is stated inline.**

Ownership after this plan: `requirements.py` and `suite-taxonomy.py` are **done** (rewritten and run,
2026-09-13). `suite-connect-us.py`, `suite-connect-non-us.py` and `suite-all.py` are another pane's;
sections 5–7 are written to be self-contained for that pane.

---

## 0. The facts a rewriter needs, stated once

### 0.1 The concept

An OMS **category IS an Amazon product type** (`SHOES`, `LUGGAGE`, `AUTO_PART`) — never a browse-node
id, never the legacy `parentCode_childBrowseNodeId` path. A **browse node is a reference value, not a
taxonomy**: only its id and its breadcrumb path travel, and they travel as *picker rows inside
`category_attributes`*. There is no browse-node entity, no hierarchy, no reconciliation, and **no
request-level `browse_node_ids` array** — that ask is withdrawn.

### 0.2 The envelope of `POST /rest/v1/bulk_categories_attributes` (one call per product type)

| Field | Rule |
|---|---|
| `store_code`, `marketplace_code`, `category_code` | the connected store, its marketplace, the product type |
| `definition_version` | Amazon's `productTypeVersion.version`, **opaque** — never parsed or ordered; a date-shaped value is a defect |
| `latest_version` | Amazon's `productTypeVersion.latest`; a definition not marked latest is **refused** |
| `schema_checksum` | Amazon's own `schema.checksum`, verified (MD5) against the downloaded bytes — never recomputed locally |
| `raw_schema_json` | the schema document **verbatim**, unknown keys intact |
| `definition_status` | one of **six**, below |
| `definition_status_reason` | **absent** when `AVAILABLE`, present otherwise — with exactly one exception (§0.5) |
| `category_attributes[]` | the flattened schema; **the key is ABSENT**, not `[]`, for `UNAVAILABLE`, `PARSE_FAILED`, `FETCH_FAILED` |

**Absent keys are absent, not null.** Gson drops nulls, so no key is sent on the wire.

### 0.3 `definition_status` — six values, and what drives each

| Value | Driver | Wire consequence |
|---|---|---|
| `AVAILABLE` | clean schema | attributes complete; **no** `definition_status_reason` key |
| `UNAVAILABLE` | HTTP 404 on `getDefinitionsProductType` | **terminal, no retry owed**; reason `"Amazon defines no schema for <PRODUCT_TYPE>"`; no `raw_schema_json`; no `category_attributes` key |
| `PARSE_FAILED` | schema breaches depth 9, or an unresolvable `$ref` | `raw_schema_json` **still present**; no `category_attributes` key |
| `SCHEMA_OMITTED` | serialized message > 900 KB (921,600 B) | `raw_schema_json` dropped; `category_attributes` **complete**; body ≤ 900 KB |
| `VALUES_OMITTED` | still > 900 KB after dropping the schema | every `field_values` is `[]`; rows survive with `field_code`/`data_type`/`validation` |
| `FETCH_FAILED` | retries exhausted on a transient error, a failed schema download, a missing schema link, or a checksum mismatch | **a retry IS owed**; no `raw_schema_json`; no `category_attributes` key |

`FETCH_FAILED` must **never** be folded into `UNAVAILABLE`. Assert **six exactly** — a seventh value
is a contract breach, not a feature.

**Exact reason strings** (verbatim in `AmazonDefinitionsUtility.fetchDefinition:218-264`):
- `"downloaded schema does not match Amazon's checksum"`
- `"Amazon returned a definition it does not mark latest"`
- `"schema download failed"`
- `"definition carries no schema link"`
- `"Amazon defines no schema for " + productTypeCode`

### 0.4 Attribute rows

- `field_code` = the **dot-joined** property path (`package_info.dimensions.length`). Amazon names
  contain `_` and never `.`, so the dot is the only unambiguous join, and uniqueness is an invariant
  of the path rather than a de-duplication step. **The underscored form is the defect this ticket
  removes.**
- `field_parent_code` = the parent's `field_code`; **absent** at top level. `field_parent_id` and
  `id` stay **unset** on every Amazon row.
- `field_criteria` ∈ `independent` / `is_parent` / `is_child`. An intermediate node is `is_parent`
  **and** carries `field_parent_code`.
- Rows arrive **parent-first**: every `field_parent_code` names a row already emitted **earlier in the
  same array**. Assert on array ORDER, not set membership.
- `data_type` ∈ `string`, `textField`, `richText`, `date`, `datefield`, `singleSelect`,
  `multiSelect`, `COMBO_BOX`, `img`, `treeSelect` **plus the five added**: `number`, `integer`,
  `boolean`, `object`, `array`. OMS stores unknown values (free VARCHAR) — this is answered, not open.
- `format` → `date` ⇒ `data_type: "date"`; `date-time` ⇒ `datefield`; `uri` and any unknown format ⇒
  `string`. Must also work when the format sits on a `$ref` target or an `anyOf`/`oneOf` branch.
- `validation` carries **only the ten keys Amazon states**: `minLength`, `maxLength`,
  `maxUtf8ByteLength`, `pattern`, `minimum`, `maximum`, `minItems`, `maxItems`, `minUniqueItems`,
  `maxUniqueItems`. **An absent key means no constraint, never zero.** `multipleOf`, `item_maxLength`
  and `item_required` are **not** contract keys.
- `default` = Amazon's default (e.g. `manufacturer.language_tag` → `"fr_FR"`).
- Allowed values never change `data_type`: an enum of strings is `data_type: "string"` +
  `option_type: true` + populated `field_values[{name, value}]`, **not** `singleSelect`/`multiSelect`.
- **Arrays**: parent row `{data_type: "array", field_type: "attributes", field_criteria: "is_parent",
  validation: {minItems, maxItems}}` with **no** `maxLength`; explicit child row
  `{field_code: "<parent>.value", field_parent_code: "<parent>", field_criteria: "is_child",
  data_type: "string", validation: {maxLength}}` with **no** `minItems`. Assert the **absence** in
  each direction.
- **Measurements** are three rows: `is_parent` object, `<x>.value` child with numeric `data_type` and
  bounds, `<x>.unit` child with `option_type: true` and unit `field_values`. The unit must **not**
  appear as a key inside the parent row.
- `marketplace_code` on every row, equal to the request's.

### 0.5 Limits

- Nesting depth **9**; a breach ⇒ `PARSE_FAILED`, raw document still sent.
- **4 children per node.** A wider node publishes its first 4 **in Amazon's own property order**, the
  rest omitted from `category_attributes` and **present in `raw_schema_json`**; `definition_status`
  stays `AVAILABLE` and `definition_status_reason` reads `"<node> states <n> children; 4 published"`,
  several joined by `"; "`. **This is the one case where a reason rides an `AVAILABLE` definition.**
- `RAW_SCHEMA_MAX_BYTES` = 921,600 (900 KB). `MAX_FIELD_VALUES_PER_ATTRIBUTE` = 8000.
- `DEFINITIONS_MAX_RETRIES` = 4 ⇒ **5 attempts** when exhausted. `DEFINITIONS_REQUESTS_PER_SECOND` = 5
  (assert as a **ceiling**, never a cadence — the backoff is jittered).
- `BROWSE_NODE_REFRESH_HOLD_OFF_MILLIS` = 6 h.

### 0.6 Classification rows

| | Non-US (FR, DE, JP…) | US (`amazon_sp_us`) |
|---|---|---|
| Parent | `recommended_browse_nodes` | `item_type_keyword` |
| | `is_parent`, `data_type: array`, `validation {minItems 1, minUniqueItems 1, maxUniqueItems 1000}` | `is_parent`, `data_type: array`, `validation {minItems 1, maxItems 1}` |
| Picker | **`recommended_browse_nodes.value`** (dotted) | **`item_type_keyword.value`** (dotted) |
| | `is_child`, `string`, `option_type: true` | same |
| | `value` = the numeric node id | `value` = the keyword token (`"carry-on-luggage"`) |
| | `name` = breadcrumb path joined by **`" > "`** | `name` = display label or path |
| Third row | `recommended_browse_nodes.marketplace_id` | `item_type_keyword.marketplace_id` |

Where no node or keyword applies: the picker publishes **`field_values: []` and `free_text: true`**,
`definition_status` stays `AVAILABLE`, and the run does not stall. A US node served **without**
`<attribute name="item_type_keyword">` contributes **no** option — its id must appear nowhere.

### 0.7 Identity

`amazon_sp_us` = `ATVPDKIKX0DER` / `en_US` · `amazon_sp_fr` = `A13V1IB3VIYZZH` / `fr_FR` ·
`amazon_sp_de` = `A1PA6795UKMFR9` / `de_DE` · `amazon_sp_jp` = `A1VC38T7YXB528` / `ja_JP` ·
`amazon_sp_es` = `A1RKKUPIHCS9HS` / `es_ES` · `amazon_sp_au` = `A39IBJ37TRP1C6` / `en_AU` ·
`amazon_sp_uk` = `A1F83G8C2ARO7P` / `en_GB`.

Definition request: `marketplaceIds` = exactly one id, `requirements=LISTING_PRODUCT_ONLY`,
`requirementsEnforced=ENFORCED`, `locale` per the map, `parentageLevel=NONE`, **`productTypeVersion`
unset** (= LATEST), **`sellerId` absent** (recorded deliberately, open question O1).
Search request: one `marketplaceIds`, **no `keywords`**, **no page token** — `ProductTypeList`
v2020-09-01 has none, so AC-7 is closed with nothing to write.

### 0.8 What a suite must NOT assert (N1–N17) — asserting any of these fails against correct code

`IS_LAST_REQUEST=true` · definition messages on the store-connect topic · a held-message buffer /
`carriesTheChain` / `PendingDefinition` · `StoreConnectImpl` jumping to `FETCH_PRODUCTS`, or any
`amazon_sp` constant in the shared connector · **any distributed lock** (Redis keys, TTLs,
`setIfAbsent`) · cross-replica duplicate-run prevention (AC-17 holds **within one replica only**) ·
`item_type_keyword` reaching a listing column · any stage-progress/percentage/completion signal to
OMS (FR-16 is OMS-side) · a request-level `browse_node_ids` array · **a request for
`GET_FLAT_FILE_BROWSE_TREE_DATA`** (it does not exist in SP-API — assert its *absence*) · discrete
browse-node entities or FR-5 reconciliation · `if`/`then`/`else` or root `allOf` parsed into rows
(assert their *survival in `raw_schema_json`*) · `dependencies`/`dependentRequired` · product-type
pagination · `field_parent_id`/`id` populated · FR-13 product-side fields.

N8 is **withdrawn**: a variant inheriting its parent's browse node *is* assertable.

### 0.9 What cannot be proven in this harness

1. **There is no JPluger under test.** `transformer.py` is a stand-in; the suites are the only client
   Amazon sees. Every `[JP]` row (retry counts, Redis checkpoints, operator traces, rate pacing,
   queueing, chain release) has **no observation point** — those cases are `blocked` with the reason,
   never green, never red.
2. **The Amazon mock serves no fixture** for `latest:false`, a mismatching checksum, a missing schema
   link, an empty product-type list, or 429/500/403 on the definitions routes. `amazon.mock.json`
   declares one rule per `(productType, marketplaceId)` plus a `NOTFOUND` marker. **Do not add
   fixtures to the shared mock** — block the case and name the fixture it needs.
3. **`FATAL` is documented but not implemented** on `GET /reports/2021-06-30/reports/{reportId}`:
   every id carrying the marker answers `processingStatus: DONE` with a `reportDocumentId`. Found by
   this rewrite; reported, not repaired.
4. **The mock hardcodes `127.0.0.1:23103`** into every `schema.link.resource` and report URL. A suite
   on another port **must** rewrite the host (`requirements.schema_link_path`) or it reads another
   process's mock.
5. **The Amazon mock's call log persists across runs.** Take a high-water mark
   (`requirements.oms_high_water(BASE_AMAZON)`) before firing and pass `since=` — otherwise a case is
   judged on an earlier run's bytes.
6. **The DE browse tree is currently the 315 MB generated file.** Use the **FR** tree for browse-tree
   cases: the 300 MB generator belongs in a performance run, not a correctness suite.
7. Three fixtures are genuine captures (DE `PRODUCT`, ES `PRODUCT`, AU `AUTO_PART`); **US `LUGGAGE`
   and FR `SHOES` are SYNTHETIC** and nothing seen through them may be cited as Amazon's behaviour.
   The only `item_type_keyword` enum fixture is hand-authored.
8. OMS storage semantics — upsert, de-duplication, reparse-without-deleting — are **OMS's** by
   decision and are not observable: scope every such row to *what was sent, per run*.

---

## 1. Verdicts — `suite-taxonomy.py` (15 existing cases) — **DONE**

| Case | Verdict | Reason |
|---|---|---|
| `SRCH-1` | **KEEP (rewritten)** | Now also asserts one `marketplaceIds` per request, no `keywords`/page token, and per-entry marketplace scoping (B3). |
| `TAX-US-1` | **MERGE INTO `DEF-PARAMS-1`** | Its envelope-echo half is B2, asserted once for five markets instead of three times. Its "US LUGGAGE carries `capacity`" check is **deleted**: an assertion on the suite's own fixture. |
| `TAX-FR-1` | **MERGE INTO `DEF-PARAMS-1`** | Same echo. The orphan-`$ref` and `language_tag` checks are fixture assertions; the behaviour they guard (an unresolvable `$ref` ⇒ `PARSE_FAILED`) belongs at the wire, in `suite-connect-non-us`. |
| `TAX-EU-1` | **KEEP (rewritten)** | Now asserts differing `definition_version` and `schema_checksum` as well as differing property sets — A1's "assert on content, never on an echoed marketplaceId". |
| `TAX-AU-1` | **REWRITE** | Contract changed: the old check cited `DEFINITIONS_MAX_NESTING_DEPTH=12`; it is **9**. Now the B19 precondition — which captures breach the 4-child cap and which must not. |
| `TAX-404` | **KEEP (rewritten)** | Adds the wire consequence and the honest note that the 404 scenario is unrealistic. |
| `TAX-CKSUM` | **KEEP (rewritten)** | Now verifies a real MD5 (US `LUGGAGE`) as well as the empty-checksum fail-open, and records that the mismatch branch has no fixture. |
| `TAX-CAT-1` | **KEEP (rewritten)** | A2 restated from the contract; absorbs `TAX-CAT-2`'s key scan. |
| `TAX-CAT-2` | **MERGE INTO `TAX-CAT-1`** | Strict subset — it re-posted and re-scanned the same bodies. Its second half, a scan for browse-node-shaped **values**, is **withdrawn**: a numeric node id is now a legal `field_values` entry. |
| `TAX-CAT-3` | **KEEP (rewritten)** | FR-11/AC-20 at the category level. |
| `TAX-CAT-CR1` | **DELETE** | Withdrawn by authority: upsert and de-duplication are OMS's by decision, and no observation of a mock can settle them. Id retired, never reused. |
| `TAX-BT-REPORT` | **KEEP (rewritten)** | Now B16 in full: the whole flow, the parsed leaves, the `" > "` separator, and **zero** flat-file requests. |
| `TAX-BT-HUGE-300MB` | **DELETE** | Withdrawn: the 300 MB generator belongs in a performance run, not the correctness suite. |
| `TAX-CAT-ATTR-1` | **DELETE** | Strict subset of `NONUS-RBN-DE`, which asserts the same picker pair with more detail — and it asserted the *underscored* picker code, which is now the defect. |
| `TAX-BT-US-1` | **DELETE** | Duplicate of `US-NOREPORT-1`, which counts reports in the mock's own store; this one only re-asserted the fixture's schema shape. |

**New in `suite-taxonomy.py`:** `DEF-PARAMS-1`, `TAX-SEQ-1`, `TAX-LATEST-1` (blocked),
`TAX-CAT-ORDER-1`, `TAX-ATTR-INV-1`, `TAX-BT-FATAL-1` (blocked), `TAX-BT-ISO-1`, `TAX-BT-DUP-1`.
Final: **16 cases** (§5).

---

## 2. Verdicts — `suite-connect-us.py` (33 existing cases)

| Case | Verdict | Reason |
|---|---|---|
| `US-PRE-1` | **DELETE** | Preflight is the runner's job and already reports both mocks; a case that asserts its own preflight adds no coverage. |
| `US-AUTH-1`, `US-AUTH-EXPIRE`, `US-NEG-UNAUTHORIZED` | **MERGE INTO `US-AUTH-1`** | Three cases exercising the mock's LWA endpoint. Real token exchange is untestable (§0.9.1) and no matrix row asks for it; one case records that the mock authenticates, and says it proves nothing about SP-API. |
| `US-CAT-1` | **KEEP (rewrite)** | A2 for the US store. Drop the `children`/`parent_code` checks — no contract row states them. |
| `US-CAT-MULTI` | **MERGE INTO `US-CAT-1`** | Strict subset: same postings, count parity. |
| `US-PTD-SEARCH` | **DELETE** | Duplicate of `SRCH-1` (taxonomy), which asserts the same search for five markets. |
| `US-DEF-LUGGAGE` / `-CLOTHING` / `-ELECTRONICS` / `-TOYS` | **MERGE INTO one parameterised `US-DEF-1`** | Four copies of one envelope+schema fetch differing only in a fixture property name (`capacity`, `size`, `voltage`, `cpsia_cautionary_statement`) — assertions on the suite's own fixtures. |
| `US-MAP-LUGGAGE` / `-CLOTHING` / `-ELECTRONICS` / `-TOYS` | **REWRITE, merged into `US-MAP-1`** | Contract changed twice over: they assert underscored codes (`capacity_value`) and expected row counts derived from the superseded mapping spec. Reborn as one parameterised case asserting §0.4 on the *received* body. |
| `US-WITHDRAW-1` | **KEEP (rewrite)** | Still right for keys (N10); drop any assertion that a US store emits no `recommended_browse_nodes` **row** — B14 now owns that as the mirror-assert. |
| `US-NOREPORT-1` | **KEEP** | Counts reports in the mock's own store, which is the only way to prove a report was not requested. |
| `US-ENV-1` | **REWRITE** | Contract changed: it asserts **four** `definition_status` values; there are **six**. Add the absent-key rules (§0.2) and the `raw_schema_json` deep-equal with a planted unknown key (B4). |
| `US-VOCAB-1` | **REWRITE** | Its central assertion is now **inverted**: "no `field_code` carries a literal dot" is exactly what the contract requires. Becomes the US half of §0.4 — dotted paths, parent-first order, `id`/`field_parent_id` absent. |
| `US-CR3-1` | **DELETE** | The change request it records is **answered**: `data_type` is a free VARCHAR and `object`/`array` are accepted. Replaced by a scored check inside `US-VOCAB-1`. |
| `US-STATUS-1` | **REWRITE → `US-STATUS-1`** | Four statuses become **six**, driven in one run, asserted on the body OMS received rather than on the transformer's return value. |
| `US-RAW-1` | **REWRITE** | It asserts `schema_checksum` equals a **locally recomputed** MD5. The contract makes it Amazon's own stated value, passed through: a locally recomputed digest always matches itself and defeats change detection silently. |
| `US-E2E-LUGGAGE`, `US-E2E-MULTI`, `US-LOG-1` | **MERGE INTO `US-ENV-1`** | All three post and then read the same bodies back; the envelope case already reads from the log. |
| `US-RECON-1` | **DELETE** | Asserts soft-inactivation reconciliation, which is OMS's by decision and is not sent on any wire. |
| `US-LEGACY-1` | **KEEP** | Cheap regression guard that the legacy endpoints still answer; rename its note — the preserved fields are `id`/`field_parent_id`, which Amazon rows leave **unset**. |
| `US-ERR-1`, `US-NEG-SERVER-500` | **MERGE INTO `US-ERR-1`** | Same fault injection at the OMS hop, twice. |
| `US-NEG-INVALID-INPUT`, `US-NEG-RATE-LIMIT-429` | **DELETE** | They assert the mock's own error shapes on `/catalog` and `/auth`, endpoints this ticket does not use. C2's real content (a throttled *definitions* call is retried without duplicating stored data) cannot be driven (§0.9.2) and is recorded as blocked in `NONUS-RETRY-1`. |
| `US-NEG-RESOURCE-404` | **MERGE INTO `US-STATUS-1`** | The `UNAVAILABLE` branch of the status matrix. |
| `US-NEG-MALFORMED-PARSE` | **MERGE INTO `US-STATUS-1`** | The `PARSE_FAILED` branch; its own assertion ("0 parsed attributes") is now wrong — the key is **absent**, not empty. |

---

## 3. Verdicts — `suite-connect-non-us.py` (39 existing cases)

| Case | Verdict | Reason |
|---|---|---|
| `NONUS-PRE-1` | **DELETE** | As `US-PRE-1`. |
| `NONUS-AUTH-1`, `NONUS-NEG-AUTH-ISOLATION` | **MERGE INTO `NONUS-AUTH-1`** | One case; it proves the mock, not SP-API. |
| `NONUS-CAT-1` | **REWRITE** | Asserts `is_leaf_node`, a field no contract row states. Becomes A2 for the non-US stores. |
| `NONUS-MAP-FR` / `-DE` / `-ES` / `-AU` / `-GB` / `-JP` | **REWRITE, merged into `NONUS-MAP-1`** | Six copies of one walk with hardcoded row counts (11/147/329/449/17/13) from the superseded mapping spec, asserting underscored codes (`item_name_value`, `item_weight_unit`). One parameterised case asserting §0.4 against each schema's own constructs. |
| `NONUS-RBN-DE` | **REWRITE** | The right subject, the wrong codes: `recommended_browse_nodes_value` is now `recommended_browse_nodes.value`. Add the **third** row (`.marketplace_id`) and the `" > "` separator. This is B13. |
| `NONUS-RBN-ES-AU` | **KEEP (rewrite)** | The three real captures genuinely disagree; keep the case, fix the codes. |
| `NONUS-RBN-EMPTY` | **REWRITE** | Contract changed: the empty picker now publishes **`field_values: []`** and `free_text: true`. The old case asserts the row arrives with **no** `field_values` key. This is B15. |
| `NONUS-REPORT-1` | **KEEP** | One report per marketplace with `reportOptions.MarketplaceId` stated — the live trap. |
| `NONUS-PICKER-ISO` | **KEEP (rewrite)** | The strongest form of A1; fix the picker code. |
| `NONUS-PATH-1` | **KEEP** | Still blocked, still true, and the reason is now a fixture property rather than a requirement defect. |
| `NONUS-WITHDRAW-1` | **KEEP (rewrite)** | Keys only. Delete its third bullet — "no browse-node-shaped value on any row other than the picker" is withdrawn, because `.marketplace_id` and the picker both legitimately carry ids. |
| `NONUS-ENV-1` | **REWRITE** | Four statuses ⇒ six; add the absent-key rules. |
| `NONUS-VOCAB-1` | **REWRITE** | "No `field_code` carries a literal dot" is inverted by decision 2. |
| `NONUS-ROWS-1` | **DELETE** | Pins 147/329/449 rows, numbers measured under the superseded fold-versus-expand argument and before the 4-child cap, which now removes 9 rows from `purchasable_offer` alone on ES and AU. A count that must change whenever a cap changes is a brittle restatement of `NONUS-MAP-1`. |
| `NONUS-CR3-1` | **DELETE** | Answered, as `US-CR3-1`. |
| `NONUS-STATUS-1` | **MERGE INTO `US-STATUS-1`** | The six statuses are marketplace-independent; drive them once. Keep only the multibyte oversize variant (below). |
| `NONUS-RAW-1` | **REWRITE** | Same recomputed-checksum defect as `US-RAW-1`. |
| `NONUS-ISOLATION-1` | **MERGE INTO `NONUS-PICKER-ISO`** | Same subject, weaker form (counts rather than content). |
| `NONUS-FR-1` / `-DE-1` / `-ES-1` / `-AU-1` / `-GB-1` / `-JP-1` | **MERGE INTO `NONUS-MAP-1`** | Six end-to-end cases whose assertions are a status code and a row count already asserted by the mapping case. |
| `NONUS-RECON-1` | **DELETE** | As `US-RECON-1`. |
| `NONUS-ASSERT-1` | **DELETE** | Asserts a mock state file (`taxonomy_pushes.json`), which is the mock's bookkeeping, not the contract. |
| `NONUS-LOG-1` | **MERGE INTO `NONUS-ENV-1`** | The envelope case already reads the log. |
| `NONUS-ENCODING-1` | **KEEP** | UTF-8 fidelity through the whole hop is cheap and real; fold the "French accents" half of `NONUS-MAP-FR` into it. |
| `NONUS-NEG-RESOURCE-404` | **MERGE INTO `US-STATUS-1`** | Same branch, second marketplace. |
| `NONUS-NEG-RATE-LIMIT` | **REWRITE → `NONUS-RETRY-1` (blocked)** | It asserts the mock's 429 shape on an endpoint this ticket does not call. C2/C3's real content needs a 429 on the *definitions* route, which the mock does not serve (§0.9.2). |
| `NONUS-NEG-OMS-FAULT` | **KEEP** | Genuine fault isolation at the OMS hop: one store's 500 must not stop another's. |
| `NONUS-NEG-CORRUPT-JP` | **MERGE INTO `US-STATUS-1`** | The `PARSE_FAILED` branch again; keep only its UTF-8 assertion, in `NONUS-ENCODING-1`. |
| `NONUS-NEG-OVERSIZE-JP` | **KEEP (rewrite)** | The multibyte byte-length measurement is a real edge the ASCII fixture cannot reach. Fix the expectation: `raw_schema_json` is **absent**, not `None`. |

---

## 4. Coverage matrix → target cases

`*` = new case. `B` = blocked, with the reason named in the case.

| Row | Subject | Target | Owner |
|---|---|---|---|
| A1 | marketplace isolation, differing content | `TAX-EU-1`, `TAX-CAT-3`, `NONUS-PICKER-ISO` | taxonomy + non-US |
| A2 | `category.code` IS the product type | `TAX-CAT-1`, `US-CAT-1`, `NONUS-CAT-1` | all three |
| A3 | `PARSE_FAILED` keeps raw, no attributes key | `US-STATUS-1` | US |
| A4 | product sync does not start over an incomplete stage | `US-CHAIN-1`\* **(B)** — no `[JP]` hop | US |
| A5 | checksum mismatch is not published | `TAX-CKSUM` (positive + comparator mismatch) + `US-STATUS-1` (wire half B) | taxonomy + US |
| A6 | a non-latest definition is refused | `TAX-LATEST-1` (unblocked via `NOTLATEST` marker) | taxonomy |
| A7 | parent-first ordering | `TAX-ATTR-INV-1`\*, `NONUS-MAP-1` | taxonomy + non-US |
| B1 | the call sequence | `TAX-SEQ-1`\* (mock-side only) | taxonomy |
| B2 | definition request parameters | `DEF-PARAMS-1`\* | taxonomy |
| B3 | search scoping and completeness | `SRCH-1`, `TAX-CAT-1` (count parity) | taxonomy |
| B4 | request-level fields land verbatim | `US-ENV-1` (plant an unknown top-level key) | US |
| B5 | six `definition_status` values | `US-STATUS-1` | US |
| B6 | reason absent when `AVAILABLE` | `TAX-ATTR-INV-1`\*, `US-STATUS-1` | taxonomy + US |
| B7 | the ten `validation` keys, nothing defaulted | `TAX-ATTR-INV-1`\* (key set), `US-MAP-1` (values) | taxonomy + US |
| B8 | array parent + explicit child, nothing folded | `US-MAP-1`, `NONUS-MAP-1` | US + non-US |
| B9 | the five `data_type` additions | `US-MAP-1` | US |
| B10 | `format` → `data_type`, incl. `$ref` and `anyOf` | `US-MAP-1` | US |
| B11 | `default`, `field_parent_code`, `id` absent | `TAX-ATTR-INV-1`\*, `NONUS-MAP-1` | taxonomy + non-US |
| B12 | enums don't change `data_type`; unit is a sibling | `NONUS-MAP-1` (FR `heel_height`) | non-US |
| B13 | non-US picker: node id in `value`, path in `name` | `NONUS-RBN-DE`, `NONUS-RBN-ES-AU` | non-US |
| B14 | US picker: keyword token; a node without it is dropped | `US-KEYWORD-1`\* | US |
| B15 | an empty picker publishes as free text | `NONUS-RBN-EMPTY` | non-US |
| B16 | the XML report and the full report flow | `TAX-BT-REPORT` | taxonomy |
| B17 | categories precede attributes | `TAX-CAT-ORDER-1`\* | taxonomy |
| B18 | marketplace and store context on every row | `US-VOCAB-1`, `NONUS-VOCAB-1` | US + non-US |
| B19 | a node wider than 4 truncates and says so | `TAX-AU-1` (precondition) + `NONUS-WIDTH-1`\* (wire) | taxonomy + non-US |
| C1 | 404 ⇒ `UNAVAILABLE`, run continues, not retried | `TAX-404` + `US-STATUS-1`; retry half **(B)** | taxonomy + US |
| C2 | a throttled call is retried, nothing duplicated | `NONUS-RETRY-1`\* **(B)** | non-US |
| C3 | a throttle outlasting retries blocks product sync | `NONUS-RETRY-1`\* **(B)** | non-US |
| C4 | a per-type failure is named and left retryable | `NONUS-RETRY-1`\* **(B)** | non-US |
| C5 | a terminal 403 stops the run | `NONUS-RETRY-1`\* **(B)** | non-US |
| C6 | an empty product-type list is an answer | `SRCH-EMPTY-1`\* (unblocked via `EMPTY` marker) | taxonomy |
| C7 | a schema-download failure ≠ a definition failure | `TAX-DL-FAIL-1`\* / `US-STATUS-1` (unblocked via `SCHEMADLFAIL` marker) | taxonomy + US |
| C8 | a definition with no schema link fails cleanly | `TAX-NO-LINK-1`\* / `US-STATUS-1` (unblocked via `NOSCHEMA` marker) | taxonomy + US |
| C9 | a failed report leaves definitions untouched | `TAX-BT-FATAL-1`\* (unblocked via `CANCELLED` marker) | taxonomy |
| D1 | resumption without re-fetching | `NONUS-RESUME-1`\* **(B)** | non-US |
| D2 | the checkpoint survives a gap | `NONUS-RESUME-1`\* **(B)** | non-US |
| D3 | oversize ⇒ `SCHEMA_OMITTED`, attributes intact | `US-STATUS-1`, `NONUS-NEG-OVERSIZE-JP` | US + non-US |
| D4 | still oversize ⇒ `VALUES_OMITTED` | `US-STATUS-1` | US |
| D5 | `PARSE_FAILED` + oversize keeps `PARSE_FAILED`, reasons joined by `"; "` | `US-STATUS-1` | US |
| D6 | options cut to `MAX_FIELD_VALUES_PER_ATTRIBUTE` (8000) | `US-STATUS-1` | US |
| D7 | every `field_code` is unique | `TAX-ATTR-INV-1`\* | taxonomy |
| D8 | a manual sync repeats and does not duplicate | `NONUS-RERUN-1`\* (per-run counts only) | non-US |
| D9 | a changed definition republishes with the new version | `NONUS-RERUN-1`\* | non-US |
| D10 | a connect during an active sync is queued, not duplicated | `US-CHAIN-1`\* **(B)** | US |
| D11 | rate pacing holds ≤ 5 req/s as a ceiling | `NONUS-RETRY-1`\* **(B)** | non-US |
| D12 | two stores of one seller do not interfere | `NONUS-PICKER-ISO` | non-US |

### 4.1 Blocked-row accounting and empirical classification

The plan's original shorthand of "27 provable / 20 blocked" does not decompose cleanly into matrix rows: exactly 16 rows carried an explicit `(B)` in §4. Rows B1, B2, and B3 were marked mock-side only (proven of the mock rather than JPluger, since no JPluger runs in the harness) rather than blocked, which reaches 19. An empirical audit across a private mock on 23133 classified these rows into three clear groups:

1. **REACHABLE & UNBLOCKED (6 rows):**
   - **A5 (mismatch comparator)**: Driven in `TAX-CKSUM` via unparameterized link (`link.split("?")[0]`) returning generic fallback schema instead of LUGGAGE, proving the comparator rejects mismatched bytes without altering mock fixtures. (The wire half at OMS remains blocked pending producer emitting `definition_status`).
   - **C9**: Driven in `TAX-BT-FATAL-1` using `reportOptions.MarketplaceId="<DE id>-CANCELLED"`, which polls `CANCELLED` with no report document, proving definitions remain untouched in OMS when browse report fails.
   - **A6**: Unblocked by adding a marker-keyed rule on `GET /definitions/.../{productType}` matching `NOTLATEST` in `productType` to return `productTypeVersion.latest = false`. Tested in `TAX-LATEST-1`.
   - **C6**: Unblocked by adding a marker-keyed rule on `GET /definitions/.../productTypes` matching `EMPTY` in `query.marketplaceIds` to return `productTypes: []`. Tested in `SRCH-EMPTY-1`.
   - **C7**: Unblocked by adding a marker-keyed rule matching `SCHEMADLFAIL` in `productType` whose `schema.link.resource` points at an unrouted path (mock 404s). Tested in `TAX-DL-FAIL-1`.
   - **C8**: Unblocked by adding a marker-keyed rule matching `NOSCHEMA` in `productType` returning an envelope with no `schema` key. Tested in `TAX-NO-LINK-1`.

2. **BLOCKED OUTSIDE THE HARNESS — [JP] HOP (10 rows):**
   No JPluger process runs under test (stand-in `transformer.py` only); these rows have no observation point in the local test harness and cannot be unblocked by mock fixtures alone:
   - **A4**: Product sync does not begin over incomplete metadata stage (`US-CHAIN-1`).
   - **C1 (retry half)**: HTTP 404 is not retried (`US-STATUS-1`).
   - **C2**: Throttled call is retried and succeeds without duplicating stored data (`NONUS-RETRY-1`).
   - **C3**: Throttle outlasting retries fails stage and blocks product sync (`NONUS-RETRY-1`).
   - **C4**: Per-product-type failure recorded in operator trace and left retryable in Redis checkpoint (`NONUS-RETRY-1`).
   - **C5**: Terminal 403 stops run without burning retries (`NONUS-RETRY-1`).
   - **D1**: Partway failure resumes without re-fetching settled types (`NONUS-RESUME-1`).
   - **D2**: Checkpoint survives gaps rather than freezing (`NONUS-RESUME-1`).
   - **D10**: Concurrent connect during active sync is queued within replica (`US-CHAIN-1`).
   - **D11**: Rate pacing holds ≤ 5 req/s ceiling (`NONUS-RETRY-1`).

3. **PROVEN OF THE MOCK ONLY (3 rows):**
   Executed against the mock to verify request parameter and sequence recording, proving the mock's discrimination rather than JPluger:
   - **B1**: Call sequence (`TAX-SEQ-1`).
   - **B2**: Definition request parameters (`DEF-PARAMS-1`).
   - **B3**: Scoping and completeness of search (`SRCH-1`).

**True Accounting**: Out of 47 matrix rows: **34 provable** (including the 6 unblocked rows), **3 proven-of-the-mock-only**, and **10 blocked outside the harness** ([JP] hop). Zero rows remain blocked by mock capability.

---

## 5. Final case list — `suite-taxonomy.py` (19, ordered) — **implemented**

Mock steering per case; every case reads the OMS mock's log back rather than its own dict.

1. `SRCH-1` — search for US/FR/DE/ES/AU. 200; the store's own product type present; every returned
   entry scoped to the requested id; one `marketplaceIds` per request; no `keywords`/page token;
   search-level `productTypeVersion` is a bare string. *Steering: none.*
2. `DEF-PARAMS-1`\* — a definition per store. Echoes of `marketplaceIds` (exactly one),
   `requirements=LISTING_PRODUCT_ONLY`, `requirementsEnforced=ENFORCED`, the store's locale;
   `parentageLevel=NONE` and no `sellerId`/`productTypeVersion` in the logged query;
   `productTypeVersion` is an object with `latest: true`; `schema` is a link.
3. `TAX-SEQ-1`\* — FR connect. Exactly 1 search, N definitions in the search's order, N schema
   GETs, search before every definition, each schema after its own definition, each from
   `/s3/ptd-schema/`.
4. `TAX-EU-1` — DE vs ES `PRODUCT`. Links differ; `definition_version` and `schema_checksum` differ;
   locales differ; downloaded property sets differ; both checksums verify.
5. `TAX-AU-1` — every capture walked. AU `purchasable_offer` states 13; AU breaches at exactly
   `fulfillment_availability`, `item_display_dimensions`, `purchasable_offer`,
   `supplemental_condition_information`; FR/DE/US breach nothing; no capture reaches depth 9.
6. `TAX-404` — `NOTFOUND`-marked product type ⇒ 404 + structured errors. *Steering: `NOTFOUND` in the
   path.*
7. `TAX-CKSUM` — US `LUGGAGE`'s stated MD5 matches the served bytes; the generic fallback states an
   empty checksum (fail-open). Mismatch branch driven and scored using the generic fallback document at
   the unparameterized schema link, proving the comparator rejects mismatched bytes (wire half at OMS
   remains producer-blocked).
8. `TAX-LATEST-1`\* — a definition not marked latest is refused before its bytes are read. Driven via
   the `NOTLATEST` marker on `productType`; asserts `definition_status: "FETCH_FAILED"` with reason
   `"Amazon returned a definition it does not mark latest"`, raw schema absent, attributes absent.
9. `TAX-CAT-1` — per store: one body per discovered type, none twice, every code UPPER_SNAKE and not
   browse-node-shaped, `name` falls back to `code`, `marketplace_code` scopes the row, `store_code`
   on the query string, no browse-node key anywhere.
10. `TAX-CAT-3` — DE and ES both post `PRODUCT`; identical code, distinct `marketplace_code`.
11. `TAX-CAT-ORDER-1`\* — FR: every `bulk_categories` seq < the first `bulk_categories_attributes`
    seq; one category per type; one attributes body per type.
12. `TAX-ATTR-INV-1`\* — FR `SHOES` posted. Parent-first order; unique `field_code`s; **every nested
    code dotted**; no `id`/`field_parent_id`; no validation key outside the ten; `field_criteria` and
    `data_type` inside their sets; no withdrawn picker code; no browse-node key; `definition_status`
    present and one of six; no reason on an `AVAILABLE` body.
13. `TAX-BT-REPORT` — FR tree: create → poll → document → download → parse; every option value
    numeric; every name `" > "`-joined; zero flat-file requests. *Steering:
    `reportOptions.MarketplaceId`.*
14. `TAX-BT-FATAL-1`\* — a failed browse-tree report leaves definitions untouched. Driven on the
    `CANCELLED` marker (`reportOptions.MarketplaceId="<DE id>-CANCELLED"`) which polls `CANCELLED` with
    no document; asserts published definitions survive intact and unaffected.
15. `TAX-BT-ISO-1`\* — the same marketplace requested with and without `reportOptions`: scoped ⇒
    `rep-browsetree-<mp>`; unscoped ⇒ `rep-browsetree-DEFAULTSTORE`; the two root sets are disjoint.
16. `TAX-BT-DUP-1`\* — a duplicate `browseNodeId` inside one marketplace; records what an upsert
    keyed on node id would lose and which leaves have unsplittable paths.
17. `SRCH-EMPTY-1`\* — C6: an empty product-type catalogue is an answer, not a failure. Driven with
    `marketplaceIds` containing `EMPTY`; asserts 200 with empty `productTypes` list, exactly 1 search
    call, zero definition calls, and zero attributes posted.
18. `TAX-DL-FAIL-1`\* — C7: a schema-download failure is distinguished from a definition failure.
    Driven via the `SCHEMADLFAIL` marker whose `schema.link.resource` points to an unrouted path (mock
    404s); asserts `definition_status: "FETCH_FAILED"` with reason `"schema download failed"`, raw schema
    absent, attributes absent.
19. `TAX-NO-LINK-1`\* — C8: a definition carrying no schema link fails cleanly. Driven via the
    `NOSCHEMA` marker returning an envelope with no `schema` key; asserts
    `definition_status: "FETCH_FAILED"` with reason `"definition carries no schema link"`, raw schema
    absent, attributes absent.

---

## 6. Final case list — `suite-connect-us.py` (proposed, 14)

1. `US-AUTH-1` — the mock authenticates; states that it proves nothing about SP-API.
2. `US-CAT-1` — A2 for the US store, count parity, no browse-node key.
3. `US-DEF-1` — parameterised over `LUGGAGE`/`CLOTHING`/`ELECTRONICS`/`TOYS_AND_GAMES`: envelope
   resolves, schema link is a second GET, checksum verifies.
4. `US-ENV-1` — the envelope as received: `definition_version` == `productTypeVersion.version` and
   not date-shaped; `latest_version` == `productTypeVersion.latest`; `schema_checksum` ==
   **Amazon's stated** value; `raw_schema_json` parses **deep-equal** to the bytes served, including
   a planted `"_futureAmazonField"`; `definition_status` ∈ the six; `store_code` and
   `marketplace_code` on the query string. *Steering: a fixture carrying an unknown top-level key.*
5. `US-VOCAB-1` — §0.4 on every received row: dotted nested codes, parent-first, `id`/
   `field_parent_id` absent, `marketplace_code` on every row equal to the request's, `mandatory` a
   real boolean and not all-false, `field_type` ∈ {`attribute`, `option_type`, `attributes`}.
6. `US-MAP-1` — B7/B8/B9/B10/B12 against each US schema: all ten validation keys surface with the
   right types; a property stating only `maxLength` carries **exactly** that one key; array parent
   has bounds and no `maxLength` while its `.value` child has `maxLength` and no bounds; all five
   added `data_type`s appear and `number`/`integer` are distinguished; `format` mapping incl. on a
   `$ref` target and an `anyOf` branch; a measurement is three rows and the unit is a sibling.
7. `US-KEYWORD-1`\* — B14: the picker is `item_type_keyword.value` (never
   `recommended_browse_nodes.value`); values are keyword tokens; a node served without the attribute
   contributes no option and its id appears in no `field_values`. *Steering: the SYNTHETIC keyword
   fixture; state in the case that it is hand-authored.*
8. `US-STATUS-1` — all six statuses in one run, asserted on received bodies, plus D3/D4/D5/D6:
   `SCHEMA_OMITTED` keeps complete attributes and drops the raw schema, body ≤ 900 KB;
   `VALUES_OMITTED` empties every `field_values` but keeps the rows; a `PARSE_FAILED` oversize body
   stays `PARSE_FAILED` with **both** clauses joined by `"; "`; an over-long enum is cut to exactly
   8000. **Blocked sub-branches, named in the case:** checksum mismatch, schema-download 500 (C7),
   missing schema link (C8) — no fixtures.
9. `US-WITHDRAW-1` — no `/browse.?node/i` **key** on either payload.
10. `US-NOREPORT-1` — zero browse-tree reports for a US store, counted in the mock's store.
11. `US-CHAIN-1`\* **(blocked)** — A4 and D10: no `FETCH_PRODUCTS` over an incomplete stage, and a
    connect arriving during an active sync is queued, not duplicated — **within one replica only**
    (never assert cross-replica). No `[JP]` hop exists.
12. `US-ERR-1` — an OMS 500 is caught and recorded, and does not stop the next product type.
13. `US-LEGACY-1` — the legacy category endpoints still answer.
14. `US-RAW-1` — `raw_schema_json` survives verbatim across all four US schemas and
    `schema_checksum` is Amazon's stated value, **never** a locally recomputed digest.

---

## 7. Final case list — `suite-connect-non-us.py` (proposed, 14)

1. `NONUS-AUTH-1` — as `US-AUTH-1`, six stores.
2. `NONUS-CAT-1` — A2 for FR/DE/ES/AU/GB/JP.
3. `NONUS-ENV-1` — the envelope per market, as `US-ENV-1`.
4. `NONUS-VOCAB-1` — §0.4 per market.
5. `NONUS-MAP-1` — parameterised over the six schemas: A7 ordering, B8 array split, B11 `default` and
   absent top-level `field_parent_code`, B12 enum/unit rows (FR `heel_height` → three rows,
   `Centimètres`/`Pouces` as `field_values`).
6. `NONUS-RBN-DE` — B13 in full: parent `recommended_browse_nodes` (`is_parent`, `array`,
   `{minItems 1, minUniqueItems 1, maxUniqueItems 1000}`), picker
   **`recommended_browse_nodes.value`** (`is_child`, `string`, `option_type: true`,
   `field_values[].value` = the numeric node id, `.name` = the path joined by `" > "`), and the third
   row `recommended_browse_nodes.marketplace_id`. *Steering: the marketplace's own browse-tree
   report — use FR, not DE (§0.9.6).*
7. `NONUS-RBN-ES-AU` — the same pair on the other two real captures, each with its own titles,
   `required[]` membership and `editable` flags.
8. `NONUS-RBN-EMPTY` — B15: with no tree cached the picker arrives with **`field_values: []`** and
   `free_text: true`, `definition_status` `AVAILABLE`, and the run does not stall.
9. `NONUS-WIDTH-1`\* — B19 at the wire: serve ES/AU `PRODUCT`/`AUTO_PART`; exactly 4
   `purchasable_offer.*` child rows in Amazon's property order; the other 9 absent from
   `category_attributes` and **present in `raw_schema_json`**; `definition_status: AVAILABLE`;
   `definition_status_reason` == `"purchasable_offer states 13 children; 4 published"` (joined by
   `"; "` with the other breaches); then FR/DE/US and **no** `definition_status_reason` key at all.
10. `NONUS-PICKER-ISO` — A1/D12 at the wire: DE and ES both `PRODUCT`, each picker holds only its own
    marketplace's nodes, the two are disjoint, and a total failure of one leaves the other complete.
11. `NONUS-REPORT-1` — one XML report per marketplace with `reportOptions.MarketplaceId` stated, zero
    for `ATVPDKIKX0DER`.
12. `NONUS-PATH-1` **(blocked)** — the leaves whose breadcrumb cannot be rebuilt by splitting on
    commas, named per marketplace.
13. `NONUS-RETRY-1`\* **(blocked)** — C2/C3/C4/C5/D11 in one recorded place: 429 then 200 with each
    product type reaching OMS **once**; 429 throughout ⇒ exactly 5 attempts, no `FETCH_PRODUCTS`, a
    failure trace keyed on the product type; 403 ⇒ the loop breaks and remaining types are never
    requested (and **no** reauthorization signal is asserted — it is not sent); ≤ 5 definition
    requests in any one-second window, as a ceiling. Needs both a `[JP]` hop and definitions-route
    fault fixtures.
14. `NONUS-RESUME-1`\* **(blocked)** — D1/D2: run 2 re-fetches only what failed (3, 17, 29 — not
    everything from 3 onward) and the checkpoint clears once everything settles.

Plus kept as-is: `NONUS-WITHDRAW-1`, `NONUS-ENCODING-1`, `NONUS-NEG-OMS-FAULT`,
`NONUS-NEG-OVERSIZE-JP`, `NONUS-RERUN-1`\* (D8/D9, per-run counts only).

---

## 8. `suite-all.py`

No case logic of its own. After the rewrites: re-import, re-derive the totals from
`suite_tax.CASES + suite_us.CASES + suite_non_us.CASES`, and keep setting `AMAZON_UP`/`OMS_UP` on
each module. Its ephemeral-mock start must not seize port 23103 when another run owns it. Update the
`amazon/README.md` table's counts and totals when the two connect suites land.

---

## 9. Retired ids — never reuse

`TAX-CAT-2`, `TAX-CAT-CR1`, `TAX-BT-HUGE-300MB`, `TAX-CAT-ATTR-1`, `TAX-BT-US-1`, `TAX-US-1`,
`TAX-FR-1`; `US-PRE-1`, `US-PTD-SEARCH`, `US-CAT-MULTI`, `US-DEF-*` (four), `US-MAP-*` (four),
`US-CR3-1`, `US-RECON-1`, `US-E2E-LUGGAGE`, `US-E2E-MULTI`, `US-LOG-1`, `US-AUTH-EXPIRE`,
`US-NEG-INVALID-INPUT`, `US-NEG-UNAUTHORIZED`, `US-NEG-RATE-LIMIT-429`, `US-NEG-RESOURCE-404`,
`US-NEG-SERVER-500`, `US-NEG-MALFORMED-PARSE`; `NONUS-PRE-1`, `NONUS-MAP-*` (six), `NONUS-ROWS-1`,
`NONUS-CR3-1`, `NONUS-STATUS-1`, `NONUS-ISOLATION-1`, `NONUS-FR-1`, `NONUS-DE-1`, `NONUS-ES-1`,
`NONUS-AU-1`, `NONUS-GB-1`, `NONUS-JP-1`, `NONUS-RECON-1`, `NONUS-ASSERT-1`, `NONUS-LOG-1`,
`NONUS-NEG-AUTH-ISOLATION`, `NONUS-NEG-RESOURCE-404`, `NONUS-NEG-CORRUPT-JP`, `NONUS-NEG-RATE-LIMIT`.

Count after the rewrite: 19 + 14 + 14 = **47**, down from 87. Every deletion is recorded above with
its reason; the count is justified, not preserved.
