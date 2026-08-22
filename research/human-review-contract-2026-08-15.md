# The human review contract in AI-first, review-driven development

**Question:** How do teams and toolchains that have actually done this define the human review contract — where are the human gates placed, what is the human accountable for at each gate, and what mechanism substitutes for line-by-line reading?

**Date:** 2026-08-15

**Summary of the answer.** Two vendors publish an explicit scope for their automated reviewer, and **they contradict each other on exactly the boundary an abstraction-level split assumes**. Anthropic's Code Review "focuses on correctness: bugs that would break production, *not* formatting preferences or missing test coverage"; GitHub's Copilot code review gives, by default, "feedback on common issues such as bugs, security vulnerabilities, and style inconsistencies." Style is out of scope for one and in scope for the other, so there is no shared industry line at the mechanical layer. What both actually tune on is **checkability**: Anthropic's own guidance is to skip "anything your CI already enforces like linting or spellcheck" and to add repo rules like "new API routes must have an integration test" — an architectural/test-contract concern handed to the machine the moment it is written down as a rule. Machine review runs *up* into design and test contracts when they are stated, and *out* of formatting when a cheaper deterministic check owns it. The one concern any primary source reserves for a human by name is **test design**: Google's reviewer guide states "Tests do not test themselves… a human must ensure that tests are valid," and lists the questions to ask. Security is assigned everywhere except the spec gates — to the PR reviewer (Anthropic), to the reviewer *plus* a separate always-on scanning layer (GitHub), or to a named qualified human (Google). On gate placement the earlier finding stands: every spec-driven model puts its human gates on artifacts before code exists and keeps a terminal human gate at the PR that nobody has removed — Anthropic's reviewer "won't approve PRs — that's still a human call," and its check run "always completes with a neutral conclusion so it never blocks merging." No source states a policy of humans not reading code: Google's standing instruction is still to look at *every* line, and DORA quotes an engineer saying the reviewer "is still expected to manually audit every single line." What substitutes for reading *volume* — not for reading — is agent self-verification against a check the agent can run, automated adversarial review, and PR-size discipline.

---

## 1. Gate map

### GitHub Spec Kit

Spec Kit ships two documented paths. The "full path" for production features is nine ordered commands; the short path drops the three quality gates ([Spec Kit Quick Start](https://github.github.io/spec-kit/quickstart.html)). Gates, in order, with the artifact reviewed at each:

- **`/speckit.constitution`** — artifact: `memory/constitution.md`, the project's standing principles. Run once up front. Every later phase is evaluated against it; `/speckit.analyze` treats the constitution as "**non-negotiable**" and grades any conflict as automatically CRITICAL ([analyze.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/analyze.md)).
- **`/speckit.specify`** — artifact: `spec.md` plus an auto-generated `checklists/requirements.md`. The command runs its own validation loop, and the *only* forced human stop is on unresolved ambiguity: it may emit at most three `[NEEDS CLARIFICATION]` markers, presents each as an options table, and instructs the agent to "Wait for user to respond with their choices for all questions" ([specify.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/specify.md)).
- **`/speckit.clarify`** — artifact: the spec again. Up to five targeted questions, answers written back into `spec.md`. Purpose is stated as keeping you from "designing on top of ambiguity" ([Agentic SDD](https://github.github.io/spec-kit/reference/agentic-sdd.html)).
- **`/speckit.plan`** — artifact: `plan.md` plus `research.md`, `data-model.md`, `contracts/`, `quickstart.md`. The plan template carries a **Constitution Check** marked "*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design*", and a **Complexity Tracking** table to be filled "ONLY if Constitution Check has violations that must be justified" ([plan-template.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/plan-template.md)).
- **`/speckit.checklist`** — artifact: `checklists/<domain>.md`. This is the most explicitly human-owned gate in the toolchain (see §2).
- **`/speckit.tasks`** — artifact: `tasks.md`, organised into Setup → Foundational → one phase per user story in priority order → Polish, with `[US1]`-style story labels for traceability ([tasks-template.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/tasks-template.md)).
- **`/speckit.analyze`** — artifact: a read-only cross-artifact report over spec/plan/tasks. "**NEVER modify files**"; it produces a coverage table mapping each `FR-###`/`SC-###` to task IDs and a severity-graded findings table, then asks whether you want remediation suggested — it does not apply them.
- **`/speckit.implement`** — the checklist gate is enforced here mechanically: it counts checked/unchecked items, and "**STOP** and ask: 'Some checklists are incomplete. Do you want to proceed with implementation anyway? (yes/no)'" ([implement.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/implement.md)). Note this is a *soft* gate — "yes" proceeds.
- **`/speckit.converge`** — append-only reassessment of the codebase against spec/plan/tasks; "You're done; proceed to review or open a PR." Spec Kit's own documentation ends at the PR boundary and says nothing about how that PR is reviewed.

### AWS Kiro

Kiro's standard Feature Spec is a **three-phase workflow with explicit approval between phases**, and Kiro names the human's job at each ([Requirements-First workflow](https://kiro.dev/docs/specs/feature-specs/requirements-first/)):

- **Requirements phase** — artifact: `requirements.md`, user stories with EARS-notation acceptance criteria. *Your role:* "Review requirements for completeness / Iterate on user stories and acceptance criteria / Add any missing scenarios or edge cases / **Confirm when requirements meet your needs**."
- **Optional Analyze Requirements pass** — a deep analysis for "logical inconsistencies, ambiguities, conflicting constraints, and gaps" before design ([Feature Specs](https://kiro.dev/docs/specs/feature-specs/)).
- **Design phase** — artifact: `design.md`. *Your role:* "Review the technical approach / Iterate on architectural decisions / Validate technology choices / **Confirm the design is feasible**."
- **Tasks phase** — artifact: `tasks.md`. *Your role:* "Review the task breakdown / Adjust task priorities if needed / Mark optional tasks / Begin implementation."
- **Implementation** — tasks run individually or all at once; Kiro builds a dependency graph and runs independent tasks concurrently in "waves" ([Specs](https://kiro.dev/docs/specs/)). No documented human gate inside execution.

Kiro is unusually candid that these gates are *optional overhead*, not doctrine. Quick Spec "auto-generates `requirements.md`, `design.md`, and `tasks.md` in sequence, **with no approval gates between phases**", front-loading clarifying questions instead: "Instead of reviewing and approving each artifact, you front-load your input" ([Quick Spec](https://kiro.dev/docs/specs/quick-spec/)). The best-practices page states the difference plainly: "Both produce the same artifacts... The difference is whether you review each one before the next is generated," and recommends the gated flow when "you're working in a compliance-sensitive domain where review gates add real value" ([Best practices](https://kiro.dev/docs/specs/best-practices/)).

### Anthropic (Claude Code + Code Review)

- **Plan gate.** The documented four-phase workflow is Explore → Plan → Implement → Commit, with plan mode as the separation: "Press `Ctrl+G` to open the plan in your text editor for direct editing before Claude proceeds" ([Claude Code best practices](https://code.claude.com/docs/en/best-practices)). Explicitly proportional: "If you could describe the diff in one sentence, skip the plan."
- **Spec gate (larger features).** Have Claude interview you, write `SPEC.md`, then start a fresh session to execute it.
- **Agent-internal verification gate.** Not a human gate — a check the agent runs itself (§3).
- **Adversarial review gate.** A fresh subagent reviews the diff against the plan before the work counts as done.
- **PR gate.** Anthropic's Code Review "dispatches a team of agents on every PR", and Anthropic states the boundary: "It won't approve PRs — **that's still a human call** — but it closes the gap so reviewers can actually cover what's shipping" ([Code Review for Claude Code](https://claude.com/blog/code-review)).

### Ramp (Inspect, on Modal)

Ramp's published architecture puts the verification burden inside the agent rather than at a human gate. Inspect had to "integrate deeply enough with Ramp's stack—Sentry, Datadog, LaunchDarkly, Temporal—**to verify its own work end to end**", and each session runs in a sandbox with "a VNC stack with Chromium for visual verification of frontend changes. The agent can take before-and-after screenshots, navigate the app in a real browser, and confirm its work visually—just as a human would" ([Modal: How Ramp built a full context background coding agent](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal)). The human gate is the PR: "The current generation is already producing **review-ready** pull requests." Roughly half of merged PRs across Ramp's frontend and backend repos are started by Inspect.

### Stripe (Minions)

Stripe's own framing of the contract, from the first-party page metadata on both Minions posts: "Minions are Stripe's homegrown coding agents, responsible for more than a thousand pull requests merged each week. **Though humans review the code, minions write it from start to finish**" ([Minions part 1](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents), [part 2](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2)). The article bodies are client-rendered and I could not retrieve them (see Declared gaps), so I cannot say *how* Stripe says humans review, or against what.

---

## 2. How review responsibility is partitioned between human and machine

### 2.1 The documented scopes — and where they disagree

**Anthropic Code Review** publishes the sharpest scope statement in the corpus, and it runs opposite to the assumption that the machine takes the mechanical layer:

> "By default, Code Review focuses on correctness: bugs that would break production, **not formatting preferences or missing test coverage**. You can expand what it checks by adding guidance files to your repository." ([Code Review docs](https://code.claude.com/docs/en/code-review))

In scope: "logic errors, security vulnerabilities, broken edge cases, and subtle regressions." Findings carry three severities — 🔴 Important ("a bug that should be fixed before merging"), 🟡 Nit, 🟣 Pre-existing — and the product refuses to gate: "The check run always completes with a neutral conclusion so it never blocks merging through branch protection rules," matching the blog's "It won't approve PRs — that's still a human call" ([Code Review](https://claude.com/blog/code-review)). The local `/code-review` command has the same centre of gravity: it "reports correctness bugs and reuse, simplification, and efficiency cleanups," tagging findings with a category such as `correctness`.

**GitHub Copilot code review** publishes the opposite default. Its two effort tiers:

> "**Low**: Standard review. Provides fast, targeted feedback on common issues such as **bugs, security vulnerabilities, and style inconsistencies** (default).
> **Medium**: Routes pull requests to a higher-reasoning model for longer analysis of **complex logic, security-sensitive code, and cross-service changes**." ([About GitHub Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review))

So style is out of the machine's default scope for one vendor and in it for the other, and "complex logic" and "cross-service changes" — high-altitude concerns by any reading — are what the *more* expensive machine tier is sold on. **Two vendors shipping the same product category disagree about which side of the line style sits on**, which is the single fact most damaging to the idea of a fixed mechanical/abstract boundary.

GitHub also publishes an exclusion list, the only file-level one anyone ships: "Some file types are excluded from Copilot code review: Dependency management files, such as package.json and Gemfile.lock; Log files; SVG files. If you include these file types in a pull request, Copilot code review will not review the file."

Its stated intended use is not a partition at all but a supplement — "**Supplementing human code review**: Copilot code review is intended to quickly provide feedback on a developer's code, enabling developers to get code ready to merge more quickly" — and the reciprocal limit is stated twice, in the concept doc ("Copilot is not guaranteed to spot all problems or issues in a pull request… **Supplement Copilot's feedback with a human review**") and in the application card ([Application card: GitHub Copilot Agents](https://docs.github.com/en/copilot/responsible-use/agents)).

**Kiro** ships no automated PR reviewer with a published scope. Kiro Web's agent draws on "learnings from previous code reviews" ([Working with the agent](https://kiro.dev/docs/web/using-the-agent/)), but the reviewer in that loop is the human; there is no Kiro document stating what a machine review covers and what it leaves behind.

**Spec Kit** scopes an artifact, not a reviewer: "In a custom checklist, `[x]` means the reviewer determined the requirements-quality criterion is satisfied; **it does not mean implementation work is complete**" ([Agentic SDD](https://github.github.io/spec-kit/reference/agentic-sdd.html)). The reviewer signs for requirement quality and nothing further — a genuine scoping of accountability, but it never says who signs for the code.

### 2.2 On what axis the line is drawn

**No primary source names an axis.** But both vendors that let you *tune* the reviewer describe the tuning in terms of checkability and confidence, never in terms of altitude.

Anthropic's `REVIEW.md` guidance names the exclusion criterion outright:

> "**Skip rules**: list paths, branch patterns, and finding categories where Claude should post no findings. Common candidates are generated code, lockfiles, vendored dependencies, and machine-authored branches, along with **anything your CI already enforces like linting or spellcheck**." ([Code Review docs](https://code.claude.com/docs/en/code-review))

Work leaves the LLM reviewer's plate because a cheaper deterministic check already owns it — not because it is low-level. The same page moves work *up*: "**Repo-specific checks**: add rules you want flagged on every PR, like '**new API routes must have an integration test**'." That is a test-contract rule, exactly the thing the abstraction reading reserves for the human, assigned to the machine the moment it is written down as a rule. And it adds a confidence lever independent of both: "**Verification bar**: require evidence before a class of finding is posted. For example, 'behavior claims need a `file:line` citation in the source, not an inference from naming'."

GitHub's customization guidance has the same shape. Its recommended instruction-file template has sections for Naming Conventions, Code Style, Error Handling, **Security Considerations**, **Testing Guidelines**, and Performance; its worked `AGENTS.md` example opens "Your primary goal is to validate that incoming code changes are secure, performant, and match this repository's engineering standards," with rules like "React components must keep local UI state completely isolated from global stores" — an architectural constraint, machine-enforced, because someone stated it ([Customize code review](https://docs.github.com/en/copilot/tutorials/customize-code-review)). What GitHub says *doesn't* work is not "too abstract" but too unspecifiable: under "Vague quality improvements" it lists `Be more accurate`, `Don't miss any issues`, `Be consistent in your feedback`, plus instructions that would change the product's function, such as `Block a PR from merging unless all Copilot code review comments are addressed`.

The mechanism Anthropic states elsewhere is the same axis expressed as a consequence: "Claude stops when the work looks done. Without a check it can run, 'looks done' is the only signal available, and **you become the verification loop**" ([best practices](https://code.claude.com/docs/en/best-practices)). The human absorbs whatever has no runnable check.

**Verdict.** Nobody declares an axis, so this is inference — but the observable behaviour is consistent with *checkability* and inconsistent with *abstraction level in both directions*: machine review climbs into architecture and test contracts when those are written as rules, and drops formatting when CI already covers it. The abstraction reading also predicts that machine review is most reliable on small mechanical diffs; the measured behaviour in §2.3 is the reverse.

### 2.3 Where machine review is measurably strong and weak

**Yield scales with PR size, in Anthropic's data.** On PRs over 1,000 lines changed, 84% get findings, averaging 7.5 issues; under 50 lines, 31%, averaging 0.5. Engineers mark under 1% of findings incorrect, and substantive review comments went from 16% to 54% of PRs after deployment ([Code Review](https://claude.com/blog/code-review)). Small, mechanical diffs are where the machine yields *least*.

**GitHub documents the opposite-facing limitation** — that large and complex is where its reviewer misses most:

> "**Missed code quality problems**: Copilot may not identify all of the problems that are present in code, **especially where changes are large or complex**. To ensure that all relevant problems are identified and corrected, Copilot code review should be supplemented with careful human code review." ([Application card](https://docs.github.com/en/copilot/responsible-use/agents))

These two are not strictly contradictory — Anthropic reports findings *yield*, GitHub warns about *coverage* — but neither publishes an escape rate, so neither statement supports a claim about what fraction of defects the machine layer actually catches.

**GitHub's other documented limitations**, all first-party, all about the machine layer's failure modes:

- **False positives**: "Copilot code review has a risk of hallucination—it may highlight problems in reviewed code that do not exist or are based on misunderstandings of the code."
- **Its own suggestions can be wrong or unsafe**: "code generated by Copilot may contain security vulnerabilities or other issues. You should always carefully review and test code generated by Copilot."
- **Style/language bias**: "Copilot code review may be biased toward certain programming languages or coding styles, which can lead to suboptimal or incomplete feedback."
- **Infrastructure-dependent depth**: if GitHub-hosted runners are disabled, "code reviews will fall back to a more limited review."

**Coverage and confidence trade against each other explicitly.** Anthropic's `/code-review` effort levels: "At `low` and `medium`, the review reports only the findings it's most confident in, so you see fewer false positives; `high` through `max` broaden coverage and may include findings the review is less sure about" ([Code Review docs](https://code.claude.com/docs/en/code-review)). A team choosing a review setting is choosing a point on that curve, not turning a layer on.

**What machine review catches that high-level review structurally cannot** is documented in §5 and worth restating here as the case *for* the machine layer: the one-line change that would have broken authentication, and the pre-existing type mismatch silently wiping an encryption key cache in code the PR merely touched. Neither is visible from requirements, acceptance criteria, or a green test run.

### 2.4 Who reviews the tests

**One primary source assigns test review to a human by name, and it is the pre-AI one.** Google's reviewer guide, under Tests:

> "Make sure that the tests in the CL are correct, sensible, and useful. **Tests do not test themselves, and we rarely write tests for our tests—a human must ensure that tests are valid.**" ([What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html))

It also states *how*, as four questions: "Will the tests actually fail when the code is broken? If the code changes beneath them, will they start producing false positives? Does each test make simple and useful assertions? Are the tests separated appropriately between different test methods?" Plus a constraint on test complexity: "Remember that tests are also code that has to be maintained. Don't accept complexity in tests just because they aren't part of the main binary." Its review summary lists "Code has appropriate unit tests" and "**Tests are well-designed**" as separate line items.

**No AI-era source assigns it.** Anthropic's Code Review explicitly excludes "missing test coverage" from its default scope and does not say who picks it up — the only route back is a `REVIEW.md` rule handing a specific test requirement to the machine. Kiro extracts properties from the EARS requirements itself, generates the tests, and states the failure mode plainly — "**A property that is too weak, or that states the wrong invariant, will pass while the real behavior is still wrong**" ([Correctness](https://kiro.dev/docs/specs/correctness/)) — but names no reviewer for the property set. Its documented human touchpoint fires only on failure: "You can then chat with Kiro to understand the failure and determine the appropriate fix - whether that's updating the implementation, adjusting the test, or refining the requirement itself." That is a real human adjudication over which of three artifacts is wrong, but it never fires for a property that is too weak, which is the case Kiro itself flags. And "PBTs are optional by default."

**"The tests pass" is treated as insufficient by three sources, from three directions.** Kiro: property-based testing "provides evidence of correctness, not a proof… passing tests raise confidence but do not guarantee the absence of bugs." Google: tests do not test themselves. Anthropic, on why the second-opinion subagent exists: "so the agent doing the work isn't the one grading it" ([best practices](https://code.claude.com/docs/en/best-practices)). None of the three names a machine that can grade a test *contract* — only ones that can run it.

### 2.5 Who owns security

**Security is assigned — three different ways, none of them to the artifact gates.**

- **Anthropic → the PR reviewer.** "Security vulnerabilities" is one of the four named target classes of Code Review ([Code Review docs](https://code.claude.com/docs/en/code-review)).
- **GitHub → the reviewer *and* a separate always-on tool layer.** Copilot code review names "security vulnerabilities" at Low and "security-sensitive code" at Medium. Separately, code scanning "is a feature that you use to analyze the code in a GitHub repository to find security vulnerabilities and coding errors" and "also prevents developers from introducing new problems" ([About code scanning](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning)). And the Copilot cloud agent runs it during generation, not review: "During code generation, the cloud agent automatically analyzes newly generated code for security vulnerabilities using CodeQL, secret scanning, and dependency analysis, and attempts to resolve any issues before they are introduced" ([Application card](https://docs.github.com/en/copilot/responsible-use/agents)). Note the seam: dependency manifests, where supply-chain risk lives, are on Copilot code review's *exclusion* list and belong to the scanning layer instead — so a team reading only the code-review docs would conclude security is covered when one of its largest surfaces is handled elsewhere.
- **Google → a named qualified human.** "If you understand the code but you don't feel qualified to do some part of the review, make sure there is a reviewer on the CL who is qualified, particularly for complex issues such as privacy, **security**, concurrency, accessibility, internationalization, etc." ([What to look for](https://google.github.io/eng-practices/review/reviewer/looking-for.html))

The unowned case is narrower than §5 states in general: it is specifically the **spec-driven flows**. Nothing in Spec Kit or Kiro's spec workflow assigns security to a gate; Spec Kit's `security.md` example checklist tests whether security *requirements are well-written*.

### 2.6 The caveats: nobody publishes a partition, and the baseline is still every line

Two things keep this from being a licence.

**First, Google's own enumeration is a priority order for one reviewer, not a split.** Design first — "The most important thing to cover in a review is the overall design of the CL" — then Functionality, Complexity, Tests, Naming, Comments, Style, Consistency, Documentation. And then the standing instruction: "In the general case, look at *every* line of code that you have been assigned to review. Some things like data files, generated code, or large data structures you can scan over sometimes, but don't scan over a human-written class, function, or block of code and assume that what's inside of it is okay." Style is not absent from the human's list; it is *demoted* — "any purely style point (whitespace, etc.) that is not in the style guide is a matter of personal preference," and "Don't block CLs from being submitted based only on personal style preferences" ([The Standard of Code Review](https://google.github.io/eng-practices/review/reviewer/standard.html)). What makes style cheap for a human is that a written style guide is "the absolute authority" — checkability again, one layer down.

**Second, Google does document a partition by concern — but among humans.** Under Every Line → Exceptions, a reviewer may be asked "To review only certain aspects of the CL, such as the high-level design, privacy or security implications, etc.", and then: "note in a comment which parts you reviewed," granting LGTM only "after confirming that other reviewers have reviewed other parts of the CL." So partition-by-concern has a primary-source precedent with two conditions welded on — **the split must be declared on the change, and someone qualified must cover each part**. Substituting a machine for one of those reviewers is the step no source takes.

**And the current-practice datapoint runs the other way.** DORA, quoting a Google engineer: "While an author can use AI to quickly generate a massive changelist (CL) or pull request (PR), **the reviewer is still expected to manually audit every single line** for correctness and style" ([Balancing AI tensions](https://dora.dev/insights/balancing-ai-tensions/)). No primary source states a policy of humans not reading code. What they state is where machine review is *allowed to run* and what it does *not* certify — a smaller and more defensible claim.

DORA is the only source that prescribes a direction of travel for the split rather than describing a product: "Build context-aware review agents to **automatically enforce organizational standards before human intervention is required**," and, on the gate itself: "traditional code review is a quality gate, and in this new era of AI, it may be worth thinking about the purpose of the quality gate itself and whether other techniques could fulfill parts of it." Standards enforcement to the machine, pre-review; the purpose of the human gate left open.

---

## 3. What substitutes for line-by-line review

**A check the agent can run.** This is the load-bearing mechanism in Anthropic's guidance, and it is framed as displacing the human: "Claude stops when the work looks done. Without a check it can run, 'looks done' is the only signal available, and **you become the verification loop**: every mistake waits for you to notice it." The escalation ladder is in-prompt → `/goal` condition → Stop hook (deterministic, blocks the turn from ending) → a second-opinion subagent, "so the agent doing the work isn't the one grading it" ([best practices](https://code.claude.com/docs/en/best-practices)).

**Evidence instead of assertion.** "Have Claude show evidence rather than asserting success: the test output, the command it ran and what it returned, or a screenshot of the result. **Reviewing evidence is faster than re-running the verification yourself**, and it works for sessions you weren't watching" (ibid.). This is the closest thing in the corpus to a stated substitute for reading the diff — and note that it substitutes for *re-verifying*, not for reading.

**Full-context agent self-verification against production systems.** Ramp's Inspect runs tests, reaches Sentry/Datadog/LaunchDarkly/Temporal, and does visual before/after checks in a real browser, all inside one sandbox with no network hop to the test suite ([Modal](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal)).

**Requirement-to-task traceability as a coverage proof.** Spec Kit's `/speckit.analyze` builds a requirements inventory keyed on `FR-###`/`SC-###`, maps every task to one or more requirements, and emits a coverage table plus metrics including "Coverage % (requirements with >=1 task)"; requirements with zero tasks and tasks with no mapped requirement are both findings ([analyze.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/analyze.md)). Its checklist generator enforces traceability at the item level: "MINIMUM: ≥80% of items MUST include at least one traceability reference" ([checklist.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/checklist.md)).

**Property-based tests derived from the requirements themselves.** Kiro extracts properties from EARS requirements, generates hundreds or thousands of random inputs, and shrinks failures to a minimal reproducer; it maintains "a clear, traceable link between your requirements and the tests that validate them" ([Correctness](https://kiro.dev/docs/specs/correctness/)). For bugfixes it also encodes non-regression as a requirement: "**WHEN** [condition] **THEN** the system **SHALL CONTINUE TO** [existing behavior]" ([Best practices](https://kiro.dev/docs/specs/best-practices/)).

**Automated adversarial review before human review.** Anthropic runs multi-agent Code Review on nearly every PR: agents look for bugs in parallel, verify to filter false positives, rank by severity, and post one overview comment plus inline findings. Measured internally: substantive review comments rose from 16% to 54% of PRs, engineers mark under 1% of findings incorrect ([Code Review](https://claude.com/blog/code-review)). DORA's recommendation is to move that feedback earlier still: "**Shift automation and AI to the author:** AI-generated feedback on the code should be delivered to the author during the writing phase to catch issues earlier, which is far more efficient than providing AI-generated feedback on the code to the reviewer" ([Balancing AI tensions](https://dora.dev/insights/balancing-ai-tensions/)).

**PR-size discipline.** Google's engineering practices are unambiguous and predate AI: "100 lines is usually a reasonable size for a CL, and 1000 lines is usually too large," and "**reviewers have discretion to reject your change outright for the sole reason of it being too large**" ([Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)). DORA names small batches as "a critical countermeasure to the risks of AI-assisted development." Anthropic's data shows why size matters for machine review too: on PRs over 1,000 lines changed, 84% get findings averaging 7.5 issues; under 50 lines, 31% averaging 0.5 ([Code Review](https://claude.com/blog/code-review)).

---

## 4. What makes high-level review possible

These are the artifact properties the primary sources actually specify, i.e. what makes a spec reviewable without the diff.

- **Testable, unambiguous requirement syntax.** EARS: `WHEN [condition/event] THE SYSTEM SHALL [expected behavior]`. Kiro claims four properties for it — clarity, testability ("each requirement can be directly translated into test cases"), traceability, completeness ([Feature Specs](https://kiro.dev/docs/specs/feature-specs/)).
- **Measurable, technology-agnostic success criteria.** Spec Kit's `SC-###` items must be measurable, technology-agnostic, user-focused, and "verifiable without knowing implementation details." Its own worked examples make the discipline concrete — good: "Users can complete checkout in under 3 minutes"; bad: "API response time is under 200ms (too technical, use 'Users see results instantly')" ([specify.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/specify.md)).
- **A stated independent test per user story.** The spec template requires, for each prioritised story, an "**Independent Test**: [Describe how this can be tested independently]", and requires each story to be independently developable, testable, deployable and demonstrable ([spec-template.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/spec-template.md)).
- **Explicit assumptions and scope boundaries.** The spec template's mandatory **Assumptions** section is where reasonable defaults are recorded, with the template's own examples including scope exclusions ("Mobile support is out of scope for v1"). Anthropic's guidance says the same for hand-written specs: "The most useful specs are self-contained: they name the files and interfaces involved, **state what is out of scope**, and end with an end-to-end verification step that proves the feature works" ([best practices](https://code.claude.com/docs/en/best-practices)).
- **Requirement→task labelling.** `[US1]`/`[US2]` story labels on every task, so "[Story] label maps task to specific user story for traceability" ([tasks-template.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/tasks-template.md)).
- **A standing constraint set outside the feature.** Spec Kit's constitution and Kiro's steering files both hold conventions that no individual spec restates. Kiro's foundation files are `product.md` (purpose, users, business objectives), `tech.md`, `structure.md`, loaded into every interaction; its own best practice is "**Treat steering changes like code changes - require reviews**" ([Steering](https://kiro.dev/docs/steering/)).
- **Requirements-quality checklists — "unit tests for English."** Spec Kit's checklist command forbids implementation-testing items and mandates requirement-quality items: not "Verify landing page displays 3 episode cards" but "Are the number and layout of featured episodes explicitly specified? [Completeness, Spec §FR-001]" ([checklist.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/checklist.md)). This is the artifact that most directly gives a business reviewer something to judge.
- **A written justification table for complexity.** The plan template's Complexity Tracking table forces `Violation | Why Needed | Simpler Alternative Rejected Because`, so an architectural deviation is reviewable as prose ([plan-template.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/plan-template.md)).

---

## 5. Counter-evidence and risk

**The verification tax is real, measured, and lands on the reviewer.** DORA: "the time saved in creation is frequently re-allocated to auditing and verification," and this "may explain some of our own findings: **higher AI adoption is associated with an increase in both software delivery throughput and software delivery instability**." A quoted engineer: "I feel somewhat more productive, but it's at a cost. While I end up spending less time writing code, I spend more time babysitting the AI and reviewing what it is trying to do." Another: "Reviewing [another's] code is so much harder than writing it. AI tools are increasing the rate at which people can churn out code that needs to be reviewed…" ([DORA, Balancing AI tensions](https://dora.dev/insights/balancing-ai-tensions/)). The 2025 DORA report also finds 30% of developers report little or no trust in AI-generated code.

**Perceived speedup is not evidence of speedup.** METR's RCT — 16 experienced developers, 246 real issues in repos averaging 22k+ stars — found developers took **19% longer** with AI allowed. They forecast a 24% speedup beforehand and still believed they had been sped up 20% afterwards. METR notes the setting matters: "AI capabilities may be comparatively lower in settings with very high quality standards, or with many implicit requirements (e.g. relating to documentation, testing coverage, or linting/formatting)" ([METR](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)). METR has since flagged these results as out of date and published a [February 2026 follow-up](https://metr.org/blog/2026-02-24-uplift-update/) which I did not read.

**Review debt is the pre-existing condition, and AI worsens it before it helps.** Anthropic: code output per engineer grew 200% in a year; **before** deploying automated review, only 16% of PRs got substantive review comments — "many PRs get skims rather than deep reads" ([Code Review](https://claude.com/blog/code-review)). A business-goal review layered on top of a skim is a skim.

**There are defect classes a high-level review structurally cannot catch, and Anthropic documents two.** A one-line change to a production service "looked routine and was the kind of diff that normally gets a quick approval" — it would have broken authentication; the engineer "shared afterwards that they wouldn't have caught it on their own." And on a customer's ZFS encryption refactor, the reviewer found *pre-existing* adjacent-code breakage — "a type mismatch that was silently wiping the encryption key cache on every sync… the kind of thing a human reviewer scanning the changeset wouldn't immediately go looking for" (ibid.). Neither is visible from requirements, acceptance criteria, or a green test run. Note also the size asymmetry: small PRs, the ones a business reviewer feels safest waving through, are exactly where automated review yields least (31% / 0.5 findings).

**Security is a measured, not hypothetical, exposure.** A CodeQL analysis of 7,703 files explicitly attributed to AI tools found 4,241 CWE instances across 77 vulnerability types; 87.9% of files had no CWE-mapped finding, but Python files showed 16.18%–18.50% vulnerability rates ([Schreiber & Tippe, arXiv:2510.26103](https://arxiv.org/abs/2510.26103); preprint, published version in LNCS 16219). None of the review contracts studied assigns security review to the business-intent gate — though outside the spec flows it is assigned, three different ways (§2.5).

**Test contracts are evidence, not proof — and a wrong contract passes silently.** Kiro states its own limits: property-based testing "provides evidence of correctness, not a proof… passing tests raise confidence but do not guarantee the absence of bugs," and "**A property that is too weak, or that states the wrong invariant, will pass while the real behavior is still wrong**" ([Correctness](https://kiro.dev/docs/specs/correctness/)). If the human's review is of the spec and the spec generates the tests, a spec error is invisible to every downstream check.

**Tests are optional in Spec Kit's own task template, which contradicts its own methodology document.** `tasks-template.md` states: "Tests are OPTIONAL - only include them if explicitly requested in the feature specification" — while `spec-driven.md` describes Article III Test-First as "NON-NEGOTIABLE" ([tasks-template.md](https://raw.githubusercontent.com/github/spec-kit/main/templates/tasks-template.md); [spec-driven.md](https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md)). A team adopting Spec Kit as-shipped does not get a test contract by default.

**The gates are soft.** Spec Kit's `/speckit.implement` asks and proceeds on "yes." Kiro's Quick Spec removes inter-phase approval entirely and both vendors recommend it for "well-understood" work. Nothing in either toolchain enforces that a human actually read what they approved.

**Over-trust cuts both ways, including toward the reviewer agent.** Anthropic warns: "A reviewer prompted to find gaps will usually report some, even when the work is sound… Chasing every finding leads to over-engineering: extra abstraction layers, defensive code, and tests for cases that can't happen" ([best practices](https://code.claude.com/docs/en/best-practices)).

**Skill degradation is a named organisational risk.** DORA's "expertise paradox": lowering entry barriers "risks bypassing the 'productive struggle' necessary for deep technical expertise," and AI usage patterns "deliver breakthrough productivity while simultaneously blocking skill development." A team whose humans only ever review intent will, over time, contain fewer humans able to review anything else.

---

## 6. Rollout practice

**Adoption by pull, not mandate.** "Ramp didn't mandate Inspect, they let the product speak for itself." Within a couple of months roughly half of merged PRs across frontend and backend repos were started by Inspect, and "over 80% of Inspect itself" is written by Inspect ([Modal](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal)). The stated adoption precondition was performance: "a background agent that was slower or less capable than working locally would never get adopted."

**Roles widen past engineering, deliberately.** Ramp built Slack, web (hosted VS Code + streamed desktop), and Chrome-extension clients "that lets non-engineers visually select UI elements to change"; PMs and designers ship directly. Kiro's Requirements-First "Pattern 1" is explicitly a two-role rubric: "Review and iterate on requirements with PM / Generate design and validate with engineering team" ([Requirements-First](https://kiro.dev/docs/specs/feature-specs/requirements-first/)).

**DORA's concrete rollout prescriptions** ([Balancing AI tensions](https://dora.dev/insights/balancing-ai-tensions/)):
- Stop using output-based metrics; use SEQ / SPACE / HEART / value-stream measures instead — "AI can easily inflate the volume of code generated."
- Shift AI feedback to the author, pre-review.
- Build "context-aware review agents to automatically enforce organizational standards before human intervention is required."
- Work in small batches — "Forcing large AI-generated changes into reviewable, testable units."
- "**Revisit the necessity of async reviews**… Investing in robust test automation for faster feedback may provide a better return on investment than optimizing manual reviews." And, directly on Steve's question: "traditional code review is a quality gate, and in this new era of AI, it may be worth thinking about the purpose of the quality gate itself and whether other techniques could fulfill parts of it."
- Adjust estimates for the prototype→production gap: "Don't reduce estimates before investing to close this gap."
- Pair juniors with senior mentors specifically "to review AI-generated architectural decisions."

**Operational controls on automated review.** Anthropic ships monthly org spend caps, repository-level enablement, and an analytics dashboard tracking PRs reviewed, acceptance rate and cost; reviews average $15–25 and ~20 minutes, and scale depth with PR size ([Code Review](https://claude.com/blog/code-review)).

**Review feedback as a training signal.** Kiro Web: commenting on a PR with guidance like "always use our standard error handling" teaches the agent, and those learnings apply "to future work across all your repositories" — but "**Only your feedback (the user who created the task) influences the agent's learnings.** Other reviewers' comments don't affect what the agent learns" ([Steering](https://kiro.dev/docs/steering/)). That is a real constraint on using review as a team-wide teaching loop.

**Things tried and changed.** Spec Kit no longer prescribes its full constitution: "Articles IV, V, and VI are intentionally defined by each project's constitution rather than prescribed by Spec Kit," while the nine-article *structure* stays stable ([spec-driven.md](https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md)); the shipped `constitution-template.md` is placeholders with commented examples. Kiro hard-locks the workflow choice: "No, you must choose a workflow when creating the spec. If you need to change approaches, create a new Feature Spec" ([Best practices](https://kiro.dev/docs/specs/best-practices/)).

---

## Declared gaps

**Sources I could not reach.**
- **Stripe Minions Part 1 and Part 2 bodies.** Both pages at stripe.dev are client-rendered; `web_fetch` returned only the shell and first-party metadata. The Claude in Chrome extension was not connected in this session, so I could not render them. Everything I state about Stripe comes from the page's own meta description, which is first-party text but only one sentence. **Unanswered: how Stripe defines what its humans review a Minion PR *against*, what a Minion verifies itself, and what the blueprint/deterministic-node architecture implies for the review contract.** Stripe's Knowledge AI Platform post was not attempted.
- **Ramp's own engineering post**, "Why We Built Our Own Background Agent" (engineering.ramp.com and builders.ramp.com) — both return "You need to enable JavaScript to run this app." All Ramp claims here come from Modal's first-party write-up, which quotes named Ramp engineers but is Modal's account, not Ramp's.
- **The 2025 DORA report PDF itself** is gated behind a Google Cloud download form. All DORA figures here (30% low trust, throughput/instability association, 90% adoption) are quoted via dora.dev's own first-party insights article, which cites the report. The DORA AI Capabilities Model report is likewise download-gated and unread.
- **METR's February 2026 follow-up** ([uplift update](https://metr.org/blog/2026-02-24-uplift-update/)) — METR labels the 2025 results "out of date." I did not read the newer data, so the 19% figure should be treated as a 2025 snapshot, not a current estimate.

**Questions primary sources did not answer.**
- No source defines a *review rubric* for judging a spec against business goals. Spec Kit's checklists are the closest artifact, and they test requirement-writing quality, not business fit.
- **No vendor publishes a human/machine division of labour as a policy.** Anthropic and GitHub publish what their reviewer *covers*; neither states what it hands to the human beyond "supplement this with a human review." That is product scope, not a review contract, and the two scopes contradict each other on style (§2.1).
- **No source names the axis** on which the line is drawn. Checkability is inferred from tuning guidance — Anthropic's `REVIEW.md` skip rules, GitHub's custom-instruction do/don't lists — not stated by anyone as a principle (§2.2).
- **No AI-era source assigns review of test *design*.** Google assigns it to a human in a pre-AI document and says how; Kiro generates the properties and names no reviewer for them; Anthropic excludes test coverage from default scope without saying who picks it up (§2.4).
- No source states a policy of humans not reading code. Google's standing instruction is still "look at *every* line." The strongest available statements are about who *approves* (Anthropic), what a checklist item *certifies* (Spec Kit), and what an automated reviewer *covers* (Anthropic, GitHub).
- No **spec-driven** flow assigns security review to a gate. Spec Kit's checklist command offers `security.md` as an example checklist type, but it tests whether security *requirements are well-written*, not whether the code is safe. Outside the spec flows security *is* assigned — to the PR reviewer, a separate scanning layer, or a qualified human (§2.5) — so the gap is specific to the artifact gates, not general.
- No source published defect-rate or escaped-bug data comparing spec-gated review to conventional diff review, or comparing human against machine review **by category**. The Anthropic 16%→54% figure measures review *coverage* and the 84%/31% figures measure *yield by PR size*; neither is a defect-escape rate. GitHub documents missed problems as a limitation without a number. Nothing published lets you say what fraction of defects in a given category each layer catches.
- No source documents what a team abandoned after trying artifact-only review. The "tried and changed" items I found (§6) are product decisions, not retrospectives on review practice.

**Found only in secondary write-ups — not promoted into the body, unverified.**
- Stripe Minions producing "over 1,300 pull requests per week" and the "blueprints = deterministic code + flexible agent loops" architecture description (search-result summaries and InfoQ/ByteByteGo coverage). Stripe's own metadata says only "more than a thousand pull requests merged each week."
- That Ramp Inspect "can run tests, review telemetry, and query feature flags" for backend work as a discrete capability list (search summary phrasing; Modal's page says the agent integrates with Sentry, Datadog, LaunchDarkly and Temporal "to verify its own work end to end", which is consistent but not identical).
- Ramp Inspect reaching ~30% of merged PRs at an earlier date (ZenML LLMOps database entries).
- Pearce et al.'s "~40% of generated programs contained vulnerabilities" figure — surfaced in search results, primary paper not opened.
