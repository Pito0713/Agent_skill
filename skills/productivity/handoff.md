---
name: handoff
description: 將當前對話壓縮成交接文件，供下一個 session 或 agent 接手。當使用者說「交接」、「handoff」、「總結一下」、「下次繼續」時觸發。
---

# Handoff Skill

產生一份讓任何人（或新 session）能在 5 分鐘內接手的交接文件。

> **跨 harness 適用**（v5.0）：本 skill 在 Claude Code / Codex / agy 都照同一流程執行。最終寫入的 `~/.agent-sessions/<專案>/latest.md` 是**三 harness 共用的交接正本**（maintenance-protocol §6）——不管你在哪個 harness，收工必寫、開工必讀的都是同一份檔案。

---

## 輸出格式

````markdown
# Handoff Document

**時間**：<datetime>  
**任務**：<一句話說明在做什麼>  
**狀態**：🟡 進行中 / 🟢 完成 / 🔴 卡住

---

## 背景

<2-3 句話說明為什麼做這件事，問題背景>

## 當前進度

### 已完成

- [x] <完成的項目>
- [x] <完成的項目>

### 進行中

- [ ] <正在做的項目>（進度：X%）

### 待處理

- [ ] <下一步>
- [ ] <下下一步>

---

## 重要決策

| 決策 | 選擇 | 原因 |
|------|------|------|
| <決策點> | <選了什麼> | <為什麼> |

---

## 關鍵檔案

```
<path/to/file>        # 說明這個檔案的角色
<path/to/another>     # 說明
```

---

## 已知問題 / 風險

- ⚠️ <問題描述>：<可能影響 / 注意事項>
- 🐛 <bug 描述>：<重現步驟>

---

## 接手後第一步

1. <明確的第一個動作>
2. <第二步>

---

## 有用的指令

```bash
# <說明>
<command>

# <說明>
<command>
```

---

## 相關連結

- Issue / Ticket：<url>
- PR：<url>
- 相關文件：<url>
````

---

## 使用說明

執行此 skill 時：

1. 掃描當前對話歷史
2. 從 `memory/project-context.md` 補充背景
3. 填入上方模板
4. 詢問「有需要補充的資訊嗎？」
5. 確認後將文件存到 `memory/handoff-<YYYYMMDD>.md`

---

## 品質標準

好的交接文件讓接手者能：
- ✅ 不問任何問題就知道下一步是什麼
- ✅ 知道什麼已經試過、什麼沒試過
- ✅ 知道哪些決策是重要的、不要輕易改動
- ✅ 5 分鐘內上手

---

## Phase 最終：寫入跨專案進度快照

交接文件確認後，執行以下步驟將本次 session 狀態寫入 `~/.agent-sessions/<project>/latest.md`：

1. 取得專案名稱：`basename $PWD`（= 專案根目錄的資料夾名）
2. 確認目錄存在：`mkdir -p ~/.agent-sessions/<project>`
3. **無鎖併發防護（寫入前必做）**：重讀現有 latest.md——若「最後更新」時間比你這輪 session 開工時間**晚**，代表有別的 session / harness 動過 → 把對方的內容**合併進你的版本再寫**，禁止整檔覆蓋（maintenance-protocol §6）
4. 依以下格式寫入（觸發來源標記為 `handoff`）：

```markdown
# <project-name>

> 路徑：<$PWD>
> 最後更新：<YYYY-MM-DD HH:mm>
> 觸發來源：handoff
> 狀態：🟢 順暢 | 🟡 進行中 | 🔴 卡住 | ⚫ 暫停

## 當前焦點

<這輪工作的核心主題，一句話>

## 進行中

- [ ] <未完成任務>
- [x] <已完成任務>

## 下一步

1. <下次 session 第一件要做的事>

## 卡住的點

<若無則填「無」>

## 本輪決策

- <決策及原因>
```

5. 完成後輸出確認：「✅ 已更新 ~/.agent-sessions/<project>/latest.md」

---

## Phase 收尾：回寫紀律自檢（maintenance-protocol §6）

寫完 latest.md 後，收工前自檢一題——「**這輪學到的東西落在正本了嗎？**」：

- 踩坑教訓（下次還會有人踩的）→ append 到 `~/Agent_skill/governance/lessons.md`（格式見 maintenance-protocol §3）
- 重要架構決策 → 追加 ADR 到專案的 `memory/project-context.md`
- 各 harness 自帶的自動記憶（Codex Memories、agy brain）**不算落地**——沒寫進上面的檔案就等於丟失
