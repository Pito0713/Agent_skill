# AI Agent Skill Project

Claude Code 的完整 agent skill 骨架，包含 rules、skills、subagents、hooks、memory。

## 目錄結構

```
.
├── CLAUDE.md                          # 頂層入口（Claude Code 自動讀取）
├── .claude/
│   └── settings.json                  # hooks 設定
│
├── rules/                             # Coding 規範
│   ├── coding-standards.md            # 通用規範（所有語言適用）
│   ├── typescript.md                  # TypeScript strict 規範
│   ├── react.md                       # React functional component 規範
│   ├── nextjs.md                      # Next.js App Router 規範
│   ├── python.md                      # Python 3.11+ 規範
│   ├── security.md                    # 安全規範（OWASP）
│   ├── testing.md                     # 測試規範（金字塔策略）
│   └── git.md                         # Git workflow / commit 規範
│
├── skills/                            # 工作流程 skills
│   ├── coding-workflow.md             # 新功能實作標準流程
│   ├── debug.md                       # 系統性除錯流程
│   ├── testing-strategy.md            # 測試策略設計
│   ├── documentation.md               # 文件撰寫模板
│   └── handoff.md                     # 交接文件生成
│
├── agents/                            # 專責 subagents
│   ├── 01-core-development/
│   │   ├── api-architect.md           # API 設計專家
│   │   ├── backend-engineer.md        # 後端工程師
│   │   └── frontend-engineer.md       # 前端工程師
│   ├── 02-language-specialists/
│   │   ├── typescript-expert.md       # TS 型別系統專家
│   │   └── python-expert.md           # Python 專家
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
└── memory/
    └── project-context.md             # 架構決策歷史
```

## 快速開始

### 1. 複製到你的專案

```bash
# 複製整個骨架到你的專案
cp -r your-project/

```

### 2. 安裝 pre-commit hook

```bash
cp hooks/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 3. 填入專案資訊

```bash
# 更新專案架構決策
vim memory/project-context.md
```

### 4. 根據技術堆疊調整 rules/

- 純 Node.js 後端：保留 `typescript.md`、刪 `react.md`、`nextjs.md`
- Python 專案：保留 `python.md`、刪 `typescript.md`、`react.md`、`nextjs.md`
- 全端 Next.js：全部保留

## 使用方式

### 呼叫 Skills

在 Claude Code 中：

```
執行 skills/coding-workflow.md
```

### 委派 Subagent

```
使用 agents/04-security/security-auditor.md 審查 src/api/users.ts
```

### 查看規範

```
根據 rules/typescript.md，幫我 review 這個函式
```
