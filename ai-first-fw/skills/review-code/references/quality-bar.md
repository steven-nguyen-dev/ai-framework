# Quality bar

The bar a pass is answered against. Every file a pass was given carries a §1 answer:

- A file with nothing to report reads `all clear`.
- A file holding a finding or an unsettled line answers item by item, and each unsettled line reads
  `unknown` with what stopped you.
- A file that adds or modifies an entry point, or moves a field to a terminus, answers items 5, 6, 7
  and 9 by name — that is where a silent drop and an open door live, so each carries its own line.

Files the inventory puts in one `shape` group carry one answer between them, written against the
representative the group names and closing `N others share this shape: <paths>`. Eight transformers
generated from one template are one file under eight names, and answering them eight times buys the
same finding eight times. An item that turns on a file's own identity — a name, a value, a call unique
to it — is still answered per file.

The answered checklist is the deliverable; the findings are what falls out of it. Every finding names
the item it fell out of, by number.

## Grading

Grade from blast radius: the boundary a human observes the failure at — the status the caller
receives, the row persisted, the value sent onward, the credential printed, the request that hangs.
A finding names its boundary.

- `blocker` — merge waits on a human disposition.
- `defect` — fix before merge, or take a disposition.
- `note` — neither.

§1 and §2 findings grade on blast radius, up to `blocker`. §3 findings carry `note`.

Severity travels one way: a contradicted requirement lifts a finding one step; every other input
leaves it where blast radius put it, so a leak, a race, an unguarded entry point and a swallowed
failure keep their grade whatever the ask authorised.

## §1 — The code on its own terms

Pass A's checklist, over every carried file. This pass holds the code to itself: it reads what the
diff added, and asks of each line what it does to a caller, a row and a thread.

1. **Resource lifecycle** — every stream, connection, client, lock, transaction, thread pool, session
   and temp file the diff opens: name where it closes on the success path and on every throw. A close
   inside `finally`, try-with-resources or the language's equivalent is the one that holds.
2. **Failure paths** — every call that can throw or return an error: name what catches it, what the
   caller receives, and what state is left behind. A catch that swallows, logs and continues, or
   converts a failure into a success status is a finding on its own.
3. **Concurrency** — name the shared mutable state reachable from two threads, and hold each
   check-then-act sequence, compound operation, publication and blocking call inside a lock against
   it. State held on an instance the container shares across requests is shared state.
4. **Boundaries** — for each new parameter, each new branch condition and each new collection
   operation, name what the type admits and what the code handles. The gap is the finding.
5. **Authorisation per entry point** — every new or modified endpoint, handler, listener or consumer:
   name where the caller's right to *this* resource is checked, in this handler.
6. **Untrusted input** — every value reaching a query, path, URL, command, deserializer, template,
   redirect or reflective call: name the constraint that holds it — a parameterised statement, an
   allow-list, a path canonicalised under its root, output encoded for its sink, an origin or token
   check on a state-changing request, a type-bound deserializer. A value reaching a sink with none of
   these named is the finding.
7. **Secrets and disclosure** — credentials, tokens, keys and personal data in logs, exception
   messages, error responses, and anything serialised outward.
8. **Cost per call** — name the work each new call does as its inputs grow: queries per row, page and
   query bounds, collections that grow with caller-supplied input, an index behind each new predicate
   or join column, allocation per element on a hot path, and the complexity of each new loop nest.
9. **Terminus** — every field the diff moves reaches one: a column, an outbound field, a response, a
   log line. Account for each at its terminus, in the shape and unit it arrived in. A field landing
   nowhere, or landing changed, is a silent drop — no exception, no red test, the count its only
   signal. Pass A raises it as a question; pass C settles it.
10. **Tests** — every new branch is named by a test that fails without it, and every assertion a
    modified test kept still asserts what it asserted.
11. **The stack's own traps** — read the stack and version from the build file, list that stack's
    traps, then read the diff for them.
12. **Naming and shape** — each new name states what the thing does or holds, each new unit does one
    job, and each piece of logic a reader cannot follow from the code carries the comment that
    explains why it is that way.

## §2 — What the base did and this does not

Pass B's checklist. Every line is answered by reading the files in B's inventory at both SHAs. An
added file answers from its own text and from what the base wrote for it to read.

- **Provenance** — every value the diff touches had a supplier at the fixed point. For each read the
  diff removes, each field a framework or mapper filled before the new code runs, and each condition
  the diff rewrote: name who supplied the value then, and who supplies it now. A supplier with no
  successor is a silent regression — no exception, no red test. Count the remaining references to any
  member the diff stopped reading; zero across the module is the finding.
- **Conditionality** — every branch the diff removes, widens, or replaces with an unconditional path:
  name the condition at the fixed point, the inputs it excluded, and what now runs for them. A path
  the base gated and this runs for everything is a silent widening — the excluded inputs carry no
  exception and no red test.
- **Contract at the edge** — a changed signature, DTO field, enum value, column, index, queue message
  or config key: name every caller, producer, consumer and migration at the fixed point, and say for
  each whether it still holds.
- **Tests that were load-bearing** — a test deleted, disabled, retagged, or made to pass by relaxing
  an assertion. Look for it deliberately; it is a `blocker`.
- **Both versions running** — through the rollout and on the rollback. Does the base code work
  against this schema, field and message shape? Does the new code work against the rows and messages
  the base wrote?

## §3 — The smells

Fowler, *Refactoring* ch.3. Match all fourteen against the diff every run — Mysterious Name,
Duplicated Code, Long Function, Long Parameter List, Feature Envy, Data Clumps, Primitive Obsession,
Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle
Man, Refused Bequest.

- Each is a heuristic over the diff's own hunks, so a match names the hunks or files that make it one.
- Each runs once per shape group, not once per file — Duplicated Code across eight files generated
  from one template is one finding naming the group, not eight naming each other.
- Each is reported by its own name, hedged — "possible Feature Envy" — and carried at `note`.
- Each names what is wrong and stops there; the refactoring is the author's.

## §4 — What earns a suppression

A suppression is earned per smell and named in the report.

- **A found authority overrides.** Where the standard endorses what a smell would flag, the smell is
  suppressed and the standard's line is quoted.
- **An enabled tooling rule, quoted.** A rule suppresses a smell where it constrains structure and is
  switched on in the config, per smell and per rule.
- **A sibling's deliberate choice, named.** The nearest working sibling is a convention where it
  holds one consistently — a naming shape, an error-handling shape, a layering rule — and the
  suppression names the file and what it demonstrates. A habit is evidence *for* the finding:
  Duplicated Code, Primitive Obsession, Message Chains, Middle Man and Repeated Switches stand where
  a sibling repeats them, because that sibling is the finding's own evidence.
- **Every suppression is reported.** Close with one line — `smells: <n>/14 · applied: <names> ·
  suppressed: <smell> (<rule or file that earned it>), …` — where the applied names number exactly
  `<n>` and no name stands in both lists, so the coverage line carries what the floor gave up.
