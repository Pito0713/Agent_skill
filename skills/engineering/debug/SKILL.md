---
name: debug
description: |
  系統性除錯工作流程，不猜測、要測量，依序縮小範圍：
  1. Step 1 重現：確認最小重現條件與環境
  2. Step 2 收集資訊：錯誤訊息、stack trace、近期變更
  3. Step 3 形成假設（最多 3 個，按可能性排序）
  4. Step 4 系統性驗證：git bisect、加 log、隔離測試
  5. Step 5 修復與驗證：修根因、加回歸測試、移除 debug log

  觸發場景：一般由 debug-flow 協調載入作為 Phase 1 執行依據，也可在使用者直接描述錯誤症狀時單獨參考。
  示例觸發：「這個功能一直報錯，我想系統性抓一下」「這段邏輯結果不對，但沒有 error message」「幫我用二分法找出是哪個 commit 弄壞的」
metadata:
  trigger: debug-flow Phase 1 依據；或直接描述錯誤症狀時參考
  version: "1.0"
  last_updated: "2026-06-08"
---

# Debug Workflow

不要猜測，要測量。依序縮小範圍。

---

## Step 1：重現（Reproduce）

```
[ ] 確認能穩定重現問題
[ ] 記錄重現步驟
[ ] 確認最小重現條件（哪些條件一定要、哪些不必要）
[ ] 確認是否只在特定環境發生（dev/staging/prod）
```

如果無法穩定重現 → 先建立監控/logging，等下次發生。

---

## Step 2：收集資訊

### 錯誤訊息分析

```
[ ] 完整錯誤訊息（不是截圖，是文字）
[ ] Stack trace（完整，不要只看最後一行）
[ ] 錯誤的第一次出現時間
[ ] 最近的 code change（git log --oneline -20）
```

### 常見 Stack Trace 解讀

```
Error: Cannot read properties of undefined (reading 'id')
    at getUserName (user.ts:42:18)  ← 從這裡開始看
    at processRequest (handler.ts:15:22)
    at ...

→ user.ts 第 42 行，user 是 undefined
→ 往上找：handler.ts 第 15 行為什麼傳入 undefined user？
```

---

## Step 3：形成假設

列出 3 個以內可能的根本原因，按可能性排序：

```
假設 1（最可能）：...
假設 2：...
假設 3：...
```

每個假設要有對應的**驗證方式**，不要全部猜完才開始測試。

---

## Step 4：系統性驗證

**二分法**：找到問題出現的邊界

```bash
# 找到最後一個 commit 正常的版本
git bisect start
git bisect bad HEAD
git bisect good v1.2.0
# git 會幫你二分，每次標記 good/bad
```

**加 logging 縮小範圍**：

```ts
// 在懷疑的位置加 structured log
console.log('[DEBUG] fetchUser called', { userId, timestamp: Date.now() })
console.log('[DEBUG] fetchUser result', { user: JSON.stringify(user) })
```

**隔離測試**：

```ts
// 把問題抽成最小的 test case
it('reproduces the bug', () => {
  const result = buggyFunction(problemInput)
  // 先確認 fail，再修復讓它 pass
  expect(result).toBe(expectedOutput)
})
```

---

## Step 5：修復與驗證

```
[ ] 修復根本原因（不是症狀）
[ ] 加回歸測試確保不再發生
[ ] 搜尋有無類似問題存在其他地方
[ ] 移除 debug logging
[ ] 更新文件（如有行為變更）
```

---

## 常見問題速查

### undefined / null 錯誤

```ts
// 找到資料進入點，往上追
// 常見原因：
// 1. async 時序問題（資料還沒到）
// 2. API response 結構變了
// 3. optional chaining 少加
// 4. 初始 state 未處理 loading
```

### 無限 re-render（React）

```ts
// 檢查：
// 1. useEffect 的 dependency array 是否有 object/array reference
// 2. 是否在 render 中 setState
// 3. useCallback / useMemo 的 deps 是否正確
```

### 非同步 race condition

```ts
// 症狀：結果不固定，有時對有時錯
// 解法：加 cancellation token 或 AbortController
// 或改用 state machine 管理 loading 狀態
```

### 環境差異（works on my machine）

```bash
# 比對 Node.js / Python 版本
node --version
python --version

# 比對套件版本
npm ls <package-name>
pip show <package>

# 比對環境變數
env | grep APP_
```

---

## 輸出格式

Debug 完成後輸出：

```
根本原因：[一句話]

修復內容：[修改了什麼]

防止再發：[加了什麼測試或監控]

後續建議：[有無類似問題需要注意]
```
