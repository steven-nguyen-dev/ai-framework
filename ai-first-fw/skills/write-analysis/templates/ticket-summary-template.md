# [KEY] Summary — [Short Feature Title]

**Document Identifier:** `[KEY]-[TOPIC]-summary.md`
**Requirement:** `[KEY]` — [user story N / feature name]
**Related:** `[SIBLING_KEY]` ([what it covers]) · `[SIBLING_KEY]` ([what it covers])
**Source documents:** `[KEY]-[TOPIC]-mapping-spec.md` · `[KEY]-[TARGET_SYSTEM]-[TOPIC]-requirements-spec.md`
**Claim library:** `[KEY]-[TOPIC]-library.md` — every `L-n` in this document resolves there
**Author / Team:** `[Author / Team Name]`
**Written in:** Simplified Technical English, using the terms the repository's context files give.

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **summary**. It is written last and read first. It is the front door of the contract: it
carries conclusions at the level a reader settles scope from, it carries the definition of done for
all four documents, and it points to the specs for every detail.

**Writing rules.**

- Write in ASD-STE100 Simplified Technical English. Short sentences. Active voice. One idea per
  sentence. Spell out every contraction.
- Use the word the repository's context files give for every system, party, key and wire field, and
  name the context file that owns a term two files share.
- Write every line in the present tense, as the state that holds when the work is done.
- Section 2 states the changes the contract requires. Every item starts with a verb — Add, Remove,
  Send, Replace, Implement, Audit, Keep, Reject, Read — and names the system it lands in.
- Group section 2 by the team that builds it, then by endpoint, flow or domain inside each team. Head
  each inner group with the same unit, in the same order, that mapping spec section 4 and
  requirements spec sections 2 and 3 use. Each team section carries its tier in its heading.
- An `integration` or `internal` gap is an item this codebase builds, in 2.1 with its `C-n`. An
  `external` limit is a precondition in section 4.
- `C-n` and `CR-n` are permanent, like `L-n`. Group items by the function they land in and let the
  numbers run out of order. A split item takes a letter — `C-6a`, `C-6b`.
- Keep each item at the level of the logic that changes. The property rows live in the mapping spec;
  the columns and validations live in the requirements spec.
- Put an action in 2.1 or 2.2, and a fact in 2.3. Each thing appears once.
- Section 3 is the definition of done. Give every item of the requirement's stated definition of done
  a `D-n` row in the requirement's words, and add a `D-n` for each state this analysis settles that
  the requirement leaves unstated. `D-n` is permanent, like `L-n`.
- Every claim carries an `L-n`. The claim library states the citation rule and holds every locator.
- Use pure Markdown headings and links.
- Use a bullet list from three items up.

---

## 1. Context

### What the requirement must do

*(State the business situation in plain sentences. Name the actors with the terms the context files
give.)*

[Two or three sentences that set the scene.]

[Lead-in sentence for the facts:]

- [Fact 1] `L-n`
- [Fact 2] `L-n`

[Lead-in sentence for the rules the external party imposes:]

- [Rule 1] `L-n`
- [Rule 2] `L-n`

### What [THIS_CODEBASE] does today

[What is sent, stored or supported today.] `L-n`

- [Thing 1]
- [Thing 2]

[The consequence, in one or two sentences. Say whether the current behaviour is incomplete or
wrong — those are different results, and the difference sets the scope.]

### Ownership

*(Include this section when the work crosses an `internal` contract. Delete it when it does not.
Where the repository's context files state the team's ownership rule, cite that file and delete the
rest.)*

[Which contracts this team sets, and which are fixed. State what a missing field means in each case,
and the tier that settles it.] `L-n`

---

## 2. Changes

Grouped by the team that builds it, then by endpoint, flow or domain inside each team — the same
units, in the same order, as mapping spec section 4 and requirements spec sections 2 and 3. Each
line is an action, and its `L-n` names its row in the claim library.

### 2.1 [THIS_CODEBASE] work — `integration`

*(What this team builds. Start each item with a verb. Where a value crosses an `internal` contract,
this side widens its ingress and becomes reachable here first; 2.2 carries the request that follows.)*

#### `[POST /path/to/endpoint_a]`

- **C-1** [Action.] `L-1`
- **C-2** [Action.] `L-2` `L-3`

#### `[POST /path/to/endpoint_b]`

- **C-3** [Action.] `L-4`

#### Changes that land on no endpoint

*(Flows, components and assumptions, matching requirements spec section 3.)*

- **C-4** [Action.] `L-n`

### 2.2 [OTHER_SYSTEM] changes to request — `internal`

*(What another internal team builds. Give each item a priority, and name the `C-n` in 2.1 that makes
this side reachable before that team builds. The requirements spec holds the rows.)*

#### `[POST /path/to/endpoint_a]`

- **CR-1** [Action.] — [priority] · this side: **C-1** `L-5`

#### `[POST /path/to/endpoint_b]`

- **CR-2** [Action.] — [priority] · this side: **C-3** `L-6`

**[CR-n] carries the most weight.** [One or two sentences. Reserve this for the change whose absence
removes the feature.]

### 2.3 Facts that set the shape of the work

*(Verified facts that constrain the design. State the fact and cite it.)*

- [Fact.] `L-7`
- [Fact.] `L-8`

---

## 3. Definition of done

The work is done when every line below holds. Rows marked `stated` carry the requirement's own
definition of done, in the requirement's words. Rows marked `settled` are what this analysis adds.

| # | Done when | Tier | From | Checked at | Claim |
| :-- | :--- | :---: | :--- | :--- | :--- |
| D-1 | [The requirement's first definition-of-done item, in its own words.] | integration | stated | `[KEY]-[TARGET_SYSTEM]-[TOPIC]-requirements-spec.md` A-1 | `L-n` |
| D-2 | [The requirement's next item, in its own words.] | internal | stated | `[KEY]-[TOPIC]-mapping-spec.md` section 5 | `L-n` |
| D-3 | [The state this analysis settles that the requirement leaves unstated.] | integration | settled | `...requirements-spec.md` A-4 | `L-n` |
| D-4 | [What keeps working, stated as the state that holds.] | integration | settled | `[path/to/existing/tests]` | `L-n` |
| D-5 | `[this side's endpoint or operation]` is callable and documented, and `[consumer]` reaches it. | integration | settled | `[path/to/api/doc or contract test]` | `L-n` |
| D-6 | Every flow in `[KEY]-[TOPIC]-mapping-spec.md` section 3 runs end to end against the mocks. | integration | settled | `[path/to/mock/suite]` | `L-n` |

**Coverage.** [n] of the [n] items in the requirement's stated definition of done carry a `D-n` row.
`L-n` holds the requirement's list.

---

## 4. Preconditions

*(Delete this section when the contract needs no decision. A row here names an `external` contract
limit, or a decision a named person settles. An `integration` or `internal` gap belongs in section 2
as work. Settle a row and fold the answer into the section it gates, then delete the row.)*

| # | Decision to settle | Tier | Owner | Gates | Settled by |
| :-- | :--- | :---: | :--- | :--- | :--- |
| P-1 | [The limit the party's published contract sets, as a question with a stated default.] | external | `[party / name]` | mapping 4.2 · requirements 2.1 | [read their published page / ask their support] |
| P-2 | [The decision a named person settles.] | integration | `[name]` | mapping section 6 | [what settles it] |
