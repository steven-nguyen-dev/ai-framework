# <Change name> — Analysis Handoff

| § | Section | Holds |
| --- | --- | --- |
| 1 | Why | the case that fails today, and the systems it lands in |
| 2 | Today | the flows the change touches, and how the system behaves now |
| 3 | Change | what must be different, and which components carry it |
| 4 | Done when | acceptance criteria |
| 5 | Watch out | gaps, traps and unanswered questions |
| 6 | Dependencies | what other systems must change |
| A | Appendix | the open questions, and the evidence behind every grade |

<!-- HOW TO FILL THIS FILE

     Fill in this order; each step feeds the next, and the same order says which question is
     askable when. Today (§2) and Dependencies (§6) are unwritable from the ticket alone.
       1. §2.1 Flows touched — every flow enumerated before any behaviour is described. A
          component list written first misses the flows that only pass through a component, and
          those are the ones that break in the sprint.
       2. §2.2 Behaviour, from code you opened, or from the source the row names.
       3. §1 Why, and the systems it lands in.
       4. §3 Change, then §4 Done when.
       5. §6 Dependencies, from the other system's published contract.
       6. §5 Watch out, from what surprised you in steps 1-2.
     Appendix A fills as you read, not in a step of its own: a citation lands there when the
     read that produced it comes back.

     Ceilings, counting what you wrote and not these comments: 1,500 words for §1-§5 together, and
     500 words per system in Dependencies (§6). The appendix (§A) has no ceiling — that is what it
     is for.
     Delete a section of §1-§6 you have nothing for: an empty section is noise, a missing one is
     information.

     The hand-over list — one line, one check, and the last thing in this comment:
       - every flow (§2.1) whose Status is new or changed is reached by a change row (§3);
       - every change row (§3) maps to an acceptance criterion (§4);
       - every change row (§3) whose Stops at names a boundary cites a dependency subsection
         (§6) that exists — when it does not, write that subsection before this list passes;
       - every component named anywhere in this file has its bullet in the behaviour
         vocabulary (§2.2);
       - every flow (§2.1) whose Status is unknown has a row in the watch-out table (§5);
       - every claim you could not confirm is a question row in the watch-out table (§5), and
         carries 🟡 at the claim it affects when it affects one claim in particular;
       - every row graded `code` has its citation in the evidence table (§A.2);
       - §1-§5 together are within 1,500 words and each system in Dependencies (§6) within 500,
         these comments not counted;
       - every <placeholder> is replaced, and every example row is deleted. -->

<!-- WRITING RULES — they apply to every section

     Altitude. This file names systems, flows and components, and says what they do. Below that
     line — module, class, file, method, property, column, schema — is the developer's document,
     not yours: they own the design, so a column type or an interface in §1-§5 means you wrote
     theirs instead. The test: a reader could rename every class in the repo and not change a
     word of this file. "Order sync asks the partner for one page and never asks for the next" —
     not "the order service passes a null page token". Two exceptions: Dependencies (§6), where
     an endpoint path is another team's contract, and the appendix (§A), which carries the
     citation behind every grade.

     Naming. The three that cost days here.
     — A flow's subject is its originator, and its name carries every hop it crosses and what
       moves between them. Systems are the subjects; the modules inside them stay unnamed.
     — Name an Anchanto product in full on first use: "Anchanto OMS (SelluSeller)", "Anchanto
       WMS (Wareo)", "Anchanto OXM". A bare `OMS`, and any name holding `wms`, resolve to the
       wrong system.
     — Stop a claim where the evidence stops. `unknown, code not in this repo` is a fact; a verb
       you have not read is a guess wearing a verb.

     Evidence. Every flow row and every behaviour row names what you read for it: code, ticket,
     doc, partner contract, or none. That grade is the only thing keeping a ticket claim from
     reading like a code claim. Most systems in a multi-system change have no source on disk,
     and `none` is the honest answer — it is also why that row is not yet a finding, and why a
     system with nothing on disk grades `none` rather than an invented behaviour. Link a source
     inline at the claim that rests on it, not in a header nobody reads; link sources rather
     than pasting them; and leave the citation to the evidence table (§A.2). A citation is
     `file · Class.method` — a property cites as well as a method — plus the line verbatim —
     never a line number, which does not survive the next merge from master.

     Words, not codes. Write "Requirement 31", not "FR-31"; "the ticket's UI section", not the
     ticket's own "§15".
     Identifiers owned outside this workspace keep their real form — a Jira key, a PR number, an
     endpoint path, a field name in someone else's contract. Four identifiers inside this
     workspace stay as codes, because they are what somebody cites back at you: AC1 / AC2 in the
     acceptance criteria (§4), the flow ids in the flows-touched table (§2.1), Q1 / Q2 in the
     appendix (§A.1), and this file's own section numbers — which carry the section's job beside
     them, "the watch-out table (§5)", never a bare "§5".

     Check: no line of §1-§5 names anything below a component, every Anchanto product is named in
     full on first use, every flow row and behaviour row carries a Source, and every section number
     has its job beside it. -->

## 1. Why

<Two or three sentences: the specific case where today's behaviour fails, and who hits it.
Link the source inline.>

**Lands in:** <Anchanto product> `<JIRA-n>` · <Anchanto product> — no ticket yet · <partner> — no ticket

<!-- Write the failure, not the fix. Having no case where today's behaviour breaks is a round
     question, and the rest of the file waits on the answer.
     Lands in names every product and partner this change reaches, and which of them has a
     ticket of its own. This section names them; Dependencies (§6) says what each must change.

     Check: the case names who hits it and what breaks today, and Lands in names every product and
     partner with its ticket or the absence of one. -->

## 2. Today

### 2.1 Flows touched

| # | Flow | Sides | Direction | Reach | Status | Source |
| --- | --- | --- | --- | --- | --- | --- |
| O1 | <originator> -> <hop> -> <target> · <flow name> | internal ↔ external | out | every partner in the area | changed | code |
| I1 | <originator> -> <hop> -> <target> · <flow name> | internal ↔ external | in | the product side | unchanged | code |
| S1 | timer -> <partner> -> <hop> -> <target> · <flow name> | internal ↔ external | self-originated | one partner | new | ticket |
| O2 | <originator> -> <hop> -> <target> · <flow name> | internal ↔ external | out | unknown | unknown | none |

**Return legs**

| # | Returns for | Flow | Direction | Reach | Status | Source |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | O1 | <originator> -> <hop> -> <target> · <what comes back> | in | the product side | changed | code |

<!-- One row per flow this change touches, across every system.

       #          — O for out, I for in, S for self-originated, R for a return leg. The change
                    rows (§3), the acceptance criteria (§4) and the watch-out table (§5) cite
                    these, so number them once and leave the numbers alone.
       Flow       — named from its ORIGINATOR, every hop named, the target last:
                    `anchanto oms (selluseller) -> jpluger -> <partner>`. A timer is the only
                    originator the integration layer may hold. Write a step inside one system as
                    `<system> internal`.
       Sides      — internal ↔ external | internal ↔ internal | external ↔ external.
                    internal is an Anchanto product; external is a partner. Read the value or
                    the config to place a side — the module, area, property or host name it sits
                    behind is not evidence. Only internal ↔ external is attested in the code:
                    claim either other pairing only with a live instance, and say where.
       Direction  — out | in | self-originated. Three, not two. A timer inside the layer
                    originates a flow; calling that flow `in` or `out` invents a requester who
                    does not exist.
       Reach      — who else feels this change, not what carries it:
                    one partner | every partner in the area | the product side | the partner
                    side | both sides | nothing on the transport | unknown.
                    A shared inbound contract reaches every partner in its area; a partner's own
                    contract reaches one. Nothing on the transport is the usual answer for a new
                    business field, because the payload between the two sides is untyped.
       Status     — new | changed | unchanged | stub | unknown.
                    stub    — the behaviour exists in name and does nothing.
                    unknown — you could not trace it.

     Return legs get their own table, always. A result can travel back to a different
     destination and leave to a different address from the one the request arrived on — the
     return leg is never the request leg reversed, and it is the leg a reader forgets exists.
     Write the table even when it holds one row, and write `unknown, not traced` in it rather
     than dropping it.

     Check: every flow this change touches has a row, every request leg that returns anything has
     a return-leg row, every Sides, Direction, Reach and Status cell holds one of the values listed
     above, and every row carries a Source. -->

#### 2.1.<n> <flow id> · <flow name>

```
<originator>  --<what carries it>-->  <hop>  --<what carries it>-->  <target>
```

<One line: what is different about this path after the change.>

<!-- Optional, and only for a flow a change row (§3) changes whose path the row cannot carry.
     Name the systems and what moves between them — a protocol, a topic, a timer. Stop the
     arrow where your evidence stops and write `unknown, code not in this repo` as the last hop. Drop this
     subsection when the flows-touched row (§2.1) says it all.

     Check: this subsection exists only where a change row (§3) cannot carry the path, and the
     arrow stops where the evidence stops. -->

### 2.2 Behaviour

The names this file uses, once each:

- **<component>** — <one line: what it is for>
- **<component>** — <one line: what it is for>

| Area | Flows | Behaves like | Source |
| --- | --- | --- | --- |
| <component> | <the flow ids (§2.1) running through it> | <trigger, frequency, what it skips, what it reads and discards> | code |

<!-- The list above is the vocabulary, declared here and nowhere else: one bullet per component
     this file names — "order sync", "product mapping", "inventory sync". The change rows (§3),
     the watch-out table (§5) and the dependencies (§6) reuse that exact name, so one thread runs
     the length of the file and a reader can follow a single component through it. A definition
     repeated in the change rows (§3) or the dependencies (§6) is the one that drifts; a name
     used later and missing from this list is a second vocabulary; a bullet nothing below uses
     is a component you dropped.

     One row per part of the system the change touches.
       Area         — the component's vocabulary name.
       Flows        — the flow ids (§2.1) that run through this component. A component with no flow id
                      is either out of scope or a flow you have not written down yet.
       Behaves like — current behaviour in a few words: what triggers it, how often, what it
                      skips, and what it reads from the partner and throws away.
     Add rows for what surprised you even when out of scope — cheaper written here than
     discovered mid-sprint.

     Check: every component this file names has one bullet here and nowhere else, every bullet is
     used below, and every row names the flow ids (§2.1) running through it. -->

#### 2.2.<n> <component>

<The claims the row could not hold.>

<!-- Optional, and only where the Behaves like cell cannot carry the behaviour — a trigger with
     conditions, a skip rule with exceptions, an ordering that matters, two flows through one
     component behaving differently. Same altitude as the row: what the component does. Drop
     this subsection when the row says it all.

     Check: this subsection exists only where the Behaves like cell could not carry the behaviour,
     and it stays at the row's altitude. -->

## 3. Change

| # | What must be different | Reaches | Stops at |
| --- | --- | --- | --- |
| 1 | <end state that must be true> | <the flow ids (§2.1) and behaviour areas (§2.2) this row touches> | <the boundary this row stops at, and its dependency subsection (§6)> |

```mermaid
flowchart LR
  A[<actor>] -->|<what flows>| B(<component from the vocabulary (§2.2)>)
  B --> C{<the decision that changes>}
  C -->|<case>| D[<outcome>]
  C -->|<case>| E[(<outcome>)]
```

**Components this lands in**

| Component | Needs |
| --- | --- |
| <component from the vocabulary (§2.2)> | <what it must start or stop doing, in behaviour terms> |

<!-- One numbered row per change, written as an end state ("orders are identifiable by X"),
     never as an instruction ("add column X").
       Reaches  — the flow ids (§2.1) and behaviour areas (§2.2) this row touches, so a reader
                  can walk from a change back to the flow it changes. A flow whose Status is changed
                  that no row reaches is either mis-statused or a change you have not written.
       Stops at — where this repo's work ends and someone else's begins, named with the
                  dependency subsection (§6) that carries the rest: "the partner's order API ·
                  §6.1.1". Write
                  `nothing, ends here` when the row is wholly ours, and `unknown` when you
                  could not trace where it stops. Every row gets a value: a row stopping at a
                  boundary with no dependency subsection (§6) to cite is a dependency nobody has
                  written
                  down, and this column is where that shows.
     The diagram is optional.
     The components table is the blast radius, held at component level.

     Check: every row is an end state, names the flows (§2.1) and behaviour areas (§2.2) it
     reaches, and holds a value in Stops at. -->

## 4. Done when

- **AC1** — Given <state>, when <action>, then <observable result>.
- **AC2** — <the next one, same shape>

**Not in scope:** <thing a reader would assume is included> — <why>.

<!-- One AC per testable behaviour, in Given / When / Then, in the words QA will use. Keep each
     result observable from outside the system — a status, a payload, a row, a log line.
     An AC that changes a flow names its flow id (§2.1), so QA knows which path to drive.
     Name the ACs that cannot pass on this repo alone, and which dependency subsection (§6) each
     waits on.
     Not in scope names what a reasonable reader would assume is included, and why it is not.
     Write it even when it feels obvious — it is the line that stops scope creep at code
     review.

     Check: every AC is Given / When / Then with a result observable from outside, an AC that
     changes a flow names its flow id (§2.1), and Not in scope is written. -->

## 5. Watch out

| Component · flow · gap | Change to | Owner | Status |
| --- | --- | --- | --- |
| **<component, or flow id and name>.** <the condition that is wrong, missing, or contradicts what a reader would assume> | <what it must become> | dev | flagged |
| <need: access, credential, environment, decision> | <what unblocks it> | <name> | requested <yyyy-MM-dd> |
| 🟡 `Q<n>` <question — and what you assumed in the meantime> | <what changes if the answer is no> | <name> | **blocking** |

<!-- Every row ends in something someone does differently: the left column names the gap, the
     right column names what it must become. A row that ends in nothing is a description, and
     descriptions get deleted.

     Write the consequence, not what the code already shows. "The connector uses a 10-thread
     pool" is not a watch-out. "Two stores syncing at once corrupt each other's variant state"
     is.

     Three kinds of row, mixed freely:
       trap     — costs days if met unprepared: a behaviour that contradicts the requirement,
                  data that violates the shape you would assume, a silent dependency.
       need     — must exist before work can start: credentials, sandbox, access, a decision.
       question — prefix 🟡, unconfirmed. Say what you assumed in the meantime, and what it
                  costs if the answer is no.

     Every flow (§2.1) whose Status is unknown lands here, as a question or a need.

     Every question is a `Q<n>` row in the appendix (§A.1). This section keeps the blocking ones and
     cites the rest by number, so it always holds every trap, every need and every blocking
     question — those are what the developer acts on tomorrow, and nineteen questions bury them.

     Owner is a person's name, or `dev`. Status is one word, plus the date where one exists;
     use **blocking** when the developer cannot start without it.

     Check: every row ends in something someone does differently, every trap, every need and every
     blocking question is here, and every row carries an owner and a status. -->

## 6. Dependencies

What another system must change for the end-to-end flow to work. Request in, response out.

### 6.1 <System>

#### 6.1.1 `<METHOD> <endpoint path>`

<One line: which flows (§2.1) cross this endpoint, and which other endpoints share this payload.>

**Request**

| Action | What | For |
| --- | --- | --- |
| add | <field or value we need to send, described> | <Requirement n · ACn> |
| remove | nothing | |

**Response**

| Action | What | For |
| --- | --- | --- |
| add | <what we need back, and what we do with it> | <Requirement n · ACn> |
| remove | nothing | |

#### 6.1.<n> Answers we need — no change if the answer is yes

| # | Question | If no |
| --- | --- | --- |
| 1 | <what we need confirmed about their contract> | <which subsection above grows, or what becomes unsized> |

### 6.<n> <System with no endpoint>

<One or two sentences. What they must provide or approve, and its lead time.>

<!-- Only the wire: an endpoint, a request delta, a response delta. You do not know this system,
     so describe the value you need rather than naming a field they may not have, and quote a
     field name only where their published contract already holds it.

     Two tables per endpoint, always both. Write "remove | nothing" and "add | nothing" rather
     than dropping the table — an empty row proves you considered it; a missing table reads as
     an oversight.

     Number every subsection. The change rows (§3), the acceptance criteria (§4) and the
     watch-out table (§5) point at these numbers, so they must be citable.

     Answers we need is not a change request. It is the set of questions whose answer decides
     how much of the section above is real work. Give each one its cost when the answer is no —
     that is what turns a question into a scheduling decision.

     A dependency with no endpoint — an approval, a credential, an upstream story, test data —
     gets its own subsection and one or two sentences. Its value is that it is named and
     numbered, not that it is described.

     Check: every endpoint subsection is numbered and carries both tables, and every dependency
     with no endpoint has its own numbered subsection. -->

## Appendix A — questions and evidence

### A.1 Questions

| # | Question | Why it matters | Assumed meanwhile | Cost if the answer differs | Owner | Blocking |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | <what is unconfirmed> | <what rests on it — a change row (§3), an AC, a flow (§2.1)> | <what you wrote in the handoff while waiting> | <what changes, and roughly what it costs> | <name> | no |

Under a question whose sources disagree, one comparison table — three documents with three answers do not fit
in a cell:

| Source | Says | Read on |
| --- | --- | --- |
| <document, ticket, or person> | <the answer that source gives> | <yyyy-MM-dd> |

### A.2 Evidence

| Supports | Citation | Says |
| --- | --- | --- |
| <flow id (§2.1), or behaviour area (§2.2)> | <file · Class.method> | <the line, verbatim> |

<!-- This appendix ships with the handoff — it is content, and it has no ceiling.

     A.1 — one row per question, numbered Q1 upward. The watch-out table (§5) cites the numbers,
     so they do not get reused. Assumed meanwhile is the column that lets work continue — a
     question with no assumption beside it stops the sprint rather than steering it.

     A.2 — one row per citation, written as the read that produced it comes back. Supports names
     the flow id (§2.1) or the behaviour area (§2.2) the citation grades; every row graded `code`
     up there has a row down here, and that is what makes the grade checkable by the developer
     holding this file. Quote the line rather than paraphrasing it, in the citation form the
     writing rules give.

     Check: every question is numbered with an Assumed meanwhile beside it, and every row graded
     `code` above has its citation row here. -->
