# Running tests against a mock server

How a mock is turned into a test rig: declaring a suite so it can be started from the browser, the
results file the page renders, and the contract a runner has to meet.

Engine and CLI: [README.md](README.md). Config format: [CONFIG.md](CONFIG.md). What a specific
mock does: its own folder's README.

---

## The `/test` page

Every running mock serves **`/test`** on its own address, next to `/log`. Left panel is one section
per suite — its description, its options, its **Run** button, and its own runs nested underneath,
newest first, collapsed past ten. The content is a table of case results; clicking a row expands it
into expected against actual, the calls the case produced, and whatever else the runner captured.

**The engine renders, it never judges.** Whatever runs the tests writes `results.json`.

### Where runs live

```
<mock folder>/test-results/        override with "test_results_dir"
└── <suite-id>/                    one folder per test_suites[].id
    └── run-<stamp>/
        ├── results.json           the verdicts — a folder without one is not a run
        └── …                      evidence, left alone and listed
```

Results are addressed from the config's own folder, not from `state_dir`, so moving what the mock
writes into `mock-data/` leaves every run where it was.

A run is grouped by the folder it sits in, so a runner writing to `test-results/<its suite id>/`
gets grouped correctly without telling the server anything. Runs found anywhere else — directly in
the results dir, or under a folder matching no declared suite — are listed under **Unfiled runs**
rather than hidden. A suite renamed in the config, or removed from it, is precisely when its old
runs need to still be reachable.

---

## Declaring a runnable suite

Add `test_suites` to the mock config. The page then shows a **Run** button per suite, streams the
output live, and reloads the results when it finishes.

```jsonc
"test_suites": [
  { "id":          "flow2",
    "name":        "createOrder flow 2",
    "description": "OMS -> partner, 17 cases",
    "estimate":    "~6 min, or ~90s fast",
    "command":     ["python3", "./suite-<name>.py"],
    "options":     [ { "flag": "--fast", "label": "Fast — skip the two retry cases" } ] }
]
```

The command resolves relative to the config file and runs with that folder as its working
directory. One run at a time; **Stop** terminates it.

`id` is also the folder its runs are grouped under, so the runner has to agree on it — a suite file
declares it as `SUITE.id` and the engine records it in `meta.json` and `results.json`, so a folder
that gets moved still says what produced it.

**The browser can only name a suite, never a command.** The command lives in the config, which is
already trusted, and the only arguments accepted are the exact `options[].flag` strings that suite
declares — anything else in the request is dropped. Combined with the default bind to `127.0.0.1`,
the page cannot run anything the config does not already permit. The `command` field is not sent to
the browser at all.

---

## `results.json`

```jsonc
{
  "name":     "createOrder flow 2 (OMS -> partner)",
  "at":       "2026-08-14T03:47:19Z",
  "summary":  { "pass": 15, "fail": 1, "blocked": 1 },
  "evidence": { "status": "complete", "mock log": "captured",
                "orders table": "not captured" },
  "cases": [
    { "id":       "N1",
      "name":     "Plain item - happy path",
      "shape":    "normal",
      "checks":   [
        { "label": "create calls sent", "what": "POST /api/v0.2/saleorders/single",
          "expected": "1", "actual": "1", "ok": true },
        { "label": "rows written to orders", "what": "rows in `orders` for SO-ETON-CO-N1",
          "expected": "1", "actual": "1", "ok": true }
      ],
      "expected": "create x1 -> 200, pricing x0",
      "actual":   "create x1 -> 200, pricing x0",
      "verdict":  "pass",
      "given":    "what the case is handed",
      "then":     ["one acceptance criterion per entry"],
      "note":     "why this case exists — what regression it catches",
      "detail":   { "order_id": "92000001" },
      "calls":    ["create  -> 200  [default]"] }
  ]
}
```

Only `cases[].id` and `verdict` are required; everything else renders when present.

**Report `checks`, one entry per assertion, and a one-line `summary`.** A case asserts several
things at once, and a single string that packs them together — `create x1 -> 200, 'New', pricing
x0, db 1` — cannot be read without a key that exists nowhere on the page. `label` names the
assertion in words, `what` names the thing being counted in full and shows on hover, which is where
partner vocabulary gets spelled out.

How the page uses them:

| Case | Shows |
|---|---|
| passing | `summary` on one line, plus `n/n` beside the verdict |
| failing | only the checks that failed, aligned, the row tinted; the rest collapse to a count |
| clicked | every check, `expected` beside `actual`, each marked |

Seventeen green checklists bury the one row that matters, so the breakdown is what a failure gets
and what anyone can ask for — not the default. A runner reporting only the older
`expected`/`actual` strings still renders; they are shown stacked.

**Say what the case proves, not what it does.** `given` / `then` / `note` render above the detail
table when a row is expanded. A one-line label — `carrier data.order_adjustment.adjustments` — is
shorthand only its author can read; a reader arriving at a red row needs the input, the criteria,
and why anyone cared. The reasoning usually already exists in the plan the suite was written from,
and belongs in the case file where the page can reach it.

| Verdict | |
|---|---|
| `pass` / `fail` | the obvious two |
| `blocked` | could not prove anything, for a known reason — kept distinct from `fail` so a documented gap is not read as a regression |
| `skip` | not run |
| `pending` / `running` / `sent` | in flight, see below |

---

## Writing a suite

**One suite is one file.** `suite/` holds the engine every suite shares — preflight,
reset, firing, capture, judging and publishing — so a suite file declares only what its flow sends,
what has to be true afterwards, and why each case exists. A requirement change or a defect is an
edit to that one file, with no runner to keep in step with it.

How to write one, the check vocabulary, and what each escape hatch costs:
[`suite/README.md`](suite/README.md). Start from [`TEMPLATE.py`](suite/TEMPLATE.py) beside it.

```bash
python3 eton/suite-flow2.py                  # every case
python3 eton/suite-flow2.py --fast           # skip the cases that only wait out a backoff
python3 eton/suite-flow2.py N1 K1 K4         # only the cases named
python3 eton/suite-flow2.py --list           # the cases and what each expects
python3 eton/suite-flow2.py --judge <run>    # re-score a folder, fire nothing
python3 suite/selftest.py                    # the engine itself, no app or mock needed
```

**`--judge` is what an expectation change is checked with.** Verdicts are read out of the run
folder, never out of the live mock, so editing the numbers and re-scoring the runs already on disk
says which of them the new contract agrees with — without firing anything. It is also how a suite
whose expectations changed explains itself: `run-20260816-231529` is where N12's old expectation
last failed, and re-judging it under the new one is a second's work.

---

## The runner contract

The engine above already meets this; it is written down for anything that does not use it.

A runner is any executable. To behave well on the page it should:

1. **Publish `results.json` before the first case**, every case `pending`. The page follows the
   newest run while a suite is going, so this is what makes it track the live run instead of the
   last finished one.
2. **Mark the case in flight `running`**, and judge each case as soon as it settles — so the table
   shows a real pass/fail as it goes, not a placeholder that resolves only at the end.
3. **Overwrite with the final verdicts** when everything has run.
4. **Capture its evidence into the run folder** — the mock's call log, whatever database or queue
   state the assertions need. Anything it could not capture should read `not captured` rather than
   silently passing. **Accumulate, never overwrite**, and judge from the folder rather than the
   live file — see the trap below.
5. **Reset what it owns first** — the mock's stores, the call log, and any rows a previous run
   left behind. A run that inherits state is not repeatable.
6. **Write into its suite's folder** — `test-results/<suite-id>/run-<stamp>/`. That folder is what
   groups the run on the page.
7. **Preflight loudly.** Check the app, the mock, the database and the fixtures *before* firing.
   A missing seed row produces an identical failure in every case and tells you nothing; a
   preflight that names it takes a second.

### Traps worth knowing

- **stdin.** If the runner loops over a plan file on stdin, anything inside the loop that consumes
  stdin — `docker exec -i` above all, which is how `mysql` is reached when there is no local
  client — swallows the rest of it and the loop silently ends after one case. Read the plan on a
  dedicated file descriptor (`read <&3` / `done 3<`) and give stdin-hungry commands `< /dev/null`.
- **Empty arrays under `set -u`.** macOS ships bash 3.2, where `"${arr[@]}"` on an empty array is
  an unbound-variable error, and the `:-` workaround expands to one empty string — which turns
  "run everything" into "match the empty id", i.e. run nothing. Avoid arrays for that.
- **Live evidence is not the run's evidence.** The call log and the stores are global and stay
  mutable for as long as the mock is up: the Clear button on `/log` deletes the log, and any second
  runner's reset empties the stores. A runner that re-fetches them into its run folder on each case
  copies that loss over its own record. Run `20260814-140740` captured N1–N10 correctly, overwrote
  the file at 14:10 with a log someone had just cleared, and reported ten passing cases as `fail` —
  `seq` restarted at 1 and the calls simply were not there to count. Union each capture into what
  the folder already holds, renumber on merge (`seq` comes from the file's length, so a cleared log
  restarts it and collides), and note a live file that has shrunk instead of letting it erase the
  record. `suite/evidence.py`.
- **Async transports.** If the app consumes from Kafka or a queue, the controller returning 200
  means "published", never "succeeded". Wait before asserting, and assert on the mock.
- **The mock is not the partner.** Where the real API is stateful, make the mock stateful too —
  otherwise a retry is answered as a fresh success and the integration does something it would
  never do in production. That is a mock artefact, and it will look like a defect.

---

## Reference implementation

[`eton/suite-flow2.py`](eton/suite-flow2.py) is the worked example, and the
only file its suite has: 17 cases fired at the JPluger controller and judged against the Eton
mock's call log, the `orders` table and the `pushUnsynchronizedOrder` queue. It carries every part
of the engine — two call groups, a checklist of seven, mock stores, a database dump and reset, a
queue watched before and after, a seed preflight that names the schema actually holding the fixture,
and a case marked `blocked` under a documented gap. Runs land in
`eton/test-results/flow2/run-<timestamp>/`. See [eton/README.md](eton/README.md).

The engine behind it is `suite/`, and what each of its files decides is listed in
[its README](suite/README.md).
