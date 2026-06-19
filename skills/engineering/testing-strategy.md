---
name: testing-strategy
description: 為功能或專案設計測試策略。當使用者說「這個要怎麼測」、「test plan」、「幫我規劃測試」時觸發。只輸出測試計畫文件，不寫測試程式碼（程式碼實作交由 test-engineer agent）。
---

# Testing Strategy

先策略，後實作。本 skill 只負責**輸出測試計畫**，不寫任何測試程式碼。
計畫完成後，交由 `agents/05-quality-assurance/test-engineer.md` 執行實作。

---

## Step 1：分析被測目標

```
[ ] 這是什麼類型的程式碼？
    □ 純函式（工具/計算）→ Unit test 為主
    □ 有副作用（DB/API/外部服務）→ Integration test 為主
    □ UI 元件 → Component test + E2E
    □ API endpoint → API test + Integration

[ ] 有哪些 critical paths？（失敗代價最高的）
[ ] 有哪些 edge cases？（空值、邊界、concurrent）
[ ] 有哪些已知 bug 需要防止 regression？
```

---

## Step 2：決定測試分佈

依照 rules/testing.md 中的金字塔原則，輸出：

```
測試計畫：
- Unit tests: X 個（覆蓋：...）
- Integration tests: Y 個（覆蓋：...）
- E2E tests: Z 個（覆蓋：critical paths）

預估覆蓋率：~X%
```

---

## Step 3：輸出測試計畫文件

計畫格式固定如下，不含任何程式碼：

```
## 測試計畫：<功能名稱>

### 測試分層
- Unit tests: X 個
  - 覆蓋：<函式/邏輯清單>
- Integration tests: Y 個
  - 覆蓋：<API/DB 互動清單>
- E2E tests: Z 個
  - 覆蓋：<critical user journey 清單>

### Critical Paths（失敗代價最高）
1. <path 1>
2. <path 2>

### Edge Cases 清單
- <空值/null 場景>
- <邊界值場景>
- <concurrent 場景>

### Regression 防護
- <已知 bug 或需防止重現的場景>

### 預估覆蓋率：~X%

→ 交由 test-engineer 依此計畫實作
```
