---
name: knowledge-search
description: |
  知識檢索，--source 決定搜哪裡：knowledge（repo 規範庫）、vault（Obsidian 筆記）、both（預設）。片段一律標來源路徑，沒命中就明說沒有。 觸發：查知識庫、rag、查一下我們的規範、這個我們有沒有記錄、有沒有相關規範、查我的筆記、Obsidian 有沒有記錄、之前有記過嗎、查歷史筆記
metadata:
  trigger: 需要先查既有知識（repo knowledge/ 或 Obsidian vault）再回答時觸發
  version: "1.0"
  last_updated: "2026-08-25"
---

# Knowledge Search（知識檢索）

> 由 `rag-search`（repo 知識庫）與 `obsidian-query`（個人 vault）合併而成。
> 兩者的差別只有「搜哪個目錄」，流程完全相同，因此收成一個 skill 加一個 `--source` 參數。

---

## Phase 0：決定 source

| 使用者說的 | source |
|-----------|--------|
| 查知識庫、我們的規範、這個有沒有記錄、rag | `knowledge` |
| 查我的筆記、Obsidian 有沒有、之前有記過嗎、查歷史筆記 | `vault` |
| 沒指定來源 | `both`（預設）|

| source | 搜尋根目錄 | 內容性質 |
|--------|-----------|---------|
| `knowledge` | `~/Agent_skill/knowledge/` | 專案共用規範與模式，跟著 repo 版控 |
| `vault` | `$OBSIDIAN_VAULT_PATH` | 個人筆記與歷史決策，含 mentor 存入的學術節點 |

**衝突時 vault 贏**：個人筆記代表使用者實際採用的做法，與通用規範不同時照 vault，並主動說明差異。

---

## 前置：只有 `vault` 與 `both` 需要

```bash
ENV_FILE="$HOME/Agent_skill/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ 找不到 $ENV_FILE"
  echo "  1. cp ~/Agent_skill/.env.example ~/Agent_skill/.env"
  echo "  2. 填入 OBSIDIAN_VAULT_PATH=/your/vault/path"
  echo "     （Obsidian 左下角 vault 名稱右鍵 → 在 Finder 中顯示）"
  exit 1
fi

source "$ENV_FILE"

if [ -z "$OBSIDIAN_VAULT_PATH" ]; then
  echo "❌ .env 中 OBSIDIAN_VAULT_PATH 尚未填入"; exit 1
fi
if [ ! -d "$OBSIDIAN_VAULT_PATH" ]; then
  echo "❌ 找不到 vault 目錄：$OBSIDIAN_VAULT_PATH"; exit 1
fi
echo "✅ vault：$OBSIDIAN_VAULT_PATH"
```

**`both` 模式下 vault 不可用不是錯誤**：降級成只搜 `knowledge/`，並在輸出中說明「vault 未設定，本次只涵蓋 repo 知識庫」——**必須說**，否則使用者會以為筆記裡真的沒有。

---

## Phase 1：萃取關鍵字

從問題提取 2–4 個核心關鍵字，中英都試（技術詞優先英文）。

```
問：「Docker 容器要怎麼設定環境變數？」
→ Docker、環境變數、container、env
```

**不要直接把整句話拿去 grep**——那幾乎必然 0 命中。

---

## Phase 2：搜尋

```bash
KEYWORDS=("關鍵字1" "關鍵字2" "關鍵字3")

# 依 Phase 0 決定要搜哪些根目錄（both 就兩個都放進來）
ROOTS=()
[ "$SOURCE" != "vault" ] && ROOTS+=("$HOME/Agent_skill/knowledge")
[ "$SOURCE" != "knowledge" ] && [ -n "$OBSIDIAN_VAULT_PATH" ] && ROOTS+=("$OBSIDIAN_VAULT_PATH")

HIT_FILES=()
for root in "${ROOTS[@]}"; do
  for kw in "${KEYWORDS[@]}"; do
    while IFS= read -r f; do HIT_FILES+=("$f"); done \
      < <(grep -r "$kw" "$root" --include="*.md" -l -i 2>/dev/null)
  done
done

# 跨關鍵字命中次數越多越相關；去重後取前 5
UNIQUE_FILES=($(printf '%s\n' "${HIT_FILES[@]}" | sort | uniq -c | sort -rn | awk '{print $2}' | head -5))
```

無命中 → 拆分關鍵字再搜一次；仍無命中 → 明確告知「查無記錄」，改用一般知識回答並標注。

---

## Phase 3：讀取命中片段

```bash
for f in "${UNIQUE_FILES[@]}"; do
  echo "=== $f ==="
  grep -i -A 5 -B 2 "${KEYWORDS[0]}" "$f" 2>/dev/null | head -20
done
```

**上限：最多 3 個檔案、每檔最多 2 個片段**，避免 context 爆掉。命中 > 5 筆時只取跨關鍵字命中次數最多的 3 筆。

---

## Phase 4：組合輸出

每則資訊都標來源路徑，來源以外的補充明確分開。

**repo 知識庫命中：**
```
📚 來源：knowledge/<路徑>
<整理後的片段>

（片段不足以完整回答時補一句「以下為模型補充，非知識庫內容」）
```

**vault 一般筆記命中：**
```
📓 從 Obsidian 找到相關筆記：
  • Docker 設定筆記（knowledge/tech/2026-06-30-docker-notes.md）
    → 上次記錄：使用 .env 檔搭配 --env-file 旗標

以下回答結合歷史筆記與當前知識：
```

**vault 學術筆記命中**（含 `#academic` 標籤，由 mentor-* 存入）：
```
📚 從 Obsidian 找到學術筆記：
  • 多巴胺與動機迴路（knowledge/neuro/2026-06-30-dopamine.md）
    最高確定性：✅
    → 核心機制：多巴胺是預測與渴望系統，非快樂本身
    → 文獻：Schultz et al.（1997）✅、Twenge et al.（2018）⚠️
    → 深化問題（未解）：戒除手機設計策略應如何改變？

以下回答結合歷史學術筆記與當前知識：
```

**`both` 兩邊都命中**：先列 vault（個人的優先），再列 knowledge，衝突處明講「你的筆記跟通用規範不同，我照你的」。

---

## Checklist

```
[ ] source 已判定（both 為預設，vault 不可用時已降級並說明）
[ ] 關鍵字是萃取出來的，不是整句話
[ ] grep 真的執行過，不是從記憶回答
[ ] 每則資訊都標了來源檔案路徑
[ ] 無命中時明確告知，沒有假裝查到
[ ] 回答長度合理（單一 source 不超過 300 字）
```
