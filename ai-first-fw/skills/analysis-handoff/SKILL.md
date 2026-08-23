---
name: analysis-handoff
description: Fill the analysis-handoff template from a requirement, its materials and a repo.
disable-model-invocation: true
version: 0.9.0
---

# analysis-handoff

Write one analysis handoff: what must become true for a change.

`templates/analysis-handoff.md` carries the shape and every rule of the writing, in inline comments:
`HOW TO FILL` and `WRITING RULES` govern all sections, and each section has its own comment ending
in a `Check:` line. Read the two global comments before writing a word; a section's comment when you
reach that section. No rule of the writing is repeated here. This file carries the run.

Fill from what you already have, research what is left, ask only what is still open.

## Step 0 — Open the copy

The intake is whatever you were given: a Jira item, an email, meeting notes, a document, the user's
own words. Nothing is required, and nothing about it stops the run.

Slug: kebab-case of whatever names the change — its Jira key lowercased, or a name taken from the
intake.

1. Copy `templates/analysis-handoff.md` to `.scratchpads/<slug>/analysis-handoff.md` under the repo
   root when the run is pointed at a repo, else under the working directory, and edit that copy. The
   bundled template stays unedited.
2. Add `.scratchpads/` to that repo's root `.gitignore` when it is absent there.

Completion: the copy is open at its path.

## Step 1 — Fill from the context

Read everything the session already holds: the request, the requirement source, every attached and
linked document, the repo you are in. Read it yourself, all of it, before any lookup.

Then fill every cell that reading answers, in the `HOW TO FILL` order, each with its Source grade,
and write each citation into the evidence table (§A.2) as you write the claim. What is left unfilled
after this pass is the gap list Step 2 works from.

Completion: every cell the context answers is filled and graded; the rest is a named gap.

## Step 2 — Research the gaps

Only the gaps, against whatever this run can reach — the repo, the linked material, the tools. Every
thing the sources name and the context did not settle — flow, component, job, endpoint, config key —
goes out to a sub-agent, in parallel; read one inline when you already hold its path. Ask in the
shape the handoff needs, never per file:

- **trace `<flow>`** — the hops in order, and per hop what happens there in the file's own words.
- **describe `<component>`** — trigger, frequency, what it skips, what it reads and discards.

Both return citations as `file · Class.method` plus the line verbatim, never a line number. Evidence
comes back; answers do not — the columns are yours to pick from what arrived. Grade a row `code`
only once its citation is sitting in the evidence table (§A.2); a grade written ahead of its
citation is a grade from memory.

Completion: every named gap is filled, or reads `not found`; every `code` grade has its citation.

## Step 3 — Ask what is left

Never ask for a fact the context carries or a sub-agent can read. Ask only what the handoff turns on
— a flow (§2.1), a change row (§3), an acceptance criterion (§4), a dependency (§6). Scope beyond
this change, schedule, cost, staffing and who the document is addressed to turn none of it, and are
never asked.

Questions go out in rounds, never one at a time. A round is every open question this session's
user owns whose prerequisites are settled; the prerequisite order is the `HOW TO FILL` order and
nothing else. Ask them in one message, numbered, each carrying your recommended answer, then stop
and wait. The answer you write into the copy is theirs, never your recommendation standing in for
it. Record each answer, recompute, ask the next round.

- A question anyone else owns — the partner, another product's team, a person who is not here —
  never enters a round: it is a watch-out row (§5) or an appendix question (§A.1), 🟡 standing in.
- Skipped twice, or nobody in the loop: write the assumption, mark it 🟡, carry on.

```
🧭 **Round 2** — 3 questions · ⏳ 1 held for a lookup

❓ **Q1 — <question title>**
<the question, the options, and what hangs on the answer>

💡 **Recommend:** <your answer, and the reason in one line>
```

| Marker | Use |
|---|---|
| 🧭 | Round header |
| ❓ | A question |
| 💡 | Your recommended answer |
| ⏳ | A question held back by a running lookup |
| ✅ | A settled assumption in the read-back |
| 🟡 | An assumption standing in for an answer |

🧭 ❓ 💡 ⏳ ✅ belong in the chat round. 🟡 is the one that also lives in the handoff.

Completion: no open question the user owns is unasked; every section of the copy is filled or
deleted; the appendix (§A) holds every question and every citation.

## Step 4 — Self-check

Work the copy top to bottom and quote, against every `Check:` line and every line of the
`HOW TO FILL` hand-over list, the line of the copy that satisfies it — or, where the check is a
count or an absence, the number you counted or the search that came back empty. How many comments
there are is the copy's to say: a deleted section takes its comment with it.

Then the two checks the copy cannot make about its own run:

- every citation in the evidence table (§A.2) came back this run, not from memory;
- every 🟡 was asked and left unanswered, or is owned by somebody who is not here — none of them is
  an assumption you made instead of asking.

Completion: every line is quoted against and both checks pass. The copy is still unstripped.

## Step 5 — Strip the copy

Delete every block opening at `<!--` through the first `-->` after it, the ones you just read
included. Nearest-match is the whole rule: every comment closes before the next live `-->`. The live
ones are the flow arrow (§2.1.<n>) and the change diagram (§3).

Completion: the copy holds no `<!--`, and the flow arrow (§2.1.<n>) and the change diagram (§3)
still render wherever the copy has them.

## Step 6 — Hand over

Reply with every path written, then two lists in the copy's own words — a list with no entries says
so:

- every watch-out row (§5) whose status is **blocking**;
- every 🟡, with the assumption standing in and what it costs if the answer differs.

Then read the standing assumptions back as ✅ lines and ask the user to confirm them. Their
confirmation ends the run. Unconfirmed — nobody there, or put twice and skipped — record it as a
`Q<n>` row in the appendix (§A.1) and say in the reply that the handoff is a draft pending that
confirmation.

Completion: the paths and both lists are in the reply, and the read-back is either confirmed or
recorded in the appendix (§A.1) as unconfirmed.
