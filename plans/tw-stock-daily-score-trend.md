# 計劃書：tw-stock-tracker 每日評分 + 分數趨勢 + 趨勢假設驗證

> **性質**：一次性執行工單，非制度檔
> **建立**：2026-10-22（在無資料的副機擬定，交由**資料主機**上的 agent session 執行）
> **發起人**：使用者（wits）· **執行方式**：tech-lead-mode（使用者已選定）
> **基準 commit**：`bf05a24`
> **狀態**：T1 草稿完成、**尚未凍結**；T2–T5 未開工

---

## 0. 需求與使用者裁決

**原始需求**：「可以每天評分然後提供給我評分趨勢，用以比較是否可以進場投資。」

使用者已裁決（2026-10-22）：

| 問題 | 裁決 |
|------|------|
| 比較方式 | **兩種都要**：同一檔看自己的分數趨勢 + 觀察清單橫向排行 |
| 觀察清單來源 | **自動**：曾查過的都算（predictions ∪ detail_views ∪ positions 的代號聯集），清單持續累進 |
| 趨勢假設驗證 | **一起做**：先預先登錄、凍結，再跑回測 |
| 評分規則 | `score.py` 計分邏輯**不改**；本計劃只新增每日快照與趨勢呈現 |

**必須維持的定位**：回測已證明單日總分無預測力（ADR-026、ADR-029）。趨勢與排行在 T5 驗證通過前，
所有輸出（CLI、儀表板）一律標示「未驗證」，且不得用「買入／賣出」字眼。

---

## 1. 執行順序（硬性）

```
T1 凍結 → T2 每日評分核心 → T3 儀表板 → T4 文件 → T5 跑驗證 → ADR-030
```

**T1 凍結前，T2–T5 一律不動工**：先看到趨勢圖再定義假設，會依圖挑定義（p-hacking）。
T5 可在 T2 之後的任何時點跑（只依賴 `backtest.py`，不依賴 T2–T4），但不得早於 T1 凍結。

---

## 2. 工單

### T1：預先登錄凍結（orchestrator 親自處理，不委派）

- 草稿：`skills/investing/tw-stock-tracker/references/preregistration-20261022-score-trend.md`（已寫好）
- 動作：把草稿 §3–§5 的關鍵設定摘要給使用者，**等使用者明確回覆「凍結」**
- 凍結後：狀態行改為「已凍結（<日期> 使用者確認）」→ 單獨 commit。之後本檔除附錄外不得修改
- 使用者要求修改 → 改完重新請使用者確認，**凍結前不得計算任何 Δ分數 IC**

### T2：每日評分核心（executor：subagent + worktree）

- **範圍**：`scripts/db.py`（只新增 `daily_scores` 表）、新增 `scripts/daily_score.py`、
  新增 `tests/test_daily_score.py`、`scripts/scheduled_update.sh`（加一步 `run_step daily_score.py run`）
- **禁區**：`score.py` 計分邏輯、`backtest*.py`、`track.py`、`references/` 全部
- **設計要點**：
  - `daily_scores`：ticker、date、score、六個 `s_*`、signal、hard_rules、`source`（`live`｜`backfill`）、computed_at；
    PK (ticker, date)
  - 子指令：`run`（抓日線 → 評今天 → upsert）、`backfill --days N`（用 `score.evaluate(conn, ticker, as_of)` 回補）、
    `trend <代號> [--days 60]`（總分與分項逐日變化）、`rank`（清單今日分數、5 日 Δ、20 日 Δ）
  - **為什麼要存快照、不全靠事後重算**：`adj_close` 會被日後除權息往回調整，校準門檻也可能變；
    事後重算的分數會與當天實際看到的不同。live 值以當天算出為準，不被 backfill 覆蓋
  - 現有排程（`scheduled_update.sh`）**不抓日線也不評分**，`run` 必須自己呼叫抓取（沿用 `fetch_twse.py` 的抓取函式）
- **驗收**：
  - [ ] 四個子指令實跑成功，貼輸出
  - [ ] 同日重跑不產生重複列；backfill 不覆蓋既有 live 列
  - [ ] 日線不足 60 根 → 略過並記錄原因，不寫半套分數
  - [ ] 新測試含 happy path、資料不足、重跑冪等；**既有測試全數通過**（貼 `python3 -m pytest tests/` 輸出）
  - [ ] 函式 ≤ 50 行、檔案 ≤ 300 行
  - [ ] 每次 `run` 在 log 記錄清單檔數（清單會持續變長，先觀察不設上限）

### T3：儀表板（executor：subagent + worktree，T2 CLOSE 後才派）

- **範圍**：`dashboard_data.py`、`dashboard_views.py`、`dashboard_detail.py`、`tests/test_dashboard.py`
- **禁區**：`dashboard.py` 的安全設定（只綁 127.0.0.1、唯讀 DB、只回應 GET）、T2 的檔案
- **驗收**：
  - [ ] 主頁新增「評分排行」卡片（今日分數、5 日 Δ、20 日 Δ）
  - [ ] 個股頁新增分數趨勢 inline SVG；backfill 值與 live 值樣式可區分
  - [ ] 兩處都有「未驗證」標示
  - [ ] 儀表板測試全數通過；`curl` `/` 與 `/stock/<代號>` 輸出含新卡片（貼輸出）

### T4：文件（orchestrator 或 executor 皆可）

- **範圍**：`SKILL.md`（新增「每日評分／趨勢」模式、觸發詞、指令）、`references/scoring-rubric.md`（定位說明）
- **驗收**：「未驗證」定位、5 日 Δ 不在驗證範圍、與 T1 判定標準文字一致；若改 SKILL.md frontmatter 觸發詞，
  依 `governance/maintenance-protocol.md` 同步索引並跑 §7 四查

### T5：跑驗證（資料主機，執行前再向使用者確認一次）

- 依預先登錄 §4 抽樣：排除清單**讀資料主機 `backtest_runs` 中 run 1、2、4 的 `tickers` 欄位**
  （副機 DB 無任何回測紀錄，清單只能在主機產生）
- 抽樣清單附到預先登錄檔末尾 → 單獨 commit → `python3 backtest.py run --years 3 --tickers <清單>`
  （預估 2 小時以上，會打 TWSE／TPEx API）
- 依 §3、§5 計算；分析 script 放 scratchpad，不進 repo
- 結果寫入 `scoring-rubric.md` 回測證據段 + `memory/project-context.md` ADR-030，**未通過也要記**
- 通過 → 另開窄工單移除「20 日 Δ」與排行的「未驗證」標示；不改總分與權重

---

## 3. Reviewer 與 Close Gate

- T2、T3 動到排程與 DB schema（既有自動化流程）→ **預設啟用 codex 對抗審查**（`cli-delegate` 模式 C，
  記得帶 `-c project_doc_max_bytes=0`）
- Close Gate 讀 diff 本身：`git diff --name-only` 比對範圍與禁區、驗收逐條附證據、測試貼實際輸出
- 結果只能 CLOSE／REOPEN（窄工單）／ESCALATE 三選一

---

## 4. 已知風險

| 風險 | 處置 |
|------|------|
| Δ分數與近 4 週價格動能高度相關，可能只是在重測短期動能／反轉 | 已在預先登錄 §2 揭露；判讀時對照 run 1、2、4 乖離分項 |
| 回測週樣本的 4 週 Δ ≠ 每日的 20 個交易日 Δ | 預先登錄 §6 已列為限制 |
| 觀察清單自動累進，每日抓取時間隨之增加 | T2 記錄清單檔數，之後再決定是否設上限 |
| 回補值有除權息回溯調整誤差 | `source` 欄區分，儀表板樣式區分 |
