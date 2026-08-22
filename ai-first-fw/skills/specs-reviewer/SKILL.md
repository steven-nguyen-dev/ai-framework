---
name: specs-reviewer
description: Cold review of a filled integration spec folder against the area's harness, the mapping plan and the human's source material, before the integration is implemented or registered.
version: 0.7.1
disable-model-invocation: true
context: fork
background: false
---

# Specs review

Execute a **cold reader** review of the filled spec folder. Evaluate assertions strictly against the area's docs and partner source material; reject inferred intent.

- **Diagnostic-only**: Report findings only: name what is wrong, where it is, and what it contradicts. Do not output corrected YAML or fixes.
- **Read-only state**: Read `raw-context.md` §0 and preserve it exactly as found.
- **Artifact-bound**: Evaluate fields based on runtime meaning per the area's docs. If a named doc is not where specified, search for its job; if absent, report it.
- **Contamination abort**: Run this skill in a fresh session. If any prior history for this integration is present in context — the planning conversation, the interview, the folder being filled, or an earlier review — abort immediately and report the contamination instead of reviewing.

---

## Inputs

You are given a **spec folder path** — `<area>/specs/<integration>/`, where *area* is the folder carrying `specs/_templates/` and is not the target code module — the **source material**, and optionally a **feature folder path**, `<repo-root>/.scratchpads/<feature-slug>/`.

| Source | What you use it for |
|---|---|
| The spec folder | The artifact under review |
| `raw-context.md` §0 | The folder's position — read at entry and preserved exactly as found; this skill never writes it (supplied only with a feature folder) |
| `mapping-plan.md` | The contract this spec folder was built from — authority the partner doc does not replace |
| The area's harness | Master template, stubs, feature forms, global spec |
| The area's instructions | Authority on fill order, precedence, required fields |
| Partner API documentation | Authority on endpoints, field names, value sets, auth |
| Captured payloads | What the partner actually sends |
| Registration code (integration identifier) | Every place the registration doc says the code must match |

**Entry conditions:**
- Stop immediately if the spec folder is missing.
- Stop immediately and report the missing artifacts if partner documentation or captured payloads are missing.
- If feature folder or integration code is missing, ask why. If no answer, report the absence and state both readings (standalone vs unfetched).
- Where a feature folder **was** supplied, stop and report if `raw-context.md` or its §0 is absent — §0 is what you preserve, and you cannot preserve what is not there.

**Delegate the reading.** Reading the codebase, reading multiple files for context, and researching
multiple online sources each go to a sub-agent. A sub-agent returns verdicts, facts and `file · Class.method` —
never file bodies, never its search narrative, and never a chosen answer. Material you quote or fill
from — the area's harness, `mapping-plan.md`, the spec files you are judging — you read yourself.
Online research covers public material only; the partner's contract is supplied by the human, never
researched. Entry condition 2 above is not satisfiable by research.

---

## Step 1 — Pin what you are reviewing

1. Confirm the area and that it has a harness — `ls -d <area>/specs/_templates/`.
2. List the spec folder in full, every file, including empty directories — delegated; it returns the tree and the counts, not the file contents.
3. Record which branch you are on, and read the area's instructions in the precedence its README states.
4. **Confirm the folder is non-empty and holds more than copied stubs.** A folder still carrying template placeholders throughout has not been filled; report that and stop.

State the area, the branch, the file count and the feature count at the head of your report.

---

## Reading a blank — or a pre-filled — field

A blank slot is not one thing. It can mean *take the default*, *you decide*, *nobody knows yet*, or
*this field doesn't belong to this kind* — and the wrong reading is silent. A pre-filled slot is the
same problem inverted: a contract the generator relies on, or a demonstration of what most partners
do. The four passes below cite these rules by name; they are the standard a blank is judged against.

**Marker semantics are documented per area, and they differ.** The skeleton is fixed, so the places
to look are always the same; what you find there is not. Search before interpreting anything:

```bash
T=<area>/specs/_templates
grep -rn 'esolution rule' $T/
grep -rniE 'USER INPUT|recommended:|required when|TODO|verify' $T/ | head -30
```

Read what those turn up in the area's field reference, and use its rule. **An area that defines none
of it is telling you a blank there carries no marker semantics** — that is an answer, not a gap in
your search. This is a real split: some areas define a full resolution rule (blank falls back to a
recommendation block, a literal `none` is an explicit opt-out, any other value wins) and some define
none at all, and two areas that both define one may still differ clause for clause. **Never carry
one area's rule into another** — read the rule where that area states it, every time.

What the field reference will not tell you:

- **A field scoped to another kind is omitted, not blanked.** The `Kind` column says which fields
  belong; it does not say that a blank is itself an answer, so blanking an inapplicable field states
  something the builder did not mean.
- **A doc-pointed placeholder is not a gap.** A value shaped like `"<by authType — some-doc-name>"`
  is an instruction to resolve from that doc at generation time — it belongs left in place. Where a
  shipped example resolves one by hand, the field reference wins and the example is one data point;
  the builder is obliged to say which it followed.
- **A dangling key parses as null**, identical to a considered choice. Where the area states no
  resolution rule, `{}` or `[]` should be written out. Where it states one, that rule wins — and an
  explicit empty collection may then mean the opposite of "empty".
- **A `""` in a filled spec can be a positive instruction** rather than a gap. Read the comment
  beside it first.
- **An empty call list can be the answer.** Where credentials are minted locally, or the partner
  documents no auth endpoint, an auth feature legitimately makes no call. A stub shipping a worked
  call — or marking its sample required — is showing the common case; the partner's contract
  decides whether it applies.
- **A feature whose data comes from a seed file is still a feature.** Where the scope says the data
  is *supplied later*, or is *empty for now*, the feature is still built: the form, the seed file and
  an explicit empty collection are the expected build. An empty set is a statement about the data, not
  a reason to skip the feature.
- **A block-level "do not edit" can have field-level exceptions.** Where an area's field reference
  defines user-input slots inside a pre-filled block, the README's blanket prohibition does not reach
  them. Where it defines no such convention, the block is frozen — establish which case you are in
  before calling an edit a finding.
- **Content type can be set globally and overridden per call**, so the global setting does not tell
  you any particular request's payload format. Outbound transport, where an area has one, is set
  once. Find where this area decides each before assuming JSON; for XML, the mapping's nesting *is*
  the payload structure.

*This section is duplicated by design in `specs-reviewer` and `specs-builder` — installs symlink the
whole skill directory, so a shared file outside either does not ship. Its twin is the section of the
same name under `4 · Fill` in `specs-builder/SKILL.md`, and the two are edited in the same change.*

---

## The four passes

Execute passes 1 through 4 sequentially. Complete each pass before starting the next. Report findings under their respective pass section without merging or reranking.

### Pass 1 — Integrity

- **Structure**: Every folder the area's instructions require is present.
- **Parse**: Every file in the folder parses. Report the file and the line for duplicate keys or invalid YAML.
- **Pointers resolve**: Every `sample:` target resolves relative to the README's target. A pointer that does not resolve means the payload does not exist.
- **Dangling keys**: Evaluate dangling keys strictly according to the blank-field rules above.
- **Registration code consistency**: Find the registration doc, list each place the integration's registration code must match, and check each one.

### Pass 2 — Harness conformance

> Apply the blank-field rules above when evaluating blank slots, pre-filled values, doc-pointed placeholders, dangling keys, or frozen blocks.

- **Kinds resolve**: Every kind used has a matching form in the area's harness.
- **Buckets declared**: Every bucket referenced resolves to a declaration in the global spec.
- **Master template checks**: A field documented, applicable and absent is a finding. A field the stub shipped that the partner does not appear to need is evaluated per the blank-field rules above — it is the area's blank/marker semantics, not automatically a defect.
- **Signal interpretation**: Evaluate omitted fields, doc-pointed placeholders, trims, and frozen blocks according to the blank-field rules above.
- **Harness defects — structural only**: Report a key the stubs use that the master lacks, a kind with no form, a `sample:` pointer that does not resolve. A divergence the files' own roles or comments explain is **not** a defect — `ordered/` stubs ship disabled scaffolding while a `feature.KIND` form shows an enabled feature, and an area's README may document that split outright.
- **Output contract — on authored lines only**: Separate what the builder wrote from what the harness shipped; diff the spec against the area's stub to tell them apart. On **authored** lines, confirm the line is one of the three authored forms — a template field with its resolved value and nothing trailing it; a one-line comment carrying the fact itself; or a `notes` entry in the shape that area's harness sets (its `EXAMPLE.*` where it ships one, otherwise the `notes:` description in its `master-template.yml`) — then apply both tests the builder applied:
  1. *Can the generator act on it?* Flag any line that informs a human instead: implementation status, reasoning, provenance narrative, an open question, or a comment repeating the YAML.
  2. *Does it resolve for a reader holding only this repo?* Open every reference an authored line makes. Picture a reader who cloned the codebase and never saw the planning folder: `mapping-plan.md`, `raw-context.md` and every ID either of them mints are absent from their hands, so the test is that reader rather than a list of prefixes — a series the framework adds tomorrow fails it the day it is minted. Anything reached from outside the codebase, the planning folder included, is a finding: the fact stays, its paper trail belongs in the `mapping-plan.md` row. A comment needing a clause of justification to stand up is over-long by the same test.
  **Test 2 subtracts only — it never clears a line.** A reference resolving inside the spec folder (a sibling numbered spec, a `sample:` path, a symbol in core) survives *this* test, which is not the same as surviving the check: a line already flagged by test 1 stays flagged. `samples/PROVENANCE.md` resolves cleanly and is still provenance narrative, whose home is the sample file itself.
  A `# NEW — not yet in <Symbol>` marker on a `contract:` line is a declared cross-reference (a symbol being requested), not a finding.
- **Rebuttals beneath frozen lines**: a stub header describes the harness's common case, not this partner. Where it states something that does not hold for this integration, the finding is never the header — it is any authored line placed under it to correct, qualify or answer it. Read the line directly below every stub header comment and check whether it exists to rebut the header; that is where authored prose most often enters a spec folder, and template fidelity alone does not see it because the header itself is untouched.
- **`notes` density — by command, not by reading**: the harness's own longest shipped `notes` block is the ceiling. Run this from `<area>/specs/_templates/`, then from the spec folder under review. *(The builder runs the same measurement and reports both numbers at hand-off — measure rather than take them. Duplicated by design: installs symlink the whole skill directory, so a shared copy does not ship.)*

  ```bash
  python3 - <<'CHK'
  import pathlib, yaml
  rows = []
  for f in sorted(pathlib.Path('.').rglob('*.y*ml')):
      try: d = yaml.safe_load(f.read_text(encoding='utf-8')) or {}
      except Exception: continue
      n = d.get('notes')
      if isinstance(n, str):
          rows.append((len([l for l in n.splitlines() if l.strip()]), str(f)))
  rows.sort(reverse=True)
  for c, f in rows[:5]: print(c, f)
  print('MAX', rows[0][0] if rows else 0)
  CHK
  ```

  A filled `MAX` above the harness's `MAX` is a finding naming the file: content with a home in the placement map is sitting in a spec. Quote both numbers in the report. **A `MAX` at or under the ceiling is not a clean bill** — the counter bounds volume, not kind, so prose compressed to fit scores exactly what directives score. Equal numbers oblige the output-contract check above, not excuse it.
- **Stub `notes` survived — by command, not by reading**: every non-blank line a stub shipped in `notes` is still present in the filled file. Run from the spec folder under review, with `T` pointing at the area's stub directory:

  ```bash
  python3 - <<'CHK'
  import pathlib, yaml
  T = pathlib.Path('<area>/specs/_templates/ordered')
  bad = []
  for f in sorted(pathlib.Path('ordered').glob('*.y*ml')):
      s = T / f.name
      if not s.exists(): continue
      sn = (yaml.safe_load(s.read_text(encoding='utf-8')) or {}).get('notes') or ''
      fn = (yaml.safe_load(f.read_text(encoding='utf-8')) or {}).get('notes') or ''
      for line in [l for l in sn.splitlines() if l.strip()]:
          if line.strip() not in fn:
              bad.append(f'{f}: stub notes line dropped: {line.strip()}')
  print('\n'.join(bad) or 'PASS')
  CHK
  ```

  `PASS` is the pass condition. Every other line is a `blocker`: the harness shipped an integration-specific signal and the build destroyed it. Quote the dropped line in the finding — it is gone from the delivery and from the planning folder both, so the report is the only place it still exists.
- **Harness-authored text is frozen, not audited**: stub headers, pre-filled values, and the `notes` a stub shipped are checked for being byte-identical to the area's template — nothing else. Reasoning, status or an open question in shipped `notes` is **not** a finding; an area's README may name those blocks as its uncertainty channel and instruct confirming against the partner. A trimmed or rewritten harness note **is** a finding.
- **Template fidelity**: Flag any stub header comment differing from the area template's text, and any edited pre-filled value. Where a pre-filled value disagrees with a partner or platform source, the area's declared precedence settles it — what the precedence settles is neither an edit nor a defect.

### Pass 3 — Provenance

- **Named source**: Every value has a named source or a flag. Copied is settled when the source can be named. Derived is settled only when the file and the field within it can be named.
- **Silent failure fields**: Check `silent failure field` justifications (contract placement role, near-miss distinction, business consequences). Absence of justification on a silent-failure field is a finding.
- **Check rejected candidates**: Check what else the source contract offered. Missing exclusion list on a silent-failure field is a finding.
- **Carried-over defaults**: A harness default left in a slot governed by the partner is unsourced.
- **Samples sourced**: Every sample says where the capture came from.
- **Rebuilt samples**: Compare each sample against partner doc and captured payloads. Samples rebuilt from DTOs that drop unmapped fields/enums are findings.
- **Closed value sets**: Value sets must be closed by documentation (schema, enumeration, partner doc), not by samples.

### Pass 4 — Fidelity

**Divergence tracking**: A spec diverging from partner doc is a mapping error. Diverging from `mapping-plan.md` is a build error — the spec was written from that file. State which one it diverges from. This review runs before G2, so neither is a gate violation; both are findings that go back to the builder.

- **Confidence-based Audit**: When reviewing fields mapped in `mapping-plan.md`, adjust scrutiny based on the stated confidence score:
  - **Confidence A (Surely correct)**: Perform a fast sanity check. Verify that the YAML spec matches the mapping plan exactly as written.
  - **Confidence B (Likely correct)**: Cross-reference the partner API documentation and payload samples. Verify that the logical deduction made by the builder actually holds up against the evidence.
  - **Confidence C (Assumed)**: Apply maximum scrutiny. Actively search the partner API doc, schemas, and payloads to attempt to **prove the assumption wrong** — delegate one disproof search per assumption, returning the verdict and the citation that carries it. If no proof can be found to either validate or refute it, explicitly flag it as a high-risk unverified assumption in the report.
  - **A sibling-sourced row, whatever its grade**: any row whose Reason cites another integration owes three
    things in that cell — which impl, whether it is live, and whether the behaviour was confirmed or only a
    candidate. A row citing a sibling without all three is a finding at the grade it claims. Sibling code looks
    second-grade because it compiles and it is right there, so a `B` laundered from one is more dangerous than
    an honest `C`: a `B` does not get re-checked after this review.
- **Challenge the reading**: Verify that key identifiers align with contract placement role. Name any contradiction between field labels and contract placement.
- **Mapping details survived**: Verify fallbacks, cardinality, null-versus-absent, and closed value sets against the mapping plan.
- **Mappings vs Partner Doc & Payload**: (For B and C confidence levels) Compare mappings against captured payload field names, nesting, and types.
- **Unmapped destinations**: An unmapped value must take the declared fallback or flow through untouched. A table with no fallback and a target that cannot accept arbitrary input is a finding.
- **Signal interpretation**: Evaluate content types, auth, and empty features according to the blank-field rules above.
- **Scope creep**: Capabilities present but unrequested by scope or partner doc are findings.

---

## The report

Head it with the pinned fixed point and a **verdict line** — `blockers: n · defects: n · notes: n`. Then one section per pass, in pass order.

A **finding** is four things and no more:
1. **What is wrong** — one sentence.
2. **Where** — the file and the quoted line.
3. **What it contradicts** — the area's document and its line, the partner document and its section, the captured payload, the master template, or the other file in the folder.
4. **Severity** — `blocker` (the gate must not pass), `defect` (fix before the gate, or take a disposition like a gap), or `note`.

Close each section with one line: the finding count for that pass, and the worst finding **within that pass**. Never a winner across passes.

If a pass has 0 findings, report '0 findings' explicitly.

**When sources disagree**, name both, quote what each says, and stop there. Report the contradiction as an open finding without adjudicating it.

**Write the report to disk**: where a feature folder was supplied, save the formatted report as `specs-review-report.md` in that folder — the planning folder itself, beside `raw-context.md`. This review runs before the implementation plan is written, so do not expect that file to be there yet. Where no feature folder was supplied (standalone review), save it as `specs-review-report.md` at the root of the spec folder under review instead. A re-review overwrites this file, so the file on disk always reflects the latest run. Post the same report in chat as well.

---

## Done when

- [ ] The area, branch, file count, feature count and verdict line are pinned and stated in the report.
- [ ] The partner documentation and captured payloads were present, or the review was stopped and the gap named.
- [ ] All four passes have run, in order, each completed before the next started.
- [ ] Every file in the folder has been opened and parsed; every `sample:` pointer resolved or listed as unresolvable.
- [ ] Every value has been placed as copied, derived, or unsourced — walked, not sampled.
- [ ] Every mapping has been read against the partner documentation individually, and against a captured payload where one exists.
- [ ] Where a feature folder was supplied, every mapping in `mapping-plan.md` has been audited according to its confidence level (A/B/C) and divergences labelled.
- [ ] `mapping-plan.md` ships stripped — it holds no `<!--`. An authoring comment surviving into the delivered file means the builder skipped its strip stage, and every rule that comment carries is unverified.
- [ ] Every `MAP-xx` row carries a grade in its Confidence cell, and every silent-failure row carries Reason, Contract role, Near-miss and Consequence. An empty Confidence cell is a blocker, not a note.
- [ ] `raw-context.md` §0 is exactly as you found it.
- [ ] The report has four sections and four closing lines.
- [ ] No finding proposes a rewrite.
- [ ] Report written to `specs-review-report.md` (feature folder if supplied, else the spec folder root), and also posted in chat.
