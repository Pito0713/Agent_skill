---
name: debug-flow
description: |
  除錯協調器，系統性縮小問題範圍，必要時切換具體舉例或委派 codex 交叉驗證。 觸發：bug、壞掉了、為什麼錯、不如預期、找不到原因、一直出錯、error、為什麼會這樣
metadata:
  trigger: bug / 錯誤訊息 / 行為不如預期時觸發
  version: "1.0"
  last_updated: "2026-07-04"
---

# Debug Flow — Orchestrator

## 觸發後第一步：確認症狀

詢問使用者（若未說明）：
> 1. 錯誤訊息是什麼？（貼上完整 error message）
> 2. 預期行為 vs 實際行為？
> 3. 最後一次正常運作是什麼時候？（或這是新功能從未運作過）

確認後進入 Phase 0。

---

## Phase 0：分類問題類型

依症狀判斷走哪條路：

| 症狀 | 分類 | 走向 |
|------|------|------|
| 有明確 error message | 執行期錯誤 | Phase 1 → 直接定位 |
| 行為錯誤但無 error | 邏輯錯誤 | Phase 1 → 追蹤資料流 |
| 反覆同一個錯誤看不懂 | 理解障礙 | Phase 2 切換具體舉例 |
| 改了 A 壞了 B | 副作用 / 耦合 | Phase 1 → 影響範圍分析 |
| 只在特定環境發生 | 環境差異 | Phase 1 → 環境對比 |

**輸出**：「問題分類為：[類型]，開始追蹤」

---

## Phase 1：系統性縮小範圍

依據 `skills/engineering/debug/SKILL.md`：

```
[ ] 確認錯誤發生的最小可重現條件
[ ] 用二分法縮小：哪一層出問題（UI / API / DB / 外部服務）
[ ] 確認最近的變更（git log / git diff）
[ ] 確認輸入資料是否符合預期（在入口加 log 驗證）
[ ] 確認環境變數 / 設定是否正確
```

若問題涉及大型檔案或整個 codebase，詢問：
> 「是否啟用 codex 掃描協助定位？(y/n)」

**y：**（codex 依 `cli-delegate.md` 前置確認偵測；副檔名依專案語言調整）
```bash
# Bash tool timeout 建議 570000 ms（cli-delegate 模式 B）
find ./src -name "*.ts" -o -name "*.tsx" -o -name "*.py" | xargs cat | codex exec -s read-only -c project_doc_max_bytes=0 "
定位以下問題的可能來源，條列相關模組與程式碼位置，不超過 15 行。
問題描述：[貼入症狀與 error message]
繁體中文。"
```

---

## Phase 2：假設 → 驗證循環

針對縮小後的範圍，逐一驗證假設：

```
[ ] 提出假設：「我認為問題出在 [位置]，原因是 [推測]」
[ ] 設計最小驗證：加 log / 寫一個最小測試 / 單獨呼叫該函式
[ ] 驗證結果：符合假設 → 進 Phase 3 / 不符合 → 提出下一個假設
```

**若使用者說「我看不懂為什麼」——切換成具體舉例**（原 `concrete-example` skill，2026-08-25 內聯）：

抽象邏輯轉成可逐步追蹤的具體情境。**優先用使用者自己的真實資料**，抽不出來才用代表性虛構資料。

依邏輯類型挑呈現格式：

| 邏輯類型 | 用什麼呈現 |
|---------|-----------|
| 時間計算、滑動窗口、累計計數 | 時間軸狀態表（逐行顯示每步狀態變化）|
| 條件判斷、多重 if/else | 決策路徑表（每個條件對應實際值與結果）|
| 資料轉換 filter/map/reduce | 輸入 → 中間步驟 → 輸出逐層對照 |
| 非同步、執行順序 | 時間序列圖（誰先誰後）|
| 狀態流轉（訂單、流程）| 狀態機圖 + 實際資料走一遍 |
| 遞迴、巢狀結構 | 展開樹狀圖，逐層標示當前值 |

輸出兩個方案，讓使用者選方向：

- **方案 A（正常邏輯）**：用具體資料走一遍正確步驟，結尾指出「第 X 步是關鍵，因為…」並指向具體函式或行數
- **方案 B（跳脫框架）**：換一種思路解同一個問題，講清楚它避開了 A 的哪個難點、代價是什麼

---

**Phase 2.5：Tech Lead Mode 判斷（可選）**

根因確認後，若符合 `skills/engineering/tech-lead-mode/SKILL.md` 啟用條件（預估 >3 檔案 / 曾卡關 / 高風險 gate / 易 scope creep），詢問使用者是否切換為 tech-lead-mode 執行 Phase 3（工單化 + 委派 executor + close gate），取代直接修正。不符合條件則略過，直接進入 Phase 3。

---

## Phase 3：修正

確認根因後執行修正：

```
[ ] 修正範圍最小化（只改有問題的地方）
[ ] 加入防禦性程式碼（避免同樣問題再發生）
[ ] 補上錯誤處理（空 catch → 記錄 log + re-throw）
```

修正完成後自我檢查：
```
[ ] 原本的錯誤已消失
[ ] 相關測試仍通過
[ ] 無新增 console.log 留在程式碼中
```

---

## Phase 4：codex 交叉驗證（可選）

詢問使用者：「是否啟用 codex 交叉驗證修正是否完整？(y/n)」

**y：**（codex 依 `cli-delegate.md` 前置確認；codex 不可用時走模式 C 的 Claude Subagent Fallback）
```bash
# Bash tool timeout 建議 570000 ms（cli-delegate 模式 C）
git diff HEAD | codex exec -s read-only -c project_doc_max_bytes=0 "
以下是一個 bug 修正的 diff。
已知問題根因：[貼入根因描述]

請審查：
1. 修正是否正確解決根因
2. 是否有遺漏的 edge case
3. 修正是否引入新的問題

格式：[確認 / 疑慮 / 風險] 描述 → 說明
繁體中文。"
```

Claude 收到後裁決，有疑慮項目回到 Phase 3 修正。

---

## Phase 5：防止復發

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接輸出報告
> - 使用者明確說「緊急修復，先上線，後補測試」
> - 根因為環境設定錯誤（非程式碼問題，無 regression test 必要）
> - 現有測試 suite 已覆蓋此路徑（Claude 確認無需補測試）

```
[ ] 補寫一個能捕捉此 bug 的測試（regression test）
[ ] 若是邏輯理解問題 → 補 inline comment 說明為什麼這樣寫
[ ] 若是環境問題 → 更新 .env.example 或 README 說明
```

---

## 最終輸出

```
## Debug 報告
問題描述：[原始症狀]
根因：[確認的根因]
修正位置：[檔案:行號]
修正方式：[摘要]

codex 驗證：[通過 / 發現 N 個疑慮已處理 / 未啟用]

防止復發：
- [ ] regression test 已補
- [ ] comment 已補
- [ ] 文件已更新

下一步建議：
- [ ] code-review（確認修正品質）
- [ ] deploy-prep（若準備上線）
```

---

## 分工原則

| 角色 | 負責 Phase |
|------|------|
| Orchestrator（本 skill）| 全流程控制、假設裁決 |
| `debug.md` | Phase 1 系統性縮小範圍 |
| `cli-delegate` 模式 B | Phase 1 大檔掃描協助定位 |
| `cli-delegate` 模式 C | Phase 4 修正交叉驗證 |

---

## ✅ 正確做法 / ❌ 常見錯誤

```
✅ 先收集完整症狀（error message + 預期行為 vs 實際行為）再開始定位
✅ 用二分法逐層縮小：UI → API → DB → 外部服務，確認問題在哪一層
✅ 一次只驗證一個假設，驗證前寫下預期結果
✅ 找到根因後，修正範圍最小化，不順便重構不相關的地方
✅ 修完確認：原錯誤消失 + 現有測試仍通過 + 無新增 console.log

❌ 看到 error 直接猜原因，跳過縮小範圍直接改 code
❌ 同時修改多個地方再看結果（無法定位是哪個改動修好的）
❌ 用「感覺」決定根因，沒有實際驗證（加 log 或最小可重現條件）
❌ 修完就結束，沒有補 regression test 或防止同樣問題再發生
```
