# AI-First Framework

A comprehensive framework and toolkit designed to power high-rigor, review-driven, specification-first software development for AI agents and human engineers.

---

## 📖 Introduction

The **AI-First Framework** (`ai-first-fw`) provides an end-to-end ecosystem for AI-assisted software engineering. It standardizes how AI agents understand requirements, design specifications, plan implementations, execute changes, and pass strict cold diagnostic review gates before creating pull requests.

---

## 🏗 Repository Structure

```
ai-first-fw/
├── skills/              # Core lifecycle skills governing the development workflow
├── utilities/           # Standalone utility skills for specialized engineering tasks
├── local-theme/         # Unified Dark Report Theme design tokens, CSS, & JS toolkit
├── local-test-servers/  # Spec-driven mock HTTP servers and integration test engine
├── local-mcps/          # Local Model Context Protocol (MCP) servers
└── local-report-servers/# Local live reporting and analytics dashboards
```

---

## 🧩 Components Overview

### 1. [`skills/`](skills) — Core Lifecycle Skills
A set of six specialized, composable skills that guide AI agents through a gated development lifecycle:
- **`analysis-handoff`**: Captures systems touched, blast radius, required end states, and dependencies before planning begins.
- **`implementation-planner`**: Orchestrates the multi-step lifecycle across approval gates (`G1` requirements approval, `G2` implementation plan approval).
- **`specs-builder`**: Analyzes API documentation and payload samples to produce mapping plans and integration specifications.
- **`specs-reviewer`**: Performs cold diagnostic audits on specifications against integration harnesses and API documentation.
- **`plan-reviewer`**: Conducts independent audits on implementation plans against business requirements and codebase evidence.
- **`code-reviewer`**: Audits branch diffs against requirements, project conventions, and approved plans prior to gate approval.

### 2. [`utilities/`](utilities) — Standalone Skills
Independent helper skills for focused tasks outside the core lifecycle (e.g. codebase audits, architecture reviews, migration tools).

### 3. [`local-theme/`](local-theme) — Unified Local Design System
Central design tokens (`theme.json`), shared stylesheets (`theme.css`), and JavaScript visualization toolkit (`theme.js`) used across all test servers, mock servers, and report servers.

### 4. [`local-test-servers/`](local-test-servers) — Mocks & Test Suite Engine
A self-contained testing environment to validate integration flows end-to-end without needing live third-party sandboxes:
- **Spec-Driven Mock Server** (`mock.py`): Dynamically answers endpoints from OpenAPI/Swagger definitions and fixture rules.
- **Test Suite Engine** (`suite/`): Executes declarative integration test flows against local mock servers and databases.
- **Central Portal** (`portal.py`): Web-based control dashboard on port 23000 to manage mock servers, inspect call logs, and view test run results.

### 5. [`local-mcps/`](local-mcps) — Local MCP Servers
Model Context Protocol servers built to extend AI assistant capabilities in local developer environments:
- **`local-mcps/jira-reader`**: Zero-dependency universal Python MCP server providing issue metadata extraction, ADF description parsing, JQL search, batch attachment downloads, and direct text/log streaming into context.
- **`local-mcps/kibana-explorer`**: FastMCP server for Kibana Observability / Logs, searchable with KQL. Authenticates the way the browser does (session cookie) because only Kibana `:5601` is reachable — no Elasticsearch endpoint, no API key. Ships a local KQL parser, since Kibana never exposes KQL over HTTP.

### 6. [`local-report-servers/`](local-report-servers) — Local Live Reports & Analytics
Live dashboard servers generating actionable engineering reports directly from live repositories and tools:
- **Central Reports Portal** (`portal.py`): Web-based management dashboard on port 24000 to monitor, start, stop, and restart all report servers.
- **`local-report-servers/daily-report`**: Live daily work report viewer and markdown aggregator with on-going matter tracking on port 24001.
- **`local-report-servers/jpluger-pr-stats`**: Live pull request backlog, review coverage, aging distribution, and monthly velocity dashboard on port 24002 (standalone app: `jpluger-pr-stats-1.0.0.zip`).
- **`local-report-servers/ai-skills-report`**: Universal AI skills & plugins catalog, marketplace manager, and environment inspector for Claude & Antigravity/Gemini on port 24003 (standalone app: `ai-skills-report-1.0.0.zip`).
- **`local-report-servers/elk-log-explorer`**: Interactive dark-themed ELK log explorer with multi-agent AI natural language query translation and 1-click macOS launcher on port 24004 (standalone app: `elk-log-explorer-1.0.0.zip`).

---

## 🔐 Security & Configuration Standard (`.env.example`)

To prevent accidental credential leaks and guarantee smooth onboarding for teammates, every component with secrets or environment configurations adheres to the **`.env.example` Standard**:

1. **Strict Git Ignore (`*.env`)**:
   - Real credentials, API keys, passwords, and session cookies reside in `.env` files and are **never committed**.
   - `*.env` is strictly enforced by `.gitignore` across the entire repository.
2. **Standard Templates (`.env.example`)**:
   - Every service needing secrets commits a `.env.example` with dummy placeholders and parameter descriptions.
3. **Automated Provisioning (`setup.sh` / `--init-env`)**:
   - Running `./setup.sh` or `python3 server.py --init-env` checks for `.env`. If absent, it automatically copies `.env.example` $\rightarrow$ `.env` and instructs the developer to populate their personal credentials.

---

## 🚀 Workflow Lifecycle

```
[ Input Requirements ]
         │
         ▼
 ┌─────────────────────────┐
 │    analysis-handoff     │ ──► .scratchpads/<feature>/analysis-handoff.md
 └───────────┬─────────────┘
             ▼
 ┌─────────────────────────┐
 │ implementation-planner  │ ──► Gate G1: Requirements & Acceptance Criteria Approval
 └───────────┬─────────────┘
             ▼
 ┌─────────────────────────┐     ┌─────────────────────┐
 │      specs-builder      │ ──► │   specs-reviewer    │ (Cold Spec Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼
 ┌─────────────────────────┐     ┌─────────────────────┐
 │ implementation-planner  │ ──► │    plan-reviewer    │ (Cold Plan Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼                   └── Gate G2: Plan Approval (Unblocks Code Changes)
 ┌─────────────────────────┐     ┌─────────────────────┐
 │      Development        │ ──► │    code-reviewer    │ (Cold Diff & Quality Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼
 [ Verified Code & Pull Request ]
```

## 📦 Installation & Usage

### 1. Via Plugin Marketplace
Add this repository to your agent's marketplace catalog and install the plugins directly:

```bash
# Register repository as a marketplace
plugin marketplace add steven-nguyen-dev/ai-framework

# Install core framework lifecycle skills
plugin install ai-first-fw-skills@ai-framework

# Install standalone utilities
plugin install ai-first-fw-utilities@ai-framework
```

### 2. Via `npx skills` (Direct Skill Installation)
Install individual skills directly into any project using the `skills` CLI:

```bash
# Core Lifecycle Skills
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/analysis-handoff
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/implementation-planner
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/specs-builder
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/specs-reviewer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/plan-reviewer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/code-reviewer

# Utility Skills
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/git-coordinator
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/pr-desc-writer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/unslop
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-diagram-maker
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-architecture-review
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-doc-writer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-prompt-builder
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/glossary-maker
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/naver-api-extractor
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lotteon-api-extractor
```

### 3. Antigravity / Gemini Workspace Configuration
Register the paths in `.agents/skills.json` or `~/.gemini/config/skills.json`:

```json
{
  "entries": [
    { "path": "ai-first-fw/skills" },
    { "path": "ai-first-fw/utilities" }
  ]
}
```

---

## 🏷️ Versioning Policy

- **Skill Independence**: Every skill has its own independent `version` declared in its `SKILL.md` YAML frontmatter. Skills do not need to share a lockstep version with other skills inside the plugin.
- **Plugin Patch (`x.y.Z` → `x.y.Z+1`)**: Increment plugin patch version when *any* skill inside the plugin is updated.
- **Plugin Minor (`x.Y.0` → `x.Y+1.0`)**: Increment plugin minor version when a *new skill* is added, or when *>3 skills* are updated simultaneously.
- **Plugin Major (`X.0.0` → `X+1.0.0`)**: Increment plugin major version when *>5 skills* undergo significant modifications (>20% lines changed in their `SKILL.md`).
