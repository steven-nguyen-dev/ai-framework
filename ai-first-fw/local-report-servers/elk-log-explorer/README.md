# 🔍 ELK AI Log Explorer & Query Dashboard

An interactive AI-powered ELK / Kibana Log Explorer with dual AI Agent integrations:
- 🧠 **Claude 3.7 Sonnet** (Medium Reasoning)
- ⚡ **Antigravity AGY Gemini 3.7 Flash** (High Reasoning)
- 🔍 **Direct KQL Engine** (Real-time Kibana Search)

---

## 🚀 1-Click Launch

### Option A: macOS Native Application
Double-click **`Install.command`** or run:
```bash
./install_app.sh
```
Then launch **"ELK AI Log Explorer"** from your `/Applications` folder or Spotlight.

### Option B: Terminal Service
Double-click **`Start.command`** or run:
```bash
./start.sh
```
Opens browser automatically at `http://localhost:8448`.

---

## 🌟 Key Features
- **AI Agent Selector**: Toggle between **Claude Sonnet** and **AGY Gemini Flash 3.7** with one click.
- **Natural Language to ELK KQL**: Enter questions in plain English; the AI formulates the optimal Kibana query and explains the results.
- **Deep JSON Unpacking**: Unpacks stringified payloads (`"key": "value"`), Ruby hashes, and nested dictionaries.
- **Syntax Highlighting & Formatting**: 2-space indented multi-line JSON with full color tokens for keys, strings, numbers, and booleans.
- **One-Click Formatted Copy & Export**: Copy or export clean JSON payloads.
