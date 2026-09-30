---
name: tw-market-rotation
description: |
  台股大盤量能狀態（充足／普通／不足）+ 類股 RRG 近似象限與成交比重變化，寫入契約表供 tw-stock-tracker 記錄背景欄位（不影響評分）。所有數字由 script 計算。與 tw-stock-tracker 的界線是大盤／類股層 vs 個股層。 觸發：大盤量能、量能夠不夠、類股輪動、資金輪動、板塊輪替、哪個類股在走強、資金流向哪裡、市場寬度
metadata:
  trigger: 台股大盤量能／類股資金輪動／板塊輪替
  version: "1.0"
  last_updated: "2026-09-30"
---

# 台股大盤量能與類股輪動

> **這個 skill 不提供投資建議。** 它只描述大盤與類股的量能、相對強弱狀態。
> 個股評分走 `skills/investing/tw-stock-tracker/SKILL.md`；
> 投資觀念（輪動策略的證據、行為偏誤）走 `skills/learning/mentor-invest/SKILL.md`。

---

## 職責切分（不可違反）

| 誰做 | 做什麼 |
|------|--------|
| **Script（確定性）** | 抓資料、量能比、寬度、大盤狀態、RS-Ratio、RS-Momentum、象限、成交比重變化 |
| **LLM（你）** | 解讀報告、指出哪些類股資金流入／流出、提醒證據強度與門檻未校準 |

**LLM 絕不自行生成任何量能比、象限或比重數字。** script 失敗或資料不足 → 據實回報，不補數字。

---

## 環境

- 資料庫：`~/.stock-tracker/tracker.db`（與 tw-stock-tracker 共用，可用 `STOCK_TRACKER_DB` 覆寫）
- 相依：Python 3 標準庫，無需 pip 安裝
- 資料源：TWSE 盤後開放資料，免金鑰（MI_INDEX、BFIAMU、t187ap03_L）

執行目錄一律為本 skill 的 `scripts/`。

---

## 使用流程

```bash
cd skills/investing/tw-market-rotation/scripts
python3 rotation.py sync            # 增量回補（預設保有 60 個交易日）＋重算
python3 rotation.py report          # 最新交易日報告
python3 rotation.py report --date 2026-09-15
```

**首次執行**：需回補約 60 個交易日，每日 2 次請求、間隔 3 秒，約 6–7 分鐘。先告知使用者。
之後每次 sync 只抓新日期。

**呈現報告時**：
1. 先講大盤狀態（量能比、寬度），再講類股
2. 類股依象限分組：Leading／Improving 的資金流入（比重變化為正）最值得注意
3. 使用者接著問個股 → 指出該股所屬類股的象限，再交給 tw-stock-tracker 評分

---

## 與 tw-stock-tracker 的整合

本 skill 寫入的契約表（`market_context`、`sector_context`、`stock_industry`）
會在 tracker `record` 時被讀成背景欄位 `market_state`、`sector_quadrant`，
並在 `track.py report` 依這兩欄分組統計命中率。

**背景欄位不影響六維評分。** 要讓它參與評分，必須先有對帳樣本證明組間命中率有穩定差距。
想讓個股預測帶上背景欄位 → 先跑本 skill 的 `sync`，再跑 tracker 的 `record`。

---

## 已知限制

1. **盤後資料**：非盤中即時；當日資料約收盤後才公布，太早跑會缺今天。
2. **門檻未校準**：大盤狀態門檻是暫定值，見 `references/method.md`。
3. **RRG 是近似**：數值與商業版本（StockCharts）不同，只看象限語意。
4. **證據強度**：產業動能有學術支持；景氣循環輪替證據弱，本版不納入總經指標。
5. **母類股排除**：電子工業、化學生技醫療等綜合類股不進排名（避免重複計算）。

公式與門檻細節見 `references/method.md`。
