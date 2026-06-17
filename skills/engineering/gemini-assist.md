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
> - **n**：終止，不執行後續任何模式

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
$CLI_CMD -p "請使用 google_web_search 搜尋：'<關鍵字>'

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

# 單一大檔案
$CLI_CMD -p "閱讀這份檔案，提取：<架構概覽 / 核心邏輯 / 外部依賴>
條列式輸出，不超過 20 行。不要建議修改。繁體中文。" < 檔案路徑

# 多檔案 / 整個目錄
find ./src -name "*.ts" | xargs cat | $CLI_CMD -p "分析整體架構，
條列主要模組與職責，不超過 20 行。不要建議修改。繁體中文。"
```

---

## 模式 C：對抗式審查（Second Opinion）

### 觸發條件
「幫我 review」、「給我第二個意見」、「交叉驗證」、「有沒有漏洞」

**觸發後先詢問：**
> 「這個任務可以透過 AI CLI（agy / gemini）進行獨立的對抗式審查，是否啟用協作？(y/n)」
> - **y**：繼續執行以下流程
> - **n**：由 Claude 自行審查，無第二模型交叉驗證

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

# 審查 git diff
git diff HEAD | $CLI_CMD -p "審查這個 diff，僅回報問題，不提供修改方案。

審查維度：邏輯漏洞、邊界條件缺失、安全風險
每個問題格式：
[嚴重度] 位置：描述 → 潛在影響

嚴重度：CRITICAL / HIGH / MEDIUM / LOW
無問題時輸出：「未發現問題」
繁體中文。"

# 審查單一檔案
$CLI_CMD -p "審查以下程式碼，僅回報問題，不提供修改方案。
[同上格式]" < 檔案路徑
```

---

## CLI 優先順序

| 優先 | CLI | 說明 |
|------|-----|------|
| 1 | `agy`（PATH） | Antigravity CLI，推薦版本 |
| 2 | `~/.local/bin/agy` | agy 安裝但未加入 PATH |
| 3 | `gemini`（PATH） | 舊版 Gemini CLI，介面相容 |
| — | 均不可用 | 提示安裝 agy，或 Claude 自行處理 |

## 執行限制

| 限制 | 說明 |
|------|------|
| 每分鐘上限 60 次 | 同時不超過 2 個 CLI 任務 |
| 模式 B 無工具權限 | 使用 `< 路徑` 傳入，不依賴 CLI 讀檔工具 |
| 結果整合 | CLI 輸出作為參考，最終判斷由 Claude 負責 |

---

## 分工原則

```
Claude       → 決策、規劃、整合、最終輸出
agy / gemini → 資料收集、大量讀取、第二意見
```

CLI 的輸出不直接使用，Claude 必須驗證後再整合。
