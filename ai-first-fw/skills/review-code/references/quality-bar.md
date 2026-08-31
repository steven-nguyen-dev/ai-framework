# Quality bar

The bar a pass is answered against. Every line of §1 is answered for every changed file, and every
line of §2 at both SHAs: a line with nothing to report reads `clear`, and a line you could not settle
reads `unknown` with what stopped you. The answered checklist is the deliverable; the findings are
what falls out of it.

§1 and §2 grade on blast radius and reach `blocker`. §3 carries `note`.

## §1 — The code on its own terms

Pass A's checklist. This pass holds the code to itself: it reads what the diff added, and asks of
each line what it does to a caller, a row and a thread.

1. **Resource lifecycle** — every stream, connection, client, lock, transaction, thread pool, session
   and temp file the diff opens: name where it closes on the success path and on every throw. A close
   inside `finally`, try-with-resources or the language's equivalent is the one that holds.
2. **Failure paths** — every call that can throw or return an error: name what catches it, what the
   caller receives, and what state is left behind. A catch that swallows, logs and continues, or
   converts a failure into a success status is a finding on its own.
3. **Concurrency** — shared mutable state reachable from two threads, check-then-act sequences,
   non-atomic compound operations, unsafe publication, a blocking call inside a lock, and state held
   on a bean that outlives one request.
4. **Boundaries** — null, empty, zero, negative, one element, max size, off-by-one, overflow,
   duplicate and out-of-order, for each new parameter, each new branch condition and each new
   collection operation. For each, name what the type admits and what the code handles.
5. **Authorisation per entry point** — every new or modified endpoint, handler, listener or consumer:
   name where the caller's right to *this* resource is checked, in this handler. Authentication
   elsewhere answers a different question.
6. **Untrusted input** — every value reaching a query, path, URL, command, deserializer, template,
   redirect or reflective call: name what constrains it. Parameterised statements, an allow-list of
   hosts, a canonicalised path resolved under its root, output encoded for its sink, an origin or
   token check on a state-changing request, and a type-bound deserializer are the constraints that
   hold; injection, XSS, CSRF, path traversal, SSRF and deserialization of caller-supplied types are
   what stands where one is missing.
7. **Secrets and disclosure** — credentials, tokens, keys and personal data in logs, exception
   messages, error responses, and anything serialised outward.
8. **Cost per call** — a query inside a loop over rows, an unbounded query or page size, a loop or
   collection that grows with caller-supplied input, a new predicate or join column with an index
   behind it, an allocation per element on a hot path, and the complexity of each new loop nest.
9. **Terminus** — every field the diff moves reaches one: a column, an outbound field, a response, a
   log line. Account for each at its terminus, in the shape and unit it arrived in. A field landing
   nowhere, or landing changed, is a silent drop — no exception, no red test, the count its only
   signal. Pass A raises it as a question; pass C settles it.
10. **Tests** — every new branch is named by a test that fails without it, and every assertion a
    modified test kept still asserts what it asserted.
11. **The stack's own traps** — read the stack and version from the build file, list that stack's
    traps, then read the diff for them. Java Spring Boot is the expected target.
12. **Naming and shape** — each new name states what the thing does or holds, each new unit does one
    job, and each piece of logic a reader cannot follow from the code carries the comment that
    explains why it is that way.

## §2 — What the base did and this does not

Pass B's checklist. Every line is answered by reading the changed files at both SHAs.

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

Fowler, *Refactoring* ch.3, matched against the diff every run. Each reads *what it is* → *how it is
fixed*, and each is a labelled heuristic — "possible Feature Envy" — carried at `note`.

- **Mysterious Name** — a function, variable or type whose name leaves what it does or holds unsaid.
  → rename it; where no honest name comes, the design is the finding.
- **Duplicated Code** — the same logic shape stands in more than one hunk or file in the change.
  → extract the shape, call it from both.
- **Long Function** — a function holding several jobs, read by scrolling. → extract each job to a
  named function.
- **Long Parameter List** — a call taking more arguments than a reader holds at once. → pass the
  object the arguments describe, or derive them inside.
- **Feature Envy** — a method reaching into another object's data more than its own. → move the
  method onto the data it envies.
- **Data Clumps** — the same few fields or parameters travel together, a type waiting to be born.
  → bundle them into one type and pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept. → give the
  concept its own small type.
- **Repeated Switches** — the same switch or if-cascade on the same type recurs across the change.
  → replace it with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff.
  → gather what changes together into one module.
- **Divergent Change** — one file is edited for several unrelated reasons. → split it so each module
  changes for one reason.
- **Speculative Generality** — abstraction, parameters or hooks serving a need the ask does not
  carry. → inline it back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller depends on. → hide the walk behind
  one method on the first object.
- **Middle Man** — a class or function that mostly delegates onward. → call the real target direct.
- **Refused Bequest** — a subclass or implementer that overrides or ignores most of what it inherits.
  → use composition.

## §4 — What earns a suppression

A suppression is earned per smell and named in the report.

- **A found authority overrides.** Where the standard endorses what a smell would flag, the smell is
  suppressed and the standard's line is quoted.
- **An enabled tooling rule, quoted.** A rule covering the smell and switched on in the config
  suppresses it, per smell and per rule; formatting rules cover none of §3.
- **A sibling's deliberate choice, named.** The nearest working sibling is a convention where it
  holds one consistently — a naming shape, an error-handling shape, a layering rule — and the
  suppression names the file and what it demonstrates. A habit is evidence *for* the finding:
  Duplicated Code, Primitive Obsession, Message Chains, Middle Man and Repeated Switches stand where
  a sibling repeats them, because that sibling is the finding's own evidence.
- **Every suppression is reported.** Close with one line — `smells: <n>/14 applied · suppressed:
  <smell> (<rule or file that earned it>), …` — so the coverage line carries what the floor gave up.
