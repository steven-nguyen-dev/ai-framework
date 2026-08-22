---
name: analysis-handoff
description: Fill the analysis-handoff template from a requirement, its materials and a repo.
disable-model-invocation: true
version: 0.7.1
---

# analysis-handoff

Write one analysis handoff: what must become true for a change, and what it costs.

Two files govern the run. `templates/analysis-handoff.md` carries the shape and the rules of the
writing, in inline comments: two that govern every section — `HOW TO FILL` (fill order, ceilings,
the hand-over list) and `WRITING RULES` (altitude, naming, evidence) — and one under each section
that carries rules of its own, every one of those ending in a `Check:` line. Read the two global
comments before writing a word; a section's own comment is read when you reach that section. No rule
of the writing is repeated in this file — the template is mandated reading and the copy is open from
Step 0 on, so a second copy of a rule is only a source that drifts. This file carries the run: six
steps, and the round every one of them asks in. Read `The round` below before the first question goes out.

## Step 0 — Take the inputs, then open the copy

| Input | Missing → |
|---|---|
| Jira key, and a change name to slug | ask for both — the key heads the handoff, the name makes the slug |
| Requirement source: Jira item, email, MOM, or the user's own words | ask |
| Repo path | ask — nothing from Step 1 on runs without it |
| Budget in days, given or agreed | ask; do not derive one |
| Every other Anchanto product or partner the change reaches | ask — each takes a dependency subsection (§6) |
| Materials: the paths and links the requirement points at | proceed, and open a need row in the watch-out table (§5) once the copy is there |

Every missing row above goes out together as Round 0 — one message, numbered, 💡 on each but the
budget: a recommended budget is a derived budget, so that one goes out bare.

Slug: kebab-case of the change name, or the Jira key lowercased.

Then open the copy, so every read from Step 1 on has somewhere to land:

1. Copy this skill's `templates/analysis-handoff.md` to
   `<repo root>/.scratchpads/<slug>/analysis-handoff.md` in the target repo, and edit that copy.
   The bundled template stays unedited.
2. Add `.scratchpads/` to the repo root's `.gitignore` when it is absent there.

Completion: Round 0 is answered, or every unanswered row of it is back on the frontier; slug, repo
root and Jira key fixed; every other system named; every supplied material path resolves or reads
`not found`; the copy is open at its path — or the run stopped for a missing repo root or Jira key
and said so.

Those two are the inputs nothing can stand in for. With either of them still missing — nobody there
to ask, or the question skipped twice — the run stops here and says which one, rather than inventing
it.

## Step 1 — Read, then grade

Read every requirement source and material yourself, before opening the repo.

Then the repo. Every thing the sources name — flow, component, job, endpoint, config key — goes out
to a sub-agent, in parallel; read one inline when you already hold its path. Ask in the shape the
handoff needs, never per file:

- **trace `<flow>`** — returns the hops in order, and per hop what happens there in the file's own
  words, cited as `file · Class.method` plus the line verbatim, no line numbers.
- **describe `<component>`** — returns trigger, frequency, what it skips, and what it reads and
  discards, each cited in that same form.

Evidence comes back; answers do not. Every column of the flows-touched table (§2.1) is yours to
pick from what arrived.

Write each citation into the copy's evidence table (§A.2) as the read that produced it comes back.
Grade a row's Source `code` when its citation is already sitting there — a grade written ahead of
its citation is a grade from memory, and that is what Step 3 goes looking for.

Put every surprise the user owns onto the frontier now — the watch-out table (§5) is filled last,
and by then the round is cold and the surprises are unrecoverable.

Completion: every flow the sources name has its hops or reads `not found`; every component named
has its trigger and its skips; every flow and component you will write carries its Source grade;
the evidence table (§A.2) already holds a row for every `code` grade you have written.

## Step 2 — Fill the copy

1. Fill the copy under its comments, in the order the `HOW TO FILL` comment gives.
2. Run rounds until the frontier is empty, and write each answer into the section that was waiting
   on it.

Completion: the frontier is empty; every section of the copy is either filled or deleted; the
appendix (§A) carries every question and every citation.

## Step 3 — Self-check

Every comment left in the copy ends in a `Check:` line, except `HOW TO FILL`, which ends in the
hand-over list. Together those lines are the checklist, and they are countable: work the copy top
to bottom and, against each one, quote the line of the copy that satisfies it — or, where the check
is a count or an absence, the number you counted or the search that came back empty. How many
comments there are is the copy's to say and is never a number written here — Step 2 deletes any
section it has nothing for, and that deletes its comment. Then the two checks the copy cannot make
about its own run:

- every citation in the evidence table (§A.2) came back this run, not from memory;
- every `🟡` row was either put to the user in a round and left unanswered, or is owned by somebody
  who is not here — none of them is an assumption you made instead of asking.

Completion: every `Check:` line in the copy and every line of the hand-over list is quoted against,
and both checks pass. The copy is still unstripped — Step 4 is what ends that.

## Step 4 — Strip the copy

Delete every block opening at `<!--` through the first `-->` after it, the ones you just read
included. Nearest-match is the whole rule and needs no list of exceptions: every comment closes
before the next live `-->`. The live ones are the flow arrow (§2.1.<n>) and the change diagram (§3),
which is what the completion criterion checks — leave the diagram as the change's own picture, not
a map of the system that goes stale.

Completion: the copy holds no `<!--`, and the flow arrow (§2.1.<n>) and the change diagram (§3)
still render wherever the copy has them.

## Step 5 — Hand over

Reply with every path written, then two lists, in the copy's own words:

- every watch-out row (§5) whose status is **blocking**;
- every `🟡` question, with the assumption standing in for the answer, and what it costs if the
  answer differs.

Then read the standing assumptions back as ✅ lines and ask the user to confirm them. Their
confirmation ends the run.

Unanswered — nobody there, or the read-back put twice and skipped twice — it takes the treatment
every other unanswered question takes: record it as a `Q<n>` row in the appendix (§A.1) with the
assumptions unconfirmed, and say in the reply that the handoff is a draft pending that confirmation.
That ends the run too.

Completion: the paths and both lists are in the reply, a list with no entries says so, and the
read-back is either confirmed or recorded in the appendix (§A.1) as unconfirmed.

## The round

Every question you put to the user goes out in a round, never one at a time.

**The frontier is every open question this session's user owns whose prerequisites are settled** —
the ones you can ask now, of the person here, without guessing an answer you have not heard. A
question anyone else owns is never on it. Prerequisite order is the template's `HOW TO FILL` order
and nothing else, once Round 0 is out — Round 0 asks the inputs, which sit above the fill order:
nothing can be read without most of them, and the budget is settled before the reading can talk you
into a different one. Below it: a change row (§3) hangs off the flow it changes (§2.1), an
acceptance question (§4) off the change row that needs it, a dependency question (§6) off the change
row that stops at that boundary, and a watch-out row (§5) off all of them. Nobody draws the tree —
the fill order is it.

Compute the frontier. Ask **every** question on it in one message, numbered, each carrying your
recommended answer, the budget excepted (Step 0). Then stop and wait; the answer you write into the
copy is theirs, never your recommendation standing in for it. Record each answer, recompute the
frontier, ask the next round.
A question that depends on another open question waits for the next round; that is the only limit
on a round's size. A skipped question is re-asked in the next round; skipped twice, it leaves the
frontier as a 🟡 assumption, which is what keeps Step 2 finite — the repo root and the Jira key
aside, and those stop the run instead (Step 0).

**Finding facts is your job.** Never ask the user for a fact a sub-agent can read from the repo, the
materials or the tools. A running lookup is an unsettled prerequisite: it holds back only the
questions beneath it, so ask the rest of the frontier now. Here the rule protects the grade as well as the user's time — a question you could have looked
up costs a row the `code` it was entitled to.

**Owner decides the destination.** A question owned by anyone but this session's user — the partner,
another Anchanto product's team, a person who is not here — never reaches the frontier; it is a
watch-out row (§5) or an appendix question (§A.1), with the assumption standing in. This file ships
with open questions by design; that is what 🟡 and `Assumed meanwhile` are for.

**No human in the loop** — write the assumption, mark it 🟡, and carry on.

🧭 ❓ 💡 ⏳ ✅ belong in the chat round. 🟡 is the one that also lives in the handoff.

| Marker | Use |
|---|---|
| 🧭 | Round header |
| ❓ | A question |
| 💡 | Your recommended answer |
| ⏳ | A question held back by a running lookup |
| ✅ | A settled assumption in the read-back |
| 🟡 | An assumption standing in for an answer |

```
🧭 **Round 2** — 3 questions · ⏳ 1 held for a lookup

❓ **Q1 — <question title>**
<the question, the options, and what hangs on the answer>

💡 **Recommend:** <your answer, and the reason in one line>
```
