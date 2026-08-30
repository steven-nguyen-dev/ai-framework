# Levers

Write and prune every skill against these eight sections. A skill carries **steps** — the ordered
actions — and **reference** — the rules and facts consulted on demand, in any mix.

## §1 Write the description as a pointer

A **pointer** names material outside the agent's context and encodes the condition for reaching it.
Its wording decides when the material is reached. Each **branch** — a distinct case the skill
handles — contributes one trigger.

- Lead with the word that does the triggering.
- Give each branch one trigger, and collapse the synonyms of a branch into that trigger.
- Leave the identity the body carries to the body.

## §2 Spend the two budgets deliberately

Every line added spends one:

- **Context load** — the agent's window, charged every turn by always-loaded material: a
  `description`, an `AGENTS.md` line. Charge to it what the agent reaches on its own.
- **Cognitive load** — the human holding which documents exist and when to reach for each. Charge to
  it what human judgement decides.

A pointer costs its own line and holds its target off the window until it fires.

## §3 Place each piece on the ladder

Three rungs, by how immediately the agent needs the material:

1. **In-file step** — what the agent does, in order.
2. **In-file reference** — consulted on demand. A flat peer-set on one rung is a sound arrangement.
3. **Disclosed reference** — a separate file behind a pointer, loaded when the pointer fires.

- Inline what every branch needs; disclose what one branch reaches.
- Group a concept's definition, rules and caveats under one heading, so reading one part brings its
  neighbours.
- Hold each file short enough that attention carries across every line: disclose the reference, and
  split by branch or sequence so each path carries what it needs.

## §4 End every step on a completion criterion

Write the bound so a second reader settles done from not-done by reading the output. Two properties
make it a lever:

- **Clarity** — a sharp bound holds attention on the step while the later steps sit in view.
- **Demand** — how much it requires. "Every modified model accounted for" drives the digging that
  "produce a change list" leaves optional. Demand binds reference as well as steps: "every rule
  applied" carries the same bar over a flat rule set.

Make each criterion checkable and exhaustive.

## §5 Split where the cut earns its load

- **By sequence** — split a run of steps where the later ones pull attention off the step in front.
  Hiding them works across a real context boundary: a hand-off, or a sub-agent dispatch.
- **By invocation** — split off a model-invoked skill where a distinct leading word triggers it on
  its own, or another skill reaches it. Its description is permanent context load, so let that
  independent reach earn it.

## §6 Anchor behaviour with leading words

Pick a **leading word** the model already holds — *lesson*, *tracer bullets*, *frontier*, *the bar*
— and repeat it as a bare token across the document. It anchors a region of behaviour in the fewest
tokens: the agent reaches for the same behaviour each time the word appears, and shared language
across prompts, docs and code reaches the material reliably.

Refactor toward it. A triad spelled out at three sites collapses into one token:
"fast, deterministic, low-overhead" → *tight*.

State every instruction as the behaviour to perform. A named behaviour is the one that becomes
available to the agent, so name the target.

## §7 Prune line by line

Keep each line that changes what the agent does. Five earn deletion:

| The line | The move |
|---|---|
| States what the agent does by default | Delete the sentence whole |
| Repeats a template, `CLAUDE.md`, or a config the agent reads | Delete it; name that file once |
| States a meaning the document states elsewhere | Keep one place, delete the other |
| Steers by prohibition | Rewrite it as the behaviour to perform |
| Describes behaviour or a world that has moved on | Write what holds now |

Three tests decide each line:

- **Single source of truth** — hold each meaning in one authoritative place, so a change is a
  one-place edit.
- **The cache test** — the environment states its own truth: `package.json` scripts, config files,
  the directory layout, `--help` output. Write down what the agent reads nowhere else — the
  unwritten convention, the reason behind a choice, the gotcha no config states — and leave the
  one-file, one-command lookups to the environment, where they hold current.
- **The no-op test** — ask what this line changes against the default, and settle a disagreement by
  running the document. It grades leading words too: a word that leaves the default in place gives
  way to a stronger word.

## §8 Choose the invocation with the user

| Choice | Reach | Cost | Mechanics |
|---|---|---|---|
| **Model-invoked** | The agent fires it, other skills reach it, the human types it | The description is permanent context load | `disable-model-invocation: false`; description written as a pointer (§1) |
| **User-invoked** | The human types its name | Cognitive load — the human is the index | `disable-model-invocation: true`; description written as a human-facing one-liner |

Model-invocation earns its load where the agent or another skill reaches the skill on its own. A
skill that fires by hand stays user-invoked.

Where user-invoked skills multiply past memory, a **router skill** — one user-invoked skill naming
the others and when to reach for each — returns the index to one entry.
