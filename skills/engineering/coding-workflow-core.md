---
name: coding-workflow-core
description: 實作任何功能的核心流程守則（常駐版）。包含四個強制階段與 commit 前 checklist。
---

# Coding Workflow — Core

所有實作任務的強制流程，不得跳過。

---

## Phase 0：自動偵測技術堆疊（每次 session 開始執行一次）

讀取專案根目錄的設定檔，自動載入對應規範：

| 偵測條件 | 自動載入 |
|---------|---------|
| `tsconfig.json` 或 `*.ts` 存在 | `@rules/typescript.md` |
| `package.json` 含 `"react"` | `@rules/react.md` |
| `next.config.*` 存在 | `@rules/nextjs.md` |
| `requirements.txt` / `pyproject.toml` / `*.py` 存在 | `@rules/python.md` |
| `*.test.*` / `*.spec.*` / `jest.config.*` / `pytest.ini` 存在 | `@rules/testing.md` |
| `.git/` 存在且任務涉及 commit / PR / branch | `@rules/git.md` |
| `package.json` 含 `"react"` / `"vue"` / `"next"` | `@rules/frontend-security.md` |

```bash
# 快速偵測指令（在專案根目錄執行）
ls tsconfig.json next.config.* requirements.txt pyproject.toml 2>/dev/null
grep -s "\"react\"\|\"vue\"\|\"next\"" package.json
find . -maxdepth 2 -name "*.test.*" -o -name "jest.config.*" -o -name "pytest.ini" 2>/dev/null | head -3
```

---

## Phase 1：理解（Understand）

```
[ ] 讀取相關檔案，理解現有架構
[ ] 確認技術堆疊與框架版本（Phase 0 已自動偵測）
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

**Phase 2.5：Tech Lead Mode 判斷（可選）**

若符合 `skills/engineering/tech-lead-mode.md` 啟用條件（預估 >3 檔案 / 曾卡關 / 高風險 / 易 scope creep），詢問使用者是否切換為 tech-lead-mode 執行 Phase 3（工單化 + 委派 executor + close gate），取代直接實作。不符合條件則略過，直接進入 Phase 3。

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
