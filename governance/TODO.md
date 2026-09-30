# TODO — 待辦與暫緩項目

> 記錄「已知但決定先不做」與「已知缺陷待修」。做完就刪除該項，不留已完成紀錄（歷史查 git log）。
> 格式：`## 標題` + 狀態 / 背景 / 待辦 / 決策者與日期。

---

> 2026-09-14 重新開項：逐條實勘 2026-08-08～08-25 各份 handoff 的「待處理」與 `plans/`，
> 以下 5 項為現況仍成立者。處理順序照編號。第 1、2 項已於 2026-09-30 修畢移除（見 git log）；第 6 項為修第 1 項時新發現。

## 3. skill-usage 計劃書 Phase 2（自我修正機制）gate 未裁決

- **狀態**：🟡 待使用者裁決
- **背景**：`plans/skill-usage-and-self-correction.md` Phase 2 = feedback 事件 log + 週檢 skill。
  決策 gate 原定最早 2026-08-22，已過期未談；2026-08-08 提出的接線方案（改三份索引檔鐵律 vs 只改
  `coding-workflow-core`，當時建議後者）未獲回覆。另：計劃書標頭狀態仍寫「待使用者核准後實作」，
  但 Phase 1 已於 2026-08-08 完成，標頭過時
- **待辦**：使用者決定做或不做 Phase 2；無論結果，同步計劃書標頭狀態
- **決策者與日期**：使用者，2026-09-14

## 4. `plans/token-budget-optimization.md` 歸檔或刪除

- **狀態**：🟡 待使用者裁決
- **背景**：計劃書全部目標已於 2026-08-07～08-10 完成（見其標頭），§7 明訂去留由使用者決定，2026-08-10 起懸置
- **待辦**：使用者裁決歸檔（移位置）或刪除
- **決策者與日期**：使用者，2026-09-14

## 5. token-budget waiver 理由文字過時

- **狀態**：待處理（小改）
- **背景**：4 個 `mentor-*` 共用的 waiver 寫「六個 mentor 系 skill 互相競爭路由」，ADR-025 停用
  `mentor-society` / `academic-mentor` 後只剩 4 個 mentor。理由本身仍成立，只是數字錯。
  同一字串出現在 `skills/index.json`（4 處）、`bin/test-token-budget.sh:74`、baseline JSON。
  同源漂移：`skills/learning/_shared/mentor-protocol.md` 第 8 / 206 / 257 行仍寫「新增第六個 mentor」
- **待辦**：修改 waiver 屬 §8 🟡（只有使用者能核准），需使用者同意措辭；改後同步測試常數與 baseline 引用；
  mentor-protocol 的「第六個」屬事實錯誤，順手修
- **決策者與日期**：使用者，2026-09-14

## 6. tw-stock-tracker 還原價未納入現金增資

- **狀態**：待處理（低優先）
- **背景**：2026-09-30 修第 1 項時發現，`fetch_twse.rebuild_adj_close` 只用現金股利與配股率算參考價，
  TWT48U_ALL 的 `SubscriptionRatio` / `SubscriptionPricePerShare`（現金增資認購）被忽略。
  實例：2614 東森 2026-10-06 權息同時有增資 0.38195352 股 @ 12.8 元。除權參考價公式應含認購項，
  漏掉會讓該日之前的還原價偏差；不會報錯
- **待辦**：確認 TWSE 除權參考價公式（含認購）後改 `rebuild_adj_close` 與 dividends schema，附離線測試
- **決策者與日期**：使用者，2026-09-30

---

2026-08-07 清空：原有 5 項（交接檔並發控制 Phase A–C、hook 部署狀態腳本化、Codex
discovery root 遷移、Codex/agy 常駐強制力不對等、inject 殘留偵測後續）皆為 2026-07
至 08-04 期間累積的舊議題，與當前版本已有落差，由使用者決定整批撤除而非逐項評估。

**要找回任何一項**：`git log -p -- governance/TODO.md`，或直接看清空前的最後一版
`git show <本次 commit>^:governance/TODO.md`。這些項目的背景、五漏洞分析、Phase A–E
拆解、基率評估都完整保存在 git 歷史裡，需要時原文取回即可，不必重新推導。

**日後要重新開項**：不要從 git 歷史整段複製回來——那些描述寫於當時的版本假設，
其中至少三項（pre-commit 安裝數、下游專案清單、Codex 版本行為）當時就已被實測推翻
過一次。要做先重新實勘現況，再寫新的項目。
