# anchanto-wms — Anchanto WMS (Wareo3)

```bash
python3 mock.py anchanto-wms --reset     # port 23002
```

Anchanto's own WMS product. The API JPluger's `wms3` area calls, via `connector/wms3-connector` and
`${WMS_3_URL}` — `wms-api.anchanto.com` in prod.

Full endpoint reference, with the call site behind every field:
[`docs/anchanto-wms-api.md`](../../docs/anchanto-wms-api.md).

## Is it working?

```bash
python3 anchanto-wms/suite-smoke.py        # or click Run on /test
```

31 cases, 90 checks, about five seconds — all 27 operations, both OAuth2 grants, every marker, the
PUT-only product update and its wrong-verb negative, and the store write contracts. It drives the
mock alone, so a red row is the mock or the spec and never an integration. Results land in
`test-results/smoke/run-<stamp>/` and render at <http://127.0.0.1:23002/test>.

---

## Pointing JPluger at it

One property: **`WMS_3_URL` → `http://127.0.0.1:23002`**.

`WMS3_BASE_URL` and `WREO_DOMAIN` exist only in `wms3-core`; point them here too if you are
exercising the two legacy reads (ops 26–27). Tokens are never validated.

---

## The 27 operations

`…` below is `/rest/v2/customers/{customer_code}`.

| # | Method | Path |
|---|---|---|
| 1 | POST | `/oauth/token` — both the initial grant and the refresh |
| 2–8 | POST/GET | `…/b2c_orders`, `/{order_number}/cancel`, `/complete`, `/tracking`, `/shipping_docs`, `/{orig_order_number}/initiate_return`, `GET /{order_number}/details` |
| 9 | POST | `/rest/v1/b2c/orders/{order_number}/update_unassigned_order` |
| 10–13 | POST/GET | `…/b2b_orders`, `GET /{order_number}/details`, `GET /order_items`, `…/sto/orders` |
| 14–17 | POST/**PUT**/POST/GET | `…/products`, `…/products/{sku}`, `…/products/change_status`, `GET …/products/{sku}` |
| 18–23 | POST/GET | `…/suppliers`, `…/suppliers/update_supplier`, `GET …/suppliers/{supplier_code}`, `…/buyers`, `…/buyers/update_buyer`, `GET …/buyers/{code}` |
| 24–25 | POST/GET | `…/consignments`, `GET …/consignments/{consignment_number}/details` |
| 26–27 | GET | `/rest/v1/b2c/orders/{order_number}/details`, `/rest/v1/b2b/orders/{order_number}/details` |

---

## Six things this mock gets right that a naive one would not

**1. `/oauth/token` is the live auth, and `/rest/v1/tokens/generate` is deliberately absent.** The
v1 token is never used for a v2 call. A mock answering the v1 path would let a broken auth path look
healthy. This route serves both the initial basic-auth grant (no body) and the refresh grant —
`Wms3RequestHandler` posts to the same URL for each, and `token_grants.json` is the only way to tell
which happened.

**2. `warehouse-code` is a HEADER.** Kebab-case, set from `requestParameter.getExtras()`. The
snake_case `warehouse_code` is a *body* field. Both constants sit side by side in `Wms3Constants`.
Every write records the header into its store so a test can prove it was sent.

**3. Validation failures answer 422, not 400.** Wareo3's contract. Mocking it as 400 would test
something the real API never does.

**4. `…/products/{sku}` is PUT-only.** The single PUT in 27 operations. The suite asserts both that
PUT works *and* that POST on the same path 404s — without the negative, the mock could hide a
wrong-verb bug that fails in production.

**5. camelCase inside snake_case bodies is accepted.** `orderNumber`,
`externalReturnOrderNumber` and every member of `deliveryDetails` carry no `@SerializedName`, so
Gson emits the Java name. A mock demanding `order_number` would reject the real client.

**6. Identifiers are echoed, and two of them are load-bearing.** `data.return_order_number` on
op 7 and `order_number` on op 24 are persisted by the caller — omit either and the return or
consignment is stranded.

### Reproduced inconsistencies, not tidied away

- `status_code` is a **String** on the b2c read, an **Integer** on the b2b read, and a plain **int**
  on the consignment read. Three types, one field name. The mock returns each as its own DTO
  declares.
- The supplier read is `{supplier_code}`; the buyer read is `{code}`.
- Suppliers and buyers share one `Wms3PartyDataDTO`, so `supplier_type` rides along on buyer
  payloads. Accepted, and recorded, rather than rejected.
- Ops 26–27 use `%s` placeholders and `String.format` — a third placeholder style, alongside
  `{order_number}` and the v1 `<number>`.

---

## Markers

Put one in the order number, sku, or party code.

| Marker | Status | Exercises |
|---|---|---|
| `9990500` · `SERVERERROR` | 500 | server error |
| `9990429` · `RATELIMIT` | 429 | rate limiting |
| `9990422` · `INVALID` | 422 | validation failure — Wareo3's actual code |
| `9990401` · `NOAUTH` | 401 | token rejected mid-flow |
| `9990404` · `NOTFOUND` | 404 | reads only |
| `9990001` · `BIZERR` | 200 | 2xx whose `response` field says `error` |
| `EMPTY` | 200 | op 12 only — empty item list with `meta.total` 0 |
| `NOAUTH` in `client_id` | 401 | op 1 only — credentials rejected |
| `EXPIRE` in `client_id` | 200 | op 1 only — token valid 1 second, to force a refresh |

`9990001` is the one worth knowing: writes carry their own `response` field, so a test asserting
only on the HTTP status passes wrongly.

---

## Stores

Every store sits in `mock-data/`, beside the call log, and nothing else in this folder is written
by the mock.

| File in `mock-data/` | Type | Holds |
|---|---|---|
| `token_grants.json` | list | every `/oauth/token` call with its `grant_type` — initial vs refresh |
| `created_orders.json` | set | order numbers accepted, b2c and b2b/sto |
| `order_pushes.json` | list | every order-lifecycle write, tagged by kind, each recording the `warehouse-code` header |
| `returns.json` | list | return initiations by `orig_order_number` |
| `product_pushes.json` | list | product writes, with `length_cm` / `weight_gm` to prove the unit-suffixed fields arrived |
| `party_pushes.json` | list | supplier and buyer writes, with `supplier_type_present` |
| `created_consignments.json` | set | consignment numbers accepted |
| `consignment_pushes.json` | list | consignment creates with item lists |

---

## What this mock cannot do

It answers HTTP. The `wms3` area also has Kafka topics carrying Java-serialized
`IntegrationMessageDTO` payloads — no HTTP client can produce one — and a **file-drop** flow (SFTP
poll plus CSV parse) that is its documented fourth flow. Drive those through JPluger's own inbound
surface (`/jpluger/wms3/*`) rather than here.

`customer_code` is scoped into every v2 path but is **not** chosen by the caller: it comes from the
Kafka message header `EHeaderKeys.CUSTOMER_CODE`. Driving a real flow means setting it upstream, not
by picking a URL.
