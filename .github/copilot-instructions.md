# GitHub Copilot Instructions

這份文件為 GitHub Copilot 提供本專案的核心規範與 skill 索引。

---

## Coding 規範

- 命名揭示意圖，禁止縮寫（url / id / api 除外）
- 函式 < 50 行，參數 ≤ 3 個
- Boolean 用 is / has / can / should 前綴
- 提前 return 取代巢狀 if
- catch 不能為空：必須 log + re-throw
- 禁止 `console.log` 進 production
- 禁止 hardcode secrets、API keys

## TypeScript

- 禁止 `any`，使用具體型別或 `unknown`
- 優先 `interface` 定義資料結構，`type` 用於 union / intersection
- 所有 async function 使用 try/catch，不混用 `.catch()`

## 安全

- 所有外部輸入視為不可信任，須驗證
- SQL 只用 parameterized query
- 禁止 `innerHTML = userInput`，使用 textContent 或 DOMPurify
- Secrets 從 `process.env` 讀取，`.env` 進 `.gitignore`

---

## Skill 索引

完整 skill 清單與觸發詞：`skills/llms.txt`

常用 skill：
- 新增功能 → `skills/engineering/new-feature/SKILL.md`
- 除錯 → `skills/engineering/debug-flow/SKILL.md`
- Code Review → `skills/engineering/code-review/SKILL.md`
- 安全審查 → `skills/engineering/security-review/SKILL.md`
