# [TICKET_KEY] Summary — [Short Feature Title]

**Document Identifier:** `[JIRA_ISSUE_KEY]-[TOPIC]-summary.md` (e.g. `IA-5105-product-types-summary.md`)
**Ticket:** `[JIRA_ISSUE_KEY]` — [user story N / feature name]
**Related:** `[SIBLING_TICKET_KEY]` ([what it covers]) · `[SIBLING_TICKET_KEY]` ([what it covers])
**Source documents:** `[JIRA_ISSUE_KEY]-[TOPIC]-mapping-spec.md` · `[JIRA_ISSUE_KEY]-[TARGET_SYSTEM_LOWER]-[TOPIC]-requirements-spec.md`
**Claim library:** `[JIRA_ISSUE_KEY]-[TOPIC]-library.md` — every `L-n` in this document resolves there
**Author / Team:** `[Author / Team Name]`
**Written in:** Simplified Technical English, using the terms in the repository's context file.

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **summary**. It is written last and read first. It is the front door of the contract:
it carries conclusions at the level a reader decides scope from, it carries the definition of done
for all four documents, and it points to the specs for every detail.

**Writing rules.**

- Write in ASD-STE100 Simplified Technical English. Short sentences. Active voice. One idea per
  sentence. Spell out every contraction.
- Use the terms the repository's context file gives. Where that file names a thing, use its word.
- Section 2 states the changes the contract requires. Every item starts with a verb — Add, Remove,
  Send, Replace, Implement, Audit, Keep, Reject, Read — and names the system it lands in.
- `C-n` and `CR-n` are permanent, like `L-n`. Group items by the function they land in and let the
  numbers run out of order. A split item takes a letter — `C-6a`, `C-6b`.
- Keep each item at the level of the logic that changes. The property rows live in the mapping
  spec; the columns and validations live in the requirements spec.
- Put an action in 2.1 or 2.2, and a fact in 2.3. Each thing appears once.
- Section 3 is the definition of done. Give every item of the ticket's own definition of done a
  `D-n` row in the ticket's words, and add a `D-n` for each thing this analysis settles that the
  ticket leaves unstated. `D-n` is permanent, like `L-n`.
- Write every line in the present tense, as the state that holds when the work is done.
- Every claim carries an `L-n`. The claim library states the citation rule and holds every locator.
- Use pure Markdown headings and links.
- Use a bullet list from three items up.

---

## 1. Context

### What the ticket must do

*(State the business situation in plain sentences. Name the actors with the terms the context file
gives.)*

[Two or three sentences that set the scene.]

[Lead-in sentence for the facts:]

- [Fact 1] `L-n`
- [Fact 2] `L-n`

[Lead-in sentence for the rules the external system imposes:]

- [Rule 1] `L-n`
- [Rule 2] `L-n`

### What [OUR_SYSTEM] does today

[What is sent, stored or supported today.] `L-n`

- [Thing 1]
- [Thing 2]

[The consequence, in one or two sentences. Say whether the current behaviour is incomplete or
wrong — those are different results, and the difference sets the scope.]

### Ownership

*(Include this section when the work touches an internal system. Delete it when it does not. Where
the repository's context file states the team's ownership rule, cite that file and delete the rest.)*

[Which contracts this team sets, and which are fixed. State what a missing field means in each
case, and whether this team waits.] `L-n`

---

## 2. Changes

Each line is an action. The `L-n` names its row in the claim library.

### 2.1 [OUR_SYSTEM] work

*(What this team builds. Start each item with a verb.)*

- **C-1** [Action.] `L-1`
- **C-2** [Action.] `L-2` `L-3`
- **C-3** [Action.] `L-4`

### 2.2 [INTERNAL_SYSTEM] changes to request

*(What another internal team builds. Give each item a priority, and name the endpoint it lands on —
the requirements spec holds the rows.)*

- **CR-1** [Action] on `[POST /rest/v1/endpoint]` — [priority] `L-5`
- **CR-2** [Action] on `[POST /rest/v1/endpoint]` — [priority] `L-6`

**[CR-n] carries the most weight.** [One or two sentences. Reserve this for the change whose absence
removes the feature.]

### 2.3 Facts that set the shape of the work

*(Verified facts that constrain the design. State the fact and cite it.)*

- [Fact.] `L-7`
- [Fact.] `L-8`

---

## 3. Definition of done

The work is done when every line below holds. Rows marked `ticket` carry the ticket's own definition
of done, in the ticket's words. Rows marked `analysis` are what this analysis settles on top of it.

| # | Done when | From | Checked at | Claim |
| :-- | :--- | :--- | :--- | :--- |
| D-1 | [The ticket's first definition-of-done item, in the ticket's own words.] | ticket | `[JIRA_ISSUE_KEY]-[TARGET_SYSTEM_LOWER]-[TOPIC]-requirements-spec.md` A-1 | `L-n` |
| D-2 | [The ticket's next item, in the ticket's own words.] | ticket | `[JIRA_ISSUE_KEY]-[TOPIC]-mapping-spec.md` §5 | `L-n` |
| D-3 | [The state this analysis settles that the ticket leaves unstated.] | analysis | `...requirements-spec.md` A-4 | `L-n` |
| D-4 | [What keeps working, stated as the state that holds.] | analysis | `[path/to/existing/tests]` | `L-n` |

**Coverage.** [n] of the [n] items in the ticket's definition of done carry a `D-n` row. `L-n` holds
the ticket's list.

---

## 4. Preconditions

*(Delete this section when the contract needs no decision. Each row names one decision the contract
rests on, the person or team who settles it, and the section that follows from it. Settle a row and
fold the answer into the section it gates, then delete the row.)*

| # | Decision to settle | Owner | Gates | Settled by |
| :-- | :--- | :--- | :--- | :--- |
| P-1 | [The decision, as a question with a stated default.] | `[name / team]` | §2.2 CR-1 · requirements §2.1 | [ask X / read Y / audit Z] |
| P-2 | [The decision.] | `[name / team]` | mapping §6 | [what settles it] |
