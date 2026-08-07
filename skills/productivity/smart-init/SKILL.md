---
name: smart-init
description: |
  初始化新的工作 session，讀取專案記憶建立工作上下文（完整接手新專案請走 onboarding）。 觸發：session 開始、開始新工作、幫我初始化、smart init
metadata:
  trigger: session 開始需快速建立工作 context 時觸發
  version: "1.0"
  last_updated: "2026-06-09"
---

# Smart Init

建立有效的工作 context，讓 Claude 在 session 開始時掌握全局，避免重複說明。

## 執行步驟

[ ] **讀取專案記憶** - 讀取 memory/project-context.md（如存在）- 確認目前專案目標與背景

[ ] **確認工作範疇**
向使用者詢問：- 這次 session 的主要目標是什麼？- 有無時間限制或優先順序？- 需要繼續上次未完成的工作嗎？

[ ] **載入相關 rules**
依據任務類型自動點名適用規範：- 前端任務 → rules/react.md + rules/typescript.md - 後端任務 → rules/python.md 或 rules/typescript.md - 任何任務 → rules/coding-standards.md + rules/security.md

[ ] **輸出 session 摘要**
確認以下資訊後開始工作：

    ```
    ## Session 初始化完成

    **目標**：<使用者的主要目標>
    **載入規範**：<適用的 rules 列表>
    **注意事項**：<memory 中的重要決策或限制>
    **第一步**：<建議的起始動作>
    ```

## 輸出格式

session 摘要（純文字），確認後直接進入工作，不需要使用者再重複說明背景。
