# GitHub Skill Registry

收集來源清單。每次新增 repo 時在此登記，再依照 `skills/convert-skill.md` 流程處理。

---

## 格式說明

```
### [Repo 名稱](GitHub URL)
- **作者**：
- **說明**：這個 repo 提供什麼
- **收集狀態**：未收集 / 部分收集 / 已完成
- **對應分類**：engineering / marketing / productivity
- **已收錄 Skills**：（收錄後填入檔名）
```

---

## 收集清單

### [Claude-Pro-Optimizer](https://github.com/Shift2Dev/Claude-Pro-Optimizer)

- **作者**：Shift2Dev
- **說明**：Claude Pro token 優化策略，包含 session 初始化、.claudeignore、context 管理
- **收集狀態**：部分收集
- **對應分類**：productivity
- **已收錄 Skills**：`skills/productivity/smart-init.md`

---

### [Ponytail](https://github.com/DietrichGebert/ponytail)

- **作者**：DietrichGebert
- **說明**：Lazy Senior Developer 哲學的 AI agent plugin。透過六關決策梯（YAGNI → stdlib → native → 現有套件 → 一行 → 最小程式碼），強制 AI 在生成程式碼前評估必要性。支援 13 個 AI agent 平台（Claude Code、Cursor、Codex、Windsurf 等）。實測可減少 80–94% 程式碼行數、42–75% API 費用。
- **收集狀態**：部分收集（概念重新設計，非直接引入）
- **對應分類**：engineering
- **已收錄 Skills**：`skills/engineering/lazyengineer.md`、`skills/engineering/lazyengineer-review.md`
- **改寫說明**：原專案命名為 ponytail，本專案改名為 lazyengineer；保留核心決策梯邏輯，移除多平台安裝架構，整合進 code-review Orchestrator（Phase 1.5）
