---
name: agy-assist
description: 將資料密集型任務委派給 Antigravity CLI（agy）執行，節省 Claude token 並提供交叉驗證。當使用者說「幫我搜尋」、「這個檔案太大」、「掃一下整個專案」、「給我第二個意見」、「交叉驗證」時觸發。
---

# AGY Assist（AI 分工協作）

將三類任務委派給 Antigravity CLI（agy）：網路搜尋、大檔案掃描、對抗式審查。
Claude 負責決策與整合，agy 負責資料密集工作。

---

## 前置確認（每次執行前必須通過）

### Step 1：偵測可用的 CLI 工具

依優先順序偵測，找到第一個可用的即設為 `$CLI_CMD`：

```bash
# 優先順序：agy（PATH） → ~/.local/bin/agy（常見安裝路徑）→ gemini（相容舊版）
if command -v agy &>/dev/null; then
  CLI_CMD="agy"
  echo "✅ 使用 agy (Antigravity CLI)"
elif [ -x "$HOME/.local/bin/agy" ]; then
  CLI_CMD="$HOME/.local/bin/agy"
  echo "✅ 使用 ~/.local/bin/agy（建議加入 PATH）"
elif command -v gemini &>/dev/null; then
  CLI_CMD="gemini"
  echo "⚠️  使用 gemini CLI（舊版相容，建議遷移至 agy）"
else
  CLI_CMD=""
fi
```

**若 `$CLI_CMD` 為空（三者均未找到）：**
> 詢問使用者：「找不到 agy 或 gemini CLI，是否現在安裝 Antigravity CLI？(y/n)」
> - **y**：執行以下指令：
>   ```bash
>   curl -fsSL https://antigravity.google/cli/install.sh | bash
>   echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc && source ~/.zshrc
>   agy  # OAuth 認證
>   ```
> - **n**：
>   - 模式 A（網路搜尋）/ 模式 B（大檔掃描）→ 終止，改由 Claude 以現有知識處理
>   - 模式 C（對抗式審查）→ **不得直接跳過**，自動改用 Claude Subagent Fallback（見下方）

> 💡 **PATH 修正提示**（若使用 `~/.local/bin/agy`）：
> 執行 `echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc && source ~/.zshrc`
> 可讓後續 session 直接用 `agy` 指令。

**後續所有指令模板中的 `agy` 請替換為 `$CLI_CMD` 的實際值。**

### Step 2：確認安全設定

```bash
# 檔案不存在 → 自動建立
if [ ! -f ~/.agents/settings.json ]; then
  mkdir -p ~/.agents
  cat > ~/.agents/settings.json <<'EOF'
{
  "excludeTools": [
    "write_file",
    "edit_file",
    "delete_file",
    "run_shell_command"
  ]
}
EOF
  echo "✅ 已建立 ~/.agents/settings.json 並設定安全限制"
else
  # 檔案已存在，確認 excludeTools 是否設定
  python3 -c "
import json, sys
with open('$HOME/.agents/settings.json') as f:
    cfg = json.load(f)
if 'excludeTools' not in cfg:
    print('⚠️  缺少 excludeTools，請手動加入安全限制')
    sys.exit(1)
else:
    print('✅ 安全設定已確認')
"
fi
```

**兩步驟均通過後，才進入模式選擇。**

---

## 模式 A：網路搜尋

### 觸發條件
「幫我搜尋」、「查一下最新」、「有沒有相關資料」

**觸發後先詢問：**
> 「這個任務可以透過 AI CLI（agy / gemini）進行網路搜尋，是否啟用協作？(y/n)」
> - **y**：繼續執行以下流程
> - **n**：改由 Claude 以現有知識回答，不呼叫 Gemini

### Prompt 規範

```
必須包含：
  ✅ 明確的搜尋關鍵字（英文效果較佳）
  ✅ 限定回傳筆數（3-5 筆）
  ✅ 結構化輸出格式（標題 / URL / 摘要 / 是否有具體指令）
  ✅ 若有具體指令，截取指令內容回傳
  ✅ 語言指定（繁體中文輸出）

禁止：
  ❌ 讓 Gemini 自行決定搜尋關鍵字
  ❌ 找不到時自行補充知識庫內容（要求明確說「未找到」）
```

### 指令模板

```bash
# $CLI_CMD = agy / ~/.local/bin/agy / gemini（Step 1 偵測結果）
# Bash tool timeout: 120s（agy --print-timeout 90s + 30s 緩衝）
$CLI_CMD --print-timeout 90s -p "請使用 google_web_search 搜尋：'<關鍵字>'

回傳格式（每筆）：
- 標題：
- URL：
- 核心概念：（2-3 句）
- 具體指令或步驟：（有則截取，無則填「無」）

限制：3-5 筆結果，找不到請直接說找不到，不要補充其他內容。
輸出語言：繁體中文。"
```

---

## 模式 B：大檔案 / Repo 掃描

### 觸發條件
「這個檔案太大」、「掃一下整個專案」、「幫我理解這個 codebase」

**觸發後先詢問：**
> 「這個任務可以透過 AI CLI（agy / gemini）的大上下文視窗進行掃描，是否啟用協作？(y/n)」
> - **y**：繼續執行以下流程
> - **n**：由 Claude 直接讀取，token 消耗較高

### Prompt 規範

```
必須包含：
  ✅ 明確指定要提取什麼（架構 / 依賴 / 核心邏輯，三選一）
  ✅ 輸出行數上限（不超過 20 行條列）
  ✅ 指定輸出語言

禁止：
  ❌ 讓 Gemini 建議修改方向（那是 Claude 的工作）
  ❌ 同時要求多個提取目標（一次只問一件事）
```

### 指令模板

```bash
# $CLI_CMD = agy / ~/.local/bin/agy / gemini（Step 1 偵測結果）
# Bash tool timeout: 270s（agy --print-timeout 4m + 30s 緩衝）

# 單一大檔案
$CLI_CMD --print-timeout 4m -p "閱讀這份檔案，提取：<架構概覽 / 核心邏輯 / 外部依賴>
條列式輸出，不超過 20 行。不要建議修改。繁體中文。" < 檔案路徑

# 多檔案 / 整個目錄
find ./src -name "*.ts" | xargs cat | $CLI_CMD --print-timeout 4m -p "分析整體架構，
條列主要模組與職責，不超過 20 行。不要建議修改。繁體中文。"
```

---

## 模式 C：對抗式審查（Second Opinion）

### 觸發條件
「幫我 review」、「給我第二個意見」、「交叉驗證」、「有沒有漏洞」

**觸發後先詢問：**
> 「這個任務可以透過 AI CLI（agy / gemini）進行獨立的對抗式審查，是否啟用協作？(y/n)」
> - **y**：繼續執行以下流程
> - **n** 或 agy 不可用：**不得直接跳過**，改用 Claude Subagent Fallback（見下方）

### Prompt 規範

```
必須包含：
  ✅ 指定審查維度（邏輯漏洞 / 邊界條件 / 安全，可複選）
  ✅ 要求嚴重程度分級：CRITICAL / HIGH / MEDIUM / LOW
  ✅ 無問題時明確說「未發現問題」

禁止：
  ❌ 讓 Gemini 直接提供修改方案（只回報問題，修改由 Claude 決定）
  ❌ 問題描述模糊（要求：「第 X 行，原因是 Y，潛在影響是 Z」）
```

### 指令模板

```bash
# $CLI_CMD = agy / ~/.local/bin/agy / gemini（Step 1 偵測結果）
# Bash tool timeout: 210s（agy --print-timeout 3m + 30s 緩衝）

# 審查 git diff
git diff HEAD | $CLI_CMD --print-timeout 3m -p "審查這個 diff，僅回報問題，不提供修改方案。

審查維度：邏輯漏洞、邊界條件缺失、安全風險
每個問題格式：
[嚴重度] 位置：描述 → 潛在影響

嚴重度：CRITICAL / HIGH / MEDIUM / LOW
無問題時輸出：「未發現問題」
繁體中文。"

# 審查單一檔案
$CLI_CMD --print-timeout 3m -p "審查以下程式碼，僅回報問題，不提供修改方案。
[同上格式]" < 檔案路徑
```

---

## 模式 C Fallback：Claude Subagent 冷啟動審查

> 當 agy 不可用、或使用者選擇不啟用 agy 時強制執行。
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

### 與 agy 的差異標示

輸出報告中標記來源，讓使用者知道用了哪種模式：

```
交叉驗證：Claude Subagent（agy 不可用）⚠️ 同模型，獨立性低於異模型交叉驗證
```

---

## CLI 優先順序

| 優先 | CLI | 說明 |
|------|-----|------|
| 1 | `agy`（PATH） | Antigravity CLI，推薦版本 |
| 2 | `~/.local/bin/agy` | agy 安裝但未加入 PATH |
| 3 | `gemini`（PATH） | 舊版 Gemini CLI，介面相容 |
| — | 均不可用 | 模式 A/B：提示安裝 agy；模式 C：強制改用 Claude Subagent Fallback |

## 執行限制

| 限制 | 說明 |
|------|------|
| 每分鐘上限 60 次 | 同時不超過 2 個 CLI 任務 |
| 模式 B 無工具權限 | 使用 `< 路徑` 傳入，不依賴 CLI 讀檔工具 |
| 結果整合 | CLI 輸出作為參考，最終判斷由 Claude 負責 |
| **Timeout 規範** | 模式 A：agy 90s / Bash 120s；模式 B：agy 4m / Bash 270s；模式 C：agy 3m / Bash 210s |
| Timeout 原則 | Bash tool timeout 必須 > agy `--print-timeout`，讓 agy 先超時結束，避免被強制 kill |

---

## 分工原則

```
Claude               → 決策、規劃、整合、最終輸出
agy / gemini         → 資料收集、大量讀取、第二意見（異模型，獨立性高）
Claude Subagent      → 模式 C 的 fallback，冷啟動審查（同模型，獨立性較低但不可省略）
```

無論使用哪種模式，第二意見的輸出都不直接採用，Claude 主 agent 必須裁決後再整合。

**模式 C 鐵律：交叉驗證不得跳過，agy 不可用時強制走 Subagent Fallback。**
