---
name: project-dashboard
description: |
  讀取 ~/.agent-sessions/ 下所有專案的 latest.md，輸出跨專案進度總覽表：
  1. 掃描所有專案的 latest.md 檔案
  2. 提取每個專案的狀態、最後更新時間、觸發來源、當前焦點與是否有 blocker
  3. 彙整成單一總覽表格，對 🔴 狀態或有 blocker 的專案額外展開完整內容

  觸發場景：同時手上有多個專案在跑，想快速掌握每個專案目前的進度與是否卡住，不用逐一切換專案查看。
  示例觸發：「幫我看一下所有專案目前的狀態」「project dashboard」「這幾個專案現在進度到哪了，給我一個總覽」
metadata:
  trigger: 需要跨專案進度總覽時觸發
  version: "1.0"
  last_updated: "2026-06-25"
---

# Project Dashboard

聚合所有專案的 `~/.agent-sessions/*/latest.md`，輸出跨專案進度總覽。

---

## 執行流程

### Phase 1：掃描所有 latest.md

```bash
find ~/.agent-sessions -name "latest.md" | sort
```

若無任何檔案：告知使用者「尚無專案紀錄，請在專案中執行 handoff 或 commit 後再查看。」

### Phase 2：提取各專案關鍵欄位

對每個 `latest.md` 提取：

```bash
# 專案名稱（第一行）
head -1 <file>

# 最後更新時間與觸發來源
grep "最後更新\|觸發來源" <file>

# 狀態
grep "狀態：" <file> | head -1

# 當前焦點（## 當前焦點 後第一個非空行）
grep -A 2 "^## 當前焦點" <file> | tail -1

# 卡住的點是否有內容
grep -A 2 "^## 卡住的點" <file> | grep -v "^##\|^$\|^無$"
```

### Phase 3：輸出聚合總覽

```
## 跨專案狀態（<today>）

| 專案 | 狀態 | 最後更新 | 來源 | 當前焦點 | Blocker |
|------|------|---------|------|---------|---------|
| my-app | 🟡 | 2026-06-25 14:32 | commit | JWT 認證模組 | ✅ |
| admin-panel | 🟢 | 2026-06-25 09:10 | handoff | 報表匯出 | — |
| api-gateway | 🔴 | 2026-06-24 18:00 | git-hook | rate limiting | ✅ |
```

### Phase 4：展開有問題的專案

若有 🔴 狀態或 Blocker（✅），展開該專案的完整 `latest.md` 內容。

---

## 來源標記說明

| 觸發來源 | 代表意義 |
|---------|---------|
| `handoff` | 使用者刻意整理過，內容最完整 |
| `commit` | commit 當下由 Claude 寫入，內容完整 |
| `git-hook` | terminal 直接 commit，只有 metadata |

---

## Checklist

```
[ ] find 指令有執行，非從記憶回答
[ ] 每個專案的狀態欄位都有填
[ ] 有 🔴 或 Blocker 的專案有展開詳細內容
[ ] 若無任何紀錄，有明確告知使用者
```
