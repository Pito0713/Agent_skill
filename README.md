# AI Agent Skill Project

Claude Code 的完整 agent skill 骨架，包含 rules、skills、subagents、hooks、memory。

用於收集、整理、管理 AI coding agent 的行為規範與工作流程 skill。

---

## 目錄結構

```
.
├── CLAUDE.md                          # 頂層入口（Claude Code 自動讀取）
├── .claudeignore                      # Claude 工具掃描排除清單
│
├── rules/                             # Coding 規範
│   ├── coding-standards.md            # 通用規範（常駐）
│   ├── security.md                    # 安全規範 OWASP（常駐）
│   ├── typescript.md                  # TypeScript strict 規範（按需）
│   ├── react.md                       # React functional component 規範（按需）
│   ├── nextjs.md                      # Next.js App Router 規範（按需）
│   ├── python.md                      # Python 3.11+ 規範（按需）
│   ├── testing.md                     # 測試規範（按需）
│   └── git.md                         # Git workflow / commit 規範（按需）
│
├── skills/                            # 工作流程 skills
│   ├── convert-skill.md               # GitHub → 標準格式轉換 SOP
│   ├── _inbox/                        # 待處理的原始收集素材
│   ├── engineering/
│   │   ├── coding-workflow-core.md    # 核心流程守則（常駐，Phase 1-4）
│   │   ├── coding-workflow-ref.md     # 實作模式速查（按需）
│   │   ├── coding-workflow.md         # 完整版（參考用）
│   │   ├── debug.md                   # 系統性除錯流程
│   │   ├── testing-strategy.md        # 測試策略設計
│   │   └── documentation.md           # 文件撰寫模板
│   ├── marketing/                     # 行銷相關 skills（待填充）
│   ├── productivity/
│   │   ├── handoff.md                 # 交接文件生成
│   │   ├── smart-init.md              # Session 初始化
│   │   └── version-log.md             # 版本紀錄更新
│   └── learning/                      # 學習 / 練習導向 skills（按需）
│       └── feedback-loop.md           # 刻意練習立即回饋循環
│
├── agents/                            # 專責 subagents
│   ├── 01-core-development/
│   │   ├── api-architect.md           # API 設計專家
│   │   ├── backend-engineer.md        # 後端工程師
│   │   └── frontend-engineer.md       # 前端工程師（Tailwind / Form / Routing）
│   ├── 02-language-specialists/
│   │   ├── typescript-expert.md       # TS 型別系統專家
│   │   └── python-expert.md           # Python 專家（FastAPI / pytest）
│   ├── 04-security/
│   │   ├── security-auditor.md        # 安全審計（OWASP Top 10）
│   │   └── owasp-reviewer.md          # OWASP 合規報告
│   └── 05-quality-assurance/
│       ├── test-engineer.md           # 測試工程師
│       └── e2e-tester.md              # E2E 測試（Playwright）
│
├── hooks/
│   ├── pre-commit.sh                  # Lint + Type check + Secret scan
│   └── pre-tool-run.sh                # 危險指令攔截
│
├── sources/
│   └── registry.md                    # GitHub skill 來源登記清單
│
└── memory/
    └── project-context.md             # 架構決策歷史
```

---

## 快速開始

### 1. 安裝 pre-commit hook

```bash
cp hooks/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 2. 啟用 Claude Code hooks

建立 `.claude/settings.json`：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "bash hooks/pre-tool-run.sh" }]
      }
    ]
  }
}
```

### 3. 根據技術堆疊按需載入 rules

在對話中引入：

```
@rules/typescript.md   # TypeScript 專案
@rules/python.md       # Python 專案
@rules/git.md          # 進行 commit / PR 時
```

### 4. 新增 GitHub Skill

參考 `sources/registry.md` 登記來源，再依照 `skills/convert-skill.md` 流程轉換格式。

---

## 常駐 vs 按需

| 類型 | 內容 | 說明 |
|------|------|------|
| 常駐 | `rules/coding-standards.md` | 語言無關，每次都適用 |
| 常駐 | `rules/security.md` | 安全規範，不可省略 |
| 常駐 | `skills/engineering/coding-workflow-core.md` | 四階段實作守則 |
| 按需 | `rules/typescript.md` / `python.md` | 依語言選一 |
| 按需 | `rules/git.md` | commit / PR 時才需要 |
| 按需 | `skills/engineering/coding-workflow-ref.md` | 查實作模式時 |
| 按需 | `skills/learning/feedback-loop.md` | 練習 / 刻意改進特定能力時 |

---

## 版本紀錄

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v1.0 | 2026-06-01 | 初始化專案：rules、skills、agents、hooks 基礎骨架 |
| v1.1 | 2026-06-09 | 修復 pre-commit.sh 語法錯誤；補強 frontend-engineer、python-expert agents |
| v1.2 | 2026-06-09 | 重構 skills 分類（engineering / marketing / productivity）；新增 GitHub skill 收集系統 |
| v1.3 | 2026-06-09 | 新增 smart-init、.claudeignore；拆分 coding-workflow-core / ref；CLAUDE.md 常駐/按需架構 |
| v1.4 | 2026-06-09 | 新增 skills/learning/ 分類；建立 feedback-loop skill；更新 README 與 CLAUDE.md 結構 |
