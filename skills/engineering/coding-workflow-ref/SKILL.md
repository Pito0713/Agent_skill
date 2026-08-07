---
name: coding-workflow-ref
description: |
  常見實作模式速查手冊（API endpoint / React 元件 / bug 修復）。 觸發：查實作模式、怎麼寫 API、component 怎麼做、有沒有範本
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
