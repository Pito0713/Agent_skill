# TODO — 待辦與暫緩項目

> 記錄「已知但決定先不做」與「已知缺陷待修」。做完就刪除該項，不留已完成紀錄（歷史查 git log）。
> 格式：`## 標題` + 狀態 / 背景 / 待辦 / 決策者與日期。

---

> 2026-09-14 重新開項：逐條實勘 2026-08-08～08-25 各份 handoff 的「待處理」與 `plans/`，
> 以下 5 項為現況仍成立者。處理順序照編號。

## 1. tw-stock-tracker 的 script 輸入驗證未掃

- **狀態**：⚠️ 待處理（唯一可能是真 bug 的項目）
- **背景**：2026-08-17 修 cooking-flow `scale.py` 時，11 條發現裡 8 條屬同一性質——**靜默給出看似合理的錯數字**
  （NaN 繞過 `<= 0` 檢查、負數通過、缺鍵整筆消失、未知單位降級）。tw-stock-tracker 用同一套
  「script 算數字、LLM 不心算」切分，但那條規約只保證數字來自 script，不保證 script 的輸入驗證是對的。
  該 skill 自 `f1ad25a` 後無任何 commit 碰過
- **待辦**：對照 cooking-flow `scale.py` 的 `validate_ingredient()` / `is_finite_number()` 兩道防線，掃 tw-stock-tracker 的 script
- **決策者與日期**：使用者，2026-09-14 指示依序處理

## 2. `token-budget --strict` 未掛進 pre-commit

- **狀態**：待處理
- **背景**：`maintenance-protocol.md` §8.6 寫 `--strict` 是給 pre-commit 與 CI 用的，但 `hooks/pre-commit-audit.sh`
  內沒有呼叫它（2026-08-10 handoff 已記，至今未做），目前靠人記得跑
- **待辦**：評估掛載方式（fail-open / 只在 skill 或 frontmatter 有變更時跑）後動 `hooks/pre-commit-audit.sh`
- **決策者與日期**：使用者，2026-09-14

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
