# Agent Skills — Universal Entry Point

> 本 skill 體系的通用入口，適用於所有支援 AGENTS.md 的 AI agent 平台（Cursor、Copilot 等）。
> Claude Code 用戶請參閱 CLAUDE.md。本檔不依賴 @file 語法，核心規則 inline，其餘用路徑引用。

---

## 常駐核心規則（inline，任何任務都適用）

### Coding
- 意圖揭示命名，禁止縮寫（除 url、id、api）
- 函式單一職責，< 50 行，參數 ≤ 3 個，提前 return 取代巢狀 if
- 不吞錯誤：catch 內必須有處理邏輯或 re-throw
- 禁止 `console.log` 進 production、禁止 hardcode secrets、禁止 `any`（TypeScript）

### 安全（OWASP 基準）
- 所有外部輸入視為不可信任，必須驗證
- SQL 一律 parameterized query；禁止 `innerHTML = userInput`
- secrets 從環境變數讀取並做 runtime validation，`.env` 進 `.gitignore`

---

## 核心鐵律

1. **驗證不自驗**：自己產出的東西不能自己驗收——檔案用 read-back、程式碼用實跑測試（貼輸出）
2. **不猜意圖**：命中多個 skill 觸發詞或出現模糊詞（「優化」「完善」）→ 列出選項問使用者
3. **卡住就停**：同一件事重試兩輪失敗 → 停下，帶失敗軌跡升級或問使用者
4. **動 repo 前先 `git status`**：非預期變更 → 停下來問，不默默覆蓋
5. **完成要有證據**：「應該會過」「邏輯上正確」= 進行中，不是完成

---

## 路由表（需要時讀對應檔案）

| 情境 | 讀這份 |
|------|--------|
| 查 skill 觸發詞與完整索引 | `skills/llms.txt` |
| 語言/框架 rules 偵測條件 | `skills/engineering/coding-workflow-core.md` Phase 0 |
| 委派、模型選擇、升降級 | `governance/model-orchestration.md` |
| 完成判準、何時問人、何時換路 | `governance/judgment-rubrics.md` |
| 派工 prompt 模板 | `governance/delegation-templates.md` |
| 卡關/跨檔案/高風險實作 | `skills/engineering/tech-lead-mode.md` |
| 修改制度檔的權限 | `governance/maintenance-protocol.md` |

---

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 回應先給極短摘要，再給可執行內容
- 指出邏輯漏洞，不為友善而同意
