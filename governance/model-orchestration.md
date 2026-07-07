# 模型調度守則（C）

> 主對話的模型是指揮官。指揮官的價值是判斷，不是打字。
> 依據見 `governance/harness-diagnosis.md`。派工 prompt 直接套 `governance/delegation-templates.md`。

---

## 1. 指揮官不下場

以下工作**禁止**在主對話直接做，一律委派，主對話只接收結論：

| 工作 | 派給 | 原因 |
|------|------|------|
| 掃整個 repo / 找檔案 / 找符號定義 | 唯讀搜尋型 subagent（§2 查對應參數） | 讀取量大，塞爆主對話 context |
| 需要讀 >3 個檔案的研究 / 理解 | 全工具 subagent | 同上 |
| 網路搜尋 | agy 模式 A（`gemini-assist.md`）或本 harness 的搜尋 subagent | 異質模型 + 不佔主對話 |
| 批次改檔（>3 檔或重複套用同一 pattern）| 全工具 subagent + 隔離（§2） | 隔離、可整批驗收 |
| 長 log / 大檔分析 | agy 模式 B 或全工具 subagent | 讀取量大 |
| 對抗式審查 | agy 模式 C，不可用時冷啟動 subagent | 異質性、獨立性 |

主對話**保留**：需求理解、切工單、仲裁 review 發現、close gate、與使用者的所有溝通。

**沒有 subagent 機制時**（或當前 harness 額度更划算時）：開一個**獨立的低成本 session**（照 §5 選該 harness 的便宜 model），把 `delegation-templates.md` 對應模板整包貼入當開場 prompt，回報照 §4 合約。效果等同 subagent，差別只是要人工把結論帶回主 session。

---

## 2. Harness 適配表（先認環境，再查表，不憑印象）

本制度倉庫被三個 harness 讀取：Claude Code、Codex、Antigravity（CLI 名 `agy`）。**委派參數沒有通用語法**：派工前先確認自己所在的 harness，只用下方對應欄的參數；表中沒有你的 harness → 以當前工具 schema 為準找等價能力，**禁止照抄其他 harness 的參數名**（會直接 Validation Error）。

| 能力 | Claude Code<br>（2026-07-03 實測） | Codex<br>（2026-07-07 官方文件查證，未本機實測） | Antigravity / agy<br>（2026-07-04 session 回報 + 2026-07-07 本機 CLI 實測） |
|------|------|------|------|
| 唯讀搜尋型 subagent | `subagent_type: "Explore"`（廣度 quick / medium / very thorough） | 無專用型：spawn worker agent 並在 prompt 明確寫「只讀不寫」 | `TypeName: "research"`（參數名未經本端驗證） |
| 全工具 subagent | `subagent_type: "general-purpose"` | 支援（2026-03 GA）：manager-worker 架構，單任務最多 8 個平行 agent，各自獨立 context 與雲端 sandbox；可用 TOML 定義 agent role | `TypeName: "self"`（繼承當前配置；參數名未經本端驗證） |
| 規劃型 subagent | `subagent_type: "Plan"` | 無專用型，用 worker + 唯讀指示 | 無對應，用 `self` + 明確唯讀指示 |
| 改 code 的隔離 | `isolation: "worktree"`（一律加） | 雲端 sandbox 天然隔離 | `Workspace: "branch"`（隔離）或 `"share"`（共享）（未驗證） |
| 逐次指定 model | 可：`model: haiku / sonnet / opus / fable` | 對話中逐次指定**未確認**；session 層可在 `~/.codex/config.toml` 設 `model` 或用 profiles 切換 | CLI 啟動時 `agy --model` 可指定；**工具 payload 塞 `model` 欄位會 Validation Error** |
| effort / thinking | 無法逐次指定（由 `.claude/agents/*.md` 控制），需更高 effort 改用更強 model | `model_reasoning_effort`: `minimal` / `low` / `medium`（預設）/ `high` / `xhigh`（成本約 3-5 倍） | model 名稱自帶檔位（如 `Gemini 3.1 Pro (High)`），選 model 即選 thinking 檔 |

**派發後的等待紀律（所有 harness 通用）**：背景委派派出後**不要輪詢**——不要空轉 loop、不要用無意義的工具呼叫「原地等」。Claude Code 背景 subagent 完成會自動通知（必要時用 Monitor / ScheduleWakeup 設長間隔 fallback）；Antigravity 派發後直接結束回合交還控制權，或用 `/schedule` 設 TimerCondition；Codex 平行 agent 由 manager 彙整。

**注意**：repo 內 `agents/` 目錄下的檔案（api-architect、backend-engineer 等）是**委派用的 prompt 定義檔**，不是任何 harness 的 subagent 類型。用法：把該檔內容放進全工具 subagent 的 prompt，**不要**填進類型參數（會報錯）。

**外部 CLI**：agy 可用（PATH：`/Users/wits/.local/bin/agy`）。gemini CLI 已停服，**任何流程檔看到 gemini CLI 都視為過時內容**。

---

## 3. 派工三件套（缺一不派）

每次委派的 prompt 必須包含，缺任何一件就是還沒準備好派工：

1. **目標與動機**：做什麼 + 為什麼（讓 executor 遇到邊界情況能對齊意圖）
2. **驗收條件**：可客觀驗證的清單（測試通過輸出 / 檔案存在 / grep 命中），禁止「做好做滿」「品質要高」
3. **回報格式**：明確規定回什麼、多長、長產物放哪

---

## 4. 回報合約（subagent / 低成本 session 端）

- 回報 ≤ 15 行結論 + `檔案:行號` 引用
- 長產物（分析報告、大 diff、清單）寫入檔案，回傳路徑，禁止整份貼回主對話
- 必附：做了什麼 / 證據在哪 / 剩餘風險（哪怕是「無」也要寫）
- 失敗時：貼實際錯誤輸出，不寫「試過了不行」

---

## 5. 模型選擇表（三 harness 各自的實際型號）

型號為 2026-07-07 查證值：Claude 為官方文件 + 本 harness 實測；Codex 來自 developers.openai.com/codex/models（未本機實測）；agy 來自本機 `agy models` 實跑輸出。**過期就會漂**——發現型號已下架，照 maintenance-protocol 🟢 級修正本表。

| 角色 | 用在 | Claude Code | Codex | Antigravity / agy |
|------|------|------|------|------|
| 機械工 | 格式轉換、批次套用已知 pattern、單檔小修、簡單查找 | `haiku` | `gpt-5.4-mini` | `Gemini 3.5 Flash`（L/M） |
| 工作馬（預設） | 實作、debug、審查、研究、文件 | `sonnet` | `gpt-5.4`（effort `medium`） | `Gemini 3.1 Pro (Low)` 或 `Claude Sonnet 4.6 (Thinking)` |
| 複雜推理 | 跨模組設計、根因不明的 debug、模糊需求拆解 | `opus` | `gpt-5.5`（effort `high`） | `Gemini 3.1 Pro (High)` 或 `Claude Opus 4.6 (Thinking)` |
| 最高階仲裁 | 制度設計、多方衝突裁決 | `fable`（額度稀缺，日常不用） | `gpt-5.5`（effort `xhigh`，成本 3-5 倍，非延遲敏感才用） | `Gemini 3.1 Pro (High)`（agy 池內已是頂） |

- 不確定用哪個 → 用該 harness 的工作馬。
- agy 額度**按 model 分池**（Gemini / Claude 各自獨立）：Gemini 池耗盡時切 Claude 池是合法的橫向移動，不算升級。
- agy 池另有 `GPT-OSS 120B`：僅當作異質第二意見來源，不當工作馬。

---

## 6. 升降級路徑

```
機械工錯 1 次            → 直接升工作馬（不給第二次）
工作馬同一子任務錯 2 次   → 帶完整失敗軌跡升複雜推理級
複雜推理級仍解不了        → 停下問使用者（最高階仲裁級的額度歸使用者管，不自行動用）
```

各級對應的實際型號查 §5 表格自己所在 harness 那一欄。

**失敗軌跡格式**（升級時必附，讓上層不用重新踩坑）：
```
任務：<原始目標一句話>
嘗試 1：做了 <what> → 輸出 <actual> → 錯在 <why>
嘗試 2：做了 <what> → 輸出 <actual> → 錯在 <why>
已排除：<確定不是原因的方向>
```

**降級**：強模型解出 pattern 後（例：確認了修法、寫出了第一個範例），把 pattern 寫成明確指令，降回機械工 / 工作馬批次套用到其餘位置。

**重試上限**：同一件事最多兩輪。第三輪之前必須發生以下之一：升級模型 / 換方法（見 judgment-rubrics R4）/ 問使用者。

**harness 差異**：逐次指定 model 僅 Claude Code 的 Agent tool 支援。Codex 在 session 內換 model 未確認可行 → 升級 = 開新的高階 session 帶失敗軌跡；agy 升級 = 停下，帶失敗軌跡**提示使用者**切換模型後重試——不要自己往工具 payload 塞 `model` 欄位。

---

## 7. 驗證不自驗

| 產出類型 | 驗收方式 | 執行者 |
|---------|---------|--------|
| 寫入的檔案 | read-back：重新讀取確認存在且內容完整 | fresh-context subagent 或主對話（若非自己寫的）|
| 程式碼 | 測試實跑 / 實際執行，貼輸出 | 編譯器與測試（客觀）、不是 executor 的口頭保證 |
| 高風險判斷（金流、安全、上線）| 第二意見：agy 模式 C 或冷啟動 subagent | 異質來源 |
| 高價值生成（重要文件、關鍵設計）| 多答案評審：產 2-3 版，冷啟動 reviewer 選優 | 冷啟動 subagent |

鐵律：**寫的人不驗收自己寫的東西**。主對話寫的 → subagent 驗；subagent 寫的 → 主對話讀 diff 驗（不讀完工報告）。

---

## 8. 跨 harness 分工（什麼任務放哪個 harness）

三個 harness 共用同一份制度正本（`~/Agent_skill`），但長處不同：

| Harness | 適合 | 原因 |
|---------|------|------|
| Claude Code | 主指揮、制度維護、跨檔複雜實作、需要細粒度委派的任務 | subagent 生態最全（型別 + 逐次指定 model + worktree 隔離）；制度正本的 symlink 分發在此維運 |
| Codex | 平行批次實作、大量機械性改檔、可丟進雲端 sandbox 跑的長任務 | 最多 8 平行 worker + 雲端 sandbox 隔離；`xhigh` 適合非交互式深推理 |
| Antigravity / agy | 網路搜尋、大檔掃描、對抗式審查 / 第二意見；一般實作亦可 | 模型池異質（Gemini + Claude + GPT-OSS），天然的獨立意見來源；額度與另兩家分開計 |

規則：
- **同一件事不要兩個 harness 同時做**（衝突覆寫風險，見 lessons 2026-07-03）。動手前 `git status`，交接走 `~/.agent-sessions/<專案>/latest.md`。
- 對抗式審查的 reviewer 盡量選**與 executor 不同的模型家族**（例：Claude 寫的 code 讓 agy 的 Gemini 審），盲點不重疊。
- 一個 harness 額度見底 → 把任務連同交辦包移到另一家，不硬撐。

---

## 9. 誠實標註

- 拆解、驗證、多樣本評審補得了執行品質；**品味與模糊題補不了**（產品方向、命名美感、寫作風格）→ 升級模型、外部第二意見、或明說做不到，見 `judgment-rubrics.md`。
- agy 的 review 幻覺率不低（見 gemini-assist.md），發現一律逐條查證後才採信，查證流程見 `tech-lead-mode.md` Phase 4。
- **未確認事項**（2026-07-07，查不到就標，不編造）：Codex 對話中逐次指定 model 是否可行；agy 的 `TypeName` / `Workspace` 參數名（來自 agy session 回報，本端無法驗證）；agy 付費 credit 換算比例；Claude「被導向 Opus 4.8 的請求是否消耗原方案額度」→ 到對應平台 usage 頁實測後回填本檔。
