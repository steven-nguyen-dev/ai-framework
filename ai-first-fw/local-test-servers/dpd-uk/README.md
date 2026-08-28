# DPD UK mock

Stands in for the DPD UK Shipping API so `dpdUK-integration` can be driven end to end locally.
Engine and CLI: [../README.md](../README.md). Config format: [../CONFIG.md](../CONFIG.md). Test rig:
[../TESTING.md](../TESTING.md).

- **Target module** — `carrier-integrations/dpdUK-integration`
  (`com.anchanto.carrier.integration.dpduk`), which also serves `dpd_local`
- **Address** — `http://127.0.0.1:23102` · call log `/log` · test results `/test`
- **Launch** — `python3 mock.py dpd-uk` (run it as a background task)
- **Spec** — `dpd-uk-openapi.json`. DPD publishes no OpenAPI document, so this one is transcribed
  by hand from *DPD API Northern Ireland Specification V1.2*, pages 11–52, and covers the four
  operations the integration calls. 3 are configured below; `GET /shipping/network/` answers from
  the document's own example.

## Required app config

`DPD_UK_BASE_URL` is hardcoded to `https://api.dpd.co.uk/` in
`dpdUK-integration/src/main/resources/application-local.properties`, and nothing outside the app
overrides it — `dpdUK-integration` registers no secrets listener, so
`JPluger/secrets/integrations/local/…` is not read on this path. Start the app with:

```
-DDPD_UK_BASE_URL=http://127.0.0.1:23102/
-DDPD_UK_LOCAL_BASE_URL=http://127.0.0.1:23102/
```

**The trailing slash matters.** Every URL is built as `baseUrl + "shipping/shipment"`. Without it the
request goes to `/23102shipping/shipment` and the mock answers 404.

A run where every case reports "no shipment call" and `/log` is empty is this setting, not a mapping
defect.

## Runtime state

All of these are **state, not fixtures** — the server appends as it runs, and `--reset` clears them.
Every one sits in `mock-data/`, the only folder this mock writes into; the seed the flow needs first
is `seed-data/dpd_uk_local_seed_data.sql`.

| File in `mock-data/` | |
|---|---|
| `logins.json` | that a GeoSession was issued, and which one. It cannot be counted: every login is answered with the same session, and a run folder unions its captures by value, so two identical entries collapse into one. Count the login **calls** instead, on `/log` or in the run's `mock-log.json` — a run of 24 shipments that shows two is the cache holding and two renewals, not two logins per order |
| `shipments.json` | every shipment request received, accepted or refused, so the mapping can be read back without opening the HAR |
| `session_refused.json` | order numbers already answered 401 once, so the renewal retry is the attempt that succeeds |
| `api-calls.har.json` | the call log |
| `../test-results/<suite>/run-<stamp>/` | one folder per run, under the suite that produced it |

Being state, they are erasable mid-run — see [Traps worth
knowing](../TESTING.md#traps-worth-knowing). Never read these files for a run that has already
finished; read that run's folder, which the engine unions each capture into.

---

## Markers

Behaviour is keyed off `consignment[0].consignmentRef`, which `DpdUKUtility.createOrderOnDPDUK` sets
from `data.order_number` — so **one marker in the order number steers the whole shipment**, and the
label calls with it. Matching is case-insensitive.

`shippingRef1` carries the same value under `@Size(max = 25)`, so an order number longer than 25
characters is refused by the app's own validator before DPD is called at all. Keep markers short.

| Marker in the order number | Shipment call |
|---|---|
| `SESSIONEXPIRED` | `401` on the first attempt for that order, `200` on the next — exercises `DpdUKGeoSessionCache.refresh` and the second send |
| `SESSIONDEAD` | `401` every time — the integration renews once and then gives up |
| `ONSTOP` | `200` with error `1014`, account on stop |
| `BADPOSTCODE` | `200` with error `1009`, invalid postcode |
| *(none)* | `200`, shipment created |

Two behaviours are keyed off the payload rather than a marker:

| Condition | Answer |
|---|---|
| `consignment[0].numberOfParcels` is 2 | two parcel numbers, and a two-page HTML label |
| `generateCustomsData` is `Y` | held to the documented customs obligations below |

## Endpoints

1. **Login** — `POST /user/?action=login` → `200 {"error":null,"data":{"geoSession":…}}`.
   Authentication is not simulated: the `Authorization` header is never checked, and the header is
   redacted in the log along with `GeoSession`.

2. **Insert shipment** — `POST /shipping/shipment` → the response `CreateOrderResponseDTO` reads.
   `shipmentId` echoes the order number back (see below). Every request is appended to
   `shipments.json` before any rule answers.

3. **Get labels** — `GET /shipping/shipment/{shipmentId}/label/`. The `Accept` header chooses the
   format: `text/vnd.citizen-clp` returns a thermal print string, anything else returns the label
   HTML that `wkhtmltopdf` is handed. The body is the print string itself, not JSON.

4. **Everything else** — the spec's example, or a body synthesized from its response schema.

### What the mock does that DPD does not

- **`shipmentId` is `SHP-<order number>`.** DPD issues an integer of its own. The echo is what makes
  a label call attributable to the case that caused it: the label URL carries the shipmentId and
  nothing else, and a suite has to recover a case's whole traffic from the log without relying on
  timing.
- **The label page count is keyed off the order number.** DPD returns one page per parcel, and
  `DpdUKCarrierService` splits the converted PDF on that count. The label request says nothing about
  the shipment it is labelling, so a two-page label is returned for a shipmentId containing `2PKG`.
- **One parcel number, unless the shipment says two.** The mock cannot count parcels from the label
  call, so anything beyond the two-parcel rule needs a rule of its own.

---

## Payload validation

Two [validation](../CONFIG.md#validation) rules sit after the markers, so a marker still wins.

**`validation failed (documented customs obligations)` — on.** What the specification's field tables
oblige once `generateCustomsData` is `Y`: the invoice and both its parties, the sender's EORI number,
each party's country, postcode, street and town, `customsValue` and `customsCurrency`, and on every
customs line its commodity code, origin, unit value, unit weight and quantity. `isBusiness` is
required only where the destination postcode starts `BT`, because the receiver's classification is a
Windsor Framework field and an international shipment declares customs data without one. A shipment
carrying no customs data — a Great Britain domestic one — is held to none of it.

The integration satisfies this rule today, on the Northern Ireland route and on the international
network codes alike. A hand-written payload, or a regression in
`DpdUKUtility.createOrderOnDPDUK`, is what trips it.

**`validation failed (collectionDate carries milliseconds and a zone)` — off.** DPD's error 1002 for
`collectionDate` reads *Incorrect date format YYYY-MM-DD*, and every `collectionDate` in the
specification is a second-precision local datetime — `2024-05-15T09:00:00`.
`DpdUKUtility.collectionDateMapping` formats with `SELLUSELLER_DATE_FORMAT`,
`yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`, so it sends milliseconds and a zone marker the documentation never
shows. Whether DPD accepts that is a question for DPD; the rule is written down so it can be
switched on the moment that is settled.

**Not enforced here.** DPD accepts one party's UKIMS number and requires that same party's EORI
number alongside it. The mock cannot state "one of these two fields" in a `required_when`, and
`DpdUKUtility.validateShipment` refuses those shipments before DPD is ever called — cases R2 and R8
of the suite cover them.

---

## Test suite — Northern Ireland shipment

37 cases covering `DpdUKCarrierService.createOrder` on the Northern Ireland route, the two routes it
must leave alone, every pre-submission refusal, and the GeoSession renewal. One case per rule of
IA-4752 sections 3.1 to 3.9 and per field of IA-5213's mapping table; each case's `note` names the
rule it comes from. Start it from <http://127.0.0.1:23102/test>, or:

```bash
python3 dpd-uk/suite-ni-shipment.py                 # all 37, ~2 min
python3 dpd-uk/suite-ni-shipment.py N1 R3           # only these
python3 dpd-uk/suite-ni-shipment.py --list          # the cases and what each expects
python3 dpd-uk/suite-ni-shipment.py --judge dpd-uk/test-results/ni-shipment/run-…
```

The suite is one file: payloads, expectations and the reasoning behind each case all live in
`dpd-uk/suite-ni-shipment.py`, and the engine it runs on is `suite/`. Change a requirement there and
re-score the runs already on disk with `--judge` before firing anything.

| Piece | Where |
|---|---|
| The suite — payloads, expectations, reasoning | `dpd-uk/suite-ni-shipment.py` |
| The engine every suite shares | `suite/`, [TESTING.md](../TESTING.md#writing-a-suite) |
| Where every field comes from | `JPluger/.scratchpads/IA-4752-dpd/mapping-plan.md` |
| The partner specification | `JPluger/.scratchpads/IA-4752-dpd/DPD API Northern Ireland Specification V1.2 (1).pdf` |
| DB seed | `dpd-uk/seed-data/dpd_uk_local_seed_data.sql` (re-runnable) |
| The same payload as a unit-test fixture | `dpdUK-integration/src/test/resources/createOrderNorthernIreland/request.json` |

### Before the first run

```bash
docker compose up -d                                   # in docker/ — mysql, redis, kafka, rabbitmq
export MYSQL_PWD=$(grep '^MYSQL_PASSWORD=' docker/.env | cut -d= -f2-)
docker exec -i -e MYSQL_PWD="$MYSQL_PWD" mysql \
  mysql -u jpluger carrier_integrations_test \
  < dpd-uk/seed-data/dpd_uk_local_seed_data.sql
```

**Seed the schema the app actually reads.** `carrier-core`'s `application-core-local.properties`
points at `carrier_integrations_test` with `ddl-auto=none`, so the seed creates its own tables. Three
rows have to exist before any DPD call is made, and each is checked by preflight:

- **the seller**, by `selluseller_seller_id` = 42. `CarriersCustomORM.getSeller` is called before
  anything else and its result is dereferenced straight away.
- **`username` and `password`** for `carrier_code = 'dpd_uk'`. `EParameterType.getEnum` throws on any
  other `key_name` and the throw is swallowed, so one wrongly named row loses the whole credential
  set and the shipment fails with no GeoSession.
- **a dispatch time slot** for the seller and `dpd_uk`. `collectionDateMapping` counts seconds from
  midnight to `data.order_date_in_smp_timezone` and asks for the slot holding that instant; the
  seeded slot spans everything, which is what makes a fixed test date usable.

### Known gap — `wkhtmltopdf`

`DpdUKCarrierService` fetches both labels, converts the HTML one with `wkhtmltopdf`, splits the PDF
per parcel, and only then reports the shipment to the product and writes the `corders` row. Without
the binary on `PATH` the conversion throws into the catch-all: the shipment on DPD is unaffected and
every mapping assertion still holds, but the last two — what the product was told, and the row —
cannot be made.

Those cases are reported **`blocked`, never `pass`**, so a machine without it never reads as proof.
Preflight says so once, and `WKHTMLTOPDF` is recorded in the run's `meta.json`. Re-judge an old
folder with `WKHTMLTOPDF=present` when the machine judging is not the machine that fired.

Homebrew dropped the cask when upstream archived the project, so on macOS there is nothing to
install. `tools/wkhtmltopdf` is a stand-in that does the same job through Chrome's own
print-to-PDF — a real conversion of the real label, proving everything except wkhtmltopdf itself.
**The app is what shells out to it, so it has to be on the app's PATH, not the suite's:**

```bash
PATH="$PWD/dpd-uk/tools:$PATH" mvn -pl dpdUK-integration spring-boot:run …   # or the IDE's PATH
PATH="$PWD/dpd-uk/tools:$PATH" python3 dpd-uk/suite-ni-shipment.py
```

Nothing is on the default PATH, so a run that says nothing about it is a run without it.

### Known gap — 403 against 401

The specification documents **403** for a GeoSession that was not found or is invalid (page 14).
`DpdUKCarrierService.isUnauthorized` compares against **401** alone, so under DPD's documented status
the session is never renewed and the shipment fails on its first attempt. The default rule answers
401 — which is what the integration handles, and what case E2 proves. The disabled rule
*GeoSession refused with the documented 403* answers 403 instead; turn it on and E2 goes red with one
shipment call rather than two. Which status DPD really sends on this path is worth confirming with
DPD.
