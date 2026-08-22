---
name: lv1-prompt-builder
description: "Turn a rough requirement — or an existing prompt — into a runnable, self-contained AI prompt: pick a structure (max 5 parts), interview the user (max 5 questions), then run it in-session or extract it for a new session."
disable-model-invocation: true
version: 0.0.1
---

# lv1-prompt-builder

Build one prompt for one AI session from the user's rough requirement, through a short interview. Prompt chains and multi-session pipelines are out of scope.

The whole run is judged by one test — the **fresh-session test**: a new session with zero history, given only the final prompt text, produces the result the user wants. Every step feeds that test.

## Step 1 — Choose the structure

Classify the requirement's purpose and take the matching structure. Five purposes cover the space:

| Purpose | Typical ask | Structure (parts in final order) |
|---|---|---|
| Generate | write, draft, create from scratch | TASK · CONTEXT · RULES · OUTPUT |
| Transform | rewrite, translate, summarize, reformat | TASK · INPUT · RULES · OUTPUT |
| Extract / classify | pull fields, tag, score, review against criteria | TASK · INPUT · RULES · OUTPUT · EXAMPLE |
| Advise / decide | recommend, plan, diagnose, compare | ROLE · TASK · CONTEXT · RULES · OUTPUT |
| Procedure | multi-step job the AI works through in order | TASK · CONTEXT · STEPS · RULES · OUTPUT |

Part meanings:

- **ROLE** — expertise lens, one line, only when it changes the answer ("You are a senior contract lawyer").
- **TASK** — the action, one imperative sentence, then its specifics.
- **CONTEXT** — facts the AI cannot know: domain, audience, and why the work matters.
- **INPUT** — the material worked on, or a marked placeholder: `<<paste X here>>`. One marker covers everything the user supplies at run time, in either shape: pasted material, or a typed value (`<<VERSION>>`).
- **STEPS** — numbered procedure, when order matters.
- **RULES** — constraints, edge cases, and what to do when uncertain.
- **OUTPUT** — format, length, structure, and language of the deliverable.
- **EXAMPLE** — 1–3 input→output pairs, when the format is easier shown than told.

Adjust within the hard cap of **5 parts**: drop a part with nothing to say (a single rule folds into TASK). When the format is easier shown than told, EXAMPLE earns a slot — at 5 parts it displaces the weakest part present rather than becoming a sixth, usually by folding CONTEXT into TASK or STEPS into RULES.

An existing prompt as the requirement → split its text into the chosen structure's parts before marking; a part its own wording already answers is **filled**.

Completion: structure chosen; every part marked **filled** (the requirement already answers it) or **open**.

## Step 2 — Interview

Ask about open parts only — the requirement's own words already fill the rest. No open parts → go straight to Step 3.

One message, up to 3 questions, ordered by damage-if-guessed: (1) deliverable and audience, (2) material and facts the AI works from, (3) quality bar and edge cases. Follow-ups only when an answer exposes a new gap that blocks a part — max 2, hard cap 5 questions for the whole interview.

Question contract:

- One fact per question, in the user's domain language: "Who will read this report?" — the user never needs to know what CONTEXT means.
- Enumerable answer space → offer 2–4 options plus a stated default. Open answer space → ask for the concrete thing ("paste one example row").

At the cap, fill each remaining open part with a stated default written into the prompt itself (`OUTPUT: … in English (assumed)`) and proceed.

Completion: every part filled or defaulted; at most 5 questions asked.

## Step 3 — Build the prompt

Assemble the parts, labeled in CAPS, in the structure's order. One exception: INPUT longer than ~20 lines moves to the top, above TASK.

Every line of the prompt is an instruction or a fact the AI needs. Measurable bounds over adjectives ("150–300 words", not "brief"). State what to do — a "don't" survives only when it has no positive form. Plain text, no courtesy or selling. Every interview answer that matters appears in the text.

Worked example — requirement: "help me turn merged PRs into release notes"; classified Transform; interview gave audience = customers, input = PR titles + descriptions, grouping = New/Improved/Fixed:

```
TASK: Write customer-facing release notes for version <<VERSION>> from the merged pull-request list below.

INPUT: <<paste merged PR list: title + one-line description each>>

RULES:
- Rewrite each PR title as the change a customer sees; skip internal-only changes (CI, refactors, tests).
- Unclear customer impact → keep the original title and mark it [verify].

OUTPUT: Markdown, 150–300 words. Three headings: New, Improved, Fixed; one bullet per change; no intro or closing text.
```

Completion: the prompt passes the fresh-session test — read it back cold and check every fact it depends on is inside it.

## Step 4 — Run or extract

Ask exactly one final question, single-select, exactly two options:

1. **Run prompt** — execute it here, now.
2. **Extract prompt** — print it for a new session.

Run → treat the prompt text as the user's next instruction and carry it out in this session. If the prompt carries `<<placeholders>>`, ask the user to supply each one first — pasted material or a typed value — then run. Run executes with the interview still in context, so it never tests the prompt cold; the Step 3 read-back is the only fresh-session check this branch gets.

Extract → reply with the complete prompt in one fenced code block, followed by at most one line listing assumed defaults. `<<placeholders>>` mark what the user supplies before running.

Completion: the user has chosen; on extract, the whole prompt sits in one fenced block and every `<<placeholder>>` names what to supply.
