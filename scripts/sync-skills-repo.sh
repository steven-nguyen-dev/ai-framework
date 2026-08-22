#!/usr/bin/env bash
# ==============================================================================
# Sync User-Facing Skills Repository (ai-first-framework-skills)
# Publishes only user-facing skills, utilities, and plugin manifests.
# Excludes internal builder tools (theme, test servers, report servers, mcps).
# ==============================================================================
set -e

MONOREPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_REMOTE="${SKILLS_REMOTE_URL:-$(git -C "$MONOREPO_ROOT" remote get-url skills-upstream 2>/dev/null || echo "https://github.com/nguyennguyen-anchanto/ai-first-framework-skills.git")}"
TMP_DIR="$(mktemp -d)"

echo "🔄 Preparing user-facing skills repository in $TMP_DIR..."

# 1. Initialize temporary git repository
cd "$TMP_DIR"
git init -b main
git config user.name "Nguyen Nguyen"
git config user.email "nguyennguyen-anchanto@users.noreply.github.com"
git remote add origin "$TARGET_REMOTE"

# 2. Copy user-facing skills and utilities
mkdir -p "$TMP_DIR/skills" "$TMP_DIR/utilities" "$TMP_DIR/.claude-plugin"
cp -R "$MONOREPO_ROOT/ai-first-fw/skills/"* "$TMP_DIR/skills/"
cp -R "$MONOREPO_ROOT/ai-first-fw/utilities/"* "$TMP_DIR/utilities/"

# 3. Create .claude-plugin/marketplace.json
cat << 'MARKETPLACE_EOF' > "$TMP_DIR/.claude-plugin/marketplace.json"
{
  "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
  "name": "ai-first-framework-skills",
  "description": "AI-First Software Engineering Framework: Core Lifecycle Skills and Standalone Utilities",
  "owner": {
    "name": "Nguyen Nguyen",
    "email": "nguyennguyen-anchanto@users.noreply.github.com"
  },
  "plugins": [
    {
      "name": "ai-first-fw-skills",
      "description": "Core AI-First Framework lifecycle skills: analysis-handoff, implementation-planner, specs-builder, specs-reviewer, plan-reviewer, and code-reviewer.",
      "version": "1.0.0",
      "source": "./skills"
    },
    {
      "name": "ai-first-fw-utilities",
      "description": "Standalone engineering utility skills: lv1-diagram-maker, lv1-architecture-review, lv1-doc-writer, lv1-prompt-builder, naver-api-extractor, and lotteon-api-extractor.",
      "version": "1.0.0",
      "source": "./utilities"
    }
  ]
}
MARKETPLACE_EOF

# 4. Create .gitignore
cat << 'GITIGNORE_EOF' > "$TMP_DIR/.gitignore"
.DS_Store
*.pyc
__pycache__/
*.env
.scratchpads/
GITIGNORE_EOF

# 5. Create user-facing README.md
cat << 'README_EOF' > "$TMP_DIR/README.md"
# 🧩 AI-First Framework Skills & Utilities

A production-ready collection of review-driven, specification-first engineering skills and standalone utilities for **Claude Code**, **Claude Cowork**, **Google Antigravity 2.0**, and **Gemini**.

---

## 🚀 1-Command Installation

### Claude Code & Claude Cowork (Plugin Marketplace)

Add this repository to your plugin marketplace and install the skills in one step:

```bash
# 1. Register the marketplace
plugin marketplace add nguyennguyen-anchanto/ai-first-framework-skills

# 2. Install core lifecycle skills
plugin install ai-first-fw-skills@ai-first-framework-skills

# 3. Install standalone utilities
plugin install ai-first-fw-utilities@ai-first-framework-skills
```

---

### Direct Installation (`npx skills`)

Install individual skills directly into your local workspace using the `skills` CLI:

```bash
# Core Lifecycle Skills
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/skills/analysis-handoff
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/skills/implementation-planner
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/skills/specs-builder
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/skills/specs-reviewer
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/skills/plan-reviewer
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/skills/code-reviewer

# Standalone Utility Skills
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/utilities/lv1-diagram-maker
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/utilities/lv1-architecture-review
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/utilities/lv1-doc-writer
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/utilities/lv1-prompt-builder
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/utilities/naver-api-extractor
npx skills add nguyennguyen-anchanto/ai-first-framework-skills/utilities/lotteon-api-extractor
```

---

### Google Antigravity 2.0 & Gemini CLI Setup

Add the skill directory paths to your agent configuration (`~/.gemini/config/skills.json` or `.agents/skills.json`):

```json
{
  "entries": [
    { "path": "skills" },
    { "path": "utilities" }
  ]
}
```

---

## 🛡️ Core Lifecycle Skills (`skills/`)

The core skills guide autonomous AI agents through a gated engineering lifecycle:

| Skill | Gate / Phase | Purpose |
| :--- | :--- | :--- |
| **`analysis-handoff`** | Pre-Planning | Maps system boundaries, blast radius, error topologies, and regression risks before planning starts. |
| **`implementation-planner`** | G1 & G2 Gates | Orchestrates the multi-stage lifecycle, managing requirements approval (G1) and technical plan approval (G2). |
| **`specs-builder`** | Spec Authoring | Builds rigorous API field mapping specifications from Swagger/OpenAPI docs and payload samples. |
| **`specs-reviewer`** | Spec Gate Audit | Cold diagnostic reviewer auditing specifications against integration harnesses and edge cases. |
| **`plan-reviewer`** | Plan Gate Audit | Independent auditor verifying implementation plans against codebase evidence before code is touched. |
| **`code-reviewer`** | Code Gate Audit | Cold pull request and branch diff reviewer ensuring compliance with requirements, standards, and safety. |

```
[ Input Requirements ]
         │
         ▼
 ┌─────────────────────────┐
 │    analysis-handoff     │ ──► .scratchpads/<feature>/analysis-handoff.md
 └───────────┬─────────────┘
             ▼
 ┌─────────────────────────┐
 │ implementation-planner  │ ──► Gate G1: Requirements & Acceptance Criteria Approved
 └───────────┬─────────────┘
             ▼
 ┌─────────────────────────┐     ┌─────────────────────┐
 │      specs-builder      │ ──► │   specs-reviewer    │ (Cold Diagnostic Spec Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼
 ┌─────────────────────────┐     ┌─────────────────────┐
 │ implementation-planner  │ ──► │    plan-reviewer    │ (Cold Plan & Evidence Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼                   └── Gate G2: Plan Approved (Unblocks Code Changes)
 ┌─────────────────────────┐     ┌─────────────────────┐
 │      Development        │ ──► │    code-reviewer    │ (Cold Diff & Quality Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼
 [ Verified Code & Pull Request ]
```

---

## ⚡ Standalone Utility Skills (`utilities/`)

Independent skills for specific engineering tasks:

* **`lv1-diagram-maker`**: Creates clean, professional Mermaid architecture and sequence diagrams using muted-dark aesthetics.
* **`lv1-architecture-review`**: High-level system architecture and modularity design reviewer.
* **`lv1-doc-writer`**: Formats clear, maintainable technical documentation and runbooks.
* **`lv1-prompt-builder`**: Compiles structured, context-rich system prompts for subagent workflows.
* **`naver-api-extractor` & `lotteon-api-extractor`**: Automated extractors and parsers for third-party marketplace APIs.

---

## 📄 License & Maintainers

Maintained by **Nguyen Nguyen** (`nguyennguyen-anchanto`).  
Released under the MIT License.
README_EOF

# 6. Commit and push to skills repository
git add -A
git commit -m "feat(skills): publish user-facing lifecycle skills and standalone utilities v1.0.0"
echo "🚀 Pushing to nguyennguyen-anchanto/ai-first-framework-skills..."
git push origin main --force

# 7. Cleanup
rm -rf "$TMP_DIR"
echo "✔ Successfully synced and pushed user-facing skills repository!"
