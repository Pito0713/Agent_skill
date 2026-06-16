---
name: new-feature
description: 新功能開發協調器。當使用者說「幫我做一個功能」、「新增 feature」、
  「實作 X」、「我要做 Y」、「建立 Z 功能」時觸發。
  自動偵測專案類型，協調 API 設計 → 實作 → 測試 → 文件 → 版本記錄的完整流程。
---

# New Feature — Orchestrator

## 觸發後第一步：釐清需求

詢問使用者（若未說明）：
> 1. 這個功能的**目標**是什麼？（一句話描述）
> 2. 涉及的範圍？前端 / 後端 / 全端
> 3. 有沒有現有的相關程式碼需要修改？

確認後進入 Phase 0。

---

## Phase 0：偵測專案類型 + 載入對應規則

```bash
ls tsconfig.json next.config.* requirements.txt pyproject.toml 2>/dev/null
grep -s '"react"\|"vue"\|"next"' package.json 2>/dev/null
```

| 偵測結果 | 載入規則 |
|---------|---------|
| `tsconfig.json` 存在 | `rules/typescript.md` |
| `package.json` 含 react / next | `rules/react.md` 或 `rules/nextjs.md` |
| `requirements.txt` / `*.py` 存在 | `rules/python.md` |
| 任何專案 | `rules/coding-standards.md`（常駐）|
| 任何專案 | `rules/security.md`（常駐）|

**輸出**：「偵測到：[技術堆疊]，載入對應規則，開始規劃」

---

## Phase 1：理解與確認需求

依據 `coding-workflow-core.md` Phase 1：

```
[ ] 讀取相關現有檔案，理解架構
[ ] 確認這個功能會影響哪些模組
[ ] 找出相關 types / interfaces / schema
[ ] 確認 edge cases 與限制條件
```

**輸出**：「我理解的需求是：[摘要]，涉及 [模組清單]」→ 等待確認

---

## Phase 2：API 設計（有後端時執行）

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 3
> - 使用者確認「純前端功能，不涉及資料新增/修改」
> - 使用者確認「複用既有 API，無需新增 endpoint」
> - Phase 0 偵測為純前端專案（無任何後端設定檔）

委派 `agents/01-core-development/api-architect.md`：

```
[ ] 定義 endpoint 路徑與 HTTP method
[ ] 定義 request / response schema
[ ] 確認認證與授權需求
[ ] 確認錯誤回應格式
```

**輸出**：API spec 草稿 → 等待確認後進入 Phase 3

---

## Phase 3：實作計畫

依涉及範圍，列出需要建立 / 修改的檔案：

```
後端  → agents/01-core-development/backend-engineer.md
前端  → agents/01-core-development/frontend-engineer.md
型別  → agents/02-language-specialists/typescript-expert.md（TS 專案）
Python → agents/02-language-specialists/python-expert.md（Python 專案）
```

實作順序（由內而外）：
```
1. Types / Schema 定義
2. 核心邏輯 / Service 層
3. API / Controller 層
4. UI / Component 層
5. 串接與整合
```

**輸出**：條列式實作計畫 + 檔案清單 → 等待確認後開始實作

---

## Phase 4：實作執行

依 Phase 3 計畫逐步實作，每個檔案完成後自我檢查：

```
[ ] 無 TypeScript 錯誤（tsc --noEmit）
[ ] Linter 無錯誤（eslint / ruff）
[ ] 函式長度 < 50 行
[ ] 無 console.log / hardcoded values
[ ] 錯誤處理完整
```

---

## Phase 5：測試

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 6
> - 使用者明確說「這是 prototype / 先不寫測試」
> - 使用者明確說「hotfix，緊急，後補測試」
> - 本次變更行數 < 15 行且為純設定調整（非邏輯修改）

委派 `skills/engineering/testing-strategy.md` 設計測試策略，
再依規模委派 `agents/05-quality-assurance/test-engineer.md` 執行：

```
[ ] 撰寫 unit test（核心邏輯）← test-engineer
[ ] 撰寫 integration test（API 層）← test-engineer
[ ] 涵蓋 happy path + error case + edge case
[ ] 若有 UI → 委派 agents/05-quality-assurance/e2e-tester.md
```

---

## Phase 6：文件更新

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 7
> - Phase 2 已跳過且無新 API endpoint（純 UI 功能）
> - 本次修改不改變公開介面 / 使用方式（純內部重構）
> - 使用者明確說「不需要文件更新」
> - 本次變更行數 < 15 行

委派 `skills/engineering/documentation.md`：

```
[ ] 更新 API 文件（若有新 endpoint）
[ ] 更新 README（若有新的使用方式）
[ ] 補充 inline comment（複雜邏輯）
```

---

## Phase 7：版本記錄 + Gemini 交叉驗證

### Step 1：版本記錄

觸發 `skills/productivity/version-log.md`：
```
[ ] 更新 README 版本紀錄表
[ ] 確認 commit message 符合 rules/git.md
```

### Step 2：Gemini 交叉驗證（可選）

詢問使用者：「是否啟用 Gemini 交叉驗證？(y/n)」

**y：**
```bash
git diff HEAD | agy -p "
這是一個新功能的實作 diff，請審查：
1. 邏輯是否正確，有無邊界條件遺漏
2. 安全風險（注入、權限、資料洩漏）
3. 與現有架構是否一致

每個問題格式：
[嚴重度] 位置：描述 → 潛在影響
嚴重度：CRITICAL / HIGH / MEDIUM / LOW
無問題輸出：「未發現問題」
繁體中文。"
```

收到結果後 Claude 裁決，MEDIUM 以上問題回到 Phase 4 修正。

---

## 最終輸出

```
## 新功能完成報告
功能名稱：[名稱]
涉及範圍：[前端 / 後端 / 全端]
新增 / 修改檔案：[清單]

實作摘要：
- [主要變更說明]

測試覆蓋：
- [測試清單]

Gemini 驗證：[通過 / 發現 N 個問題已修正]

下一步建議：
- [ ] deploy-prep（上線前檢查）
- [ ] code-review（給其他人審查）
```

---

## 分工原則

| 角色 | 負責 Phase |
|------|------|
| Orchestrator（本 skill）| 全流程控制、決策、整合 |
| `api-architect` | Phase 2 API 設計 |
| `backend-engineer` | Phase 3-4 後端實作 |
| `frontend-engineer` | Phase 3-4 前端實作 |
| `typescript-expert` / `python-expert` | Phase 3-4 語言專項問題 |
| `testing-strategy` + `test-engineer` + `e2e-tester` | Phase 5 測試 |
| `documentation` | Phase 6 文件 |
| `version-log` | Phase 7 版本記錄 |
| `gemini-assist` | Phase 7 交叉驗證 |
