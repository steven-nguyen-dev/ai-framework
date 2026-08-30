# [TICKET_KEY] Summary — [Short Feature Title]

**Ticket:** `[JIRA_ISSUE_KEY]` — [user story N / feature name]  
**Related:** `[SIBLING_TICKET_KEY]` ([what it covers]) · `[SIBLING_TICKET_KEY]` ([what it covers])  
**Source documents:** `[requirements-doc.md]` · `[change-request-doc.md]` · `[mapping-doc.md]`  
**Author / Team:** `[Author / Team Name]`  
**Written in:** Simplified Technical English. The terms are the ones in `[../CONTEXT.md]`.

---

## How to use this template

*(Delete this whole section before you publish the document.)*

This is the **summary** document. It is written last and read first. It holds conclusions, not
detail, and it replaces no other document. The source documents hold the detail.

**Writing rules.**

- Write in ASD-STE100 Simplified Technical English. Short sentences. Active voice. One idea in one
  sentence. No contractions.
- Use the ubiquitous language from `CONTEXT.md`. Do not invent a second word for a thing that
  already has one.
- When you list more than two things, use bullet points. Do not run them together as sentences.
- Section 2 is a **changelog**, not a story. State the change. Do not describe how you found it, who
  found it, or what you decided along the way.
- Every item in section 2 is **actionable**. Start it with a verb: Add, Remove, Send, Replace,
  Implement, Audit, Keep, Reject, Read.
- Every claim carries a source. A source is an **index into real material** — a specification path, a
  file and line, a URL, a document section. It is never a restatement of your own reasoning.
- Sources are short numbers in the item. The full citation goes in the Sources section at the end.
- Use pure Markdown. Do not use raw HTML anchors — many renderers escape them and print the tags.
- Put defects in a separate defect file. Leave one sentence here that points to it.

**When a fact and an action are both needed,** put the action in 2.1 or 2.2 and the fact in 2.3.
Do not state the same thing twice.

---

## Before you read

This document collects the conclusions of [work package / analysis name]. It replaces no other
document. The source documents hold the detail.

*(Record here anything a reader must know before they trust the document. Examples: a document was
verified and deleted; a section was superseded; a working principle changed the framing.)*

---

## 1. Context

### What the ticket must do

*(State the business situation in plain sentences. Name the actors with the terms from `CONTEXT.md`.)*

[Two or three sentences that set the scene.]

[Lead-in sentence for the first list:]

- [Fact 1]
- [Fact 2]
- [Fact 3]

[Lead-in sentence for the rules the external system imposes:]

- [Rule 1]
- [Rule 2]

### What [OUR_SYSTEM] can do today

[State the current capability. Say what is sent, stored or supported today.]

- [Thing 1]
- [Thing 2]

[State the consequence in one or two sentences. Say plainly whether the current behaviour is
incomplete or wrong — those are different, and the difference matters.]

### The working principle

*(Include this section when the work touches an internal system. Delete it when it does not.)*

We are the integration team. For internal systems such as [INTERNAL_SYSTEM_A] and
[INTERNAL_SYSTEM_B], we decide which properties go on which endpoint payloads. A field that is absent
from the [INTERNAL_SYSTEM] specification is a **change**. It is not an unsupported gap. It is not a
blocker.

We do our part first:

- We agree the shape.
- We update our DTOs.
- We build against that shape.
- We then raise the API task for the internal team.
- We do not wait for that team.

Only the [EXTERNAL_PARTNER] contract is fixed. A field that is absent there is a real constraint.

---

## 2. Changes

A changelog. Each line is an action. The number at the end links to the source in
[Sources](#sources).

### 2.1 [OUR_SYSTEM] work — what we build

*(Actions we own. We do not wait for anybody to start these.)*

- **C-1** [Action.] [[1]](#sources)
- **C-2** [Action.] [[2]](#sources) [[3]](#sources)
- **C-3** [Action.] [[4]](#sources)

### 2.2 [INTERNAL_SYSTEM] changes to request

*(Actions another internal team owns. Give each one a priority. None of them stops our start.)*

- **CR-1** [Action.] — [Priority] [[5]](#sources)
- **CR-2** [Action.] — [Priority] [[6]](#sources)

**[CR-n] carries the most weight.** [One or two sentences on why. Reserve this for the change whose
absence removes the feature, not merely degrades it.]

None of these rows stops our start. We build our DTOs to the agreed shape while the
[INTERNAL_SYSTEM] work runs.

### 2.3 Facts that set the shape of the work

*(Verified facts that constrain the design. State the fact. Cite the source. Do not narrate the
search.)*

- [Fact.] [[7]](#sources)
- [Fact.] [[8]](#sources)

**Consequence to record.** [State any consequence that is uncomfortable but true. A summary that
hides a known gap is worse than no summary.]

### 2.4 Corrections already applied to the source documents

*(What you changed in the source documents while doing this work, so a reader of an older copy is not
misled.)*

- **D-1** [Correction.] [[9]](#sources)
- **D-2** [Correction.] [[10]](#sources)

### 2.5 Conditions to attach to the [SPIN_OFF] ticket

*(Use this section when part of the scope moves to another ticket. Conditions stop the work being
lost in the move. Delete the section when nothing moves.)*

1. [Condition.] [[11]](#sources)
2. [Condition.] [[12]](#sources)

[Name the condition that matters most and say why in two or three sentences.]

---

## 3. Open questions

These are the questions we could not answer. Each one names what would answer it.

*(List only what remains. If a working principle or a finding removed a question, say so in one
sentence — a short list is a result, not an omission.)*

### We asked the source and the source cannot say

**1. [Question?]**
[What the source does say. Where the evidence stops. Be explicit when the answer is "neither
confirmed nor denied" — that is a different result from "no".]
*To answer this: [ask X / read Y].*

### We need production data, not source

**2. [Question?]**
[What we know. What we do not know.]
*To answer this: [audit X].*

### We need [INTERNAL_SYSTEM] to confirm a behaviour

**3. [Question?]**
[What is documented. What must be confirmed. Say whether our work depends on the answer.]
*To answer this: ask the [INTERNAL_SYSTEM] owner.*

---

## Sources

**Keys.** `[KEY_A]` = `[full/path/to/specification.json]`. `[KEY_B]` =
`[full/path/to/other-specification.json]`. All other paths are relative to the
`[REPOSITORY]` root. Class names are given without their package where the name is unique in the
repository.

*(Reuse a number when two items rest on the same source. One source, one identity. Where a source
carries a caveat — it is our own decision, or it covers only one case of several — say so in the
entry. That caveat is often the most useful thing in the table.)*

| # | Source |
| :-- | :--- |
| 1 | `[KEY_A]` → `[path.to.definition]` — [what a reader finds there] |
| 2 | `[File.java:LINE-LINE]` — [what a reader finds there] |
| 3 | `[document.md]` §[N] — [what a reader finds there] |
| 4 | `[KEY_B]` — [`field_name`, 0 occurrences] *(an absence is a citation; the file is where you check it)* |

---

**Note on defects.** All defects found during this work are out of scope for `[TICKET_KEY]` and are
recorded in `[../out-of-scope-defect.md]`.
