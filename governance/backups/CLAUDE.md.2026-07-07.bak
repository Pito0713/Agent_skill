# CLAUDE.md — AI Agent Skill Project

> 制度倉庫：管理 AI coding agent 的 rules / skills / agents / memory。
> 本檔只放常駐規則與路由指標。詳細內容在被指向的檔案裡，**用到才讀，讀完就動手**。

---

## 常駐載入

@rules/coding-standards.md
@rules/security.md
@skills/engineering/coding-workflow-core.md

---

## 核心鐵律（每個 session 都適用）

1. **重活派出去**：大量讀檔、掃 repo、網路搜尋、批次修改一律委派 subagent 或 agy，主對話只進結論。做法見 `governance/model-orchestration.md`。
2. **驗證不自驗**：自己產出的東西不能自己驗收。檔案用 read-back、程式碼用實跑測試（貼輸出）、高風險加第二意見。
3. **不猜意圖**：訊息命中多個 skill 觸發詞、或出現模糊詞（「優化」「完善」「讓它更好」「改進」）→ 列出選項問使用者。判斷樹在 `skills/llms.txt` 末段「歧義處理提示」。
4. **卡住就停**：同一件事重試兩輪仍失敗 → 停下，帶完整失敗軌跡升級模型或問使用者。判準見 `governance/judgment-rubrics.md`。
5. **動 repo 前先 `git status`**：發現非預期變更（可能是其他 session 在動）→ 停下來問使用者，不默默覆蓋。
6. **隨做隨記**：重要架構決策寫入 `memory/project-context.md`（ADR 格式）；踩坑教訓 append 到 `governance/lessons.md`。

---

## 路由表（需要時才讀對應檔案，不要預先全讀）

| 情境 | 讀這份 |
|------|--------|
| 不知道用哪個 skill / 查觸發詞 | `skills/llms.txt` |
| 該載入哪些語言 / 框架 rules | `coding-workflow-core.md` Phase 0（常駐已含，照表偵測）|
| 要委派 subagent / 選 model | `governance/model-orchestration.md` |
| 判斷完成了沒 / 該不該升級 / 方向對不對 / 該不該問人 | `governance/judgment-rubrics.md` |
| 要寫派工 prompt | `governance/delegation-templates.md` |
| 網路搜尋 / 掃大檔 / 交叉驗證（agy）| `skills/engineering/gemini-assist.md` |
| 卡關 / 跨檔案 / 高風險 / 易 scope creep 的實作 | `skills/engineering/tech-lead-mode.md` |
| 要修改 CLAUDE.md 或 governance/ 制度檔 | `governance/maintenance-protocol.md` |
| 想了解制度設計的原因 | `governance/harness-diagnosis.md` |

---

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 先給極短摘要，再給可執行內容
- 指出邏輯漏洞，不為友善而同意
- 涉及數字與風險時先看基率
