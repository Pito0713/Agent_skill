# Harness 診斷報告（A）

> 日期：2026-07-03。本檔是 governance/ 全部制度檔的依據：「為什麼」寫在這裡，「怎麼做」寫在各制度檔。
> 讀者：未來每一個 session，含較小模型。修改本檔前先讀 `governance/maintenance-protocol.md`。

## 診斷方法

逐檔實測（非印象）：讀取 CLAUDE.md、四個常駐檔、skills/llms.txt、7 個 Orchestrator，以三軸排序：token 成本、失焦風險、錯誤率。

---

## 第 1 名：最漏 token — 常駐載入過重 + 同一份索引存三處

**症狀（實測數字）**
- 常駐載入共 901 行：CLAUDE.md 133 + coding-standards 127 + security 201 + coding-workflow-core 98 + gemini-assist 342。
- `gemini-assist.md` 一檔佔常駐量 38%，但只有「搜尋 / 掃大檔 / 交叉驗證」時才用得到，多數 session 整份白載。
- 舊版 CLAUDE.md 含 23 列按需載入表 + 完整歧義範例表，與 `skills/llms.txt`、README 目錄樹三處重複。三處會漂移，漂移後弱模型不知道信哪份。

**修法（已於 2026-07-03 執行）**
1. CLAUDE.md 重寫為精簡路由（約 50 行），按需內容一律指向單一事實來源。
2. `gemini-assist.md` 從常駐降為按需（觸發詞在 llms.txt：「幫我搜尋」「掃一下整個專案」「交叉驗證」）。
3. 單一事實來源原則：
   - skill 路由 → 只維護 `skills/llms.txt`
   - rules 自動偵測 → 只維護 `coding-workflow-core.md` Phase 0
   - CLAUDE.md 永遠只放指標，不放內容
4. 同步負擔歸零規則：新增 skill 只改 llms.txt，禁止往 CLAUDE.md 加列（見 maintenance-protocol）。

---

## 第 2 名：最容易失焦 — 長鏈 Orchestrator 沒有外部錨點

**症狀**
- Orchestrator 鏈可以很長（new-feature → api-architect → backend-engineer → testing-strategy → test-engineer → documentation → version-log；其中 api-architect 等是 `agents/` 目錄下的 prompt 定義檔，不是 harness subagent 類型）。弱模型走到中段會忘記初始需求，開始「看起來很忙但不收斂」。
- 「回應前先讀 rules/」這類開放式指令會誘發讀檔迴圈：讀檔 → 看到新名詞 → 再讀檔，永遠不動手。
- 「完成」的定義存在模型腦中而非檔案裡，context 一長就漂移。

**修法**
1. 錨點外置：每個 Phase 的輸出第一行必須複述原始目標（一句話），不靠模型記憶。
2. 讀檔上限：連續讀超過 5 個檔案還沒輸出計畫 → 強制停下，先輸出目前理解 + 計畫草稿。
3. 符合「>3 檔案 / 曾卡關 / 高風險 / 易 scope creep」任一 → 走 `skills/engineering/tech-lead-mode.md`：done definition 寫在工單裡，close gate 讀 diff 不讀報告。
4. 委派一律帶「派工三件套」（目標與動機 / 驗收條件 / 回報格式），見 `governance/model-orchestration.md` 第 3 節。

---

## 第 3 名：最容易出錯 — 自我驗證 + 抽象判準

**症狀**
- Executor 自己宣稱完成（「測試應該會過」）；自己寫的 code 自己審，盲點重疊。
- 規則中的抽象判準（「高品質」「嚴重度 CRITICAL/HIGH/MEDIUM/LOW」）超出弱模型判斷力，結果是編造假問題、或對真問題視而不見。

**修法**
1. 驗證不自驗：檔案落地用 fresh-context read-back；程式碼用測試或實跑（貼輸出）；高風險判斷加第二意見（agy 或冷啟動 subagent）。細則見 `governance/model-orchestration.md` 第 7 節。
2. 抽象判準拆成二元 checklist：不問「品質好嗎」，問「tsc --noEmit 過了嗎（是/否）」。完整 rubric 見 `governance/judgment-rubrics.md` R5。
3. 完成與否由 close gate 判定（讀 diff + 證據），不由 executor 宣告。

---

## 誠實標註：本診斷的極限

- 以上修法補的是「執行品質」。模糊題（產品判斷、命名品味、寫作風格）拆解補不了 → 遇到時升級模型或問使用者，處理方式見 judgment-rubrics「誠實標註」節。
- 本 harness 無法逐次指定 subagent 的 reasoning effort（effort 由 `.claude/agents/*.md` 定義檔控制，本專案目前無自訂定義檔）；model 可以逐次指定（haiku / sonnet / opus / fable）。
- 環境實測（2026-07-03）：agy 在 PATH 可用（`/Users/wits/.local/bin/agy`）；gemini CLI 已不存在（勿再寫進流程）。
