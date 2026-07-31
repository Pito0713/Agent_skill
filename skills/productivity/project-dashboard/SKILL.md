---
name: project-dashboard
description: |
  讀取 ~/.agent-sessions/ 下所有專案的 latest.md，並對各專案 repo 現跑 git 取得即時狀態，輸出跨專案總覽表：
  1. 掃描所有專案的 latest.md 檔案
  2. 提取狀態、最後更新時間、觸發來源、當前焦點與是否有 blocker
  3. 對 latest.md 記載的路徑現跑 git：最後 commit、分支、未 commit 變更數
  4. 算出「交接落後」——交接檔寫完後又累積了幾個 commit
  5. 彙整成單一總覽表格，對 🔴 狀態、有 blocker 或交接嚴重落後的專案額外展開

  觸發場景：同時手上有多個專案在跑，想快速掌握每個專案目前的進度與是否卡住，不用逐一切換專案查看。
  示例觸發：「幫我看一下所有專案目前的狀態」「project dashboard」「這幾個專案現在進度到哪了，給我一個總覽」
metadata:
  trigger: 需要跨專案進度總覽時觸發
  version: "2.0"
  last_updated: "2026-07-31"
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

# 專案路徑（Phase 2.5 要用）
grep -m1 "^> 路徑" <file> | sed 's/.*：//'
```

### Phase 2.5：對各專案 repo 現跑 git（**不要從 latest.md 讀這些欄位**）

`最後 commit`、`分支` 這類衍生資料**一律讀取時現算**，不存進 `latest.md`。舊版
`latest.md` 可能殘留 `> 最後 commit`／`> 分支` 兩行（2026-07-31 前由已刪除的
post-commit hook 寫入）——**忽略它們**，那是過期快取。

```bash
P=<上一步取得的路徑>
U=<latest.md 的「最後更新」，格式 YYYY-MM-DD HH:mm>

[ -d "$P/.git" ] || echo "STALE：路徑已不存在或非 git repo"   # 專案搬走/刪除

git -C "$P" log -1 --format='%h %s' --date=format:'%Y-%m-%d %H:%M'  # 最後 commit
git -C "$P" branch --show-current                                    # 分支
git -C "$P" status --porcelain | wc -l                               # 未 commit 變更數
git -C "$P" log --since="$U" --oneline | wc -l                       # 交接落後：交接後又幾個 commit
```

**交接落後**是本 skill 唯一的漂移偵測。ADR-015 把交接觸發權完全交給使用者、移除
所有自動攔截，代價是「使用者忘了說收工 → latest.md 落後 repo」。這一欄把那個代價
從**不可見**變成**查得到**——偵測而非攔截，只在使用者主動叫 dashboard 時才跑。

判讀：`0` = 同步；`1–5` = 略舊；`>5` 或跨日 = 交接檔已明顯落後，值得提醒使用者
考慮補一次 handoff（**只是提醒，不主動寫**——鐵律 6）。

### Phase 3：輸出聚合總覽

```
## 跨專案狀態（<today>）

| 專案 | 狀態 | 交接更新 | 落後 | 分支 | 未 commit | 當前焦點 | Blocker |
|------|------|---------|------|------|-----------|---------|---------|
| my-app | 🟡 | 2026-07-30 14:32 | 0 | main | 0 | JWT 認證模組 | ✅ |
| admin-panel | 🟢 | 2026-07-29 09:10 | 3 | feat/x | 2 | 報表匯出 | — |
| api-gateway | 🔴 | 2026-07-24 18:00 | 12 ⚠️ | main | 0 | rate limiting | ✅ |
| old-thing | ⚫ | 2026-06-02 10:00 | STALE | — | — | （路徑已不存在）| — |
```

### Phase 4：展開有問題的專案

以下任一成立就展開該專案的完整 `latest.md`：🔴 狀態、有 Blocker、或落後 >5。

---

## 來源標記說明

| 觸發來源 | 代表意義 |
|---------|---------|
| `handoff` | 使用者明說收工/交接，由 handoff skill 寫入——**ADR-015 後的唯一合法來源** |

舊檔可能出現 `commit`（ADR-014 解耦 version-log 後失效）或 `git-hook`（ADR-015
刪除 post-commit hook 後失效）。兩者都不會再產生，遇到只代表該檔很舊。

---

## Checklist

```
[ ] find 指令有執行，非從記憶回答
[ ] 每個專案都實際跑過 git（最後 commit / 分支 / 落後數非從 latest.md 讀取）
[ ] 路徑不存在的專案標為 STALE，不當作錯誤中斷
[ ] 每個專案的狀態欄位都有填
[ ] 有 🔴 / Blocker / 落後 >5 的專案有展開詳細內容
[ ] 落後嚴重時有提醒使用者，但沒有主動寫 latest.md
[ ] 若無任何紀錄，有明確告知使用者
```
