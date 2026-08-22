# Writing a test suite

One suite is one file: `<mock>/suite-<name>.py`. The engine in this folder does
preflight, reset, firing, capture, judging and publishing, so the suite file states only what its
flow sends, what has to be true afterwards, and why each case exists. A requirement change or a
defect is an edit to that one file.

The results contract, the verdicts and the traps a runner hits:
[`../TESTING.md`](../TESTING.md). The worked example, carrying every
part of the engine: [`../eton/suite-flow2.py`](../eton/suite-flow2.py).

---

## Write it

**1. Name the calls first.** Read the flow — the integration code, the partner's spec, the mock's
own README — until you can write every call the flow makes to the partner as a method and a path
pattern, and name one value that every call of a single case carries. That value is `call_key`; it
is what makes a case's traffic recoverable from the log without relying on timing. Prefer something
the client already sends over a field invented for the test.

**2. Copy the template.** `cp suite/TEMPLATE.py <mock>/suite-<name>.py`.
`SUITE.id` has to match a `test_suites[].id` in the mock's config, because that id is the folder its
runs are grouped under.

**3. Build the payload from one base.** Write the order, message or document the flow carries once,
then a helper per repeating fragment. A case states only what it changes, so the difference between
two cases is the whole of what distinguishes them. Done when every case's payload differs from the
base exactly where that case's reason differs. Replacing fixtures that already exist: assert each
built payload equals the fixture it replaces, then move the fixtures aside.

**4. Declare the checklist once, in the order the flow happens.** Each check names the assertion in
words and names, in full, the thing it counts. A check reads its expectation by name out of the
case's `expect` block, so every case shares one checklist and differs only in numbers. Done when the
checklist read top to bottom is the journey of one case.

**5. Write the cases.** Identity, payload, `expect`, and `given` / `then` / `note` — what the case is
handed, what it has to prove, and which regression it catches. Done when every case's `note` names
that regression; a case that cannot name one is a case nobody will trust when it goes red.

**6. Give the mock its Run button.** Add `test_suites` to `<mock>/<name>.mock.json`,
`command` naming the suite file — see [TESTING.md](../TESTING.md#declaring-a-runnable-suite).
The command line runs without it; the page needs it.

**7. Prove it, in this order.**

```bash
python3 suite/selftest.py                         # the engine, no app or mock needed
python3 <mock>/suite-<name>.py --list             # every case and what it expects
python3 <mock>/suite-<name>.py --judge <run>      # re-score a folder, fire nothing
python3 <mock>/suite-<name>.py C1                 # one case end to end
python3 <mock>/suite-<name>.py                    # the suite; --fast skips the waits
```

Done when a run folder's verdicts are the ones the flow deserves — including at least one case you
made fail on purpose. A checklist that has never gone red has proved nothing.

---

## The checks

| Check | Reads | Drops itself when |
|---|---|---|
| `ControllerStatus` | the status the app answered the case with | the case was never fired |
| `Calls` | how many calls of one group the case produced | its expectation is absent from the case |
| `Status` | the status the mock answered a group with; `which="all"` holds every answer to it | the group made no calls |
| `Marker` | a business marker inside a response body, matched case-insensitively inside a longer sentence | the group made no calls |
| `Rows` | rows the case left in the database | no database is declared, or none was captured |
| `QueueDelta` | how far a queue grew across the whole run — reported in the case's detail, never judged | the case expects no message |
| `Custom` | an assertion written as a function returning `(expected, actual, ok)` | the function returns `None` |

A dropped check is absent from the results, never green: an assertion about a call that was never
made says nothing, and a database nobody could reach is stated as `not captured`.

---

## Escape hatches

| Reach for | When | Cost |
|---|---|---|
| `Custom` in the suite file | one case asserts something no other case does | nothing outside that file |
| a class in `checks.py` | the same assertion shape turns up twice | every suite gains it |
| a transport in `resources.py`, beside `PostJson` | the flow is fired any way other than one JSON POST — several calls per case, another method, a partner driven directly | written once, then suites are one file again |
| a client in `resources.py`, beside `MySql` and `Queues` | the flow writes to another database, or reports on another broker | same |

Anything under `suite/` is engine: change it, run `selftest.py`, and add a check to
`selftest.py` for what you changed.

| File | The decision that routes here |
|---|---|
| `model.py` | what a suite, a case and a call group are; how a payload override merges |
| `checks.py` | what can be asserted |
| `probes.py` | what preflight refuses to start without |
| `resources.py` | what the suite talks to — the app, the database, the queues, the mock |
| `evidence.py` | what is captured, and how the run folder is read back |
| `engine.py` | the run itself: preflight, reset, fire, judge, publish |
| `run.py` | the command line |

---

## Keeping a suite true

**An expectation changes when the integration does.** Edit the numbers in `expect`, re-score every
run folder already on disk with `--judge`, and write into that case's `note` what the previous
contract was, which commit replaced it, and which run is where the old expectation last failed. The
numbers alone say what the case wants; the note says why anyone chose it, which is what the next
reader needs when the case goes red again.

**A case that cannot prove its last assertion** under the settings a run was given is `blocked`,
not `fail` — declare it with `Blocked(when=…, reason=…)` so a documented gap is never read as a
regression. `suite-flow2.py`'s N10 is the worked example: `@Recover` only reports an order unsynchronized
when `event_name` is the value it compares against, so a run sending anything else leaves that
assertion unproven.
