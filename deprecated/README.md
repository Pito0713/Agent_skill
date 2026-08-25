# deprecated/ — 停用 skill 存放區

> 這裡的 SKILL.md **不是 skill，是文件**。放在這裡的唯一意義是「還讀得到」，不是「還會被用到」。

---

## 「停用」的精確定義

停用 = **agent 不會主動讀取或觸發**，靠的是三件事同時成立：

| 機制 | 為什麼停用有效 |
|------|--------------|
| 不在 `skills/` 樹下 | `bin/validate-skill-index.py` 只把 `skills/**/SKILL.md` 當正本；本目錄不參與 coverage 檢查 |
| 不在 `skills/index.json` / `skills/llms.txt` | 這兩份是模型路由的唯一依據，沒有一筆指向本目錄 |
| 不在 symlink farm | `bin/lib-skill-farm.sh` 依 index 建 `~/.claude/skills/` 與 `~/.codex/skills/`，並用 `prune_orphan_entries` 主動清掉已不在 index 的舊 entry |

**不是**靠 frontmatter 加個 `deprecated` 欄位，也**不是**靠 lifecycle 標記——那兩種做法檔案仍留在
`skills/` 內、仍在 index 裡、仍會被 symlink 出去，模型照樣掃得到。停用必須是**移出索引**，不是加註記。

各檔的 frontmatter 原封保留（含 `name`、`description`），方便日後復用時直接搬回去，不需要重寫。

---

## 現有清單（2026-08-25，ADR-025）

### A. 直接停用（7 個）

判準：使用統計 0 次主動選用，且功能與其他 skill 重疊或已被取代。

| skill | 原路徑 | 停用理由 | 能力去向 |
|-------|--------|---------|---------|
| `coding-workflow` | `skills/engineering/` | 自陳「拆分前的完整版，僅供對照」 | `coding-workflow-core` + `coding-workflow-ref` |
| `concrete-example` | `skills/learning/` | 0 使用 | 精簡版內聯進 `debug-flow` Phase 2 |
| `feedback-loop` | `skills/learning/` | 0 使用 | 「一次只改一項」內聯進 `cooking-flow` vault 鉤子 |
| `lazyengineer` | `skills/engineering/` | 0 使用，與下者同一把尺 | 決策梯內聯進 `code-review` Phase 1.5 |
| `lazyengineer-review` | `skills/engineering/` | 0 使用 | 檢查表內聯進 `code-review` Phase 1.5 |
| `mentor-society` | `skills/learning/` | 0 次主動選用 | 社會科學題目分流至四個專科 mentor，不匹配走一般回答 |
| `academic-mentor` | `skills/learning/` | 0 次主動選用，與四專科 mentor 重疊 | 泛學術問題收斂至 `mentor-neuro` / `-science` / `-tech` / `-invest` |

### B. 合併後退役（5 個）

判準：與其他 skill 是同一件事的不同切面，內容已整合進單一 skill。

| skill | 併入 | 內容落點 |
|-------|------|---------|
| `information-architecture` | `ui-design-flow` 模式 A | 架構模式表 → `references/design-patterns.md` |
| `wireframing` | `ui-design-flow` 模式 B | 版面模式表 → `references/design-patterns.md` |
| `ui-visual-design` | `ui-design-flow` 模式 C | 8 種視覺風格表 → `references/design-patterns.md` |
| `obsidian-query` | `knowledge-search` | `--source vault`；`.env` 引導與學術筆記輸出格式全數保留 |
| `rag-search` | `knowledge-search` | `--source knowledge` |

---

## 復用流程

```bash
# 1. 搬回 skills/ 對應分類
git mv deprecated/<name> skills/<category>/<name>

# 2. 移除 SKILL.md 頂端的「已停用」banner 區塊

# 3. 在 skills/index.json 與 skills/llms.txt 補回同一筆路由資料
#    （四個欄位必須逐字相同：name / path / triggers / description）

# 4. 重生 frontmatter description（禁止手改，正本在 index.json）
python3 bin/gen-skill-frontmatter.py --write

# 5. 驗證 + 重新接線
python3 bin/validate-skill-index.py
bash bin/token-budget.sh --strict
bash setup.sh
```

---

## 新增停用項目的規約

- **刪除檔案是 🟡**（`governance/maintenance-protocol.md` §1），停用不是——停用不刪任何內容，
  所以模型可在使用者指名時執行；但**判斷「該停用哪些」永遠是使用者的決定**，模型只能提候選。
- 停用前必須先處理**現存委派點**：`grep -rn "<name>" skills/` 找出所有引用它的活躍 skill，
  決定內聯、移除分支或改指向，不得留下指向本目錄的路徑（那等於沒停用）。
- 使用統計（`python3 bin/skill-usage.py --days 0`）只能當**候選名單**，不能單獨當停用依據：
  窗口通常只有數週、agy harness 完全未涵蓋、`critical-on-demand` 類 skill 本來就低頻。
