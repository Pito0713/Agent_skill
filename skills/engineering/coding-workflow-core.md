---
name: coding-workflow-core
description: 實作任何功能的核心流程守則（常駐版）。包含四個強制階段與 commit 前 checklist。
---

# Coding Workflow — Core

所有實作任務的強制流程，不得跳過。

---

## Phase 1：理解（Understand）

```
[ ] 讀取相關檔案，理解現有架構
[ ] 確認技術堆疊與框架版本
[ ] 找到相關的 types / interfaces
[ ] 確認 edge cases 與限制條件
```

**輸出**：用 1-3 句話摘要「我理解的需求是：...」，等待確認。

---

## Phase 2：計畫（Plan）

```
[ ] 列出需要新增/修改的檔案清單
[ ] 說明實作順序（由內而外：types → logic → UI）
[ ] 指出潛在風險或需要特別注意的地方
```

**輸出**：條列式計畫，等待確認後才進入 Phase 3。

---

## Phase 3：實作（Implement）

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
[ ] Review 自己的 diff（git diff）
```

**輸出**：「實作完成，以下是摘要：...」+ 下一步建議。
