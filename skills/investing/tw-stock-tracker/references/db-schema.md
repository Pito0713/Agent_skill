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
| stock_ratio | 每股配股數（TWSE 原始值即為每股，如配股 0.5 元 = 0.05） |
| sub_ratio, sub_price | 每股現金增資認購股數、每股認購價。認購價「尚未公告」時整筆不寫入，維持金額未知標記 |
| ref_ratio | 官方「參考價 / 前收」。有值時 `rebuild_adj_close` 直接累乘它，不用本地上一根收盤反算（本地日線有缺口時兩者會對不上）。目前只有 `TWT49U` 會填 |
| source | `TWT48U_ALL`（預告表，分項金額）／`TWT49U`（上市歷史計算結果，由參考價反推，只填 cash）／`TPEX_IMPLIED`（上櫃，由漲跌欄反推） |

還原用參考價 = (前收 − cash + sub_price × sub_ratio) / (1 + stock_ratio + sub_ratio)，出自 TWSE 除權除息參考價試算頁（`announcement/ex-right/cal.html`）的 JS。

**涵蓋範圍**：TWT48U_ALL 是**預告表**，只有滾動未來約 5 週的事件。
更早的上市除權息日由 `TWT49U` 補：`sync_ticker` 發現金額未知的日子時，以一次請求查該日期區間的
全市場計算結果，存 `ref_ratio = 參考價 / 前收`（`cash` 欄存差額僅供閱讀，`fetch_exright.py`）。
差額為 0 的事件也存（ref_ratio = 1），否則會被永遠當成金額未知、每次同步重查。
寫入用 `INSERT OR IGNORE`，不覆蓋預告表已有的分項金額。兩表都沒有的事件（如減資）維持未知。

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
| market_state | 資料基準日的大盤量能狀態：充足／普通／不足 |
| sector_quadrant | 資料基準日該股所屬類股的 RRG 近似象限：Leading／Weakening／Lagging／Improving |

`market_state` / `sector_quadrant` 來源：tw-market-rotation 寫入的契約表
（`market_context`、`sector_context` JOIN `stock_industry`）。
未安裝或未跑 `rotation.py sync` 時為 NULL，record 照常成功。
**僅供 `report` 分組校準，不影響評分**——要讓它參與評分，須先有對帳樣本證明組間命中率差異。
舊 DB 於 `db.connect()` 時以 `ALTER TABLE` 冪等補欄位，既有資料不變。

`calibration_id`：建立該筆預測時採用的 `calibrations.id`；NULL 代表當時用預設門檻。
`report` 依此分版本顯示命中率，用來比較校準前後。

### status 語意

| 值 | 意義 |
|----|------|
| open | 尚未到期 |
| resolved | 已對帳，計入統計 |
| needs_review | 持有期間跨到「金額未知的除權息日」，報酬無法正確計算，**不計入統計** |
| voided | 人工作廢 |

---

## calibrations — 訊號門檻版本

只有 `track.py calibrate --apply` 且驗證通過時才寫入一筆；`score.py` 讀 `adopted = 1` 的最新一筆。

| 欄位 | 說明 |
|------|------|
| created_at | 執行校準的日期 |
| bull_threshold / bear_threshold | 分數 ≥ bull 為偏多、< bear 為偏空 |
| train_n / valid_n | 前段（剔除重疊後）與後段筆數 |
| train_metric / valid_metric | 前段、後段的平均方向報酬 % |
| baseline_metric | 後段「全判偏多」的平均報酬 % |
| current_metric | 後段沿用舊門檻的平均方向報酬 %；舊門檻在後段無方向預測時 NULL |
| adopted | 1 = 使用者核准 |

---

## backtest_runs / backtest_samples — 歷史重演回測

`backtest.py run` 每次新增一筆 run；`report` 預設讀最新一筆。**與 predictions 完全分開**，
不計入 track record、不餵 calibrate。

| backtest_runs 欄位 | 說明 |
|------|------|
| start_date / end_date | 評估日範圍 |
| tickers | JSON array，預設為 DB 中已有日線的全部標的 |
| params | JSON：years、horizons、報告分組用的偏多／偏空門檻（評分本身用各評估日當時已核准的門檻） |
| status | `running` / `complete`；`report` 預設只讀最新一筆 complete |
| skipped | JSON：抓取或評分失敗而略過的標的與原因 |

| backtest_samples 欄位 | 說明 |
|------|------|
| run_id, ticker, as_of, horizon_days | 主鍵。as_of = 每 ISO 週最後一個交易日，評分只讀此日（含）以前的日線 |
| score / s_* / signal / hard_rules | 同 predictions 口徑 |
| end_date | 對帳日線：as_of + horizon 天後第一根，同 `track.py reconcile` |
| return_pct | 還原價報酬 %；被排除時 NULL |
| excluded_reason | `unknown_exdiv_in_window`（持有期間有金額未知的除權息）／`unknown_exdiv_in_lookback`（評分用的序列有）／`no_quote_near_due`（到期後 7 天內無日線，如長期停牌或資料缺口）；NULL = 計入統計 |

為何評分用的還原價含「日後才發生的除息」也不算偷看未來：往回還原是把整段序列乘上同一比例，
評分用到的都是比值（均線相對位置、乖離 %、RSI、MACD 正負號、距支撐 %），不受影響。
