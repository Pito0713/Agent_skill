# Coding Standards

> 語言無關的通用 coding 規範。所有任務均適用，優先順序高於語言特定規則。

---

## 核心原則

優先順序：**可讀性 → 錯誤處理 → 最小測試 → 效能**

效能優化只在有 profiling 數據支撐時進行，不憑直覺。

---

## 命名規範

- 變數、函式名稱使用**意圖揭示命名**（intention-revealing names）
- 禁止縮寫，除非是業界公認（`url`、`id`、`api`）
- Boolean 變數使用 `is`/`has`/`can`/`should` 前綴
- 函式名稱為動詞開頭：`getUserById`、`parseConfig`、`validateInput`
- 常數全大寫蛇底線：`MAX_RETRY_COUNT`

```ts
// ❌
const d = new Date()
const flg = true
function data(u: string) {}

// ✅
const createdAt = new Date()
const isAuthenticated = true
function fetchUserProfile(userId: string) {}
```

---

## 函式設計

- 單一職責：每個函式只做一件事
- 長度上限：**50 行**，超過則分解
- 參數上限：**3 個**，超過改用 options object
- 避免副作用（side effects），純函式優先
- 提前 return 取代巢狀 if

```ts
// ❌ 巢狀地獄
function process(user) {
  if (user) {
    if (user.isActive) {
      if (user.role === 'admin') {
        // ...
      }
    }
  }
}

// ✅ 提前 return
function process(user) {
  if (!user) return
  if (!user.isActive) return
  if (user.role !== 'admin') return
  // ...
}
```

---

## 錯誤處理

- **不得吞掉錯誤**：catch 內必須有處理邏輯或 re-throw
- 使用具體的 Error 型別，不使用裸字串
- 非同步函式統一使用 `try/catch`，不混用 `.catch()` 與 `try/catch`
- 對外 API 的錯誤必須記錄 log

```ts
// ❌
try {
  await fetchData()
} catch (e) {
  // 空的
}

// ✅
try {
  await fetchData()
} catch (error) {
  logger.error('fetchData failed', { error, context })
  throw new ServiceError('Failed to fetch data', { cause: error })
}
```

---

## 程式碼組織

- 相關程式碼放在一起（locality of behaviour）
- 避免過早抽象，等到第三次重複才抽
- 檔案長度上限：**300 行**，超過則分割模組
- import 順序：外部套件 → 內部模組 → 型別

---

## 註解規範

- 解釋**為什麼**，不解釋**是什麼**（程式碼本身說明 what）
- TODO 格式：`// TODO(name): description`
- 移除所有過時的 commented-out code，用 git 追蹤歷史

```ts
// ❌
// 把 user 的 name 加到 list
list.push(user.name)

// ✅
// 必須在 flush 前加入，否則 batch write 會遺漏最後一筆
list.push(user.name)
```

---

## 禁止事項

- 禁止 `console.log` 進入 production（使用 logger）
- 禁止 hardcode secrets、API keys、密碼
- 禁止忽略 linter 警告（除非有 inline 說明）
- 禁止 `any` 型別（TypeScript 專案）
- 禁止空 catch block
