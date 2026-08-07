---
name: obsidian-save
description: |
  將本次對話重點整理成結構化筆記存入 Obsidian vault，自動分類並標注標籤。需先設定 VAULT_PATH。 觸發：記起來、存到 Obsidian、幫我記錄、結束並儲存、整理我的 Obsidian、分類 inbox
metadata:
  trigger: 對話出現值得存檔的知識或使用者要求記錄時觸發
  version: "1.0"
  last_updated: "2026-07-04"
---

# Obsidian Save（寫入知識）

將當前對話中有價值的知識整理成結構化筆記，存入 Obsidian vault。
**自動偵測來源 skill，academic-mentor 輸出使用專屬學術模板。**

---

## 前置：讀取 .env 取得 VAULT_PATH

```bash
ENV_FILE="$HOME/Agent_skill/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ 找不到 $ENV_FILE"
  echo ""
  echo "請依照以下步驟建立："
  echo "  1. cp ~/Agent_skill/.env.example ~/Agent_skill/.env"
  echo "  2. 開啟並填入你的 Obsidian vault 路徑："
  echo "     （在 Obsidian 左下角 vault 名稱右鍵 → 在 Finder 中顯示）"
  echo "     OBSIDIAN_VAULT_PATH=/Users/你的帳號/Documents/Obsidian/VaultName"
  echo "  3. 儲存後重新執行此 skill"
  exit 1
fi

source "$ENV_FILE"

if [ -z "$OBSIDIAN_VAULT_PATH" ]; then
  echo "❌ .env 中 OBSIDIAN_VAULT_PATH 尚未填入"
  echo "   請開啟 ~/Agent_skill/.env 並設定："
  echo "   OBSIDIAN_VAULT_PATH=/your/vault/path"
  exit 1
fi

if [ ! -d "$OBSIDIAN_VAULT_PATH" ]; then
  echo "❌ 找不到 vault 目錄：$OBSIDIAN_VAULT_PATH"
  echo "   請確認路徑是否正確"
  exit 1
fi

VAULT_PATH="$OBSIDIAN_VAULT_PATH"
echo "✅ vault：$VAULT_PATH"
```

---

## Phase 0：偵測來源 skill

判斷本次對話的輸出來自哪個 skill：

```
偵測條件（符合任一即判斷為 mentor 系來源，走學術模板）：
[1] 對話中出現確定性符號組合（⚠️ ❓ 🚫 其中之一，或連同文字說明出現）
[2] 對話中出現四段結構標題：「核心機制」「文獻依據」「社會影響」「深化問題」（academic-mentor）
[3] 對話中出現專科 mentor 區塊標題：【定位聲明】【機制鏈】【知識層級定位】
    【Tradeoff 矩陣】【行為偏誤掃描】【知識圖譜節點】其中之一，或 [[wiki-link]] 節點連結
[4] 對話中有學術引用格式（作者 年份 〈標題〉 期刊）
[5] 使用者明確說「用學術格式存」

→ 符合任一 → 走 [路徑 A：學術模板]
→ 全不符合 → 走 [路徑 B：通用模板]

專科 mentor 來源的欄位對應：比照 A-1 表格精神，將該 mentor 的區塊
（如【機制鏈】→ 核心機制、【知識圖譜節點】→ 相關連結）對應到模板欄位，
確定性符號與 [[節點連結]] 必須完整保留。
```

---

## 路徑 A：學術模板（academic-mentor 來源）

### A-1：萃取欄位對應

| academic-mentor 輸出區塊 | Obsidian 欄位 |
|------|------|
| 核心機制解析（直觀解釋 + 精確定義）| `## 核心機制` |
| 文獻與研究依據（含確定性符號）| `## 文獻依據` |
| 降低負面影響（含確定性標注）| `## 社會影響與介入 > 降低負面影響` |
| 主動利用機制（含確定性標注）| `## 社會影響與介入 > 主動利用` |
| 常見迷思糾正（🚫）| `## 迷思糾正` |
| 思考夥伴提問 | `## 深化問題` |
| 推薦閱讀資源 | `## 推薦閱讀` |

### A-2：學術筆記模板

```markdown
# <主題標題>

> 建立時間：<YYYY-MM-DD HH:MM>
> 來源：academic-mentor 對話
> 標籤：#<領域> #academic #<主題關鍵字>
> 最高確定性：<✅ / ⚠️ / ❓>

## 核心機制

<直觀解釋（一句話）>

<精確定義，保留英文術語與中文說明>
例：前額葉皮質（prefrontal cortex, PFC）

## 文獻依據

<逐條列出，保留確定性符號>
- ✅ 作者（年份）〈標題〉，期刊，核心發現
- ⚠️ 作者（年份）〈標題〉，概略引用，建議查證

## 社會影響與介入

### 降低負面影響
- <確定性符號> 介入方式：機制層面說明

### 主動利用機制
- <確定性符號> 利用方式：設計方向說明

## 迷思糾正

（若對話中有糾正迷思則列出，否則省略此區塊）
- 🚫「<迷思>」→ <正確說明>

## 深化問題

<mentor 提出的思考問題，作為下次探索的起點>
1. <問題一>
2. <問題二>

## 推薦閱讀

- <教科書章節 / review paper>
```

### A-3：儲存位置

```bash
# 學術筆記依領域存入 knowledge/<領域>/，不進 inbox/
# 領域由 Claude 從對話主題判斷

# 判斷規則（依來源 mentor 對應目錄）
# knowledge/neuro/      → mentor-neuro：神經科學、認知心理、行為科學
# knowledge/health/     → 醫學、生理、心理健康
# knowledge/society/    → mentor-society：社會現象、科技影響、教育、傳播
# knowledge/science/    → mentor-science：自然科學、物理、化學、生物
# knowledge/tech/       → mentor-tech：技術架構、系統設計、工程權衡（概念層）
# knowledge/invest/     → mentor-invest：投資框架、行為偏誤、資產配置原則
# knowledge/            → 跨領域或無法歸類時，存根目錄

DOMAIN_DIR="$VAULT_PATH/knowledge/<判斷領域>/"
FILENAME="$(date '+%Y-%m-%d')-<主題關鍵字>.md"
SAVE_PATH="${DOMAIN_DIR}${FILENAME}"

mkdir -p "$DOMAIN_DIR"  # 若子目錄不存在則自動建立
```

---

## 路徑 B：通用模板（一般對話來源）

### B-1：判斷是否值得存

```
✅ 解決了一個具體問題（含解法與原因）
✅ 建立了一個新認知或概念
✅ 有可重複使用的指令 / 程式碼片段
✅ 使用者明確說「幫我記」

❌ 只是閒聊
❌ 只確認顯而易見的事實
❌ 臨時性的操作步驟（無重複使用價值）
```

### B-2：通用筆記模板

```markdown
# <主題標題>

> 建立時間：<YYYY-MM-DD HH:MM>
> 來源：Claude 對話
> 標籤：#<自動推斷的標籤>

## 核心概念

<1–3 句話摘要這個知識的本質>

## 細節

<重要的步驟、指令、程式碼、或說明>

## 相關連結

<如有 URL 或參考資料>

## 待追蹤

<未解決的問題或下一步行動>
```

### B-3：儲存位置

```bash
# 分類規則
# knowledge/tech/     → 技術、工具、指令、程式碼
# knowledge/business/ → 商業、規劃、流程、決策
# knowledge/personal/ → 個人想法、學習心得、目標
# inbox/              → 不確定分類時的暫存區

CATEGORY_DIR="$VAULT_PATH/inbox"  # 預設 inbox，確定分類後改對應路徑
FILENAME="$(date '+%Y-%m-%d')-<主題關鍵字>.md"
SAVE_PATH="${CATEGORY_DIR}/${FILENAME}"

mkdir -p "$CATEGORY_DIR"  # 確保目錄存在
```

---

## Phase 最終：確認輸出

```
# 路徑 A 輸出
✅ 已存入 Obsidian（學術模板）：
   路徑：<VAULT_PATH>/knowledge/neuro/2026-06-30-dopamine-phone-addiction.md
   標籤：#神經科學 #多巴胺 #academic
   文獻：2 筆（✅ 1 / ⚠️ 1）
   深化問題已存入，下次說「查我的筆記，多巴胺」即可取回

# 路徑 B 輸出
✅ 已存入 Obsidian：
   路徑：<VAULT_PATH>/inbox/2026-06-30-<主題>.md
   下次說「查我的筆記」+ 關鍵字，即可從 vault 取回
```

---

## 進階：整理 inbox

> 觸發詞：「整理我的 Obsidian」、「分類 inbox」

```bash
ls -t "$VAULT_PATH/inbox/" | head -20
```

Claude 依內容自動建議分類，使用者確認後移動：

```bash
mv "$VAULT_PATH/inbox/<filename>.md" "$VAULT_PATH/knowledge/tech/<filename>.md"
```

---

## Checklist

```
[ ] .env 存在且 OBSIDIAN_VAULT_PATH 有值
[ ] Phase 0 已判斷來源（academic-mentor 或通用）
[ ] 使用對應模板（A 或 B）
[ ] 學術模板：確定性符號保留、文獻格式完整
[ ] 學術模板：存入 knowledge/<領域>/ 而非 inbox/
[ ] 通用模板：內容有長期保存價值
[ ] 輸出確認訊息含完整路徑與摘要
```
