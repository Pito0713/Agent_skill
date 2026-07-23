---
name: tech-lead-mode
description: |
  Tech Lead 執行模式，Orchestrator 不直接寫 code，改為切工單、委派 executor、仲裁 reviewer 發現、跑 close gate：
  1. 切工單（範圍/禁區/驗收條件明確寫死）
  2. 委派 executor（subagent 或 agy）依工單執行
  3. Reviewer 審查 → Orchestrator 逐條仲裁 → Close Gate 三選一（CLOSE/REOPEN/ESCALATE）

  這是掛在既有 Orchestrator（new-feature / debug-flow / coding-workflow-core）之上的執行策略切換，不是新的任務類型入口。
  觸發場景：任務預估影響超過 3 個檔案、之前已經卡過關、容易 scope creep，或使用者明確要求工單化管理。
  示例觸發：「這個改動照 tech lead 模式跑」「這個任務容易 scope creep，切工單處理」「用 orchestrator 模式，委派 executor 去做」
metadata:
  trigger: 任務易卡關 / scope creep / 需工單化管理時觸發
  version: "1.0"
  last_updated: "2026-07-07"
---

# Tech Lead Mode

> Orchestrator 的價值是判斷，不是打字。
> Executor 不決定 done，Reviewer 不決定要不要修，人類不決定 code 怎麼寫。

---

## 啟用條件

### ✅ 建議啟用（符合任一即可主動詢問使用者是否啟用）

```
- 預估影響 > 3 個檔案，或跨服務 / 跨模組
- 這個任務之前已經卡過（前次嘗試「看起來做完但沒真的做完」）
- 過去經驗顯示這類任務容易 scope creep（diff 越改越大、收不了尾）
- 使用者主動要求「tech lead 模式」
```

### ⏭ 不啟用（維持 `coding-workflow-core.md` 正常流程即可）

```
- 單一檔案、變更 < 15 行
- 需求與範圍都非常明確，過去同類任務一次就過
- 純設定調整 / typo 修正
```

**判斷不確定時，直接問使用者**：「這個任務要走 tech lead 模式（工單化 + 委派 executor + close gate）還是直接開發？」

---

## 角色定義（不可混淆）

| 角色                                      | 負責                                                                                             | 不負責                           |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------- |
| **Orchestrator**（Claude 本身）           | 切工單、定驗收條件、委派 executor、仲裁 reviewer 發現、跑 close gate、決定 close/reopen/escalate | 親自大量寫 code                  |
| **Executor**（見下方委派協定）            | 依工單執行、回報 plan + diff + 測試結果 + 剩餘風險                                               | 決定任務算不算完成、決定驗收標準 |
| **Reviewer**（`agy-assist.md` Mode C） | 挑毛病、報風險、報 edge case                                                                     | 決定要不要修、直接改 code        |
| **人類**（使用者）                        | 產品行為判斷、風險是否可接受、最終驗收                                                           | 盯每一行 diff                    |

---

## Phase 1：切工單（Ticket）

一個工單只做一件事，範圍寫死，禁區寫死。

```markdown
## Ticket: <簡短 id>

目標（一句話）：
範圍（允許修改的檔案 / 目錄）：
禁區（明確不能碰的檔案 / 目錄，即使看起來相關）：
驗收條件（必須可客觀驗證，禁止「感覺對」「應該沒問題」）：

- [ ]
- [ ]
  不允許事項：
- 不能重構範圍外的程式碼
- 不能放寬既有測試 / gate
- 不能擴大 scope（發現新問題 → 記錄成新 ticket，不在本輪處理）
  Executor：subagent（worktree）｜ agy（見 Phase 2 委派協定）
  回報格式要求：plan、diff、測試結果、剩餘風險（缺一不算完工）
```

**輸出**：工單草稿 → 等待使用者確認範圍與驗收條件後才進 Phase 2。

---

## Phase 2：委派 Executor

### Path A：harness subagent（預設，無需改動安全設定）

**委派參數依 harness 而異，發送前先對照 `governance/model-orchestration.md` 第 2 節適配表，禁止照抄非本環境的參數名。**

Claude Code 語法：

```
Agent({
  description: "<ticket 目標>",
  subagent_type: "general-purpose",
  isolation: "worktree",
  prompt: "<完整 ticket 內容，含範圍/禁區/驗收條件/回報格式要求>"
})
```

Antigravity 等價參數：`TypeName: "self"` + `Workspace: "branch"`（隔離），prompt 內容相同。其他 harness：以當前工具 schema 為準找「全工具 subagent + 隔離工作區」的等價組合。

適用：大部分情境。同模型執行，但 executor 本來就不負責判斷對錯，只照工單做，風險可控。

**派發後等待紀律**：executor 在背景執行時不要輪詢、不要用無意義工具呼叫原地等。事件驅動 harness 完成時會喚醒你（Claude Code 自動通知；Antigravity 結束回合交還控制權或用 `/schedule` 設 TimerCondition），醒來直接進 Phase 3/4。

### Path B：agy 作為 executor（需要異質模型執行時）

2026-07-07 起 agy 是完整 harness（ADR-009）：`~/.agents/settings.json` 與 `~/.gemini/settings.json` 的全域 excludeTools 已移除，agy **可直接當 executor**，不需臨時放寬流程。派工時：

- prompt 用與 Path A 相同的完整 ticket（範圍 / 禁區 / 驗收條件 / 回報格式）
- 防線在工單層：**禁區檔案清單寫死 + close gate 讀 diff 驗收**——工具權限不再是防線，工單才是
- 例外：若發現上述 settings.json 又出現 `excludeTools`（有人鎖回去），視為使用者意圖變更 → 停下來問使用者，**不得自行解鎖**（judgment-rubrics R3「安全 vs 便利」條）

---

## Phase 3：Reviewer 審查（可選，依風險等級決定）

高風險 ticket（金流、正式環境、既有 gate）預設啟用；一般 ticket 詢問使用者是否啟用。

沿用 `agy-assist.md` Mode C：

```
git diff HEAD | agy --print-timeout 9m -p "審查這個 diff，僅回報問題，不提供修改方案。
[維度：邏輯漏洞、邊界條件缺失、安全風險、是否偏離下方驗收條件]

驗收條件：<貼入 ticket 的驗收條件>

每個問題格式：
[嚴重度] 位置：描述 → 潛在影響
嚴重度：CRITICAL / HIGH / MEDIUM / LOW
無問題時輸出：「未發現問題」
繁體中文。"
```

agy 不可用時走 `agy-assist.md` 的 Claude Subagent Fallback（冷啟動審查，不可省略）。

**鐵律：Reviewer 的發現不能直接被信任，也不能被直接忽略。** 進 Phase 4 逐條查證。

---

## Phase 4：Orchestrator 仲裁

對 Reviewer 每一條發現，Orchestrator 必須逐條查證後才能採信或否決：

```
[ ] 讀實際程式碼確認發現是否成立（不是讀 reviewer 的描述就相信）
[ ] 成立 → 標記為真實問題，列入 Close Gate 的待處理項
[ ] 不成立 → 明確標記「已查證，非真實問題」+ 一句話說明為什麼
[ ] 不確定 / 涉及產品判斷（不是純技術對錯）→ ESCALATE 詢問使用者
```

**輸出格式**：

```
Reviewer 發現 N 條，查證結果：
[CONFIRMED] <描述> → 已加入 Close Gate 待處理
[REJECTED]  <描述> → 原因：<一句話>
[ESCALATE]  <描述> → 需要使用者判斷：<問題>
```

---

## Phase 5：Close Gate

**讀 diff 本身，不讀 executor 自己寫的完工報告。** 完工報告只是索引，不是證據。

```
[ ] git diff --name-only 比對 ticket 範圍/禁區 → 禁區未被觸碰，範圍未超出宣告清單
[ ] 驗收條件逐條核對，每條都要有對應的 diff 或測試結果佐證
[ ] 測試「實際執行過」，不是「應該會過」（貼出實際執行輸出，不是 executor 的口頭保證）
[ ] 若涉及服務 / 部署 → 有實際 smoke test 證據（curl 輸出 / log / 截圖）
[ ] Phase 4 的 CONFIRMED 項目已修正，且修正本身也過一次上述檢查
```

**三種結果，只能三選一：**

| 結果        | 條件                              | 動作                                                  |
| ----------- | --------------------------------- | ----------------------------------------------------- |
| ✅ CLOSE    | 全部項目通過                      | 輸出最終報告，任務結束                                |
| 🔁 REOPEN   | 有缺口但屬於技術範疇              | 開下一輪**窄工單**，只描述缺口本身，不重寫整份 ticket |
| 🔴 ESCALATE | 缺口涉及產品判斷 / 風險是否可接受 | 停止，交給使用者決定                                  |

**禁止的第四種結果**：「大致完成，剩下的之後再說」——這正是文章描述的「diff 越滾越大、沒人敢收尾」的失敗模式，Close Gate 存在的目的就是杜絕這種模糊結案。

---

## 每輪收斂（Round Loop）

```
Round N：
  Phase 1 產出/更新 ticket（首輪）或沿用（reopen）
      ↓
  Phase 2 Executor 執行 → 回報 plan + diff + 測試結果 + 剩餘風險
      ↓
  Phase 3 Reviewer 審查（可選）
      ↓
  Phase 4 Orchestrator 逐條仲裁
      ↓
  Phase 5 Close Gate
      ↓
  CLOSE ✅ 結束 / REOPEN 🔁 開 Round N+1（窄工單）/ ESCALATE 🔴 交人類
```

Round 之間不共用「記憶」，只共用 ticket 文件本身——這是刻意設計，避免 context 拉長後模型自己漂移，也讓每一輪都可以獨立驗證。

---

## 與既有 Orchestrator 的關係

本 skill 不取代 `new-feature.md` / `debug-flow.md` / `deploy-prep.md`，而是它們在進入實作 Phase 前的一個條件分支：

```
new-feature.md   Phase 3（實作計畫）完成後 → 符合啟用條件？→ 走 tech-lead-mode 取代 Phase 4（實作執行）
debug-flow.md    Phase 2（假設驗證）確認根因後 → 符合啟用條件？→ 走 tech-lead-mode 取代 Phase 3（修正）
coding-workflow-core.md  Phase 2（計畫）完成後 → 同上邏輯
```

> 已接線：`coding-workflow-core.md` Phase 2→3、`new-feature.md` Phase 3→4、`debug-flow.md` Phase 2→3 皆已加入本 mode 的判斷檢查點；`CLAUDE.md` 按需載入表與 `skills/llms.txt` 索引已收錄觸發詞。

---

## 應用場景

| 場景特徵                                                               | 對應本 mode 的機制                                                                            |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 高風險金流 / 既有 gate 的小範圍修正（例：第三方支付 fail-closed 邏輯） | 禁區檔案鎖死非相關程式碼；Close Gate 強制要求 smoke test 證據，不接受「邏輯上應該對」         |
| 跨服務 pipeline、有明確既有 QC 條件（例：內容生成流程的品質關卡）      | 驗收條件直接對應既有 QC 定義；Reviewer 高風險預設啟用                                         |
| 先前嘗試「一直做、一直加、一直說有進展，但 close 不起來」的任務        | 每輪只開窄工單处理當輪缺口，不重寫整份需求；Close Gate 杜絕模糊結案                           |
| 多任務並行、需要控制 token 但不能犧牲品質                              | Orchestrator 只做判斷不寫 code，大量重工（誤判 root cause、修錯地方、scope 跑掉）被結構性擋掉 |

---

## 分工原則

| 角色         | 對應本專案元件                                                                               |
| ------------ | -------------------------------------------------------------------------------------------- |
| Orchestrator | Claude 本身，本 skill 全流程控制                                                             |
| Executor     | harness subagent + 隔離工作區（預設，參數查 model-orchestration §2 適配表）或 agy CLI（需臨時授權，見 Phase 2 Path B） |
| Reviewer     | `agy-assist.md` Mode C（agy 或 Claude Subagent Fallback）                                 |
| 人類終審     | ESCALATE 結果的唯一裁決者                                                                    |

---

## ✅ 正確做法 / ❌ 常見錯誤

```
✅ 工單範圍與禁區先讓使用者確認，再委派 executor
✅ Close Gate 讀 diff 本身，不讀 executor 自己寫的完工報告
✅ Reviewer 發現逐條查證，CONFIRMED / REJECTED / ESCALATE 三選一，不全信也不全部忽略
✅ 有缺口就開下一輪窄工單只處理缺口，不重寫整份 ticket
✅ 涉及產品判斷的模糊地帶直接 ESCALATE，不用技術理由硬做決定

❌ 任務不符合啟用條件也套用 tech-lead-mode（小改動被工單流程拖慢）
❌ Executor 回報「完成」就直接 CLOSE，沒有核對驗收條件與實際 diff
❌ 把 agy 的 excludeTools 放寬後忘記還原，變成永久性的安全設定變更
❌ Reviewer 報的問題全部照單全收，或覺得「懶得查證」直接忽略
❌ Close Gate 卡住時用「大致完成，之後再說」這種模糊結果結案
```
