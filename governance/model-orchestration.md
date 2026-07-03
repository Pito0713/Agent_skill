# 模型調度守則（C）

> 主對話的模型是指揮官。指揮官的價值是判斷，不是打字。
> 依據見 `governance/harness-diagnosis.md`。派工 prompt 直接套 `governance/delegation-templates.md`。

---

## 1. 指揮官不下場

以下工作**禁止**在主對話直接做，一律委派，主對話只接收結論：

| 工作 | 派給 | 原因 |
|------|------|------|
| 掃整個 repo / 找檔案 / 找符號定義 | `Explore` subagent | 讀取量大，塞爆主對話 context |
| 需要讀 >3 個檔案的研究 / 理解 | `general-purpose` subagent | 同上 |
| 網路搜尋 | agy 模式 A（`gemini-assist.md`）| 異質模型 + 不佔主對話 |
| 批次改檔（>3 檔或重複套用同一 pattern）| `general-purpose` + `isolation: worktree` | 隔離、可整批驗收 |
| 長 log / 大檔分析 | agy 模式 B 或 `general-purpose` | 讀取量大 |
| 對抗式審查 | agy 模式 C，不可用時冷啟動 subagent | 異質性、獨立性 |

主對話**保留**：需求理解、切工單、仲裁 review 發現、close gate、與使用者的所有溝通。

---

## 2. 本環境可用資源（2026-07-03 實測，不憑印象）

**Agent tool subagent 類型**：
- `Explore`：唯讀搜尋（找檔案 / grep / 「X 定義在哪」），要指定廣度 quick / medium / very thorough
- `general-purpose`：全工具，研究與執行的預設選擇
- `Plan`：架構規劃、實作策略設計
- `claude-code-guide`：Claude Code / API 本身的問題

**model 參數**（Agent tool 逐次可指定）：`haiku` / `sonnet` / `opus` / `fable`

**effort**：本 harness 無法逐次指定（由 `.claude/agents/*.md` 定義檔控制，本專案目前無自訂定義檔）。需要更高 effort 時改用更強的 model 替代。

**注意**：repo 內 `agents/` 目錄下的檔案（api-architect、backend-engineer 等）是**委派用的 prompt 定義檔**，不是 harness 的 subagent 類型。用法：把該檔內容放進 `general-purpose` subagent 的 prompt，**不要**填進 `subagent_type` 參數（會報錯）。

**外部 CLI**：agy 可用（PATH：`/Users/wits/.local/bin/agy`）。gemini CLI 已停服，**任何流程檔看到 gemini CLI 都視為過時內容**。

**隔離**：改 code 的委派一律加 `isolation: "worktree"`。

---

## 3. 派工三件套（缺一不派）

每次委派的 prompt 必須包含，缺任何一件就是還沒準備好派工：

1. **目標與動機**：做什麼 + 為什麼（讓 executor 遇到邊界情況能對齊意圖）
2. **驗收條件**：可客觀驗證的清單（測試通過輸出 / 檔案存在 / grep 命中），禁止「做好做滿」「品質要高」
3. **回報格式**：明確規定回什麼、多長、長產物放哪

---

## 4. 回報合約（subagent 端）

- 回報 ≤ 15 行結論 + `檔案:行號` 引用
- 長產物（分析報告、大 diff、清單）寫入檔案，回傳路徑，禁止整份貼回主對話
- 必附：做了什麼 / 證據在哪 / 剩餘風險（哪怕是「無」也要寫）
- 失敗時：貼實際錯誤輸出，不寫「試過了不行」

---

## 5. 模型選擇表

| model | 用在 | 不要用在 |
|-------|------|---------|
| `haiku` | 機械性任務：格式轉換、批次套用已知 pattern、單檔小修、簡單查找 | 任何需要跨檔案推理或模糊需求的事 |
| `sonnet` | **預設工作馬**：實作、debug、審查、研究、文件 | 已連錯兩次的任務（升級）|
| `opus` | 跨模組設計、根因不明的 debug、模糊需求拆解、高風險判斷 | 機械性批次工作（浪費）|
| `fable` | 最高階仲裁、制度設計、多方衝突裁決 | 額度稀缺，日常任務一律不用 |

不確定用哪個 → 用 `sonnet`。

---

## 6. 升降級路徑

```
haiku 錯 1 次          → 直接升 sonnet（不給 haiku 第二次）
sonnet 同一子任務錯 2 次 → 帶完整失敗軌跡升 opus
opus 仍解不了          → 停下問使用者（不自行升 fable，額度歸使用者管）
```

**失敗軌跡格式**（升級時必附，讓上層不用重新踩坑）：
```
任務：<原始目標一句話>
嘗試 1：做了 <what> → 輸出 <actual> → 錯在 <why>
嘗試 2：做了 <what> → 輸出 <actual> → 錯在 <why>
已排除：<確定不是原因的方向>
```

**降級**：強模型解出 pattern 後（例：確認了修法、寫出了第一個範例），把 pattern 寫成明確指令，降回 haiku / sonnet 批次套用到其餘位置。

**重試上限**：同一件事最多兩輪。第三輪之前必須發生以下之一：升級模型 / 換方法（見 judgment-rubrics R4）/ 問使用者。

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

## 8. 誠實標註

- 拆解、驗證、多樣本評審補得了執行品質；**品味與模糊題補不了**（產品方向、命名美感、寫作風格）→ 升級模型、外部第二意見、或明說做不到，見 `judgment-rubrics.md`。
- agy 的 review 幻覺率不低（見 gemini-assist.md），發現一律逐條查證後才採信，查證流程見 `tech-lead-mode.md` Phase 4。
