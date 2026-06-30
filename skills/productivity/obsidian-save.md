---
name: obsidian-save
description: 將本次對話的重點整理後存入 Obsidian vault。當使用者說「記起來」、「存到 Obsidian」、「幫我記錄」、「結束」時觸發。
---

# Obsidian Save（寫入知識）

將當前對話中有價值的知識整理成結構化筆記，存入 Obsidian vault。

---

## 前置：讀取 .env 取得 VAULT_PATH

```bash
ENV_FILE="$HOME/Agent_skill/.env"

# ── 若 .env 不存在，引導使用者建立 ──
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ 找不到 $ENV_FILE"
  echo ""
  echo "請依照以下步驟建立："
  echo ""
  echo "  1. 複製範本："
  echo "     cp ~/Agent_skill/.env.example ~/Agent_skill/.env"
  echo ""
  echo "  2. 開啟並填入你的 Obsidian vault 路徑："
  echo "     （在 Obsidian 左下角 vault 名稱右鍵 → 在 Finder 中顯示）"
  echo "     OBSIDIAN_VAULT_PATH=/Users/你的帳號/Documents/Obsidian/VaultName"
  echo ""
  echo "  3. 儲存後重新執行此 skill"
  exit 1
fi

# ── 讀取 .env ──
source "$ENV_FILE"

# ── 確認變數有值 ──
if [ -z "$OBSIDIAN_VAULT_PATH" ]; then
  echo "❌ .env 中 OBSIDIAN_VAULT_PATH 尚未填入"
  echo "   請開啟 ~/Agent_skill/.env 並設定："
  echo "   OBSIDIAN_VAULT_PATH=/your/vault/path"
  exit 1
fi

# ── 確認 vault 存在 ──
if [ ! -d "$OBSIDIAN_VAULT_PATH" ]; then
  echo "❌ 找不到 vault 目錄：$OBSIDIAN_VAULT_PATH"
  echo "   請確認路徑是否正確"
  exit 1
fi

VAULT_PATH="$OBSIDIAN_VAULT_PATH"
echo "✅ vault：$VAULT_PATH"
```

---

## 執行流程

### Phase 1：萃取重點

從本次對話中提取有長期價值的知識：

```
判斷標準（以下任一條件符合即值得存）：
✅ 解決了一個具體問題（含解法與原因）
✅ 建立了一個新認知或概念
✅ 有可重複使用的指令 / 程式碼片段
✅ 使用者明確說「幫我記」

不值得存：
❌ 只是閒聊
❌ 只確認了某個顯而易見的事實
❌ 臨時性的操作步驟（無重複使用價值）
```

### Phase 2：決定分類與檔名

```bash
# 分類規則
# knowledge/tech/     → 技術、工具、指令、程式碼
# knowledge/business/ → 商業、規劃、流程、決策
# knowledge/personal/ → 個人想法、學習心得、目標
# inbox/              → 不確定分類時的暫存區

# 檔名格式：YYYY-MM-DD-<主題關鍵字>.md
FILENAME="$(date '+%Y-%m-%d')-<主題關鍵字>.md"
SAVE_PATH="$VAULT_PATH/inbox/$FILENAME"
```

### Phase 3：生成筆記內容

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

<如有 URL 或參考資料，列在這裡>

## 待追蹤

<如有未解決的問題或下一步行動，列在這裡>
```

### Phase 4：寫入檔案

```bash
SAVE_PATH="$VAULT_PATH/inbox/$(date '+%Y-%m-%d')-<主題關鍵字>.md"

mkdir -p "$(dirname "$SAVE_PATH")"

cat > "$SAVE_PATH" <<'NOTE'
<Phase 3 生成的筆記內容>
NOTE

echo "✅ 已存入：$SAVE_PATH"
```

### Phase 5：確認輸出

```
✅ 已存入 Obsidian：
   路徑：<VAULT_PATH>/inbox/2026-06-30-docker-env.md
   標題：Docker 容器環境變數設定
   標籤：#docker #devops #env

下次說「查我的筆記」+ 關鍵字，即可從 vault 取回這份筆記。
```

---

## 進階：整理 inbox

> 觸發詞：「整理我的 Obsidian」、「分類 inbox」

```bash
ls -t "$VAULT_PATH/inbox/" | head -20
```

Claude 依內容自動建議分類，使用者確認後移動到對應子目錄：

```bash
mv "$VAULT_PATH/inbox/<filename>.md" "$VAULT_PATH/knowledge/tech/<filename>.md"
```

---

## Checklist

```
[ ] .env 存在且 OBSIDIAN_VAULT_PATH 有值
[ ] vault 目錄確認存在
[ ] 內容有長期保存價值（非臨時操作）
[ ] 檔名含日期與主題關鍵字
[ ] 分類資料夾已存在或已建立
[ ] 輸出確認訊息含完整路徑
```
