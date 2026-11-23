---
name: project-dashboard
description: |
  讀取 ~/.agent-sessions/ 下所有專案的 latest.md，並對各專案 repo 現跑 git，輸出含「交接落後」的跨專案總覽表。 觸發：project dashboard、看一下所有專案、跨專案狀態、專案總覽
metadata:
  trigger: 需要跨專案進度總覽時觸發
  version: "2.0"
  last_updated: "2026-07-31"
---

# Project Dashboard

聚合所有專案的 `~/.agent-sessions/*/latest.md`，輸出跨專案進度總覽。

---

## 執行流程

### Phase 1–3：跑 script 產生總覽（數字一律由 script 現算）

```bash
python3 ~/Agent_skill/bin/project-dashboard.py
```

- exit 1 = 沒有任何 `latest.md` → 照輸出告知使用者「尚無專案紀錄」；exit 2 = 找不到 git
- 單一專案的 latest.md 讀取失敗只會標在那一列（狀態 ❓），不影響其他專案
- `落後` 是「所有本機分支上、交接時間之後的 commit 數」；`STALE` = 路徑不存在或不是 git repo；`?` = 「最後更新」不是 `YYYY-MM-DD[ HH:mm]` 格式
- 輸出是下表格式的 markdown，**原樣貼給使用者**，不要自己改數字；最後一行「需要展開」就是 Phase 4 的名單
- script 對每個專案 repo **現跑 git**（分支、未 commit 數、交接後又幾個 commit）；latest.md 裡殘留的
  `> 最後 commit`／`> 分支`（2026-07-31 前由已刪除的 post-commit hook 寫入）是過期快取，一律不讀
- 「卡住的點」只寫「無」「無。」或「無（備註）」→ Blocker 顯示 `—`；其他內容（含「無法…」「無權限」）→ `有`

```
## 跨專案狀態（<today>）

| 專案 | 狀態 | 交接更新 | 落後 | 分支 | 未 commit | 當前焦點 | Blocker |
|------|------|---------|------|------|-----------|---------|---------|
| my-app | 🟡 | 2026-07-30 14:32 | 0 | main | 0 | JWT 認證模組 | 有 |
| admin-panel | 🟢 | 2026-07-29 09:10 | 3 | feat/x | 2 | 報表匯出 | — |
| api-gateway | 🔴 | 2026-07-24 18:00 | 12 ⚠️ | main | 0 | rate limiting | 有 |
| old-thing | ⚫ | 2026-06-02 | STALE | — | — | 舊專案收尾 | — |

需要展開：my-app、api-gateway
```

**交接落後**是本 skill 唯一的漂移偵測。ADR-015 把交接觸發權完全交給使用者、移除
所有自動攔截，代價是「使用者忘了說收工 → latest.md 落後 repo」。這一欄把那個代價
從**不可見**變成**查得到**——偵測而非攔截，只在使用者主動叫 dashboard 時才跑。

判讀：`0` = 同步；`1–5` = 略舊；`>5`（script 已加 ⚠️）= 交接檔已明顯落後，值得提醒使用者
考慮補一次 handoff（**只是提醒，不主動寫**——鐵律 6）。

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
[ ] project-dashboard.py 有執行，表格原樣輸出、非從記憶回答
[ ] 數字未經手改（分支 / 未 commit / 落後由 script 現跑 git）
[ ] 路徑不存在的專案標為 STALE，不當作錯誤中斷
[ ] 每個專案的狀態欄位都有填
[ ] 有 🔴 / Blocker / 落後 >5 的專案有展開詳細內容
[ ] 落後嚴重時有提醒使用者，但沒有主動寫 latest.md
[ ] 若無任何紀錄，有明確告知使用者
```
