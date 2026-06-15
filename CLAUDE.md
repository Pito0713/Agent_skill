# CLAUDE.md — AI Agent Skill Project

> 這是 Claude Code 的專案頂層指令。所有 rules、skills、agents、hooks 均從此檔載入。

---

## 專案概覽

這是一個用於管理 AI coding agent 行為規範的標準化專案骨架，涵蓋：
- **Rules**：coding 規範（語言、框架、安全、測試、git）
- **Skills**：可呼叫的工作流程（coding、debug、testing、docs、handoff）
- **Agents**：專責子任務的 subagent 定義
- **Hooks**：自動化觸發器（pre-commit、安全攔截）
- **Memory**：跨 session 的工作記憶

---

## 常駐載入（每次 session 自動生效）

@rules/coding-standards.md
@rules/security.md
@skills/engineering/coding-workflow-core.md
@skills/engineering/gemini-assist.md

---

## 按需載入（視任務手動引入）

| 情境 | 載入 |
|------|------|
| TypeScript 專案（自動偵測）| `@rules/typescript.md` |
| React 專案（自動偵測）| `@rules/react.md` |
| Next.js 專案（自動偵測）| `@rules/nextjs.md` |
| Python 專案（自動偵測）| `@rules/python.md` |
| 撰寫 / 執行測試（自動偵測）| `@rules/testing.md` |
| 提到 commit / PR（自動偵測）| `@rules/git.md` |
| 前端審查 / review / XSS / CORS / PII | `@rules/frontend-security.md` |
| 查實作模式 | `@skills/engineering/coding-workflow-ref.md` |
| 練習 / 刻意改進 | `@skills/learning/feedback-loop.md` |
| UI/UX 設計規劃 | `@skills/design/wireframing.md` 或 `@skills/design/information-architecture.md` 或 `@skills/design/ui-visual-design.md` |

---

## 規則索引

```
rules/
├── coding-standards.md   # 通用 coding 規範（常駐）
├── security.md           # 安全規範（常駐）
├── typescript.md         # TypeScript 規範（按需）
├── react.md              # React 規範（按需）
├── nextjs.md             # Next.js App Router 規範（按需）
├── python.md             # Python 規範（按需）
├── testing.md            # 測試規範（按需）
└── git.md                # Git workflow 規範（按需）
```

## 行為準則

1. **回應前先讀 rules/**：所有 coding 任務執行前必須確認適用的 rule 檔
2. **優先使用 skills/**：重複性工作流程使用對應 skill，不要重新發明
3. **委派 subagent**：遇到專業子任務時，優先委派對應 agent
4. **更新 memory/**：每次重要決策或架構選型後更新 project-context.md

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 回應給極短摘要，再給可執行內容
- 指出邏輯漏洞、不為友善而同意
- 涉及數字與風險時先看基率

## 快速入口

| 需求 | 對應資源 |
|------|----------|
| 開始新功能 | `skills/engineering/new-feature.md` |
| Code Review | `skills/engineering/code-review.md` |
| 查實作模式 | `skills/engineering/coding-workflow-ref.md` |
| 除錯問題 | `skills/engineering/debug.md` |
| 撰寫測試 | `skills/engineering/testing-strategy.md` |
| 撰寫文件 | `skills/engineering/documentation.md` |
| 工作交接 | `skills/productivity/handoff.md` |
| 安全審查 | `agents/04-security/security-auditor.md` |
| 刻意練習回饋 | `skills/learning/feedback-loop.md` |
| 邏輯看不懂 / 反覆出錯 | `skills/learning/concrete-example.md` |
| 頁面結構規劃 | `skills/design/wireframing.md` |
| 視覺風格決策 | `skills/design/ui-visual-design.md` |
| 導航 / 路由規劃 | `skills/design/information-architecture.md` |
| 查看專案決策 | `memory/project-context.md` |
| 新增 GitHub Skill | `sources/registry.md` → `skills/convert-skill.md` |
