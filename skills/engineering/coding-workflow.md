---
name: coding-workflow
description: 實作新功能或修改現有程式碼的標準工作流程。當使用者說「實作 X」、「新增功能 Y」、「修改 Z」時觸發。包含理解→計畫→實作→驗證四個階段。
---

# Coding Workflow

實作任何功能前，依序執行以下四個階段。不得跳過。

---

## Phase 1：理解（Understand）

```
[ ] 讀取相關檔案，理解現有架構
[ ] 確認技術堆疊與框架版本
[ ] 找到相關的 types / interfaces
[ ] 找到現有的類似實作作為參考
[ ] 確認 edge cases 與限制條件
```

**輸出**：用 1-3 句話摘要「我理解的需求是：...」，等待確認。

---

## Phase 2：計畫（Plan）

```
[ ] 列出需要新增/修改的檔案清單
[ ] 說明實作順序（由內而外：types → logic → UI）
[ ] 指出潛在風險或需要特別注意的地方
[ ] 預估測試點
```

**輸出**：條列式計畫，等待確認後才進入 Phase 3。

---

## Phase 3：實作（Implement）

遵循 rules/ 中的適用規範。

```
[ ] 從型別/介面定義開始
[ ] 實作核心邏輯
[ ] 實作 UI 或 API layer
[ ] 加入錯誤處理
[ ] 加入基本測試（至少 happy path + 1 error case）
```

**Checklist before commit**：
```
[ ] 無 TypeScript 錯誤（tsc --noEmit）
[ ] Linter 無錯誤（eslint / ruff）
[ ] 所有現有測試通過
[ ] 無 console.log / debug prints
[ ] 無 hardcoded values
[ ] 函式長度 < 50 行
```

---

## Phase 4：驗證（Verify）

```
[ ] 執行相關測試
[ ] 手動測試主要 flow
[ ] 檢查 edge cases
[ ] 確認錯誤訊息對用戶友善
[ ] Review 自己的 diff（git diff）
```

**輸出**：「實作完成，以下是摘要：...」+ 下一步建議。

---

## 常見模式速查

### 新增 API Endpoint

1. 定義 request/response types（`types/api.ts`）
2. 實作 service 層邏輯（`services/`）
3. 實作 repository 層（`repositories/`）
4. 建立 route handler（`app/api/` 或 `routers/`）
5. 加入 input validation（Zod / Pydantic）
6. 加入 auth/permission check
7. 寫 integration test

### 新增 React 元件

1. 定義 props interface
2. 建立 storybook story（如有）
3. 實作元件（Server Component 優先）
4. 加入 loading / error states
5. 寫元件測試

### Bug Fix

1. 先寫一個能重現 bug 的測試（讓它 fail）
2. 找根本原因
3. 修復
4. 確認測試 pass
5. 檢查有無類似問題存在其他地方
