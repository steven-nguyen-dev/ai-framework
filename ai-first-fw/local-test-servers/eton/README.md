# Eton WMS mock

Stands in for the eton WMS External API so `wms-integrations-legacy` can be driven end to end
locally. Engine and CLI: [../README.md](../README.md). Config format:
[../CONFIG.md](../CONFIG.md). Test rig: [../TESTING.md](../TESTING.md).

- **Target module** — `wms-integrations-legacy` (`com.anchanto.integration.wms.eton`)
- **Address** — `http://127.0.0.1:23101` · call log `/log` · test results `/test`
- **Launch** — `python3 mock.py eton` (run it as a background task)
- **Spec** — `eton-swagger.json`, eton WMS API v0.2. 102 operations answer from the document's own
  examples; the 4 below are configured.

## Required app config

`JPluger/secrets/integrations/local/core.json`:

```json
{
    "ETON_TOKEN_URL": "http://127.0.0.1:23101/connect/token",
    "ETON_BASE_URL": "http://127.0.0.1:23101"
}
```

## Runtime state

All of these are **state, not fixtures** — the server appends as it runs. `--reset` clears them.
Every one of them sits in `mock-data/`, the only folder this mock writes into; the seed the flow
needs first is `seed-data/eton_local_seed_data.sql`.

| File in `mock-data/` | |
|---|---|
| `packed_orders.json` | order codes the mock treats as already packed |
| `created_orders.json` | sale orders it has accepted, so a replay is answered BESO05 the way real eton does |
| `price_details.json` | every pricing push received, so a test can read back what was mapped |
| `api-calls.har.json` | the call log |
| `../test-results/<suite>/run-<stamp>/` | one folder per run, under the suite that produced it |

Being state, they are erasable mid-run — see [Traps worth
knowing](../TESTING.md#traps-worth-knowing). Here: the engine unions each capture into the run
folder, `log-capture.json` records whether the live log was cleared underneath, and every verdict
is judged from the folder. Never read these files for a run that has already finished.

`created_orders` matters for the retry cases. Without it a `@Retryable` replay is answered `200`
again, `handleCreatedOnEton` runs on every attempt, and the integration writes one `orders` row per
attempt — three rows for what production records once.

---

## Markers

Behaviour is keyed off the OMS order id (`ClientSoCode`) and order number (`RefCode`), which
`SaleOrdersDTO` maps from `order_id` and `order_number`. Matching is case-insensitive. Order
creation echoes `ClientSoCode` back as the WMS `Code`, so **one marker on the order id steers
creation, the pricing push and the later cancellation alike**.

`DataDTO.order_id` is a `Long`, so in an end-to-end run word markers only work in the order
*number*. The pricing push is addressed by the echoed code, i.e. the order id — hence the numeric
`9666` alongside `REJECT`.

| Marker | Creation | Pricing push | Cancellation |
|---|---|---|---|
| `SERVERERROR` | `500` → `is5xxServerError()` / `@Retryable` | — | `500` → no retry, no putaway |
| `EXISTS` | `400` / `BESO05` → treated as success | — | — |
| *(already created)* | `400` / `BESO05` — second create for a code the mock accepted | — | — |
| `INVALID` | `400` generic → logged, not retried, reported unsynced | — | — |
| `REJECT` or `9666` | — | `400` → the priceDetail call alone is retried, 3 attempts, then logged | — |
| `CANCELLED` | — | — | `400` / `BESO02` already cancelled |
| `94…` prefix, `9999400`, or `"packed"` in the body | `200`, `Status: "Packed"`, recorded | — | `400` / `BESO22` packed |

## Endpoints

1. **OAuth** — `POST /connect/token` → `200`, bearer `stub_access_token_12345`. Not in the spec
   (it lives on the STS host), so `--check` flags it; that is expected.

2. **Order creation** — `POST /api/v0.2/saleorders/single` → `CreateSingleSaleOrderModelResult`.
   Echoes `ClientSoCode` as `Code`/`ExternalCode` and `RefCode` as `RefExternalCode`. Unmarked
   orders get `200` with `Status: "New"` and are recorded in `created_orders`.

3. **Pricing detail** — `POST /api/v0.2/saleorders/{soCode}/priceDetail` → `BaseModelResult`.
   Every push is appended to `price_details.json` **whether or not it is accepted**, so a rejected
   push is still inspectable.

4. **Order cancellation** — `PATCH /api/v0.2/saleorders/{code}/cancel` → `BaseModelResult` /
   `ErrorResult`. `{code}` is the OMS order id, the same value creation echoed back.
   `cancelOrder` reads *any* `400` as "eton already packed it" and reports success to OMS with
   `skipQuantityAdjustment=true`.

5. **Everything else** — the spec's example, or a body synthesized from its response schema.

---

## Payload validation

Two [validation](../CONFIG.md#validation) rules sit after the markers, so a marker still wins.

**`validation failed (schema)` — on.** What `CreateSingleSaleOrderModel` formally declares:
`ListSODetail` present and non-empty, `SKU` and `Qty` on every line, `ClientTpl` ≤ 30 chars; plus
`SKU` and `Quantity` on every pricing line. `buildCreateSaleOrderItems` always sets SKU and Qty, so
the integration passes — only a hand-written minimal payload trips this. A bare
`{"ClientSoCode": "1001"}` returns `400 ['ListSODetail' is required]`; set `"enabled": false` if an
existing test depends on the old behaviour.

**`validation failed (documented address rules)` — off.** The obligations eton states only in
prose: `CustName`/`CustPhone`/`ShippingAddressNo`/`ShippingWardCode` unless
`DestinationClientBranch` is set, `ShippingDistrictCode` when the scheme is ADM4, `WarehouseCode`
when `ClientPickup` is true.

It ships **off because the integration does not satisfy it.** `SaleOrdersDTO` never populates
`ShippingWardCode`, `ShippingDistrictCode` or `DestinationClientBranch` — no `@JsonProperty` on any
of the three, and `setAllShippingDetails` sets only `CustName`, `CustPhone`, `CustEmail` and
`ShippingAddressNo` — while `ClientPickup` defaults to `true` and nothing sets `WarehouseCode` on
the Eton path. Gson omits nulls, so those keys never reach the wire. Turn the rule on and every
order the integration sends is rejected:

```
'ShippingWardCode' is required -- optional only if DestinationClientBranch is set
'WarehouseCode' is required -- required when ClientPickup is true
```

Whether that is a live defect or stale documentation is a question for eton. The rule is written
down so it can be switched on the moment that is settled.

---

## Test suite — createOrder flow 2

21 cases covering `EtonWmsService.createOrder` in both payload shapes. Start it from
<http://127.0.0.1:23101/test>, or:

```bash
python3 eton/suite-flow2.py                 # all 21, ~5 min
python3 eton/suite-flow2.py --fast          # skips N10, ~90s
python3 eton/suite-flow2.py N1 K1           # only these
python3 eton/suite-flow2.py --list          # the cases and what each expects
python3 eton/suite-flow2.py --judge eton/test-results/flow2/run-…
```

The suite is one file: payloads, expectations and the reasoning behind each case all live in
`eton/suite-flow2.py`, and the engine it runs on is `suite/`. Change a
requirement there and re-score the runs already on disk with `--judge` before firing anything.

| Piece | Where |
|---|---|
| The suite — payloads, expectations, reasoning | `eton/suite-flow2.py` |
| The engine every suite shares | `suite/`, [TESTING.md](../TESTING.md#writing-a-suite) |
| Plan the suite was written from | `docs/eton-createorder-test-plan.md` |
| Postman collection | `local-resources/eton/oms_eton_app_controllers_postman_collection.json`, folder **createOrder E2E (normal + kit)** |
| DB seed | `eton/seed-data/eton_local_seed_data.sql` (re-runnable) |

### Before the first run

```bash
docker compose up -d                                   # in docker/ — mysql, redis, kafka, rabbitmq
export MYSQL_PWD=$(grep '^MYSQL_PASSWORD=' docker/.env | cut -d= -f2-)
docker exec -i -e MYSQL_PWD="$MYSQL_PWD" mysql \
  mysql -u jpluger wms_integrations_test \
  < eton/seed-data/eton_local_seed_data.sql
```

**Seed the schema the app actually reads.** `application-local.properties` points at
`ss_wms_integration`, but the IDE run configuration overrides `spring.datasource.url` to
`wms_integrations_test`. With `createDatabaseIfNotExist=true` an empty schema is created silently,
so the app starts cleanly and then fails per message with a `NullPointerException` in
`WmsIntegrationParamFactory:273` — the credential lookup after `CustomORM.getSeller(7004)`. No Eton
call is made at all, so `/log` stays empty and all 17 cases fail for a reason unrelated to
`createOrder`. The runner's preflight now checks for the seller and its four `eton` credentials and
names the database that does have them. Pass a different schema with `DB_NAME=…`.

### Known gap — `event_name`

`recoverMethod` compares `event_name` against `GlobalConstant.ORDER_CREATION_EVENT` =
`"order_creation"`, and the older `wms-integration` module's `EtonOrders.recoverMethod:475`
hardcodes the same string. No Java anywhere produces or compares `"order_created"` — but the
Postman fixtures send exactly that, so retry exhaustion reports nothing to OMS.

The runner sends `order_creation` by default. To reproduce the fixture behaviour:

```bash
EVENT_NAME=order_created python3 eton/suite-flow2.py N10
```

Under `order_created`, N10 is reported `blocked` rather than `pass`: everything observable matches,
but the unsynchronized-order report cannot fire, so the last assertion is unproven. Worth confirming
with the OMS team which string is real — if it is `order_created`, no Eton order is ever reported
unsynchronized in production after retries are exhausted.

N12 carried the same gap until commit `465e7a647c3` removed the throw at the end of
`pushCreatedOrderPricing`. Commit `0b4508fc27d` then put a retry back where `SRC-01 AC 3` asked for
it — on the priceDetail call alone, three attempts, 3 to 6 seconds apart. A rejected pricing push
therefore never replays the run, never reaches `@Recover` and reports nothing, while the call that
was actually rejected is still re-attempted. N12 expects **1 create and 3 pricing pushes**, and that
ratio is what distinguishes retrying the call from replaying the run.
