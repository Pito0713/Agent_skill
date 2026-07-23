---
name: coding-workflow-ref
description: |
  常見實作模式速查手冊（按需版），配合 coding-workflow-core 使用，收錄三種模式：
  1. 新增 API Endpoint：types → service → repository → route → validation → auth → test
  2. 新增 React 元件：props → story → 實作 → loading/error/empty states → test
  3. Bug Fix：先寫重現測試 → 找根因 → 修復 → 確認測試通過 → 排查類似問題

  觸發場景：實作前需要查閱標準模式，避免遺漏步驟（如忘記 auth check 或 loading state）。
  示例觸發：「幫我加一個新的 API endpoint」「這個 React 元件怎麼寫比較標準」「修這個 bug 前該注意什麼順序」
metadata:
  trigger: 新增 API endpoint / React 元件 / bug fix 時查閱標準步驟
  version: "1.0"
  last_updated: "2026-06-09"
---

# Coding Workflow — 常見模式速查

> 配合 `coding-workflow-core.md` 使用，實作前翻閱對應模式。

---

## 新增 API Endpoint

1. 定義 request/response types（`types/api.ts`）
2. 實作 service 層邏輯（`services/`）
3. 實作 repository 層（`repositories/`）
4. 建立 route handler（`app/api/` 或 `routers/`）
5. 加入 input validation（Zod / Pydantic）
6. 加入 auth/permission check
7. 寫 integration test

---

## 新增 React 元件

1. 定義 props interface
2. 建立 storybook story（如有）
3. 實作元件（Server Component 優先）
4. 加入 loading / error / empty states
5. 寫元件測試

---

## Bug Fix

1. 先寫一個能重現 bug 的測試（讓它 fail）
2. 找根本原因
3. 修復
4. 確認測試 pass
5. 檢查有無類似問題存在其他地方
