# 🚀 AI-First Software Engineering Framework

An enterprise-grade, specification-first, and review-driven software engineering framework for **AI Agents** (Claude Code, Claude Cowork, Google Antigravity, Gemini CLI) and **Human Engineering Teams**.

---

## 📖 Overview

The **AI-First Framework** standardizes the software development lifecycle for autonomous and pair-programming AI agents. It replaces unguided code generation with structured analysis, specification-driven mapping, strict multi-stage audit gates, and dedicated local MCP servers.

```
[ Requirements / Jira Ticket ]
               │
               ▼
   ┌───────────────────────┐
   │    write-analysis     │ ──► Mapping spec, change request spec & ticket summary
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

The framework is organized into 3 independent, self-contained plugins (with zero symlinks):

```
ai-framework/
├── .claude-plugin/              # Claude Code marketplace registry
├── lv1-mcp/                     # Plugin 1: Local MCP Servers (lv1-mcps)
│   ├── jira-reader/             # Jira issue fetcher & attachment downloader
│   ├── kibana-explorer/         # Enterprise log search via KQL
│   ├── wiki/                    # Independent knowledge base & search
│   └── coordinator/             # Swarm pane orchestration & task exchange
├── lv1-fw-skills/               # Plugin 2: Core Lifecycle Skills (lv1-fw-skills)
│   ├── write-analysis/
│   ├── implementation-planner/
│   ├── specs-builder/
│   └── review-code/
├── lv1-utilities/               # Plugin 3: Standalone Utilities (lv1-utilities)
│   ├── draw-diagram/
│   ├── lead/
│   ├── make-it-short/
│   ├── sync-pr/
│   ├── write-docs/
│   ├── write-pr-desc/
│   ├── write-skill/
│   ├── naver-api-extractor/
│   └── lotteon-api-extractor/
└── research/                    # Audits, guides, and assets
```

---

## 🧩 The 3 Independent Plugins

### 1. 🔌 Local MCP Servers (`lv1-mcp/`)
* **`jira-reader`**: Jira issue metadata, ADF descriptions, and attachment downloads.
* **`kibana-explorer`**: Enterprise log investigation and incident triaging via Elasticsearch / Kibana KQL.
* **`wiki`**: High-performance semantic and keyword search across internal engineering architecture docs.
* **`swarm-coordinator`**: Task distribution, scratchpads, and execution logs across agent swarms.

### 2. 🛡️ Lifecycle Skills (`lv1-fw-skills/`)
Gated AI skills that enforce engineering rigor before code is touched:
* **`write-analysis`**: Writes the four-document contract — claim library, mapping spec, change request spec, and ticket summary.
* **`implementation-planner`**: Master lifecycle orchestrator managing approval gates (`G1` requirements approval, `G2` technical plan approval).
* **`specs-builder`**: Fills integration spec folders and writes confidence-graded mapping plans against test harnesses.
* **`review-code`**: Cold pull request and branch diff reviewer auditing requirements compliance, codebase rules, and security.

### 3. ⚡ Standalone Utilities (`lv1-utilities/`)
* **`draw-diagram`**: Generates Mermaid diagrams styled to the shared dark palette.
* **`lead`**: Fixed-pane swarm leadership orchestration across model tiers via `herdr`.
* **`make-it-short`**: Enforces repository writing limits and conciseness rules.
* **`sync-pr`**: Syncs feature branches into QA/UAT mirror branches.
* **`write-docs`**: Writes technical notes in the framework house style.
* **`write-pr-desc`**: Reads branch diffs and drafts GitHub PR descriptions.
* **`write-skill`**: Authors and revises agent skills.
* **`naver-api-extractor`** & **`lotteon-api-extractor`**: E-commerce API extractors.

---

## 📦 Installation & Usage

### Option A: Via Plugin Marketplace (Claude Code & Claude Cowork)

Add the repository marketplace and install desired plugins:

```bash
# Register repository marketplace
plugin marketplace add steven-nguyen-dev/ai-framework

# Install plugins
plugin install lv1-mcps@ai-framework
plugin install lv1-fw-skills@ai-framework
plugin install lv1-utilities@ai-framework
```

---

### Option B: Google Antigravity & Gemini CLI Setup

Add the skill directory paths to your agent configuration (`~/.gemini/config/skills.json` or `.agents/skills.json`):

```json
{
  "entries": [
    { "path": "lv1-fw-skills" },
    { "path": "lv1-utilities" }
  ]
}
```

---

## 📄 License & Maintainers

Maintained by **Steven Nguyen** (`steven-nguyen-dev`) and **Nguyen Nguyen** (`nguyennguyen-anchanto`).  
Released under the MIT License.
