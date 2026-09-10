# AI-First Framework Lifecycle Skills

Core lifecycle skills governing specification-first, review-driven software development across AI agents and human engineers.

---

## 📖 Overview

The **`ai-first-fw-skills`** plugin provides an end-to-end gated development workflow. It replaces unstructured code generation with structured requirement analysis, confidence-graded mapping plans, strict plan gates, and cold multi-pass code audits before pull requests are created.

```
[ Requirements / Jira Ticket ]
               │
               ▼
   ┌───────────────────────┐
   │    write-analysis     │ ──► Four-document contract (claims, mapping, CRs, specs)
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
   │      Development      │ ──► │   review-code    │ (3 isolated cold review passes)
   └───────────┬───────────┘     └──────────────────┘
               ▼
   [ Verified Pull Request & Production Deployment ]
```

---

## 🧩 Lifecycle Skills

| Skill | Description | Key Deliverables & Gates |
| :--- | :--- | :--- |
| **[`write-analysis`](write-analysis/)** | Writes the four-document contract from ticket brief, docs, and codebase | Claim library, field mapping, change requests, ticket summary |
| **[`implementation-planner`](implementation-planner/)** | Master lifecycle orchestrator managing multi-stage approval gates | **Gate G1** (Requirements), **Gate G2** (Plan Quality Bar) |
| **[`specs-builder`](specs-builder/)** | Generates integration spec folder and confidence-graded mapping plan | `mapping-plan.md` (Confidence `A` / `B` / `C`), integration specs |
| **[`review-code`](review-code/)** | Cold branch and PR diff reviewer across 3 isolated passes | Pass 1: Requirements · Pass 2: Repo Rules · Pass 3: Security |

> Each skill declares and versions independently in its own `SKILL.md` frontmatter. Check `plugin.json` for current plugin bundle versions.

---

## 📦 Installation & Usage

### 1. Via Plugin Marketplace (Claude Code & Claude Cowork)
```bash
# Register marketplace (if not already added)
plugin marketplace add steven-nguyen-dev/ai-framework

# Install lifecycle skills plugin
plugin install ai-first-fw-skills@ai-framework
```

### 2. Via `npx skills` (Direct Skill Installation)
```bash
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/write-analysis
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/implementation-planner
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/specs-builder
npx skills add steven-nguyen-dev/ai-framework/ai-first-fw/skills/review-code
```

### 3. Antigravity / Gemini Workspace Configuration
Register the skills directory in `~/.gemini/config/skills.json` or `.agents/skills.json`:
```json
{
  "entries": [
    {
      "path": "ai-first-fw/skills",
      "exclude": ["^review-code$"]
    }
  ]
}
```
*(Note: `review-code` is typically excluded in Antigravity to prioritize native code generation and agentic debugging tools).*

---

## 🏷️ Quality Levers & Standards

Every lifecycle skill adheres to strict quality levers:
- **Zero Hallucinated Properties**: Every field, property, and type must be traced directly to context files or official API documentation.
- **Explicit Gates**: No implementation begins before Gate G1 (requirements) and Gate G2 (plan) pass.
- **Isolated Review Passes**: Code review is conducted in isolation without prior reviewer bias.
- **Contract-Driven**: Requirements are frozen into a verifiable contract before code modification starts.
