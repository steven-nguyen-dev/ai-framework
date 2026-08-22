# Local Theme (`local-theme`)

Unified enterprise design system, color tokens, and visualization toolkit for all local services across `ai-first-fw`.

---

## 📁 Package Contents

| File | Purpose |
| :--- | :--- |
| **[`theme.json`](theme.json)** | **Single Source of Truth** for all color, surface, and semantic pill design tokens |
| **[`theme.css`](theme.css)** | CSS custom properties (`:root`), typography (`Inter` + `JetBrains Mono`), and base utility styles |
| **[`theme.js`](theme.js)** | Reusable visualization widgets (`LocalTheme.renderVelocityChart`, `LocalTheme.renderProgressList`) |

---

## 🎨 Design Tokens

- **Canvas Background**: Deep Dark Slate-950 (`#020617`)
- **Panels & Cards**: Slate-900 (`#0f172a`)
- **Sub-surfaces & Insets**: Slate-800 (`#1e293b`)
- **Borders**: Slate-800 (`#1e293b`) and Slate-700 (`#334155`)
- **Typography**:
  - Primary text: Slate-50 (`#f8fafc`)
  - Secondary text: Slate-300 (`#cbd5e1`)
  - Muted text: Slate-400 (`#94a3b8`)
  - Body font: `Inter`
  - Code/badging font: `JetBrains Mono`

### Semantic Soft Pills
- **Pass / Running / OK**: Emerald (`rgba(16, 185, 129, 0.15)` bg, `#34d399` text)
- **Fail / Stopped / Error**: Red (`rgba(239, 68, 68, 0.15)` bg, `#f87171` text)
- **Run / Action / Direct**: Blue (`rgba(59, 130, 246, 0.15)` bg, `#60a5fa` text)
- **Warn / At Risk**: Amber (`rgba(245, 158, 11, 0.15)` bg, `#fbbf24` text)
- **Neutral / Draft**: Slate (`rgba(51, 65, 85, 0.4)` bg, `#cbd5e1` text)

---

## 🔄 Reused By

1. **Local Test Servers** (`ai-first-fw/local-test-servers/`):
   - Portal (`http://localhost:23000`)
   - Mock Server Engine (`mock.py` on ports `23001`–`23200`)
2. **Local Report Servers** (`ai-first-fw/local-report-servers/`):
   - Central Reports Portal (`http://localhost:24000`)
   - Daily Work Reports (`http://localhost:24001`)
   - JPluger PR Stats (`http://localhost:24002`)
