---
name: rag-search
description: |
  搜尋 knowledge/ 知識庫，找出相關規範或模式後回答，來源會標注檔案路徑。 觸發：查知識庫、rag、knowledge base、查一下我們的規範、這個我們有沒有記錄、有沒有相關規範
metadata:
  trigger: 需要搜尋 knowledge/ 知識庫找既有規範時觸發
  version: "1.0"
  last_updated: "2026-07-04"
---

> 🚫 **已停用（2026-08-25）**
>
> 本檔已移出 `skills/`，**不在 `skills/index.json`、不在 `skills/llms.txt`、不會被任何 harness 掃到**，
> agent 不會主動讀取或觸發它。保留在此僅作為文件參考與歷史依據。
>
> **停用理由**：與 obsidian-query 合併為 knowledge-search（--source knowledge）
>
> 要復用：把整個目錄搬回 `skills/<分類>/`，在 `index.json` 與 `llms.txt` 補回同一筆路由資料，
> 跑 `python3 bin/gen-skill-frontmatter.py --write` 重生 frontmatter，再跑 `bash setup.sh`。
> 政策與完整清單見 `deprecated/README.md`。

---

# RAG Search — 知識庫搜尋

---

## 流程

### Phase 1：提取關鍵字

從使用者問題提取 2-4 個搜尋關鍵字（優先英文，中英都試）。

### Phase 2：搜尋知識庫

```bash
grep -r "<關鍵字>" ~/Agent_skill/knowledge/ --include="*.md" -l -i
```

`-l` 只回傳檔名，`-i` 忽略大小寫。

若無命中：
1. 拆分關鍵字後再搜尋一次
2. 仍無命中 → 告知使用者「知識庫無相關記錄」，改用 Claude 現有知識回答

### Phase 3：讀取命中片段

對每個命中檔案執行：

```bash
grep -A 10 "<關鍵字>" <檔案路徑>
```

限制：最多 3 個檔案、每檔最多 2 個片段，避免 context 過長。

### Phase 4：組合回答

```
**📚 來源：** `knowledge/<路徑>`
**內容：**
<整理後的知識片段>

---
若知識庫片段不足以完整回答，補充說明並標注「以下為 Claude 補充」
```

---

## Checklist

```
[ ] grep 有執行，非直接從記憶回答
[ ] 來源檔案路徑有標注
[ ] 若無命中，有明確告知使用者
[ ] 回答長度合理（不超過 300 字）
```
