# Agent Skills — Universal Entry Point

> 這份文件是本 skill 體系的通用入口，適用於所有支援 AGENTS.md 的 AI agent 平台（Gemini CLI、Cursor、Copilot 等）。
> Claude Code 用戶請參閱 CLAUDE.md。

---

## 專案概覽

這是一個標準化的 AI coding agent 行為規範庫，提供：

- **Rules**：語言與框架規範（TypeScript / React / Next.js / Python / 安全 / 測試 / Git）
- **Skills**：可呼叫的工作流程（功能開發 / 除錯 / 審查 / 設計 / 生產力）
- **Agents**：專責子任務的 subagent 定義

---

## 常駐規範（每次 session 自動生效）

以下規範適用於所有任務，執行前必須遵守：

### 核心 Coding 原則

- 命名使用意圖揭示命名，禁止縮寫（除 url、id、api）
- 函式單一職責，長度上限 50 行，參數上限 3 個
- 不吞錯誤：catch 內必須有處理邏輯或 re-throw
- 禁止 `console.log` 進入 production
- 禁止 hardcode secrets / API keys

### 安全基準（OWASP Top 10）

- 所有外部輸入視為不可信任，必須驗證
- 禁止字串拼接 SQL query，使用 parameterized query
- 禁止 `innerHTML = userInput`，使用 textContent 或 DOMPurify
- JWT 有效期最長 24h，禁止在 URL 中傳遞 token
- 禁止 hardcode secrets，從環境變數讀取並做 runtime validation

---

## Skill 索引

完整的 skill 清單、觸發詞與說明請參閱：

```
skills/llms.txt
```

### 常用 Skill 快速對照

| 需求 | 載入 |
|------|------|
| 新增功能 | `skills/engineering/new-feature.md` |
| 除錯 | `skills/engineering/debug-flow.md` |
| Code Review | `skills/engineering/code-review.md` |
| 安全審查 | `skills/engineering/security-review.md` |
| 上線前檢查 | `skills/engineering/deploy-prep.md` |
| UI 設計規劃 | `skills/design/ui-design-flow.md` |
| 精簡程式碼 | `skills/engineering/lazyengineer.md` |

---

## 按需載入規範

依偵測條件自動載入：

| 偵測條件 | 載入規範 |
|---------|---------|
| `tsconfig.json` 或 `*.ts` 存在 | `rules/typescript.md` |
| `package.json` 含 react | `rules/react.md` |
| `next.config.*` 存在 | `rules/nextjs.md` |
| `requirements.txt` / `*.py` 存在 | `rules/python.md` |
| 任務涉及 commit / PR | `rules/git.md` |
| 任務涉及前端 / XSS / CORS | `rules/frontend-security.md` |

---

## 行為準則

1. 所有 coding 任務執行前確認適用的 rules/
2. 遇到重複性工作流程，優先使用 skills/ 對應 skill
3. 遇到多個 skill 命中時，列出選項詢問使用者而非自行猜測
4. 每次重要決策後更新 memory/project-context.md

---

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 回應先給極短摘要，再給可執行內容
- 指出邏輯漏洞，不為友善而同意
