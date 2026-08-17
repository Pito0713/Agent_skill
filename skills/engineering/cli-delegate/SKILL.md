---
name: cli-delegate
description: |
  將網路搜尋、大檔案掃描、對抗式審查委派給 codex CLI，節省 token 並提供異模型交叉驗證。 觸發：幫我搜尋、查一下最新、給我第二個意見、交叉驗證、這個檔案太大、掃一下整個專案
metadata:
  trigger: 網路搜尋 / 大檔案掃描 / 對抗式審查交叉驗證時觸發
  version: "2.0"
  last_updated: "2026-08-17"
---

# CLI Delegate（AI 分工協作）

將三類任務委派給 **codex CLI**：網路搜尋、大檔案掃描、對抗式審查。
Claude 負責決策與整合，codex 負責資料密集工作。

> **為什麼是 codex**：它是 OpenAI 模型，與 Claude 異模型異訓練資料，
> 模式 C 的交叉驗證才有獨立性；Claude subagent fallback 是同模型，獨立性較低。

---

## 前置確認（每次執行前必須通過）

### Step 1：偵測 codex

```bash
if command -v codex &>/dev/null; then
  echo "✅ 使用 codex $(codex --version)"
else
  echo "❌ 找不到 codex"
fi
```

**找不到 codex 時：**
- 模式 A（網路搜尋）/ 模式 B（大檔掃描）→ 告知使用者並終止，改由 Claude 以現有知識處理
- 模式 C（對抗式審查）→ **不得直接跳過**，自動改用 Claude Subagent Fallback（見下方）

安裝方式問使用者是否要裝，不自行安裝：`npm i -g @openai/codex` 或 `brew install codex`。

### Step 2：安全預設（每次呼叫都要帶）

codex 的安全邊界是**逐次旗標**，不是設定檔，所以每條指令都必須自帶：

| 旗標 | 作用 |
|------|------|
| `-s read-only` | sandbox 唯讀，codex 不能寫檔、不能改 repo |
| `-c project_doc_max_bytes=0` | **不載入 AGENTS.md**——見下方警告，在本 repo 內是必要旗標 |
| `--skip-git-repo-check` | 允許在非 git 目錄執行（在 repo 內可省略）|
| `-c tools.web_search=true` | **只有模式 A 才加**，開啟網路搜尋 |

⚠️ **在 `~/Agent_skill` 內委派一定要帶 `-c project_doc_max_bytes=0`。**
`setup-codex.sh` 把 `AGENTS.md` symlink 到 `~/.codex/AGENTS.md`、skill farm 掛到
`~/.codex/skills/`，所以被委派的 codex session **會繼承整套制度**：它會先讀交接檔、
載入 code-review／coding-workflow-core、跑 Phase 0，然後回合就結束了，任務一個字沒做。
2026-08-17 實測連續兩次委派都這樣死掉（見 `governance/lessons.md`）。
帶上該旗標後同一個任務正常完成。委派的是**單一唯讀任務，不是一個新的工作 session**。

⚠️ **絕不使用** `--dangerously-bypass-approvals-and-sandbox` 或 `-s danger-full-access`。
委派出去的是唯讀分析任務，任何寫入都該回到 Claude 這邊決定。

⚠️ **不要用 `timeout` 包裝**：macOS 沒有 `timeout` 指令（2026-08-17 實測 `command not found`）。
節流靠 Bash tool 自己的 timeout 參數，上限 600000 ms。

**兩步驟均通過後，才進入模式選擇。**

---

## 模式 A：網路搜尋

### 觸發條件
「幫我搜尋」、「查一下最新」、「有沒有相關資料」

**觸發後先詢問：**
> 「這個任務可以委派 codex 進行網路搜尋，是否啟用協作？(y/n)」
> - **y**：繼續執行以下流程
> - **n**：改由 Claude 以現有知識回答，並明說是憑訓練資料、可能過時

### 分工原則

> **codex 只負責取得原始資料，Claude 負責判斷與整合。**

```
codex  → 搜尋 → 回傳 title + URL + 一句摘要（原文即可，不要求翻譯）
Claude → 收到後 → 判斷可信度、翻譯整理、補充背景、標注來源
```

### Prompt 規範

```
必須包含：
  ✅ 具體問題或英文關鍵字（英文關鍵字命中率較高）
  ✅ 限定回傳筆數（3-5 筆）
  ✅ 要求附上來源網址
  ✅ 找不到時說 "NOT FOUND"

禁止：
  ❌ 要求複雜結構輸出（多欄位、Markdown 表格）
  ❌ 讓 codex 自行下結論
  ❌ 找不到時自行補充知識庫內容
```

### 指令模板

```bash
# Bash tool timeout 建議 360000 ms
codex exec -s read-only -c project_doc_max_bytes=0 -c tools.web_search=true \
  "搜尋：<具體問題或 English keywords>。
只回 3-5 筆，每筆格式：標題 / 來源網址 / 一句摘要。
不要下結論、不要建議。找不到就輸出 NOT FOUND。"
```

只要最後一則訊息、不要 session 前導資訊時，加 `-o <檔案>`：

```bash
codex exec -s read-only -c project_doc_max_bytes=0 -c tools.web_search=true -o /tmp/result.md "<prompt>"
```

**輸出格式（Claude 整理後）**：

```
📡 codex 搜尋結果（外部來源，未經驗證）：

1. <標題>
   URL：<url>
   摘要：<整理後的摘要>

---
Claude 分析整合：
<基於搜尋結果 + 現有知識的綜合回答，並指出哪些點與我的既有認知衝突>
```

> **實測提醒**：codex 搜尋回來的內容仍可能有錯（2026-08-17 實測一則模型清單答案就與官方資料有出入）。
> 搜尋結果是**線索不是結論**，關鍵事實要看它附的來源網址。

---

## 模式 B：大檔案 / Repo 掃描

### 觸發條件
「這個檔案太大」、「掃一下整個專案」、「幫我理解這個 codebase」

**觸發後先詢問：**
> 「這個任務可以委派 codex 掃描，避免佔用主對話 context，是否啟用協作？(y/n)」
> - **y**：繼續執行以下流程
> - **n**：由 Claude 直接讀取，token 消耗較高

### Prompt 規範

```
必須包含：
  ✅ 明確指定要提取什麼（架構 / 依賴 / 核心邏輯，三選一）
  ✅ 輸出行數上限（不超過 20 行條列）
  ✅ 指定輸出語言

禁止：
  ❌ 讓 codex 建議修改方向（那是 Claude 的工作）
  ❌ 同時要求多個提取目標（一次只問一件事）
```

### 指令模板

```bash
# Bash tool timeout 建議 570000 ms

# 單一大檔案：stdin 會被當成 <stdin> 區塊附在 prompt 後面
codex exec -s read-only -c project_doc_max_bytes=0 "閱讀 <stdin> 的檔案內容，提取：<架構概覽 / 核心邏輯 / 外部依賴>
條列式輸出，不超過 20 行。不要建議修改。繁體中文。" < 檔案路徑

# 讓 codex 自己在唯讀 sandbox 內讀檔（多檔案 / 整個目錄時用這個）
codex exec -s read-only -c project_doc_max_bytes=0 "掃描 ./src 下的 TypeScript 檔案，條列主要模組與職責，
不超過 20 行。不要建議修改。繁體中文。"
```

第二種寫法比 `cat |` 省事也省 token——唯讀 sandbox 讓 codex 自己去讀檔，
主對話完全不需要載入檔案內容。

---

## 模式 C：對抗式審查（Second Opinion）

### 觸發條件
「幫我 review」、「給我第二個意見」、「交叉驗證」、「有沒有漏洞」

**觸發後先詢問：**
> 「這個任務可以委派 codex 進行獨立的對抗式審查，是否啟用協作？(y/n)」
> - **y**：繼續執行以下流程
> - **n** 或 codex 不可用：**不得直接跳過**，改用 Claude Subagent Fallback（見下方）

### Prompt 規範

```
必須包含：
  ✅ 指定審查維度（邏輯漏洞 / 邊界條件 / 安全，可複選）
  ✅ 要求嚴重程度分級：CRITICAL / HIGH / MEDIUM / LOW
  ✅ 無問題時明確說「未發現問題」

禁止：
  ❌ 讓 codex 直接提供修改方案（只回報問題，修改由 Claude 決定）
  ❌ 問題描述模糊（要求：「第 X 行，原因是 Y，潛在影響是 Z」）
```

### 指令模板

```bash
# Bash tool timeout 建議 570000 ms

# 審查 git diff
git diff HEAD | codex exec -s read-only -c project_doc_max_bytes=0 "審查 <stdin> 的 diff，僅回報問題，不提供修改方案。

審查維度：邏輯漏洞、邊界條件缺失、安全風險
每個問題格式：
[嚴重度] 位置：描述 → 潛在影響

嚴重度：CRITICAL / HIGH / MEDIUM / LOW
無問題時輸出：「未發現問題」
繁體中文。"

# 審查單一檔案
codex exec -s read-only -c project_doc_max_bytes=0 "審查 <stdin> 的程式碼，僅回報問題，不提供修改方案。
[同上格式]" < 檔案路徑
```

**收到結果後 Claude 必須仲裁**，不得照單全收：逐條驗證是否成立（既有實測經驗是
codex 對測試檔的假陽性明顯多於實作檔），確認成立才納入，不成立要說明為什麼不採納。

---

## 模式 C Fallback：Claude Subagent 冷啟動審查

> 當 codex 不可用、或使用者選擇不啟用時強制執行。
> **交叉驗證不得直接跳過**，至少要有一次獨立第二意見。

### 原理

Subagent 以**冷啟動**方式接收材料：不持有主 agent 的分析脈絡，確保審查獨立性。
主 agent 完成自身分析後，才將原始材料（非分析結論）交給 subagent。

### 執行流程

```
Step 1：主 agent 完成自身分析，暫不輸出結論

Step 2：整理「審查材料包」
  - diff 內容 或 檔案內容（原始碼）
  - 審查維度（邏輯漏洞 / 邊界條件 / 安全風險）
  - 不含主 agent 的任何分析或推測

Step 3：以 Agent tool 啟動 subagent，傳入材料包
  prompt 格式見下方

Step 4：收到 subagent 輸出後，主 agent 裁決
  - Subagent 發現但主 agent 未提到 → 驗證後決定是否納入
  - 雙方一致 → 信心提升，直接採用
  - 意見相左 → 主 agent 說明選擇理由
```

### Subagent Prompt 模板

```
你是一個獨立的 code reviewer，對以下程式碼進行審查。
你沒有看過任何其他 reviewer 的意見，只根據原始碼回報問題。

審查維度：邏輯漏洞、邊界條件缺失、安全風險
每個問題格式：
[嚴重度] 位置：描述 → 潛在影響

嚴重度：CRITICAL / HIGH / MEDIUM / LOW
無問題時輸出：「未發現問題」
只回報問題，不提供修改方案。
繁體中文。

---
[貼入 diff 或檔案內容]
```

### 與 codex 的差異標示

輸出報告中標記來源，讓使用者知道用了哪種模式：

```
交叉驗證：Claude Subagent（codex 不可用）⚠️ 同模型，獨立性低於異模型交叉驗證
```

---

## 執行限制

| 限制 | 說明 |
|------|------|
| 同時任務數 | 不超過 2 個 codex 任務並行 |
| Timeout | Bash tool 上限 600000 ms；模式 A 建議 360000、模式 B/C 建議 570000 |
| 不用 `timeout` 包裝 | macOS 無此指令，包了只會拿到 `command not found` |
| sandbox | 一律 `-s read-only`；要寫檔就回到 Claude 這邊做，不放寬 codex 權限 |
| 結果定位 | codex 輸出是**參考與線索**，最終判斷與仲裁一律由 Claude 負責 |

---

## 分工原則

```
Claude          → 決策、規劃、整合、最終輸出
codex           → 資料收集、大量讀取、第二意見（異模型，獨立性高）
Claude Subagent → 模式 C 的 fallback，冷啟動審查（同模型，獨立性較低但不可省略）
```

無論使用哪種模式，第二意見的輸出都不直接採用，Claude 主 agent 必須裁決後再整合。

**模式 C 鐵律：交叉驗證不得跳過，codex 不可用時強制走 Subagent Fallback。**
