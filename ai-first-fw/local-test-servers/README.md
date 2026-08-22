# Local test servers

`mock.py` is one generic mock HTTP server. Point it at a partner's Swagger 2.0 or OpenAPI 3
document and it answers every operation in that document with the example response the document
declares — the two versions hang their examples off different keys, and both are read. Add a
**config** and it answers chosen operations conditionally — a marker in the request selects the
status code and body, requests can be recorded into small JSON stores that later requests branch
on, and payloads can be validated the way the partner would validate them.

It exists so an integration can be driven end to end without a partner sandbox.

`suite/` is the second engine in this package: it runs a **test suite** against a mock — preflight,
reset, firing, capture, judging and publishing — so a suite file states only what its flow sends
and what has to be true afterwards. A suite sits in the mock's own folder and the mock's `/test`
page runs it. See [TESTING.md](TESTING.md) and [suite/README.md](suite/README.md).

```bash
python3 portal.py        # Central Portal dashboard on http://127.0.0.1:23000
python3 mock.py portal   # alias to start the portal
python3 mock.py eton     # by integration name
python3 mock.py          # lists the integrations that exist
```

The argument is the **integration folder name**, resolved next to the script. A path to a config file also works.

| Flag | |
|---|---|
| `--check` | print the route table, validate it against the spec, exit |
| `--reset` | empty the stores, call log, and test results before starting |
| `--port` / `--host` | override the config |
| `--log` / `--log-format` / `--no-log` | override logging |
| `--portal` | run the central portal dashboard |

**Authentication is not simulated.** Tokens are never validated. An auth endpoint the client must
call before it will talk to the server is declared as an ordinary route returning a canned token.

Adding a mock, or changing how one answers: [CONFIG.md](CONFIG.md). Running a test suite against
one: [TESTING.md](TESTING.md).

## Central Portal (`portal.py`)

`portal.py` runs a central web portal on **`http://127.0.0.1:23000`** to manage all local test servers from one place:

- **Start / Stop / Restart / Reset**: One-click controls for each server individually or across all servers in bulk.
- **Direct Navigation**: Instant jump links to each server's API root (`/`), Call Log viewer (`/log`), and Test Suite runner (`/test`).
- **Live Monitoring**: Real-time status detection, port inspection, uptime tracking, and live console output streaming.

## Layout

**One folder per integration**, holding its spec, its config, its suites, its state files and its
own README. The engines and central portal live here at the top.

```
local-test-servers/
  portal.py                central management portal and dashboard (port 23000)
  mock.py                  the mock server, shared by every integration
  suite/                   the test-suite engine, shared by every suite
  ../local-theme/          unified design tokens, CSS, and JS shared across all test & report servers
  README.md                this file — the engine, its CLI, and the mocks that exist
  CONFIG.md                the config format
  TESTING.md               running test suites against a mock and reading the results
  <integration>/
    README.md              what this mock does: markers, endpoints, quirks
    <name>.mock.json       the config
    <partner>-swagger.json the API document the mock answers every unconfigured operation from
    suite-<name>.py        a test suite, run from the command line or the mock's /test page
    mock-data/             what the mock writes — its stores and its call log
    seed-data/             SQL a flow has to be seeded with before a suite can prove anything
    test-results/          one folder per run
```

A file's folder says who owns it: the mock writes only inside `mock-data/`, a suite writes only
inside `test-results/`, and everything at the top of an integration folder is hand-written.

Nothing outside this folder is read to start a mock or run a suite. `local-resources/` keeps only
what stands on its own — an API document no mock answers from, and application configuration.

| Integration / Service | Folder | Launch | Port |
|---|---|---|---|
| **Central Portal** | [`portal.py`](portal.py) | `python3 portal.py` | `23000` |
| **Eton WMS** (third-party partner) | [`eton/`](eton/README.md) | `python3 mock.py eton` | `23101` |
| **Anchanto WMS (Wareo3)** | [`anchanto-wms/`](anchanto-wms/README.md) | `python3 mock.py anchanto-wms` | `23002` |
| **Anchanto OMS (SelluSeller)** | [`anchanto-oms/`](anchanto-oms/README.md) | `python3 mock.py anchanto-oms` | `23001` |

If the one you need is not in that table it does not exist — say so rather than improvising one.

### Ports

Two blocks, by who owns the product, plus the central portal at `23000`. **Anchanto's own products run from `23001` up. Third-party
systems run from `23101` up.** A new mock takes the next free number in its block; numbers are
never reused after a mock is deleted.

| Block | Owner | Allocated |
|---|---|---|
| `23000` | Management Portal | `23000` portal |
| `23001`– | Anchanto products | `23001` anchanto-oms · `23002` anchanto-wms |
| `23101`– | third-party systems | `23101` eton |

The block a mock sits in tells you which side of an integration it stands on: a `2300x` address is
Anchanto answering, a `2310x` address is a partner answering. Reading a call log or a HAR, the port
alone settles the direction.

`--port` overrides the config for one run. Use it to run two copies of a mock, not to move a mock
off its allocated number — the number is what the READMEs, the smoke runners and the JPluger local
profile all point at.

`anchanto-wms` is **Anchanto's own WMS product**, Wareo3 — `wms-api.anchanto.com` in prod, called by
`connector/wms3-connector` in the `wms3` area. 27 operations, reference in
[`docs/anchanto-wms-api.md`](../docs/anchanto-wms-api.md).

`anchanto-oms` is **Anchanto's own OMS product**, SelluSeller — `ewmsapi.selluseller.com` in prod,
reached through `SS_DOMAIN` and `selluseller.open.api.base.url` by every marketplace, carrier and
WMS connector. 74 operations, reference in [`docs/anchanto-oms-api.md`](../docs/anchanto-oms-api.md).
Its config is generated by `anchanto-oms/build-config.py`; edit the generator's
table, not the config.

OMS and WMS3 are **two different Anchanto products** behind two different base URLs. `/rest/v2`
alone does not tell them apart — OMS has its own v2 inventory endpoints. Each mock answers 404 on
the other's paths, on purpose, so a misrouted call fails instead of looking healthy.

`eton` is a **third-party** WMS, one of the partners the separate `wms` area integrates with. The two
Every mock also serves:
- **`/`** (root): Test Server dashboard, Living Specs, and test suite runner.
- **`/api`**: API root for mock requests (all spec/config endpoints are reachable under `/api` or directly).
- **`/log`**: Real-time Call Log viewer. See [TESTING.md](TESTING.md).

---

## Call log

Every request and its response is appended to `log_file`, so a run can be handed to someone else,
attached to a ticket, or turned into tests.

**`har`** (default) writes a valid **HAR 1.2** archive — the standard HTTP-log interchange format,
so the file already opens in Chrome/Firefox DevTools, imports into Postman and Insomnia, and feeds
`har-to-k6`, Playwright and `haralyzer`. HAR reserves underscore-prefixed names for custom fields,
so each entry also carries `_curl` (the whole call as one runnable command), `_rule` (which config
rule answered, or `null` for the spec's example), `_seq`, and `_json` alongside the request and
response bodies so a test asserts on objects instead of re-parsing text.

**`simple`** writes a flat JSON array of `{seq, at, durationMs, rule, curl, request, response}`
with parsed bodies throughout.

Notes:

- **Credentials are redacted.** `authorization`, `cookie`, `x-api-key` and friends are written as
  `***redacted***` in both the headers and the generated `curl`. Override with
  `log_redact_headers`. Auth is not simulated, so a redacted call still replays fine.
- **The log survives a kill.** Written to a temp file and renamed, so an interrupted write leaves
  the previous complete log rather than a truncated one; a log that fails to parse is moved to
  `*.corrupt` rather than overwritten; entries are recorded before the response is sent.
- **It grows forever.** Each append rewrites the file, so a very long run gets slow. `--reset` or
  delete the file.

### Viewer — `/log`

Each running mock serves its own log at `/log` on its own address. Calls newest-first, one row
each, showing the URL with a Swagger-style method badge, status and timestamp. Clicking a row
expands it into the **curl request** (with a copy button) and the **server response** (status,
headers, pretty-printed body), plus the rule that answered. Filter box, 3-second auto-refresh with
expanded rows staying open, and **Clear**. Viewing the log never appears in the log.

Plain HTML, no external assets, works offline.
