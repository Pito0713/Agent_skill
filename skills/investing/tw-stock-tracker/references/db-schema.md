# 資料庫結構

**位置**：`~/.stock-tracker/tracker.db`（SQLite，可用 `STOCK_TRACKER_DB` 環境變數覆寫）

**為何不放本 repo**：predictions 是個人交易判斷資料且持續增長，
本 repo 是三 harness 共用的制度正本，不該被個人資料污染。

正本定義在 `scripts/db.py` 的 `SCHEMA`。

---

## daily_quotes — TWSE 日線快取

| 欄位 | 說明 |
|------|------|
| ticker, date | 主鍵。date 為 ISO `yyyy-mm-dd` |
| open/high/low/close | 原始價（未還原） |
| volume | 成交股數 |
| is_exdiv | 1 = 該日除權息。來源：STOCK_DAY 漲跌價差欄位的 `X` 前綴 |
| adj_close | 還原收盤價。配息金額未知時等於 close（不猜數字） |

快取的用意：抓過不重抓、對帳快，且**未來要做真正的策略回測時資料已就位**。

---

## dividends — 除權息事件

| 欄位 | 說明 |
|------|------|
| ticker, ex_date | 主鍵 |
| cash | 每股現金股利 |
| stock_ratio | 每股配股數（TWSE 原始值為每千股，已除以 1000） |
| source | 目前恆為 `TWT48U_ALL` |

**涵蓋範圍限制**：TWT48U_ALL 是**預告表**，只有滾動未來約 5 週的事件。
更早的除息日偵測得到但金額查不到。

> 曾評估用 `t187ap45_L`（股利分派情形）補歷史金額，**放棄**：
> 該表有金額但無除息日，配對只能靠時序推測；
> 原本設計的「用當日價格區間驗證」實測無效——台股除息日漲跌幅仍達 ±10%，
> 配息 4.5 或 7.5 元算出的參考價全都落在合理區間內，無法辨別。
> 猜配對會默默寫入錯誤數字，違反「數字必須真實」的紅線，故不採用。

---

## predictions — 判斷記錄

| 欄位 | 說明 |
|------|------|
| created_at | 資料基準日（最後一根日線的日期），非執行日 |
| horizon_days | 時間框架，決定何時對帳 |
| close_at_pred / adj_close_at_pred | 判斷當時的真實價 |
| score | 硬規則壓制後的最終分數 |
| s_trend / s_bias / s_support / s_volume / s_macd / s_rsi | **六維分項**。事後檢驗各維度預測力、校準權重的依據 |
| signal | 強烈偏多／偏多／中性／偏空／強烈偏空 |
| entry_low / entry_high / stop_loss | 規則推導價位 |
| hard_rules / flags | JSON array |
| thesis | **唯一由 LLM 寫入的欄位** |
| status | open / resolved / voided / needs_review |
| resolve_date / close_at_resolve / adj_close_at_resolve | 對帳結果 |
| return_pct | `(還原結算價 / 還原進場價 − 1) × 100` |
| hit | 1/0；中性訊號留 NULL，不計入命中率 |

### status 語意

| 值 | 意義 |
|----|------|
| open | 尚未到期 |
| resolved | 已對帳，計入統計 |
| needs_review | 持有期間跨到「金額未知的除權息日」，報酬無法正確計算，**不計入統計** |
| voided | 人工作廢 |
