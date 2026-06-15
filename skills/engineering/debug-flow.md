---
name: debug-flow
description: 除錯協調器。當使用者說「這個壞掉了」、「為什麼會錯」、「bug」、
  「error」、「不如預期」、「一直出錯」、「找不到原因」時觸發。
  系統性縮小問題範圍，必要時切換具體舉例或委派 Gemini 交叉驗證。
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
| 反覆同一個錯誤看不懂 | 理解障礙 | 插入 concrete-example |
| 改了 A 壞了 B | 副作用 / 耦合 | Phase 1 → 影響範圍分析 |
| 只在特定環境發生 | 環境差異 | Phase 1 → 環境對比 |

**輸出**：「問題分類為：[類型]，開始追蹤」

---

## Phase 1：系統性縮小範圍

依據 `skills/engineering/debug.md`：

```
[ ] 確認錯誤發生的最小可重現條件
[ ] 用二分法縮小：哪一層出問題（UI / API / DB / 外部服務）
[ ] 確認最近的變更（git log / git diff）
[ ] 確認輸入資料是否符合預期（在入口加 log 驗證）
[ ] 確認環境變數 / 設定是否正確
```

若問題涉及大型檔案或整個 codebase，詢問：
> 「是否啟用 Gemini 掃描協助定位？(y/n)」

**y：**
```bash
find ./src -name "*.ts" | xargs cat | agy -p "
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

**若使用者說「我看不懂為什麼」：**
插入 `skills/learning/concrete-example.md`：
- Plan A：正常邏輯逐步說明
- Plan B：用具體資料跑一遍，視覺化每個步驟的狀態

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

## Phase 4：Gemini 交叉驗證（可選）

詢問使用者：「是否啟用 Gemini 交叉驗證修正是否完整？(y/n)」

**y：**
```bash
git diff HEAD | agy -p "
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

Gemini 驗證：[通過 / 發現 N 個疑慮已處理]

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
| `concrete-example.md` | Phase 2 理解障礙時切換 |
| `gemini-assist` 模式 B | Phase 1 大檔掃描協助定位 |
| `gemini-assist` 模式 C | Phase 4 修正交叉驗證 |
