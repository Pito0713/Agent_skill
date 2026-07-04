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

照 `coding-workflow-core.md` Phase 0 的偵測表執行（單一事實來源，不在本檔重複維護）。

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

**Phase 3.5：Tech Lead Mode 判斷（可選）**

若符合 `skills/engineering/tech-lead-mode.md` 啟用條件（預估 >3 檔案 / 曾卡關 / 高風險 / 易 scope creep），詢問使用者是否切換為 tech-lead-mode 執行 Phase 4（工單化 + 委派 executor + close gate），取代直接實作。不符合條件則略過，直接進入 Phase 4。

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

### Step 2：agy 交叉驗證（可選）

詢問使用者：「是否啟用 agy 交叉驗證？(y/n)」

**y：**（$CLI_CMD 與安全設定依 `gemini-assist.md` 前置確認；agy 不可用時走模式 C 的 Claude Subagent Fallback）
```bash
# Bash tool timeout: 570s（agy --print-timeout 9m + 30s 緩衝）
git diff HEAD | $CLI_CMD --print-timeout 9m -p "
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

收到結果後 Claude 逐條查證裁決（流程照 `tech-lead-mode.md` Phase 4），CONFIRMED 且 MEDIUM 以上問題回到 Phase 4 修正。

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

agy 驗證：[通過 / 發現 N 個問題已修正 / 未啟用]

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

---

## ✅ 正確做法 / ❌ 常見錯誤

```
✅ Phase 1 先輸出需求摘要並等待確認，再進入實作
✅ 實作順序：Types/Schema → 核心邏輯 → API 層 → UI 層（由內而外）
✅ 每個 Phase 輸出後等待使用者確認，不連續跳 Phase
✅ 每個檔案完成後跑 tsc --noEmit + linter，不留到最後一起修

❌ 跳過 Phase 1 直接開始寫 code（導致實作完才發現需求理解有誤）
❌ 先做 UI 後補型別（容易導致型別與 UI 不一致，需大幅重寫）
❌ 「能跑就好」直接交出，沒有確認 TypeScript 錯誤與 linter 警告
❌ 功能完成後忘記更新版本記錄，導致 git history 不反映功能對應關係
```
