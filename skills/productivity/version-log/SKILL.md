---
name: version-log
description: |
  每次 commit 前，將此次變更以版本號形式記錄到 README.md 的版本紀錄表：
  1. 確認 README.md 是否已有版本紀錄表（無則略過並告知使用者）
  2. 讀取當前版本號，依變更類型判斷 major / minor bump
  3. 產生新版本條目寫入 README.md 並 git add

  觸發場景：準備要 commit，需要先把這次的變更以版本號摘要記錄下來，供後續回溯版本歷史。
  示例觸發：「準備 commit 了，幫我記一下版本」「這次改動幫我更新版本號」「version log」
metadata:
  trigger: commit 前需記錄版本號與變更摘要時觸發
  version: "1.0"
  last_updated: "2026-06-25"
---

# Version Log

在每次 commit 前，將此次變更以版本號形式記錄到 `README.md` 的版本紀錄表。

---

## 版本號規則

```
v<major>.<minor>

major：架構重大變更、破壞性修改（+1）
minor：新增功能、補強內容、一般修改（+1）
```

範例：`v1.3` → 下一個 minor 為 `v1.4`，重大重構為 `v2.0`

---

## 前置判斷：確認版本紀錄表是否存在

```bash
grep -q '| v' README.md 2>/dev/null && echo "有版本表" || echo "無版本表"
```

- **有版本表** → 執行以下 Step 1–5
- **無版本表** → 跳過 README 更新，並告知使用者「此專案 README.md 無版本紀錄表，略過版本更新」

---

## 執行步驟

[ ] **Step 1：讀取當前版本**

```bash
# 從 README.md 版本紀錄表找最後一行
grep '| v' README.md | tail -1
```

[ ] **Step 2：確認 bump 類型**

詢問使用者（或依 git diff 自行判斷）：

| 變更類型 | bump |
|---------|------|
| 新增 skill / rule / agent | minor |
| 修改現有內容、修 bug | minor |
| 重組目錄結構、重大架構調整 | major |

[ ] **Step 3：產生新版本條目**

格式：

```
| v<新版本> | <今天日期 YYYY-MM-DD> | <一行摘要，分號分隔多項變更> |
```

[ ] **Step 4：寫入 README.md**

將新條目附加到 `## 版本紀錄` 表格的最後一行。

[ ] **Step 5：確認輸出**

顯示新增的條目給使用者確認，確認後 stage 此檔案：

```bash
git add README.md
```

---

## 輸出範例

```
新增版本條目：
| v1.4 | 2026-06-10 | 新增 version-log skill；更新 README 結構 |

已 stage README.md，可執行 commit。
```

---

## 注意事項

- 版本紀錄只追蹤**功能層級**的變更，不記錄拼字修正等微調
- 同一天的多次 commit 可合併為一個版本條目
- major bump 前請確認使用者同意
- **不寫 `~/.agent-sessions/latest.md`**（2026-07-27 ADR-014 決策：commit 與交接檔解耦）。latest.md 只由使用者明確說「收工/交接」時經 `handoff` skill 寫入；version-log 只管 README 版本表
