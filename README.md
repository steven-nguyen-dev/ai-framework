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
   │   analysis-handoff    │ ──► System boundaries, blast radius & test matrix
   └───────────┬───────────┘
               ▼
   ┌───────────────────────┐
   │ implementation-planner│ ──► Gate G1: Acceptance criteria & edge cases approved
   └───────────┬───────────┘
               ▼
   ┌───────────────────────┐     ┌──────────────────┐
   │     specs-builder     │ ──► │  specs-reviewer  │ (Cold Diagnostic Spec Audit)
   └───────────┬───────────┘     └──────────────────┘
               ▼
   ┌───────────────────────┐     ┌──────────────────┐
   │ implementation-planner│ ──► │  plan-reviewer   │ (Cold Plan & Evidence Audit)
   └───────────┬───────────┘     └──────────────────┘
               ▼                 └── Gate G2: Plan Approved (Unblocks Code Changes)
   ┌───────────────────────┐     ┌──────────────────┐
   │      Development      │ ──► │  code-reviewer   │ (Cold Branch Diff & Standard Audit)
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
│   ├── skills/                  # Core 6-stage lifecycle gated skills
│   ├── utilities/               # Standalone engineering utilities & API extractors
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
* **`analysis-handoff`**: Pre-planning artifact generator. Maps touched modules, blast radius, error topologies, and regression boundaries.
* **`implementation-planner`**: Master lifecycle orchestrator managing approval gates (`G1` requirements approval, `G2` technical plan approval).
* **`specs-builder`**: Analyzes third-party API documentation and schema samples to build robust field mapping specifications.
* **`specs-reviewer`**: Independent cold auditor that verifies specifications against API harnesses and edge-case criteria.
* **`plan-reviewer`**: Cold plan auditor that validates proposed implementation plans against codebase evidence.
* **`code-reviewer`**: Cold pull request and branch diff reviewer auditing requirements compliance, codebase rules, and security.

### 2. ⚡ Standalone Utilities (`ai-first-fw/utilities/`)
* **`lv1-diagram-maker`**: Generates elegant, professional Mermaid architecture and flow diagrams using muted-dark aesthetics.
* **`lv1-architecture-review`**: High-level system architecture and modularity design reviewer.
* **`lv1-doc-writer`**: Formats clear, maintainable technical documentation and runbooks.
* **`lv1-prompt-builder`**: Compiles structured, context-rich system prompts for subagent workflows.
* **`glossary-maker`**: Harvests a repository once into two documents — an ISO 704:2022 `GLOSSARY.md` terminology reference, and a `GOTCHAS` file per partition carrying the behaviours no single file states.
* **`naver-api-extractor` & `lotteon-api-extractor`**: Automated tools for extracting, parsing, and documenting e-commerce APIs.

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
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/analysis-handoff
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/implementation-planner
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/specs-builder
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/specs-reviewer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/plan-reviewer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/code-reviewer

# Utility Skills
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-diagram-maker
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-architecture-review
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/lv1-doc-writer
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/utilities/glossary-maker
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
