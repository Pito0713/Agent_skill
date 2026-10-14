# 輸出格式

固定格式的目的是**讓每次分析可橫向比較**，也是 track record 能結構化落檔的前提。
所有數字直接取自 script 輸出，不得改寫、不得四捨五入到更粗的精度。

---

## 模式 1：分析（決策看板）

```
## <代號> <名稱>　資料基準日 <date>（TWSE 盤後）

現價 <close>　|　綜合評分 <final_score>/100　→　<signal>

### 六維分項
| 維度 | 得分 | 滿分 | 關鍵數值 |
|------|------|------|---------|
| 趨勢 | x | 25 | MA5/MA20/MA60 |
| 乖離 | x | 20 | bias20 = x% |
| 支撐 | x | 15 | 60日低/高 |
| 量能 | x | 15 | 量比 x |
| MACD | x | 15 | DIF/DEA |
| RSI  | x | 10 | RSI14 = x |

### 價位（規則推導）
- 進場區間：<entry_low> ~ <entry_high>（<entry_status>）
- 停損：<stop_loss>

### 硬規則觸發
<逐條列出；無則寫「無」>

### 判斷摘要（thesis）
<你撰寫，見 analysis-template.md>

---
⚠️ 盤後資料，非即時報價。本內容為技術面狀態描述，非投資建議。
<若 flags 含 has_unadjusted_exdiv，此處加註歷史除權息未還原的影響>
```

---

## 模式 2：對帳 + 再次分析

先呈現**上次判斷的兌現檢討**，再接新的決策看板：

```
## 上次判斷回顧（<created_at>，horizon <n> 天）
- 當時評分 <score> → <signal>，進場區間 <entry_low>~<entry_high>
- 當時論點：<thesis>
- 實際結果：<resolve_date> 收 <close_at_resolve>，報酬 <return_pct>%，命中 <hit>
- 兌現檢討：<逐條檢視當時論點成立與否——這是質性判斷，你來寫>

> n=1 不能得出準確率結論。整體校準度請跑 `track.py report`。
```

---

## 模式 3：報告

直接呈現 `track.py report` 的原始輸出，再補一段解讀。

**解讀時必須遵守**：
- 樣本 < 30 → 開頭就講清楚統計上不具意義，不下「你很準／不準」的結論
- 重點放在**校準度**（高分區是否真的比較準），不是整體命中率
- 各維度預測力長期為負 → 提出調降該維度權重的具體建議

---

## 模式 6：個股詳情

```
## <代號> <名稱>　個股詳情（資料基準日 <price.date>）

資料更新於 <refreshed.at><若 failed_steps 有值：｜本次未更新：<failed_steps>>

### 價量與技術面
- 收盤 <close>｜還原報酬 1日 <1d>%｜5日 <5d>%｜20日 <20d>%｜60日 <60d>%
- 技術評分 <final_score>/100 → <signal>（狀態描述，非選股訊號）
- 估值：本益比 <pe>（近 3 年第 <pe_percentile> 百分位）｜淨值比 <pb>｜殖利率 <dividend_yield>%

### 三大法人（張）
| 區間 | 外資 | 投信 | 自營商 | 合計 |

### 月營收（千元）
- <latest.month>：<revenue>，年增 <yoy_pct>%、月增 <mom_pct>%、累計年增 <cum_yoy_pct>%
- 近 13 個月年增趨勢：<逐月列出或摘要>；公司備註：<note 原文>

### 財報 <period>（年初至該季累計）
- EPS <eps_cumulative> 元｜單季（近似）<eps_quarter_approx 或「尚未累積」>｜去年同期累計 <… 或「尚未累積」>
- 營業利益率 <operating_margin_pct>%｜稅後淨利率 <net_margin_pct>%

### 法說會與前瞻指引
- <date>：<summary 原文>（簡報：<slides_zh>）
<只引用擇要原文；擇要沒有的展望數字寫「請見簡報」>

### 近期新聞（<n> 則，Google News）
- <published> <source>：<title>（<link>）
<你寫：2–4 句摘要主要話題，不推論股價方向>

### 缺漏
<逐條列出 missing；無則省略本段>

---
⚠️ 盤後資料；基本面只顯示、不參與評分；新聞為第三方標題彙整。本內容非投資建議。
```

