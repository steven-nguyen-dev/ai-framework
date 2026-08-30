# The quality bar

The standard a filled spec folder is judged against. Two readers use this file, and they read it for
different reasons:

- **3 · Fill** reads *Reading a blank — or a pre-filled — field* while it decides what a
  slot means, and writes to the bar the passes set.
- **6 · Cold review** reads the whole file and runs the four passes against the finished folder.

Every rule a spec folder is graded on lives here once. The two rules the passes cite but do not hold
are the **output contract** and the **placement map**, both in `SKILL.md` under `3 · Fill` — the fill
acts on them line by line, so they sit where the filling happens.

---

## Reading a blank — or a pre-filled — field

A blank slot is not one thing. It can mean *take the default*, *you decide*, *nobody knows yet*, or
*this field doesn't belong to this kind* — and the wrong reading is silent. A pre-filled slot is the
same problem inverted: a contract the generator relies on, or a demonstration of what most partners
do.

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
none at all, and two areas that both define one may still differ clause for clause. Read the rule
where that area states it, every time, and let each area's rule govern only that area.

What the field reference will not tell you:

- **A field scoped to another kind is omitted, not blanked.** The `Kind` column says which fields
  belong; it does not say that a blank is itself an answer, so blanking an inapplicable field states
  something nobody meant.
- **A doc-pointed placeholder is not a gap.** A value shaped like `"<by authType — some-doc-name>"`
  is an instruction to resolve from that doc at generation time — it belongs in place. Where a
  shipped example resolves one by hand, the field reference wins and the example is one data point;
  say which one you followed.
- **A dangling key parses as null**, identical to a considered choice. Where the area states no
  resolution rule, `{}` or `[]` is written out. Where it states one, that rule wins — and an explicit
  empty collection may then mean the opposite of "empty".
- **A `""` in a filled spec can be a positive instruction** rather than a gap. Read the comment
  beside it first.
- **An empty call list can be the answer.** Where credentials are minted locally, or the partner
  documents no auth endpoint, an auth feature legitimately makes no call: the empty collection is
  written out with the reason. A stub shipping a worked call — or marking its sample required — is
  showing the common case; the partner's contract decides whether it applies.
- **A feature whose data comes from a seed file is still a feature.** Where the scope says the data
  is *supplied later*, or is *empty for now*, the feature is still built: the form, the seed file and
  an explicit empty collection are the expected build. An empty set is a statement about the data,
  not a reason to skip the feature.
- **A block-level "do not edit" can have field-level exceptions.** Where an area's field reference
  defines user-input slots inside a pre-filled block, the README's blanket prohibition does not reach
  them. Where it defines no such convention, the block is frozen — establish which case this is
  before calling an edit a finding.
- **For XML, the mapping's nesting *is* the payload structure.** Where an area sets content type
  globally with a per-call override, the global setting does not tell you any particular request's
  format — read where that area decides it before assuming JSON.

---

## The cold reader

The reader arrives with the folder and this file, and nothing else: no interview, no fill decisions,
no summary of what the builder chose. That absence is the whole instrument — a reader holding the
builder's reasoning reads the folder the way the builder meant it rather than the way it stands.

- **Diagnostic** — report each finding: what is wrong, where it is, what it contradicts. The repair
  belongs to the builder, so the finding names the defect and stops there.
- **Artifact-bound** — judge assertions against the area's docs and the partner's source material,
  and read fields for their runtime meaning per the area's docs. Where a named doc is not where it is
  specified, search for its job; where it is absent, report it.
- **Read-only** — write nothing.
- **Evidence, not intent** — a value the source material does not carry is a finding whatever the
  builder appears to have meant.

**Entry conditions.** Confirm the area has a harness — `ls -d <area>/specs/_templates/` — then list
the spec folder in full, every file and every empty directory, and read the area's instructions in
the precedence its README states. State the area, the branch, the file count and the feature count at
the head of the report. A missing spec folder, missing partner documentation or missing captured
payloads stops the read and is reported as the gap. A folder still carrying template placeholders
throughout has not been filled: report that and stop.

**Delegate the reading.** Reading the codebase, reading many files for context, and researching many
online sources each go to a sub-agent, which returns verdicts, facts and `file · Class.method`.
Material you quote or judge from — the area's harness, `mapping-plan.md`, the spec files themselves —
you read yourself. Online research covers public material only; the partner's contract is supplied by
the human, never researched.

---

## The four passes

Run passes 1 through 4 in order, completing each before starting the next, and report findings under
their own pass without merging or reranking.

### Pass 1 — Integrity

- **Structure**: every folder the area's instructions require is present.
- **Parse**: every file parses. Report the file and the line for duplicate keys or invalid YAML.
- **Pointers resolve**: every `sample:` target resolves relative to the README's target. A pointer
  that does not resolve means the payload does not exist.
- **Dangling keys**: judged by the blank-field rules above.
- **Registration code consistency**: find the registration doc, list each place the integration's
  registration code must match, and check each one.

### Pass 2 — Harness conformance

Judge every blank slot, pre-filled value, doc-pointed placeholder, dangling key and frozen block by
the blank-field rules above.

- **Kinds resolve**: every kind used has a matching form in the area's harness.
- **Buckets declared**: every bucket referenced resolves to a declaration in the global spec.
- **Master template**: a field documented, applicable and absent is a finding. A field the stub
  shipped that the partner does not appear to need is judged by the blank-field rules — it is the
  area's blank semantics, not automatically a defect.
- **Harness defects — structural only**: report a key the stubs use that the master lacks, a kind
  with no form, a `sample:` pointer that does not resolve. A divergence the files' own roles or
  comments explain is not a defect — `ordered/` stubs ship disabled scaffolding while a
  `feature.KIND` form shows an enabled feature, and an area's README may document that split outright.
- **Output contract — on authored lines only**: separate what the builder wrote from what the harness
  shipped by diffing the spec against the area's stub. On **authored** lines, confirm the line is one
  of the three authored forms in `SKILL.md` § *The output contract*, then apply both of that
  section's tests:
  1. *Can the generator act on it?* Flag any line that informs a human instead: implementation
     status, reasoning, provenance narrative, an open question, or a comment repeating the YAML.
  2. *Does it resolve for a reader holding only this repo?* Open every reference an authored line
     makes. Picture a reader who cloned the codebase and never saw the mapping plan:
     `mapping-plan.md` and every ID it mints are absent from their
     hands, so the test is that reader rather than a list of prefixes — a series the framework adds
     tomorrow fails it the day it is minted. Anything reached from outside the codebase, `mapping-plan.md`
     included, is a finding: the fact stays, its paper trail belongs in the `mapping-plan.md`
     row. A comment needing a clause of justification to stand up is over-long by the same test.

  **Test 2 subtracts only — it never clears a line.** A reference resolving inside the spec folder
  (a sibling numbered spec, a `sample:` path, a symbol in core) survives *this* test, which is not
  the same as surviving the check: a line already flagged by test 1 stays flagged.
  `samples/PROVENANCE.md` resolves cleanly and is still provenance narrative, whose home is the
  sample file itself. A `# NEW — not yet in <Symbol>` marker on a `contract:` line is a declared
  cross-reference — a symbol being requested — and stands.
- **Rebuttals beneath frozen lines**: a stub header describes the harness's common case, not this
  partner. Where it states something that does not hold for this integration, the finding is never
  the header — it is any authored line placed under it to correct, qualify or answer it. Read the
  line directly below every stub header comment and check whether it exists to rebut the header; that
  is where authored prose most often enters a spec folder, and template fidelity alone does not see
  it because the header itself is untouched.
- **`notes` density — by command, not by reading**: the harness's own longest shipped `notes` block
  is the ceiling. Run this from `<area>/specs/_templates/`, then from the spec folder under review.

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

  A filled `MAX` above the harness's `MAX` is a finding naming the file: content with a home in the
  placement map is sitting in a spec. Quote both numbers. **A `MAX` at or under the ceiling is not a
  clean bill** — the counter bounds volume, not kind, so prose compressed to fit scores exactly what
  directives score. Equal numbers oblige the output-contract check above, not excuse it.
- **Stub `notes` survived — by command, not by reading**: every non-blank line a stub shipped in
  `notes` is still present in the filled file. Run from the spec folder under review, with `T`
  pointing at the area's stub directory:

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

  `PASS` is the pass condition. Every other line is a `blocker`: the harness shipped an
  integration-specific signal and the build destroyed it. Quote the dropped line in the finding — it
  is gone from the delivery and from `mapping-plan.md` both, so the report is the only place it
  still exists.
- **Harness-authored text is frozen, not audited**: stub headers, pre-filled values and the `notes` a
  stub shipped are checked for being byte-identical to the area's template, and for nothing else.
  Reasoning, status or an open question inside shipped `notes` stands — an area's README may name
  those blocks as its uncertainty channel. A trimmed or rewritten harness note is a finding.
- **Template fidelity**: flag any stub header comment differing from the area template's text, and
  any edited pre-filled value. Where a pre-filled value disagrees with a partner or platform source,
  the area's declared precedence settles it, and what the precedence settles is neither an edit nor a
  defect.

### Pass 3 — Provenance

- **Named source**: every value has a named source or a flag. Copied is settled when the source can
  be named. Derived is settled only when the file and the field within it can be named.
- **Silent failure fields**: check each `silent failure field` justification — contract placement
  role, near-miss distinction, business consequences. A silent-failure field without one is a finding.
- **Rejected candidates**: check what else the source contract offered. A silent-failure field with
  no exclusion list is a finding.
- **Carried-over defaults**: a harness default left in a slot the partner governs is unsourced.
- **Samples sourced**: every sample says where the capture came from.
- **Rebuilt samples**: compare each sample against the partner doc and the captured payloads. A
  sample rebuilt from DTOs, which drops unmapped fields and enum values, is a finding.
- **Closed value sets**: a value set is closed by documentation — schema, enumeration, partner doc —
  and never by the samples.

### Pass 4 — Fidelity

**Divergence tracking**: a spec diverging from the partner doc is a mapping error; diverging from
`mapping-plan.md` is a build error, since the spec was written from that file. State which one it
diverges from. This read runs before G2, so neither is a gate violation and both go back to the
builder.

- **Confidence-based audit** — scrutiny follows the grade the row claims in `mapping-plan.md`:
  - **A (surely correct)**: sanity check that the YAML matches the mapping plan as written.
  - **B (likely correct)**: cross-reference the partner API documentation and the payload samples,
    and confirm the builder's deduction holds against that evidence.
  - **C (assumed)**: maximum scrutiny. Search the partner doc, schemas and payloads to **prove the
    assumption wrong** — one delegated disproof search per assumption, returning the verdict and the
    citation carrying it. Where nothing validates or refutes it, flag it as a high-risk unverified
    assumption.
  - **A sibling-sourced row, whatever its grade**: any row whose Reason cites another integration
    owes three things in that cell — which impl, whether it is live, and whether the behaviour was
    confirmed or only a candidate. A row citing a sibling without all three is a finding at the grade
    it claims. Sibling code looks second-grade because it compiles and it is right there, so a `B`
    laundered from one is more dangerous than an honest `C`: a `B` does not get re-checked after this
    read.
- **Challenge the reading**: confirm key identifiers align with contract placement role, and name any
  contradiction between a field label and its contract placement.
- **Mapping details survived**: check fallbacks, cardinality, null-versus-absent and closed value sets
  against the mapping plan.
- **Mappings against the wire** (B and C rows): compare mappings against captured payload field
  names, nesting and types.
- **Unmapped destinations**: an unmapped value takes the declared fallback or flows through
  untouched. A table with no fallback and a target that cannot accept arbitrary input is a finding.
- **Scope creep**: a capability present but unrequested by the scope or the partner doc is a finding.

---

## A finding

A finding is four things and no more:

1. **What is wrong** — one sentence.
2. **Where** — the file and the quoted line.
3. **What it contradicts** — the area's document and its line, the partner document and its section,
   the captured payload, the master template, or the other file in the folder.
4. **Severity** — `blocker` (the gate must not pass), `defect` (fix before the gate, or take a
   disposition like a gap), or `note`.

**Where sources disagree**, name both, quote what each says, and report the contradiction as an open
finding for the human to settle.

## The findings report

The cold reader returns, in chat:

- The pinned fixed point — area, branch, file count, feature count — and a **verdict line**:
  `blockers: n · defects: n · notes: n`.
- One section per pass, in pass order, each closing with that pass's finding count and its worst
  finding. A pass with nothing to report says `0 findings`.
- No proposed rewrite anywhere: the builder repairs.
