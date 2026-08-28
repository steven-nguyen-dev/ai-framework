# Mock config format

How a mock is configured: adding an integration, the config template, route matching,
conditions, templating, stores, validation, and the theme.

The engine, its CLI and the mocks that exist: [README.md](README.md). Running a suite against
one: [TESTING.md](TESTING.md).

---

## Adding an integration

1. Create `<integration>/` and drop the partner's Swagger/OpenAPI JSON in it.
   Four names inside it are fixed: `mock-data/` for what the mock writes, `seed-data/` for SQL a
   flow has to be seeded with, `test-results/` for runs, and `suite-<name>.py` for a suite.
2. Add a config named `*.mock.json` with `name`, `port` and `spec` — the suffix is what makes
   `python3 mock.py <integration>` find it, and one per folder keeps that unambiguous. **That alone
   is a working server**: every documented operation answers with the document's own example.
3. Add `routes` only for the operations a test needs to steer, and `stores` for any state those
   routes must remember. Prefer a marker inside an identifier the client already sends over
   inventing a new field, so one fixture drives the whole flow.
4. Verify with `--check`, add a row to the integration table in [README.md](README.md), and write
   `<integration>/README.md` covering the markers, the endpoints and anything surprising.

---

## Config template

Everything below is optional except `name` and `port`. Any key named `_comment` is ignored,
anywhere, so a config can document itself.

```jsonc
{
  "name": "Partner WMS",
  "port": 23102,                    // see the port blocks in README.md
  "host": "127.0.0.1",              // default; loopback only
  "spec": "partner-swagger.json",   // relative to this file
  "state_dir": "mock-data",         // where the mock writes: its stores and its call log

  "log_file": "api-calls.har.json", // omit to disable the call log
  "log_format": "har",              // "har" (default) or "simple"
  "log_redact_headers": ["authorization"],
  "log_ui_path": "/log",            // move it if the partner really serves /log
  "test_results_dir": "test-results", // relative to this file, not to state_dir
  "unmatched_status": 404,

  "stores": {
    "created_orders": { "file": "created_orders.json", "type": "set"  },
    "pushes":         { "file": "pushes.json",         "type": "list" }
  },

  "test_suites": [ /* see TESTING.md */ ],

  "routes": [
    {
      "path": "/api/v1/orders",
      "method": "POST",                    // or "methods": ["PUT", "PATCH"]
      "before": [ /* actions run on every request to this route */ ],
      "rules": [
        {
          "name": "shown in the log and on /test",
          "enabled": true,                 // false skips the rule entirely
          "when":    { "body.OrderCode": { "contains": "FAIL" } },
          "then":    [ { "record": { "store": "created_orders",
                                     "values": ["${body.OrderCode}"] } } ],
          "respond": { "status": 500, "body": { "error": "boom" } }
        }
      ],
      "then":    [ /* actions for the fallback below */ ],
      "name":    "no marker -- accepted, 200 \"New\"",   // names the fallback; else it logs "default"
      "respond": { "status": 200,
                   "body": { "Code": "${body.OrderCode}", "Status": "New" } }
    }
  ]
}
```

### Routes

Rules are tried in order, first match wins; a rule with no `when` always matches. The route-level
`respond` is the fallback, i.e. an always-match rule at the end. A configured route replaces the
spec-derived one for the same method and path — everything else in the spec keeps answering from
its example. Matching prefers literal segments, so `/orders/status` beats `/orders/{code}`.

**Name the fallback.** Without a route-level `name` it is logged as `default`, which is the one
rule that answers most calls and the one that then explains nothing — the happy path ends up the
least documented thing in the log. Say what it means: `no marker -- order accepted, 200 "New"`.

`respond` takes `{"status": …, "body": …, "headers": {…}, "delay_ms": 0}`. `delay_ms` is how you
provoke a client-side read timeout.

A path in neither the spec nor the config gets `unmatched_status` and a body naming the method and
path, so a wrong URL fails loudly instead of being silently absorbed.

### Conditions

Sibling keys are ANDed. `all` / `any` / `not` take nested conditions. Any other key is a
**selector** whose value is an operator object, or a bare value as shorthand for `equals`.

```jsonc
"when": { "any": [ { "body.OrderCode": { "contains": "EXISTS" } },
                   { "body.RefCode":   { "contains": "EXISTS" } } ] }
```

**Selectors** — `body.<dotted.path>` (numeric steps index lists, negatives count from the end; bare
`body` is the whole parsed body), `path.<param>`, `query.<name>`, `header.<name>`
(case-insensitive), `method`, `url`, `raw_body`, `validation.<field>`.

**Operators** — `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `ends_with`,
`matches` (regex), `one_of`, `exists` (bool), `in_store` / `not_in_store` (store name).
`contains`, `not_contains`, `starts_with` and `ends_with` ignore case by default, because they
exist to spot a marker inside an identifier; the rest are exact. Add `"case_sensitive": true`
alongside the operator to opt out. A missing selector fails every operator except `exists`, and a
field sent as `null` counts as missing.

### Templating

`${selector}` inside any string in `respond.body` or an action. A string that is *exactly* one
placeholder keeps the selected value's type, so `${body.Qty}` stays a number; anywhere else it is
interpolated as text. `${body.X|fallback}` supplies a value when the selector is missing — without
one, a missing selector renders as `null` (whole-string) or empty (interpolated).

### Actions and stores

- `{"record": {"store": "created_orders", "values": ["${body.OrderCode}"]}}` — adds to a `set`
  store, ignoring blanks and duplicates. Branch on it later with `in_store`.
- `{"append": {"store": "pushes", "entry": {"code": "${path.code}", "body": "${body}"}}}` —
  appends to a `list` store.
- `{"log": "…"}` — prints a rendered line to the server's stdout.

Stores are plain JSON files, re-read per access, so they can be inspected, reset or hand-edited
while the server runs, and asserted against once a test finishes. Use one to make the mock
**stateful** where the partner is: recording what it has accepted lets a replay be answered the way
the real API would, instead of succeeding twice.

### Validation

A Swagger document states only part of what an API rejects — conditional obligations usually live
in prose no generator reads. A rule can carry a `validate` block to write those down, so the mock
refuses the same calls the partner would.

```jsonc
{
  "name": "validation failed",
  "enabled": true,
  "validate": {
    "required":   ["Lines", "Lines[*].SKU"],
    "non_empty":  ["Lines"],
    "max_length": { "Reference": 30 },
    "required_when": [
      { "when":    { "body.Scheme": { "equals": "FULL" } },
        "fields":  ["DistrictCode"],
        "because": "required when Scheme is FULL" }
    ]
  },
  "respond": { "status": 400,
               "body": { "HasError": true, "ErrorMessages": "${validation.errors}" } }
}
```

The rule answers **only when something is actually wrong**; a clean request falls through to the
happy path. Paths are relative to the body unless they name another selector root, and `[*]`
expands over an array so one line reports `'Lines[2].SKU' is required` against the element that
broke it. More than one `[*]` in a path is expanded left to right, each against the list the ones
before it selected — `consignment[*].parcel[*].parcelProduct[*].productHarmonisedCode` is one rule
over every customs line of every parcel of every consignment. Every violation is collected, and exposed to the response template as
`${validation.errors}` (array), `${validation.summary}` (joined string) and `${validation.count}`.

---

## Theme

`/log` and `/test` share one look, and neither stylesheet names a colour — they read `var(--token)`
and the tokens come from [`../local-theme/theme.json`](../local-theme/theme.json). Retheming is a data change, and the two pages
cannot drift apart while it happens.

Precedence, later winning:

1. `THEME_DEFAULT` in `mock.py` — the fallback, so a missing or unreadable `theme.json` degrades to
   the built-in look rather than to an unstyled page.
2. `theme.json` in `local-theme/` — the unified shared theme for test and report servers.
3. A `"theme"` block in an individual `<name>.mock.json` — one mock recoloured without touching the
   others.

```jsonc
"theme": { "canvas": "#101418", "surface": "#161b22", "ink": "#e6edf3" }
```

Keys are CSS custom properties without the `--`. Unknown keys pass straight through, so a token a
page needs can be added without teaching the engine about it first; keys starting with `_` are
treated as commentary and dropped.

Two constraints the file documents and any change should hold: surfaces step apart by roughly 0.1
luminance each (`panel` < `canvas` < `surface-2` < `surface`), because one off-white for page,
panel and card reads as a single field however many hairlines are drawn on it; and `muted` must
clear WCAG AA against `panel`, the darkest surface it can land on, so one token stays safe on all
four.
