---
name: obsidian-query
description: 從 Obsidian vault 搜尋相關歷史筆記並納入回答。當使用者說「查我的筆記」、「Obsidian 有沒有記錄」、「之前有記過嗎」、「搜 Obsidian」時觸發。
---

# Obsidian Query（讀取歷史知識）

從 Obsidian vault 搜尋與當前問題相關的歷史筆記，納入回答作為背景知識。

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

### Phase 1：萃取關鍵字

從使用者的問題中提取 2–4 個核心關鍵字（中英文均可）。

```
使用者問：「Docker 容器要怎麼設定環境變數？」
萃取關鍵字：Docker、環境變數、container、env
```

### Phase 2：搜尋 vault

多關鍵字依序搜尋，合併命中結果：

```bash
# 多關鍵字：逐一搜尋，收集命中檔案清單
KEYWORDS=("關鍵字1" "關鍵字2" "關鍵字3")
HIT_FILES=()

for kw in "${KEYWORDS[@]}"; do
  while IFS= read -r f; do
    HIT_FILES+=("$f")
  done < <(grep -r "$kw" "$VAULT_PATH" --include="*.md" -l -i 2>/dev/null)
done

# 去重、取前 5 筆最相關
UNIQUE_FILES=($(printf '%s\n' "${HIT_FILES[@]}" | sort | uniq -c | sort -rn | awk '{print $2}' | head -5))

# 對每筆命中檔提取上下文
for f in "${UNIQUE_FILES[@]}"; do
  echo "=== $f ==="
  grep -i -A 5 -B 2 "${KEYWORDS[0]}" "$f" 2>/dev/null | head -20
done
```

### Phase 3：整合輸出

- 命中 1–3 筆：摘要每筆相關內容，標注來源路徑
- 命中 0 筆：告知「vault 中尚無相關記錄」，直接以現有知識回答
- 命中 > 5 筆：只取出現次數最多的 3 筆（跨關鍵字命中次數越多越相關）

**一般筆記輸出格式：**
```
📓 從 Obsidian 找到相關筆記：
  • Docker 設定筆記（knowledge/tech/2026-06-30-docker-notes.md）
    → 上次記錄：使用 .env 檔搭配 --env-file 旗標

以下回答結合歷史筆記與當前知識：
...
```

**學術筆記輸出格式**（來源為 academic-mentor，含 `#academic` 標籤）：
```
📚 從 Obsidian 找到學術筆記：
  • 多巴胺與動機迴路（knowledge/neuro/2026-06-30-dopamine.md）
    最高確定性：✅
    → 核心機制：多巴胺是預測與渴望系統，非快樂本身
    → 文獻：Schultz et al.（1997）✅、Twenge et al.（2018）⚠️
    → 深化問題（未解）：戒除手機設計策略應如何改變？

以下回答結合歷史學術筆記與當前知識：
...
```

---

## Checklist

```
[ ] .env 存在且 OBSIDIAN_VAULT_PATH 有值
[ ] vault 目錄確認存在
[ ] 關鍵字已從使用者問題中萃取（非直接複製整句話）
[ ] grep 結果有執行，非從記憶回答
[ ] 來源路徑有標注在輸出中
[ ] 無命中時有明確告知使用者
```
