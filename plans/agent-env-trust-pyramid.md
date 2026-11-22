# 計劃書：參照 inverse trust pyramid 把規則從文字下沉到環境

> **性質**：一次性執行工單，非制度檔
> **建立**：2026-11-20
> **發起人**：使用者（wits）
> **基準 commit**：`04ad83e`（main，工作區乾淨）
> **狀態**：T1 完成（`feeb3e7`）、T2 完成（2026-11-20）、T3 完成（2026-11-20）；T4–T6 未開工
> **參照來源**：Lauren Tan（poteto, SpaceXSI）〈All Code Is Slop (Except Mine)〉AI Engineer CODE 2026、pstack。觀念取自二手筆記，未看原影片

---

## 0. 需求與定位

**原始需求**：依 Lauren Tan 的 agent 開發觀念，找出本制度可以參照修改的地方。

**借用的三個觀念**（只借這三個，其餘不搬）：

1. **修正順序**：agent 犯錯 → 先改架構 → 再加 lint / test / script → 最後才寫 rule / skill
2. **完成要有看得到的結果**：agent 自己跑起來、走真實流程、交證據
3. **gardening**：定期掃出「可以變成檢查」的文字規則，把它下沉

**明確不搬**：

- outer loop 全自動化（connector 收件 → agent 自修）：規模不符，現行「線索給人看」維持
- 「99% 禁註解」：只借其中可 regex 判定的一小塊（見 T5）
- 刪除 L1 文字正本：`enforcement-layers.md` §1 鐵則（三 harness 共用底線）不變

---

## 1. 現況實勘（2026-11-20）

| 項目 | 實況 | 與觀念的落差 |
|------|------|-------------|
| `enforcement-layers.md` §3 | 已有「機械可判定 → L2」三題分工判準 | 只用在**新規則**，沒接到「犯錯後怎麼修」 |
| `lessons.md` | **41 條**、390 行 | 已超過 §4 精簡門檻（30 條 / 300 行）卻未觸發歸納；全部是文字 |
| `maintenance-protocol.md` §3 教訓格式 | 情境 / 錯誤 / 修正 / 規則 | 無「能否下沉」欄，預設產出就是文字 |
| `bin/skill-health-review.md` B2 | 檢查「教訓是否**寫回 skill**」 | 方向是文字 → 文字，沒問「能否變成檢查」 |
| `coding-workflow-core` Phase 4 | 「手動測試主要 flow」 | 無證據要求，模型可口頭帶過 |
| `judgment-rubrics.md` R2 | 完成要附證據 | 已對齊，不動 |
| `hooks/pre-commit-audit.sh` | 唯一活著的自建 L2；git hook，三 harness 皆生效 | 這條路已驗證可行，可擴充 |
| `rules/coding-standards.md:106` | 允許 `TODO(name)` | 與 R2「不准延後即回報完成」有張力 |

---

## 2. 工單

### T1　修正順序寫成規則　🟡（governance/）

- **改**：`governance/enforcement-layers.md` 新增 §3b「犯錯後的修正順序」：
  架構 → script / test / lint（L2）→ cop（L3）→ 文字規則（L1）→ 人工讀 diff（最後手段）。
  每一步都要寫「為什麼上一層做不到」才能往下走。
- **改**：`governance/maintenance-protocol.md` §3 教訓格式加必填欄
  `- 下沉：架構 | script | test | cop | 不能（理由）`；§1 🟢 那列加一句「能下沉的不准只寫 lesson」
- **驗收**：read-back 兩檔；新格式拿最近 3 條真實教訓試填，至少 1 條得出「可下沉」結論（證明欄位有鑑別力，不是全填「不能」）
- **風險**：模型為了避免寫理由一律填「不能」→ T3 的 gardener 會抽查

### T2　lessons.md 精簡＋下沉盤點　🟡（刪除 lessons 條目）

- **做**：41 條逐條分類為 ① 可下沉成 script / test ② 歸納進 `judgment-rubrics.md`，或該規則被用到的那個檔案（派工 → `delegation-templates.md`、交接 → handoff skill；2026-11-20 使用者核准）③ 保留
- **產出**：分類表先給使用者裁決，**同意後**才動（§4 規約：歸納後註明來源日期）
- **不做**：本工單不實作任何下沉腳本，只產出候選清單 → 實作另開工單
- **驗收**：分類表每條附 `lessons.md:行號`；①類每條寫出具體檢查方式（regex / 指令 / 測試名）

- **執行結果（2026-11-20）**：43 條（含當日新增 2 條）→ 移除 29、保留 14；新增 R7、R8，明細見 `lessons.md` 檔頭第二張歸納表。
  ① 候選（本 repo，實作另開工單）：

  | lessons 條目 | 檢查方式 |
  |---|---|
  | 07-22 skill 改名 | validator 已擋 name／path；補「舊名仍出現在 skills/ governance/ inject.sh 活引用」檢查 |
  | 07-31 `${VAR}` | pre-commit 警告：staged `*.sh` 跑 `grep -nP '\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7F])'` |
  | 09-30 必跑沒接 gate | 抽出「必跑」後的指令，比對 hooks/ 與 `bin/test-*` 有無呼叫（啟發式，警告級） |
  | 11-09 worktree 基底 | 派工前比對 `git rev-parse main origin/main`，不一致自動補第 0 步 |
  | 11-10 快照誤報 | project-review 登記前在 scratchpad 快照實跑，不過拒絕登記 |
  | 11-20 push email | pre-push：`git log --format='%ae%n%ce' <range>` 過濾 noreply 後有輸出就警告 |

  → 已開工單：`plans/sink-candidates-t2.md`（W1–W6，2026-11-22）

  下游 2 條（10-23 hook defer、11-20 AppKit）原文保留，依使用者裁決不另開 TODO。

### T3　gardener 加一問：能否下沉　🟡（bin/ 下的審查 prompt，影響定期體檢）

- **改**：`bin/skill-health-review.md` B2 第 3 步改為三分：已寫回 / 未寫回 / **可下沉成檢查**（附建議形式）
- **驗收**：`bash bin/test-skill-health-b.sh` 通過；手動跑一次 B 層，報告中出現 B2 下沉判斷欄
- **依賴**：T1（格式定案後才知道要比對什麼）

- **執行結果（2026-11-20）**：使用者裁決改為**兩軸**（寫回軸／下沉軸互不排除——已寫回文字的教訓仍可能該下沉），不用三分。
  下沉軸依教訓「下沉」欄分三情況：填形式 → 查 `bin/` `hooks/` 有無實作；填「不能」→ 審理由；舊格式無欄 → 自判、信心上限「中」。
  `test-skill-health.sh` 153/153 通過（新增 2 條 prompt assert）。真模型 B 層跑一次（報告寫 scratchpad，未動正式報告目錄）：
  B2 出 5 條，4 條帶「建議形式」。抽查：pre-push email 未實作 ✅ 屬實；09-30「已接 gate」為誤讀（候選是通用比對檢查，非 token-budget）；
  07-31 regex 檢查被標成 `cop`，應為 `script`。另：T2 大量刪除使 diff 超過 300 行上限被截斷，模型有自行註明
- **codex 三路交叉驗證後修補（2026-11-22）**：採納 6 項——「不能」依 §3b 逐層審（含架構／cop）、≥11-20 條目缺欄或缺理由算格式違規、
  截斷時回原檔讀完整條目、實作搜全 repo、已實作須確認接上自動執行、`lint` 視同 `script`；不採納「建議形式須說明上層為何做不到」（gardener 只給線索）。
  測試 155/155。真模型二跑：有用 Read 補截斷 ✅；新抓到 `test-skill-usage.sh`／`test-skill-health.sh` 沒有任何自動執行入口（已核實）✅；
  11-20 兩條皆有下沉欄，未誤報格式違規 ✅。一跑報的 07-22／07-31／11-09 舊條目這次沒評——它們在 diff 裡不是新增行，屬模型對範圍解讀的變異

### T4　Phase 4 要求看得到的結果　🟡（常駐 skill，三 harness 每 session 載入）

- **改**：`skills/engineering/coding-workflow-core/SKILL.md` Phase 4
  `[ ] 手動測試主要 flow` → `[ ] 實際執行主要 flow（啟動 app / 跑 CLI / 打 API），貼輸出或截圖；跑不起來要明說原因，不得以「邏輯上正確」代替`
- **選做**（見 §6 Q2）：專案層 verification recipe——`~/.agent-sessions/<專案>/` 或專案內一份「怎麼驗證本專案」的檔，Phase 4 先讀它
- **驗收**：`bash bin/token-budget.sh --strict` 通過（常駐成本增量寫進 commit message，§8.4）；
  AGENTS.md / GEMINI.md inline 段若有摘要 Phase 4，跟改並跑 §7 四查

### T5　pre-commit 擴充：擋 agent 的延後註解　🟡（hook 影響所有下游）

- **改**：`hooks/pre-commit-audit.sh` 加一條**警告級**（不擋）規則：staged 新增行出現
  `TODO` / `FIXME` / `之後補` / `暫時` / `for now` → 列出提醒。觀察兩週誤報率再決定是否升為攔截
- **同步**：`rules/coding-standards.md` 註解規範補一句「agent 不得以 TODO 代替完成；要延後就開 TODO.md 項目並告知使用者」
- **為什麼選這條**：可 regex 判定、git hook 三 harness 皆生效，正好補 L2「只在 Claude Code」的缺口
- **驗收**：目前 `pre-commit-audit.sh` **沒有專屬測試**（2026-11-20 實勘），本工單一併新增 `bin/test-pre-commit-audit.sh`：
  既有路徑洩漏規則的回歸案例 + 新規則案例 ≥3（命中 / 不命中 / `audit-ok` 旁路），fixture 放 `mktemp -d` 臨時 repo
- **風險**：誤報（字串常數、文件裡的 TODO）→ 所以先警告不攔截

### T6　skill 指令抽出到 bin/　🟢→🟡（視動到哪個 skill）

- **做**：盤點各 SKILL.md 內嵌的 bash 區塊，列出「可抽成 bin/ script」候選（如 `coding-workflow-core` Phase 0 fallback）
- **產出**：候選清單給使用者，不直接改
- **驗收**：清單附檔名:行號與預估省下的 bytes（用 `bin/token-budget.sh` 量）

---

## 3. 執行順序

```
T1 ──→ T3
 └───→ T2（分類可並行，裁決後才動檔）
T4、T5、T6 互相獨立，可在 T1 後任意順序
```

建議批次：**第一批 T1 + T4**（改動小、立即見效）→ 第二批 T2 + T3 → 第三批 T5 + T6。

---

## 4. 共通規約（每張工單都適用）

- 動 governance/ 前照 `maintenance-protocol.md` §2：備份 → 修改 → read-back
- 改變行為的工單（T1、T4、T5）追加 ADR-033 到 `memory/project-context.md`
- 改 `rules/` 時檢查 AGENTS.md / GEMINI.md inline 段是否要跟改，並跑 §7 四查
- 動 skills/ 必跑 `bash bin/token-budget.sh --strict` 與 `python3 bin/validate-skill-index.py`
- 驗收由非實作者執行（read-back / 實跑測試貼輸出）

---

## 5. 不在範圍內

- 往下游專案安裝 lint preset：違反「專案規範優先」（全域鐵律 2），各專案自己的 linter 由各專案管
- 縮減常駐 `rules/coding-standards.md` 的內容：等 T5 證明下沉路徑可行、有實測誤報率後再議
- outer loop 自動修復

---

## 6. 待裁決

| # | 問題 | 建議 |
|---|------|------|
| Q1 | 是否接受整份計劃的範圍（T1–T6）？ | 是；或至少第一批 T1 + T4 |
| Q2 | T4 是否做專案層 verification recipe？放哪？ | 先不做，T4 主體上線兩週後看 Phase 4 證據品質再決定 |
| Q3 | T5 是否先警告兩週再升攔截？ | 是 |
| Q4 | T2 的 lessons 精簡是否本次就做（已超門檻）？ | 是，但只到「分類表給你裁決」為止 |
