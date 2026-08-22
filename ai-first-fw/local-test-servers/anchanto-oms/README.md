# anchanto-oms — Anchanto OMS (SelluSeller)

```bash
python3 mock.py anchanto-oms --reset     # port 23001
```

Anchanto's order management product, SelluSeller. The API every JPluger connector reaches through
`SS_DOMAIN` / `selluseller.open.api.base.url` — `openapi-omsqa.anchanto.com` in QA,
`ewmsapi.selluseller.com` in prod.

Full endpoint reference, with the call site behind every field:
[`docs/anchanto-oms-api.md`](../../docs/anchanto-oms-api.md).

## Is it working?

```bash
python3 anchanto-oms/suite-smoke.py        # or click Run on /test
```

97 cases, 255 checks, about two seconds — all 74 operations, every marker, the store write
contracts, the validation rules and the serialization traps. It drives the mock alone, so a red row
is the mock or the spec and never an integration. Results land in
`test-results/smoke/run-<stamp>/` and render at <http://127.0.0.1:23001/test>.

`--keep-state` leaves the stores and the call log alone, for inspecting a run you already have. The
store cases assert exact counts, so a suite run under `--keep-state` will legitimately report
`create recorded once` as a failure on the second run.

---

## Pointing JPluger at it

Two properties, same value: **`SS_DOMAIN` → `http://127.0.0.1:23001`** and
**`selluseller.open.api.base.url` → `http://127.0.0.1:23001`**.

`SS_DOMAIN` covers the marketplace and carrier connectors; `selluseller.open.api.base.url` is what
`ss-connector`, `selluseller-connector` and the v2 inventory writes read. Tokens are never
validated, so any bearer value works.

Do **not** point `WMS_3_URL` or `WREO_DOMAIN` here. Those belong to
[`anchanto-wms`](../anchanto-wms/README.md), a different Anchanto product, and this mock answers
404 on its paths on purpose.

---

## The 74 operations

| Tag | Operations |
|---|---|
| Auth | 2 — `POST /oauth/token`, `GET /rest/v1/users/me` |
| Orders | 20 — create, read, update, cancel, complete, return, shipping details, status |
| Inventory | 17 — inventory products, stock locations, and v1 plus v2 stock updates |
| Catalogue | 6 — listings, price and listing status |
| Catalogue Taxonomy | 11 — brands, categories, category attributes |
| Stores | 4 — store list, store read, meta-data stamp, credentials |
| Warehouses | 3 — warehouse list, warehouse read, stock locations |
| Shipping | 6 — shipping methods and their seller-marketplace mappings |
| Misc | 5 — manifests, payouts, promotions, reports, transactions |

16 of them are **constant-only**: the path constant exists in the source but no live call site was
found, so the verb and the body are inferred. They are mocked and exercised like the rest; treat a
green row on one as lower confidence than a green row elsewhere. `docs/anchanto-oms-api.md` lists
them.

---

## Seven things this mock gets right that a naive one would not

**1. `seller_sku`, not `sellerSku`.** `SkuV2DTO` carries `@JsonProperty("sellerSku")` *and*
`@SerializedName("seller_sku")`. The v2 body is Gson-serialized, so `seller_sku` is the wire key —
the `@JsonProperty` describes the inbound Kafka payload, not the OMS wire format. The mock reads
`seller_sku` and refuses `sellerSku` with a 422, so a client sending the wrong one is told.

**2. `/rest/v1/inventory_products/update_stocks` is two operations.** PATCH and POST are both
declared on that exact path, by different connectors. Both are mocked and they record into separate
store kinds. A mock collapsing them would answer a wrong-verb client as though it were right.

**3. Validation answers the endpoint's own status code.** 422 where the operation declares it, 400
where it declares that instead — `POST /rest/v1/orders` is a 400. Imposing one code on all 74 would
mock a contract OMS does not have.

**4. Two error envelopes, kept apart.** Orders and most writes answer
`{error, error_message, status}`; Inventory and the catalogue reads answer
`{errors: [{message, error_code}]}`. The Jackson DTOs on the JPluger side are not interchangeable,
so each operation's undeclared statuses are answered in the shape its declared ones already use.

**5. Semantic markers only where the endpoint declares them.** 500, 429 and 401 ride on all 74,
because a gateway, a rate limiter and an expired token can answer anything. 404, 409, 422 and 400
appear only where the document declares them — mocking a 409 on the warehouse read would let a test
prove behaviour the real API cannot produce.

**6. Query parameters are part of the contract.** `new_status` on `update_status`, `store_code` on
`async_create_orders`, and three parameters on `POST /rest/v1/shipping_methods` are all required and
all live in the query, not the body. The mock validates them there, and markers can be written into
them.

**7. Stores hold what was accepted, never what was sent.** A write answering 500 records nothing;
the call log records it regardless. Collapsing the two would let a retry test read its own failed
attempt as a success.

### Reproduced oddities, not tidied away

- `shipping_lable` is misspelled on the wire, on both shipping-details endpoints. A mock reading
  `shipping_label` would record nothing and still answer 200.
- `OipPromotionsImpl.java:54` sends the literal string `{sku}` in the path without substituting it.
  The route template still matches; `catalogue_pushes` records `sku_path` as `{sku}`, so the bug
  shows up as data instead of being absorbed.
- The legacy `updateShippingCarrier` stub issues **GET** on `/rest/v1/shipping_methods/{id}`, also
  without substituting `{id}`. Mocked as the GET it is, not the update its constant is named after.
- `orderNumber`, `isOrderItemChange`, `storeCode`, `marketplaceCode`, `parentCode` and the whole of
  `eventParametersDTO` arrive camelCase inside otherwise snake_case bodies, because those fields
  carry no `@SerializedName`. Accepted and recorded rather than rejected.
- `POST /rest/v1/categories` is entirely camelCase while `POST /rest/v1/bulk_categories` is
  snake_case. One API, two conventions, both mocked as declared.
- 404 on `GET /rest/v1/inventory_products` is the pagination terminator, not a fault.
- `POST /rest/v1/inventory_products/{inventory_product_id}/stock_locations` is the one operation
  whose only declared success is **201**.

---

## Markers

Write one into any identifier the call already carries — a path parameter, a body field, or an
identifying query parameter. Both spellings select the same rule.

| Marker | Status | On | Exercises |
|---|---|---|---|
| `9990500` · `SERVERERROR` | 500 | all 74 | server error |
| `9990429` · `RATELIMIT` | 429 | all 74 | rate limiting |
| `9990401` · `NOAUTH` | 401 | all 74 | token rejected mid-flow |
| `9990422` · `INVALID` | 422 | 36 | validation failure |
| `9990404` · `NOTFOUND` | 404 | 22 | not found, and the paging terminator |
| `9990400` · `BADREQ` | 400 | 11 | bad request |
| `9990409` · `CONFLICT` | 409 | 6 | duplicate order number, already-complete order, stale version |
| `9990001` · `BIZERR` | 2xx | 18 | a success status carrying an in-band failure |

`9990001` is the one worth knowing. Eighteen operations report failure inside a 200 — `success`
goes false, `errors` fills up, or `error` stops being null — so a test asserting only on the HTTP
status passes wrongly against every one of them.

A marker on an endpoint that does not carry it falls through to the happy path. That is deliberate:
`GET /rest/v1/warehouses/9990409` answers 200, because a warehouse read cannot conflict.

---

## Stores

55 of the 74 operations record what the mock accepted. Every entry carries a `kind`, so an
assertion names the call it means instead of counting rows. Every store sits in `mock-data/`,
beside the call log, and nothing else in this folder is written by the mock.

| File in `mock-data/` | Type | Holds |
|---|---|---|
| `token_grants.json` | list | every `/oauth/token` exchange, with `grant_type` as sent |
| `created_orders.json` | set | order numbers accepted, single and async |
| `order_pushes.json` | list | all thirteen order-lifecycle writes, tagged by kind |
| `shipping_pushes.json` | list | shipping details, async shipping details, returns and manifests |
| `returns.json` | set | return order numbers |
| `created_inventory_products.json` | set | `inventory_sku` values accepted |
| `stock_pushes.json` | list | all thirteen stock writes — v1 and v2, absolute, delta and async |
| `created_catalogues.json` | set | catalogue skus accepted |
| `catalogue_pushes.json` | list | catalogue writes, including price and listing status |
| `taxonomy_pushes.json` | list | brand, category and category-attribute writes |
| `store_pushes.json` | list | store meta-data stamps, with the sync timestamps written |
| `shipping_method_pushes.json` | list | shipping methods and their SMP mappings |
| `misc_pushes.json` | list | payouts, reports, transactions and promotion failures |
| `async_feeds.json` | list | every asynchronous feed queued |

31 routes also carry a `validate` block for the obligations the prose states and the schema does
not. A clean request falls straight past it to the happy path.

---

## Regenerating the config

`anchanto-oms.mock.json` is **generated**, and says so in its own `_comment`. Edit the generator,
not the file:

```bash
python3 anchanto-oms/build-config.py
python3 mock.py anchanto-oms --check      # expect 74 routes, 74 configured
```

The generator reads every success and error example straight out of the swagger, so the config
cannot drift from the document. What it cannot read — which store a write records into, which field
a response echoes back, what the partner requires beyond the schema — lives in one `TABLE` at the
top of the generator, keyed by `"METHOD path"`. An operation added to the swagger and missing from
the table is reported and generated with markers only; the suite's `COV-1` case fails until it is
exercised.

---

## What this mock cannot do

It answers HTTP. The OMS integrations also consume from **Rabbit and Kafka** — the inbound half of
every connector — and no HTTP client can produce those payloads. Drive them through JPluger's own
inbound surface rather than here.

It does not simulate authentication. `POST /oauth/token` hands back a canned token and no other
operation checks it; the `NOAUTH` marker is how a mid-flow 401 is provoked.

It does not model OMS state beyond what a test records. Reads answer the document's example whatever
was written before them, so `GET /rest/v1/orders/{id}` will not return the order a previous `POST`
created. Where a flow needs that, assert against the stores instead.
