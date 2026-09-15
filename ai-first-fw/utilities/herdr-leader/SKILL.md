---
name: herdr-leader
description: Nominate this agent as the Herdr swarm leader for its current tab. Use on /herdr-leader, /lead, or /leader.
version: 1.10.0
disable-model-invocation: true
---

# herdr-leader

Orchestrates worker panes inside the active Herdr tab (`$HERDR_TAB_ID`) via the `herdr` CLI without directly editing code.

## Inputs

- **Roster** — live tab worker table from `pane-limits --init-leader`.
- **Objective** — user's goal, ticket, or problem brief to drive.
- **Coordinator** — swarm-coordinator MCP: session log, task briefs, execution plans, results, scratch payloads.
- **Wiki** — wiki MCP: durable domain knowledge, specs, mappings, traps, decisions. Read with `search`/`get`/`render`; write only with `note`, which files to the inbox for human review.

## Rapid Swarm Launchers

To close existing panes and spawn a fresh, balanced team automatically:
- `clan-l3` / `clone-l3`: 3 workers (`clan` [Opus], `agp` [Gemini], `agr` [Gemini]).
- `clan-l3a` / `clone-l3a`: 3 workers (`clan` [Opus], `cus` [Grok], `gpt` [GPT]).
- `clan-l4` / `clone-l4`: 4 workers (`clan` [Opus], `agp` [Gemini], `agr` [Gemini], `agg` [Gemini]).
- `clan-l5` / `clone-l5`: 5 workers (`clan` [Opus], `agp` [Gemini], `agr` [Gemini], `cus` [Grok], `gpt` [GPT]).

## Standing Orchestrator Directives

### Step 1 — Claim leadership and retrieve live capacity

Run `pane-limits --init-leader` to claim leadership, auto-name workers in `$HERDR_TAB_ID`, and retrieve capacity. Print the returned worker table and ask the user for the objective. Lead only worker panes in `$HERDR_TAB_ID`; leave panes in other tabs to their own sessions.

**Completion:** the leader prints the active worker table with pane IDs, models, recommended roles, and token limits, then awaits the objective.

### Step 2 — Size and assign tasks by model tier

Break the objective into bounded, self-contained briefs. Assign each brief by recommended role:
- **Opus (Top Tier / Smartest Worker)**: High-complexity tasks — architecture design, intricate cross-system refactorings, deep spec/contract synthesis, and hardest root-cause debugging.
- **Gemini (Core Workhorse / Smart Worker — Bulk of Work)**: Normal complexity and below — feature implementation, unit/integration test suites, multi-file code editing, routine audits, and specs building. Gemini panes form the backbone of the swarm and handle the lion's share of tasks.
- **Default / All Others (Simple Worker / Fire & Forget)**: Small, self-contained single-pass units — isolated utility scripts, syntax/formatting/lint cleanup, quick regex, repetitive boilerplate, and localized single-file fixes (e.g. Grok, GPT).

Treat tier roles as soft recommendations; when a target worker is busy, overflow flexibly to capable idle workers.

The token limit is a **pre-dispatch target**: the figure the pane must be under **at the moment the instruction is sent**, not a ceiling to notice after the fact.

**Clear when `current + predicted > limit`.**
- `current` — the pane's usage now, from `pane-limits <target>`.
- `predicted` — what the next task will consume: the brief itself, the files it must read, and the tool output it will generate. Estimate generously; a task that reads a large source file and runs a test suite costs far more than its brief.
- `limit` — **700K** for the big pool (Claude / Gemini / GPT), **210K** default for every other model.

Run `pane-limits <target>` immediately before every dispatch. Each row prints its **headroom** (`limit - current`) — the token budget available to the next task. Compare the prediction against it:
- `predicted <= headroom` — send the brief as it stands.
- `predicted > headroom` — clear first (Step 6), or split the unit so the prediction fits.
- `BREACH` (current is already at or over the limit) — clear before sending, whatever the task's size.

There is no warning band between OK and BREACH: a band cannot know how big the next task is, so it would shout at a nearly-full pane taking a tiny follow-up and stay quiet on an empty pane taking a huge one. The headroom figure and the prediction decide it.

**Completion:** every task brief is sized so that `current + predicted` stays within the model's limit (700K for Claude/Gemini/GPT, 210K default for all others), the headroom is verified at dispatch time, and the brief is assigned to an available worker.

### Step 3 — Delegate through the coordinator

Keep the swarm pane count fixed; allocate all briefs across existing panes.

Open every turn with `swarm-coordinator.session_log()`. It returns the roster and a bounded tail of recent delegations and completions. This is what survives compaction — the roster lives in Redis, not in the context window.

Consult the wiki for domain knowledge ahead of dispatch: use `wiki.search` to locate relevant specs, architecture, and traps.
**When `wiki.search` returns nothing useful, rephrase and retry.** The wiki ranks English full text with a trigram fallback — there is no query expansion, no synonym list and no embedding. You are the expansion: try the domain term instead of the generic one, the external system's own vocabulary instead of ours, a distinctive noun instead of a sentence, and the CJK value itself where one exists. Two or three rephrasings before concluding the wiki does not hold something. A search that returns nothing is a miss to work, not an answer.

Formulate the task for the coordinator:
- **Standard brief**: Pass directly in the `brief` argument of `delegate()`.
- **Large / multi-step plan**: Write the plan into Redis scratch via `swarm-coordinator.put("plan:<step>", plan_markdown)` and reference the key in the brief text (e.g. `Read detailed plan via swarm-coordinator.get("<key>")`). **Never write task plans into the wiki** — the wiki stores durable domain knowledge, while Redis handles ephemeral execution communication with automatic TTL.
- **`wiki_refs`**: Pass only durable domain knowledge chunks the worker needs to consult (e.g. `["standard-flows#4-5-parcel"]`), or `[]` if none.

Dispatch with `swarm-coordinator.delegate(target, brief, wiki_refs)`. One call writes the task, appends the session log and prompts the target pane. It returns the task id.

Every brief template ends with this line, verbatim:

> When finished, call `swarm-coordinator.complete("<task-id>", "done", "<3-line summary>")`. Put anything longer in `swarm-coordinator.put()` and name the key in your summary.

Before dispatch, check capacity with `pane-limits <target>`. Split the brief if the verdict is `HIGH` or `BREACH`. Interrupt a runaway task with `herdr agent send-keys <target> ctrl+c`.

**Read what `delegate` returns.** It reports whether the prompt actually reached the pane:
- `delivery: "confirmed"` — Herdr observed the pane start working. The task is running.
- `delivery: "unconfirmed"` — the command ran; nothing verified it arrived. Treat as sent, but expect Step 4 to catch it if it was not.
- `ok: false` with `herdr_code: "agent_prompt_stalled"` or `"agent_blocked"` — the submission reached no pane. The task is already written to Redis, so **re-prompt that pane; never delegate the same work twice.**

**Completion:** every brief is delegated through `delegate`, referencing relevant domain knowledge in `wiki_refs` and Redis scratch keys for large plans, ending with the `complete` line, and every return value has been read. The turn ends. **Do not wait.**

### Step 4 — Let the completions come to you

Your turn ends after delegating. A worker's `complete` call prompts this pane and starts a new turn. You do not poll, you do not `herdr agent wait`, and you do not ask the user whether the workers are done.

A new turn opens with `session_log()`, then `swarm-coordinator.get("result:<id>")` for the task that woke you.

Three workers finishing together send three prompts, so you take three turns. That is expected.

#### Reconcile every turn — before reading any result

`session_log()` returns every `delegate` and every `complete`. **Pair them.** For any delegate with no matching complete, check that pane before assuming it is still working:

```
herdr agent get <pane>
```

Two different failures leave identical traces in the log, and only the pane tells them apart:

| What you see | What happened | What to do |
|---|---|---|
| Idle, tokens **grew**, files changed | The worker finished and forgot to call `complete` | Prompt that worker once to call `complete` |
| Idle, tokens **unchanged**, tree clean | The dispatch never arrived — it never started | Re-prompt with `Task <id> — call swarm-coordinator.get("task:<id>")` |
| Working, tokens climbing | Still running | Nothing |

Say in your report which you found and what you did about it.

Do this on every turn, including turns that a completion woke you for. A dispatch that silently never started is the failure that costs a whole session, because nothing will ever report it — the write succeeded, the log looks normal, and the pane simply sits there. The user asking "what's happening?" is not a monitoring system.

**Completion:** every task reaches a `result:<id>`, and every turn has paired the log's delegates against its completes before doing anything else.

### Step 5 — Exchange payloads through Redis, not files

`swarm-coordinator.put(name, value)` writes a scratch payload and returns its key.
`swarm-coordinator.get(key)` reads it. Keys expire after 7 days.

A `complete` summary runs to three lines, so a 900-line test dump or ELK extract goes to `put()`; the summary names the key and the next pane calls `get()`. Handoffs between workers travel the same way.

`.scratchpads/` is retired. Do not create it, and do not pass file paths where a key belongs.

Scratch payloads and task execution plans stay out of the wiki. A task plan or scratch payload holds true for twenty minutes or one session; the wiki keeps durable domain knowledge. Writing execution plans or payloads into the wiki pollutes embeddings, changelog records, and domain search results.

**Completion:** no inter-agent payload touches the filesystem.

### Step 6 — Verify on disk, then clear or hand off

Zero blind trust is unchanged. A worker's `complete` is a claim, not evidence. Verify with `git diff`, `ls -la`, `wc -l`, compilers and test suites before accepting anything. Re-delegate immediately if a worker claims success without changing disk or test outcomes.

Durable learning found along the way goes to the wiki's **inbox** — a trap, a decision, a verified mapping — via `wiki.note(slug, body, summary)`, which files it at `inbox/<pane>/<slug>`. Carry the evidence in the body: the file and line, the count, the query, the payload that settles it.

A trap the wiki holds that a worker disproved becomes `wiki.note("<trap-slug>-disproved", …)` with the falsifying observation. You cannot retire the curated chunk — `upsert` and `retire` are not registered on the wiki server, by design. Promotion and retirement are the user's call, and they need your evidence to make it.

**The ticket's deliverable is a file, never a wiki entry.** A plan, an analysis, an implementation contract belongs under `jira-workspace/`. What goes to the inbox is only the fact that outlives the ticket. `search` ignores the inbox, so nothing you file there can mislead a later worker.

Clearing context:

- **Stateless:** `herdr agent prompt <target> "/clear "` (trailing space), then delegate the next brief.
- **Stateful:** delegate a brief asking the worker to `put()` its handoff and report the key; verify the key reads back; `/clear `; then delegate the next brief referencing that key in the brief text (never in `wiki_refs`, which is reserved for wiki chunk IDs only).

**Completion:** every accepted task is corroborated on disk, and every resumed worker resumes from a key that reads back.

## The bar

- The frontmatter carries `disable-model-invocation: true` and a one-liner description for human invocation.
- The `## Standing Orchestrator Directives` heading is preserved for extraction by `pane-limits --init-leader`.
- Swarm leader operations are strictly confined to `$HERDR_TAB_ID`.
- Implementation code is never written by the leader; all work is delegated.
- Task complexity matches recommended model tiers with Gemini absorbing the bulk of work.
- Swarm pane count remains fixed with sequential queueing instead of ad-hoc splitting.
- The token limit is treated as a pre-dispatch target — clear when `current + predicted > limit` (700K big pool, 210K default), done before the next instruction rather than after a finished task.
- Inter-agent payloads travel through `put`/`get`; `.scratchpads/` is never created.
- Every turn opens with `session_log()`; every brief ends with the `complete` line.
- Every turn pairs the log's delegates against its completes, and checks the pane for any delegate without one, before reading results.
- Every `delegate` return value is read; a stalled delivery is re-prompted, never re-delegated.
- Durable learning goes to the wiki inbox via `note`, with its evidence; deliverables stay files.
- The leader never waits on a worker. Completions arrive as prompts.
- All completed work is verified on disk.
- Every step terminates on a checkable completion criterion.


