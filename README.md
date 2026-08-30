# 🚀 AI-First Software Engineering Framework

An enterprise-grade, specification-first, and review-driven software engineering framework for **AI Agents** (Claude Code, Claude Cowork, Google Antigravity 2.0, Gemini CLI) and **Human Engineering Teams**.

---

## 📖 Overview

The **AI-First Framework** standardizes the entire software development lifecycle for autonomous and pair-programming AI agents. It replaces unguided code generation with structured analysis, specification-driven mapping, strict multi-stage audit gates, live integration test harnesses, and native executive dashboards.

```
[ Requirements / Jira Ticket ]
               │
               ▼
   ┌───────────────────────┐
   │    write-analysis     │ ──► Mapping spec, requirements spec & ticket summary
   └───────────┬───────────┘
               ▼
   ┌───────────────────────┐
   │ implementation-planner│ ──► Gate G1: Acceptance criteria & edge cases approved
   └───────────┬───────────┘
               ▼
   ┌───────────────────────┐
   │     specs-builder     │ ──► Spec folder & mapping plan (confidence graded)
   └───────────┬───────────┘
               ▼
   ┌───────────────────────┐
   │ implementation-planner│ ──► Gate G2: Plan Approved (Cold Plan Quality Bar)
   └───────────┬───────────┘
               ▼                 
   ┌───────────────────────┐     ┌──────────────────┐
   │      Development      │ ──► │   review-code    │ (Cold Branch Diff & Standard Audit)
   └───────────┬───────────┘     └──────────────────┘
               ▼
   [ Verified Pull Request & Production Deployment ]
```

---

## 🏗️ Repository Architecture

```
ai-framework/
├── .claude-plugin/              # Claude Code plugin & marketplace manifest
├── ai-first-fw/
│   ├── skills/                  # Core lifecycle gated skills (v2.0.0)
│   ├── utilities/               # Standalone engineering utilities & API extractors (v2.0.0)
│   ├── local-theme/             # Unified dark developer theme tokens, CSS & JS
│   ├── local-report-servers/    # Live engineering dashboards & distribution .app installers
│   ├── local-test-servers/      # Spec-driven mock engine & integration test runner
│   └── local-mcps/              # FastMCP servers (Jira issue streamer, Kibana KQL engine)
└── README.md                    # Root architecture and onboarding guide
```

---

## 🧩 Core Components

### 1. 🛡️ Lifecycle Skills (`ai-first-fw/skills/`)
Gated AI skills that enforce engineering rigor before code is touched:
* **`write-analysis`** (`v0.1.0`): Generates integration mapping spec, system requirements spec, and ticket summary for a requirement.
* **`implementation-planner`** (`v0.8.0`): Master lifecycle orchestrator managing approval gates (`G1` requirements approval, `G2` technical plan approval).
* **`specs-builder`** (`v0.10.0`): Fills integration spec folders and writes confidence-graded mapping plans against test harnesses.
* **`review-code`** (`v2.0.0`): Cold pull request and branch diff reviewer auditing requirements compliance, codebase rules, and security across 3 isolated passes.

### 2. ⚡ Standalone Utilities (`ai-first-fw/utilities/`)
* **`draw-diagram`** (`v1.0.0`): Draws one Mermaid block (flowchart, sequence, state, ER) styled to the shared dark palette and parsed before shipping.
* **`git-coordinator`** (`v0.4.0`): Syncs the current feature branch into its QA or UAT mirror branch from a separate worktree (merge, build, push, draft PR) and tears down mirrors once landed.
* **`pr-desc-writer`** (`v0.3.0`): Reads the session and diff, fills the repository PR template, and offers to apply it directly to the open GitHub pull request.
* **`write-docs`** (`v1.0.0`): Writes one technical knowledge note in the house style — drafted in temp, every fact traced to its source, every uncertainty carried to an Open questions section.
* **`write-skill`** (`v0.1.0`): Authors and revises agent skills adhering to the framework standard, structure, and quality levers.
* **`lv1-architecture-review`** (`v0.0.2`): High-level system architecture and modularity design reviewer.
* **`naver-api-extractor`** (`v0.0.1`) & **`lotteon-api-extractor`** (`v0.0.1`): Automated tools for extracting, parsing, and documenting e-commerce APIs.

### 3. 📊 Local Report Servers (`ai-first-fw/local-report-servers/`)
Native live dashboards and standalone shareable macOS `.app` packages:
* **Central Reports Portal** (`:24000`): Unified web dashboard to monitor and manage all local report servers.
* **`daily-report`** (`:24001`): Daily engineering activity viewer and matter aggregator.
* **`jpluger-pr-stats`** (`:24002`): GitHub PR backlog, review coverage, and velocity tracker.
* **`ai-skills-report`** (`:24003`): Universal AI skills and plugins registry for Claude & Antigravity.
* **`elk-log-explorer`** (`:24004`): Interactive dark-themed ELK log explorer with multi-agent natural language query translator.

### 4. 🧪 Local Test Servers (`ai-first-fw/local-test-servers/`)
* **Central Test Portal** (`:23000`): Management interface for local API mocks and integration runs.
* **Spec-Driven Mock Server (`mock.py`)**: Universal Swagger 2.0 / OpenAPI 3 mock server with dynamic state stores, HAR 1.2 request logging, and configurable latency simulation.
* **Integration Test Engine (`suite/`)**: Declarative test suite runner verifying complex asynchronous multi-service flows.
* **Pre-Configured Mocks**: `anchanto-oms` (`:23001`), `anchanto-wms` (`:23002`), `eton` (`:23101`).

### 5. 🔌 Local MCP Servers (`ai-first-fw/local-mcps/`)
* **`jira`**: FastMCP server for Jira issue metadata extraction, acceptance criteria parsing, and batch attachment analysis.
* **`kibana`**: FastMCP server for Kibana Observability & Logs with an embedded KQL parser and session-based authentication.

### 6. 🎨 Unified Design System (`ai-first-fw/local-theme/`)
* Single token source of truth (`theme.json`), dark developer CSS (`theme.css`), and zero-overlap chart components (`theme.js`).

---

## 📦 Quick Start & Installation

### Option A: Via Plugin Marketplace (Claude Code & Claude Cowork)

Add the repository as a marketplace and install plugins with one command:

```bash
# Register repository marketplace
plugin marketplace add steven-nguyen-dev/ai-framework

# Install core lifecycle skills plugin
plugin install ai-first-fw-skills@ai-framework

# Install standalone utilities plugin
plugin install ai-first-fw-utilities@ai-framework
```

---

### Option B: Via `npx skills` (Direct Global / Local CLI)

Install specific skills directly into any project:

```bash
# Core Lifecycle Skills
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/write-analysis
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/implementation-planner
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/specs-builder
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/review-code

# Utility Skills
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/draw-diagram
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/git-coordinator
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/pr-desc-writer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/write-docs
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/write-skill
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-architecture-review
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/naver-api-extractor
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lotteon-api-extractor
```

---

### Option C: Google Antigravity 2.0 / Gemini CLI Setup

Add the skill directory paths to your agent configuration (`~/.gemini/config/skills.json` or `.agents/skills.json`):

```json
{
  "entries": [
    { "path": "ai-first-fw/skills" },
    { "path": "ai-first-fw/utilities" }
  ]
}
```

---

## 🌐 Port Allocation Reference

| Category | Port | Server | Description |
| :--- | :--- | :--- | :--- |
| **Test** | `23000` | **Central Test Portal** | Mock server management & test runner |
| **Test** | `23001` | **Anchanto OMS Mock** | Order Management System mock |
| **Test** | `23002` | **Anchanto WMS Mock** | Warehouse Management System mock |
| **Test** | `23101` | **Eton Mock** | Eton logistics & tracking mock |
| **Report** | `24000` | **Central Reports Portal** | Engineering reports control portal |
| **Report** | `24001` | **Daily Work Reports** | Engineering log & matters viewer |
| **Report** | `24002` | **JPluger PR Stats** | GitHub pull request triage & velocity |
| **Report** | `24003` | **AI Skills Registry** | Skills & plugins ecosystem manager |
| **Report** | `24004` | **ELK AI Log Explorer** | Log query & multi-agent AI explorer |

---

## 🔐 Security Standard (`.env.sample`)

* **Zero Committed Secrets**: Real credentials, tokens, and cookies reside exclusively in `.env` (strictly gitignored).
* **Self-Contained Provisioning**: Running `./setup.sh` in any service automatically creates `.env` from `.env.sample` if missing.
* **Portable Execution**: All servers run on pure Python 3 standard library with zero external pip dependencies where possible.

---

## 📄 License & Maintainers

Maintained by **Steven Nguyen** (`steven-nguyen-dev`) and **Nguyen Nguyen** (`nguyennguyen-anchanto`).  
Released under the MIT License.
