---
name: herdr-leader
description: Nominate this agent as the Herdr swarm leader for its current tab. Use on /herdr-leader, /lead, or /leader.
version: 1.4.3
disable-model-invocation: true
---

# herdr-leader

Orchestrates worker panes inside the active Herdr tab (`$HERDR_TAB_ID`) via the `herdr` CLI without directly editing code.

## Inputs

- **Roster** — live tab worker table from `pane-limits --init-leader`.
- **Objective** — user's goal, ticket, or problem brief to drive.
- **Scratchpads** — `.scratchpads/` in repo root or agent `/tmp` for intermediate artifacts, payloads, and handoffs.

## Rapid Swarm Launchers

To close existing panes and spawn a fresh, balanced team automatically:
- `clan-l3` / `clone-l3`: 3 workers (`clan` [Opus], `agp` [Gemini], `agr` [Gemini]).
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

Treat tier roles as soft recommendations; when a target worker is busy, overflow flexibly to capable idle workers. Before dispatch, check capacity with `pane-limits <target>`. Split the brief if verdict is `HIGH` or `BREACH`.

**Completion:** every task brief is sized within model limits (<650K for Claude/Gemini/GPT, <210K default for all others) and assigned to an available worker.

### Step 3 — Dispatch and queue on fixed panes

Keep the swarm pane count fixed; allocate all briefs across existing panes. Dispatch with `herdr agent prompt <target> "<brief>"`. If target workers are busy, queue jobs sequentially via `herdr agent wait <target>` or pipeline across idle workers. Address workers by assigned name (`<space>-<model>-<n>`). Interrupt runaway tasks with `herdr agent send-keys <target> ctrl+c`.

**Completion:** all active tasks run on existing fixed panes without adding new panes.

### Step 4 — Exchange data via scratchpads

For passing complex payloads, task briefs, test output dumps, or intermediate data between agents, use the `.scratchpads/` directory in the repository root or `/tmp`. Keep source directories clean of transient files. When passing data between workers, write to `.scratchpads/<name>.<ext>` and pass the path in the dispatch prompt.

**Completion:** all inter-agent files and dumps reside strictly in `.scratchpads/` or `/tmp`.

### Step 5 — Verify on disk (zero blind trust)

Track task progress with `herdr agent wait <target>`. Verify on disk directly using `git diff`, `ls -la`, `wc -l`, compilers, and test suites before accepting task completion. Re-dispatch immediately if a worker claims success without modifying disk or test outcomes.

**Completion:** every completed task is corroborated by actual disk modifications or passing test commands.

### Step 6 — Clear or hand off context

- **Stateless tasks**:
  1. `herdr agent prompt <target> "/clear "` (include trailing space).
  2. Wait: `herdr agent wait <target> --timeout 30000` (or `sleep 1`).
  3. Dispatch next brief.
- **Stateful tasks**:
  1. `herdr agent prompt <target> "Write handoff to '.scratchpads/<target>-handoff.md' covering uncommitted work, decisions, verified counts, open items, and traps."`
  2. Verify on disk: `wc -l .scratchpads/<target>-handoff.md`.
  3. Send `herdr agent prompt <target> "/clear "`.
  4. Wait: `herdr agent wait <target> --timeout 30000`.
  5. Resume: `herdr agent prompt <target> "Read '.scratchpads/<target>-handoff.md' in full FIRST, then proceed with <next-task>."`

**Completion:** target pane is cleared, and resumed stateful tasks have verified handoff files on disk.

## The bar

- The frontmatter carries `disable-model-invocation: true` and a one-liner description for human invocation.
- The `## Standing Orchestrator Directives` heading is preserved for extraction by `pane-limits --init-leader`.
- Swarm leader operations are strictly confined to `$HERDR_TAB_ID`.
- Implementation code is never written by the leader; all work is delegated.
- Task complexity matches recommended model tiers with Gemini absorbing the bulk of work.
- Swarm pane count remains fixed with sequential queueing instead of ad-hoc splitting.
- Inter-agent communication, drafts, and handoffs sit in `.scratchpads/` or `/tmp`.
- All completed work is verified on disk.
- Every step terminates on a checkable completion criterion.

