# Amazon Selling Partner API (SP-API) Mock Server

A high-fidelity local mock server and comprehensive mock data library for the **Amazon Selling Partner API (SP-API)**, built from and bundled with the official [`amzn/selling-partner-api-models`](https://github.com/amzn/selling-partner-api-models) repository.

It enables end-to-end offline testing of marketplace integrations, order sync, inventory updates, listings, pricing, feeds, reports, and merchant fulfillment with **900+ official Amazon sandbox test fixtures** and zero rate limits.

```bash
# Start via Central Management Portal (port 23000)
python3 portal.py

# Or start directly
python3 mock.py amazon

# Validate route table against the consolidated spec (375 routes)
python3 mock.py amazon --check

# Run the automated smoke test suite (39 test cases, 152 assertions)
python3 amazon/suite-smoke.py

# Run the Marketplace Taxonomy suite -- the discovery calls, and the OMS category payload
python3 amazon/suite-taxonomy.py

# Run the store-connect suites -- the OMS attributes payload, US and non-US (needs the OMS mock)
python3 amazon/suite-connect-us.py
python3 amazon/suite-connect-non-us.py
```

## The IA-5105 suites

Three of the four suites judge what the integration sends to Anchanto OMS. They share
[`ia5105_requirements.py`](ia5105_requirements.py), which holds every expected value with the
document and section it comes from: the IA-5105 browse-node and listing plan (the current
amendment), the OMS taxonomy requirements spec, the product-types mapping spec,
`anchanto-oms/anchanto-oms-swagger.json`, and Amazon's own captured schemas. **No expected value in
it was derived by reading the JPluger Amazon integration**, so a failing check is an argument about
the requirement rather than a description of the code.

| Suite | Judges | Needs |
|---|---|---|
| `suite-smoke.py` | The SP-API mock itself -- 375 routes, the sandbox fixtures, the S3 data plane | Amazon mock only |
| `suite-taxonomy.py` | Definitions discovery per market, and `POST /rest/v1/bulk_categories` | OMS mock for the `TAX-CAT-*` cases; without it they are `blocked` |
| `suite-connect-us.py` | `POST /rest/v1/bulk_categories_attributes` for a US store, and the absence of a browse-node row and of any browse-tree report | Both mocks |
| `suite-connect-non-us.py` | The same for DE, ES, FR, AU, GB and JP, and the `recommended_browse_nodes` pair in full | Both mocks |

**Payloads are judged on what arrived, not on what was built.** Each suite clears the OMS mock's
call log in preflight, fires, and reads the bodies back out of `:23001/log/data`. A suite that
asserts on a dict it still holds in memory proves only that its input is its input.

**What produces the payload.** `amazon_taxonomy_transformer.py` is a local stand-in for the JPluger
Amazon integration, which this harness cannot start -- there is no app under test here the way
`eton/suite-create-order.py` has one. Where the stand-in and the requirement disagree, the suites
fail, and that is the report.

---

## Service Profile

| Property | Value |
|---|---|
| **Service Name** | Amazon Selling Partner API (SP-API) |
| **Port** | `23103` |
| **Base URL** | `http://127.0.0.1:23103` |
| **Auth Token URL** | `http://127.0.0.1:23103/auth/o2/token` |
| **RDT Endpoint** | `http://127.0.0.1:23103/tokens/2021-03-01/restrictedDataToken` |
| **Web Dashboard & Living Specs** | `http://127.0.0.1:23103/` |
| **Real-time Call Log Viewer** | `http://127.0.0.1:23103/log` |
| **Test Suite Runner** | `http://127.0.0.1:23103/test` |
| **Specification** | [`amazon-sp-api-swagger.json`](amazon-sp-api-swagger.json) (371 operations) |
| **Upstream Repo (Vendored)** | [`upstream/`](upstream/) (`amzn/selling-partner-api-models`) |
| **Mock Fixtures Library** | [`mock-fixtures/`](mock-fixtures/) (900+ sandbox static test cases across 44 domains) |
| **Official Schemas** | [`schemas/`](schemas/) (58 report, notification, and feed schemas) |

---

## Mock Data & Fixtures Library

The server includes all official mock data and fixtures extracted directly from `amzn/selling-partner-api-models`:

### 1. Extracted Sandbox Fixtures (`mock-fixtures/`)
Over **900 static test cases** with realistic parameters, bodies, and responses:
- [`mock-fixtures/all-sandbox-fixtures.json`](mock-fixtures/all-sandbox-fixtures.json): Master dictionary of all 900+ sandbox fixtures indexed by endpoint and case label.
- **44 Domain-specific Fixtures Files**:
  - `mock-fixtures/orders.json`: 39 order sync, line items, buyer info, address, and regulated order test fixtures.
  - `mock-fixtures/product-pricing.json`: 22 pricing calculation, offers, and competitive price fixtures.
  - `mock-fixtures/vendor-direct-fulfillment-shipping.json`: 29 direct fulfillment shipping and label fixtures.
  - `mock-fixtures/fulfillment-inbound.json`: 110 FBA inbound shipment and item tracking fixtures.
  - `mock-fixtures/services.json`: 147 service appointment and job management fixtures.
  - `mock-fixtures/seller-wallet.json`: 98 financial wallet, transaction, and transfer fixtures.
  - `mock-fixtures/listings-items.json`: 20 listing update, patch, and validation fixtures.
  - `mock-fixtures/catalog-items.json`: 8 catalog search, classification, and ASIN fixtures.
  - `mock-fixtures/reports.json` & `mock-fixtures/feeds.json`: Asynchronous lifecycle fixtures.
  - ... and 34 more domains (e.g. `finances.json`, `shipping.json`, `easy-ship.json`, `notifications.json`).

### 2. Official Schemas & Sample Payloads (`schemas/`)
- **`schemas/reports/`** (22 schemas): `sellerSalesAndTrafficReport.json`, `vendorSalesReport.json`, `vendorInventoryReport.json`, `accountHealthReport-2020-11-18.json`, `marketplaceAsinPageViewMetrics.json`, `sellingPartnerSearchCatalogPerformanceReport.json`, etc.
- **`schemas/notifications/`** (23 schemas): `OrderChangeNotification.json`, `AnyOfferChangedNotification.json`, `FeedProcessingFinishedNotification.json`, `ReportProcessingFinishedNotification.json`, `FBAOutboundShipmentStatusNotification.json`, etc.
- **`schemas/feeds/`** (5 schemas): `listings-feed-schema-v2.json`, `listings-feed-processing-report-schema-v2.example.json`, etc.
- **`schemas/data-kiosk/`**: GraphQL query analytics schemas.

---

## Authentication & Tokens

Amazon SP-API uses **Login with Amazon (LWA)** OAuth 2.0 access tokens and **Restricted Data Tokens (RDT)** for PII access:

### 1. LWA OAuth2 Token (`POST /auth/o2/token`)
Accepts form-urlencoded or JSON with `grant_type=refresh_token`, `refresh_token`, `client_id`, `client_secret`.
```bash
curl -s -X POST http://127.0.0.1:23103/auth/o2/token \
  -d "grant_type=refresh_token&refresh_token=mock_refresh_token&client_id=client123&client_secret=secret123"
```
**Response (200 OK):**
```json
{
  "access_token": "Atza|IQEBLjAsAhQmock_sp_api_access_token_1234567890",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "rws_mock_refresh_token_12345"
}
```

### 2. Restricted Data Token (`POST /tokens/2021-03-01/restrictedDataToken`)
Exchanges an access token for an RDT scoped to sensitive PII fields (buyer email, shipping address).
```bash
curl -s -X POST http://127.0.0.1:23103/tokens/2021-03-01/restrictedDataToken \
  -H "Content-Type: application/json" \
  -d '{"targetApplication":"amzn1.sp.solution.123","restrictedResources":[{"method":"GET","path":"/orders/v0/orders/{orderId}/address","dataElements":["shippingAddress"]}]}'
```

---

## Steering & Official Sandbox Test Cases

The mock server supports both **official Amazon `TEST_CASE_*` parameters** and **custom steering markers**:

### Official Upstream Sandbox Test Cases
| Parameter Value | Endpoint | Behavior |
|---|---|---|
| `CreatedAfter=TEST_CASE_200` | `GET /orders/v0/orders` | Returns 200 with orders `902-1845936-5435065` & `902-8745147-1934268` |
| `CreatedAfter=TEST_CASE_200_NEXT_TOKEN` | `GET /orders/v0/orders` | Returns 200 with `NextToken: "2YgYW55IGNhcm5hbCBwbGVhc3VyZS4"` |
| `CreatedAfter=TEST_CASE_400` | `GET /orders/v0/orders` | Returns 400 with `InvalidInput` |
| `orderId=TEST_CASE_IBA_200` | `GET /orders/v0/orders/{orderId}` | Returns 200 Invoicing by Amazon (IBA) order `921-3175655-0452641` |
| `orderId=TEST_CASE_400` | `GET /orders/v0/orders/{orderId}` | Returns 400 `InvalidParameterValue` |
| `asin=TEST_CASE_404` | `GET /catalog/2022-04-01/items/{asin}` | Returns 404 `NotFound` |
| `asin=TEST_CASE_429` | `GET /catalog/2022-04-01/items/{asin}` | Returns 429 `QuotaExceeded` |
| `asin=TEST_CASE_500` | `GET /catalog/2022-04-01/items/{asin}` | Returns 500 `InternalServerError` |

### Steering Markers
| Marker | Location | Behavior / Response |
|---|---|---|
| `SERVERERROR` | Query, Path, or Body | Returns `500 InternalServerError` |
| `RATELIMIT` | Query or Path | Returns `429 QuotaExceeded` (Rate limit exceeded) |
| `NOTFOUND` | `orderId`, `sku`, `asin`, `feedId`, `reportId` | Returns `404 NotFound` / `ResourceNotFound` |
| `INVALID` | `orderId`, `sku`, `carrierCode`, `feedType`, `reportType` | Returns `400 InvalidInput` / `InvalidParameterValue` |
| `EMPTY` | `CreatedAfter`, `sellerSkus` | Returns `200 OK` with empty list `[]` (e.g. `Orders: []`) |
| `PAGE2` / `NextToken` | `query.NextToken` | Returns page 2 cursor paginated orders |
| `RDT_REQUIRED` | `orderId` in `/address` | Returns `403 Unauthorized` (Restricted Data Token required) |
| `INPROGRESS` | `feedId`, `reportId` | Returns `200 OK` with `processingStatus: "IN_PROGRESS"` |
| `FATAL` | `feedId`, `reportId` | Returns `200 OK` with `processingStatus: "FATAL"` |
| `CANCELLED` | `reportId` | Returns `200 OK` with `processingStatus: "CANCELLED"` |
| `BROWSE_TREE` in `reportType` | `POST /reports/2021-06-30/reports` | `reportId` becomes `rep-browsetree-<reportOptions.MarketplaceId>`, or `rep-browsetree-DEFAULTSTORE` when `reportOptions` is absent |
| `MERCHANT_LISTINGS` in `reportType` | `POST /reports/2021-06-30/reports` | `reportId` becomes `rep-listings-<marketplaceIds[0]>` |
| `browsetree-<marketplaceId>` | `reportDocumentId` | Selects that marketplace's browse tree; `browsetree` alone serves the default store's |
| `listings-<marketplaceId>` | `reportDocumentId` | Selects that marketplace's listings TSV, with localised column headers for FR |

---

## State Stores (`mock-data/`)

The mock tracks mutations in small, inspectable JSON files located in `mock-data/`:

- **`lwa_tokens.json`**: Records OAuth token grants and client IDs.
- **`created_orders.json`**: Active Amazon Order IDs.
- **`shipment_confirmations.json`**: Dispatched shipment confirmations (orderId, trackingNumber, carrierCode, shipDate).
- **`order_acknowledgements.json`**: Order acknowledgement payloads.
- **`feeds.json` & `feed_documents.json`**: Feed submissions and document upload endpoints.
- **`reports.json`**: Requested asynchronous reports.
- **`listings.json`**: Product listings and SKU updates.
- **`mfn_shipments.json`**: Merchant Fulfilled shipments created with carrier labels.
- **`feed_uploads.json`**: Raw feed bodies PUT to the stand-in S3 upload URL, so a test can assert what the client actually sent.

---

## Core Operations Reference

### Orders API (`v0`)
- `GET /orders/v0/orders?MarketplaceIds=ATVPDKIKX0DER&CreatedAfter=TEST_CASE_200`: List orders.
- `GET /orders/v0/orders/{orderId}`: Get single order metadata.
- `GET /orders/v0/orders/{orderId}/orderItems`: Line items for order (ASIN, SKU, price, quantity).
- `GET /orders/v0/orders/{orderId}/address`: Shipping address.
- `GET /orders/v0/orders/{orderId}/buyerInfo`: Buyer details.
- `POST /orders/v0/orders/{orderId}/shipmentConfirmation`: Confirm shipment tracking.

### Feeds API (`2021-06-30`)
- `POST /feeds/2021-06-30/documents`: Request S3 upload URL for feed payload.
- `POST /feeds/2021-06-30/feeds`: Submit feed for asynchronous processing.
- `GET /feeds/2021-06-30/feeds/{feedId}`: Poll feed processing status (`DONE`, `IN_PROGRESS`, `FATAL`).
- `GET /feeds/2021-06-30/documents/{feedDocumentId}`: Download feed processing report.

### Reports API (`2021-06-30`)
- `POST /reports/2021-06-30/reports`: Request report generation.
- `GET /reports/2021-06-30/reports/{reportId}`: Check report status (`DONE`, `IN_PROGRESS`, `CANCELLED`).
- `GET /reports/2021-06-30/documents/{reportDocumentId}`: Retrieve presigned S3 download URL.

### Listings & Catalog (`2021-08-01`, `2022-04-01`)
- `GET /catalog/2022-04-01/items/{asin}`: Catalog item details and brand.
- `PUT /listings/2021-08-01/items/{sellerId}/{sku}`: Create or update product listing.
- `GET /listings/2021-08-01/items/{sellerId}/{sku}`: Retrieve SKU listing status and buyability.

### Pricing & FBA Inventory (`v0`, `v1`)
- `GET /products/pricing/v0/price?MarketplaceId=ATVPDKIKX0DER&ItemType=Asin&Asins=B00005N5PF`: Retrieve product pricing.
- `GET /fba/inventory/v1/summaries?marketplaceIds=ATVPDKIKX0DER`: Retrieve FBA fulfillable and reserved stock.

### Merchant Fulfillment (MFN) (`v0`)
- `POST /mfn/v0/eligibleShippingServices`: Get eligible carrier shipping options.
- `POST /mfn/v0/shipments`: Purchase shipping label and retrieve PDF.

---

## The S3 Data Plane (`/s3/...`)

Amazon's Reports and Feeds APIs hand back a **presigned S3 URL**; the body itself never travels
over the SP-API host. Those URLs used to point at the real `tortuga-prod-na.s3-external-1.amazonaws.com`,
which is unreachable offline — so the report *lifecycle* was mockable but no report was ever
**downloadable**, and no feed was ever **uploadable**. These four routes close that gap. They are
deliberately not in the SP-API spec, so `--check` flags them as `not in spec`.

| Endpoint | Purpose |
|---|---|
| `GET /s3/report-download/{reportDocumentId}` | Serves the report body. Browse tree (XML) or merchant listings (TSV), selected by the markers in the document id. |
| `PUT\|POST /s3/feed-upload/{feedDocumentId}` | Accepts a feed body and records it to `feed_uploads.json`. Answers `200` with an empty body, as S3 does. |
| `GET /definitions/2020-09-01/productTypes/{productType}` | The definition **envelope**. `schema` is a `SchemaLink`, not an inline schema. |
| `GET /s3/ptd-schema/{productType}` | The document `schema.link.resource` points at — the actual JSON Schema. |

`getReportDocument` returns **no `compressionAlgorithm`** and the bodies are served
**uncompressed**. Real Amazon usually gzips them, so a client must read the field rather than
assume GZIP.

### Browse tree reports

`GET_XML_BROWSE_TREE_DATA` is **not** in `amzn/selling-partner-api-models` — it has no model, no
JSON schema and no sandbox fixture, because `reportType` is a free-form string and Amazon publishes
no schema for an XML flat report. The fixtures here are written into the config instead. Their
element shape follows Amazon's published *Browse Tree Reports* example, and three real-world traps
are represented on purpose:

- **Parentage is derived, not given.** There is no `isRoot` and no `parentNodeId`. `browsePathById`
  carries an unnamed leading root id, so a top-level node has exactly two entries and a node's
  parent is `browsePathById[size-2]`.
- **`browseNodeId` is not unique within a marketplace.** The DE fixture contains the real
  `amazon.de` pair from `amzn/selling-partner-api-models` issue #4742: id `13528201031` under two
  names, two parents and two depths. An upsert keyed on marketplace + node id collapses them.
- **`browsePathByName` cannot be split on commas.** Category names contain commas
  (`Küche, Haushalt & Wohnen`), and the naive split's token count often *equals* the id count — so
  a length assertion passes on corrupted data. Resolve the id chain through a node map instead.

Five trees are served, with disjoint root sets so a test can prove which one it received:

| `reportOptions.MarketplaceId` | Tree | Root node ids | Leaves for a product type |
|---|---|---|---|
| `A1PA6795UKMFR9` (DE) | German major appliances, duplicate node id | `908824031`, `3169011` | `PRODUCT` ×2 |
| `A13V1IB3VIYZZH` (FR) | French home & DIY | `340859031` | `MAJOR_APPLIANCES` ×1 |
| `A1RKKUPIHCS9HS` (ES) | Spanish home & kitchen — **SYNTHETIC** | `599392031` | `PRODUCT` ×2 |
| `A39IBJ37TRP1C6` (AU) | Australian automotive — **SYNTHETIC** | `4851723051` | `AUTO_PART` ×1 |
| omitted, or anything else | **Seller's default store** — US electronics, plus Amazon's own documented example node | `172282`, `000000001` | `HEADPHONES`, `BLUE_PRODUCT_ITEM` |

**The leaves are what the picker is built from,** and the DE tree had none until IA-5105 needed
them: every node in the original German fixture states `hasChildren=true`, so the plan's §4.3
transform — which skips a node unless it is a leaf that states `productTypeDefinitions` — yielded
nothing for it. The leaves added to DE, and the whole of the ES and AU trees, carry an XML comment
saying **SYNTHETIC** and why: no capture in this repository states a German, Spanish or Australian
browse node, so those ids are invented and must not be cited as observed. One DE leaf states
`browseNodeAttributes/recommended_browse_nodes` with a value that differs from its `browseNodeId`,
so the plan's value precedence (the stated attribute wins, `browseNodeId` is the fallback) is
observable rather than assumed.

That last row is the point: **omit `reportOptions` and every store receives the same tree.** That is
what the real API does, and it makes the marketplace-isolation failure reproducible offline
(suite case `REP-2`).

### Merchant listings reports

`GET_MERCHANT_LISTINGS_ALL_DATA` is served as TSV with the full 29-column header. Amazon
**localises those headers**: the FR variant uses `nom-produit`, `sku-vendeur`, `prix`, `quantité`,
`date-ouverture`, `id-offre`, `id-produit` and `état`. The same seller SKU carries a different
ASIN, price and currency in each marketplace, which is what makes cross-border product isolation
testable (suite case `REP-4`).

### Product type definitions

`getDefinitionsProductType` returns `schema` as a **link plus a checksum**, and
`productTypeVersion` as an **object** (`{version, latest, releaseCandidate}`) — not the string that
`searchDefinitionsProductTypes` returns under the same field name. Fetching the attributes takes a
**second GET** to `schema.link.resource`, which now resolves. The linked schema models measurement
attributes the way Amazon does: `item_weight` is an object with sibling `value` and `unit`
properties, `unit` carrying its own enum — not a scalar with a separate unit list. `requirements`,
`requirementsEnforced` and `locale` are echoed from the query so a test can assert what it asked
for (suite case `DEF-1`).

Amazon's own sandbox only publishes one product type (`LUGGAGE`, `ATVPDKIKX0DER`) with a
generic fallback schema for everything else. [`build_taxonomy_fixtures.py`](build_taxonomy_fixtures.py)
layers ten marketplace-specific product types on top, keyed on `(productType, marketplaceId)`. It is
idempotent — re-run it if the fixtures change.

**Three of the ten are genuine captures. The other seven are not, and each says so in its own
`x-fixture-provenance`** at the top of the file. Nothing observed through a SYNTHETIC fixture may be
cited as Amazon's behaviour; that is what gate G-4 on the IA-5105 plan is open about.

| Market | marketplaceId | productType | Provenance |
|---|---|---|---|
| DE (Europe) | `A1PA6795UKMFR9` | `PRODUCT` | **Genuine capture** from live Amazon (claim `L-31`) |
| ES (Europe) | `A1RKKUPIHCS9HS` | `PRODUCT` | **Genuine capture** from live Amazon (claim `L-32`) |
| AU (Far East) | `A39IBJ37TRP1C6` | `AUTO_PART` | **Genuine capture** from live Amazon (claim `L-33`) |
| US (North America) | `ATVPDKIKX0DER` | `LUGGAGE` | SYNTHETIC — the mapping spec §1.1 calls it "hand-authored for a different test, not a capture" |
| FR (Europe) | `A13V1IB3VIYZZH` | `SHOES` | SYNTHETIC — hand-authored edge cases: an orphan `$ref`, a non-English locale, an unmodelled `amazonFutureKeyword` |
| US | `ATVPDKIKX0DER` | `CLOTHING`, `ELECTRONICS`, `TOYS_AND_GAMES` | SYNTHETIC — no requirement document names them |
| UK (Europe) | `A1F83G8C2ARO7P` | `FURNITURE` | SYNTHETIC — and its `recommended_browse_nodes` shape matches none of the three real captures |
| JP (Far East) | `A1VC38T7YXB528` | `BEAUTY` | SYNTHETIC — same divergent shape as `FURNITURE` |

The five originals are the exact fixture files under JPluger's
`marketplace-integrations/src/test/resources/amazon/definitions/`, plus the provenance line. Two
things make this more than a bigger `DEF-1`:

- **DE and ES share a productType name.** Amazon reuses `PRODUCT` across marketplaces, so the
  schema link carries `?marketplaceId=` and the `/s3/ptd-schema/{productType}` route branches on
  it — a mock (or a client) keyed on `productType` alone would silently collapse two sellers'
  categories onto one schema (suite case `TAX-EU-1`, the non-US counterpart of the browse tree's
  `REP-2`).
- **The generic fallback's `schema.checksum` is empty, not a fixed fake hex string.** A real
  client verifies the downloaded schema bytes against it
  (`AmazonDefinitionsUtility.checksumMatches` in JPluger); a static body can never hash to a fixed
  checksum computed ahead of time, so the fallback would fail every real client's verification.
  Empty/absent is the documented "Amazon stated none" pass-through (suite case `TAX-CKSUM`).

---

## Rebuilding & Extracting Upstream Assets

To refresh the vendored repository, re-extract all 900+ fixtures, and re-generate `amazon-sp-api-swagger.json`:

```bash
python3 amazon/build-config.py
```
