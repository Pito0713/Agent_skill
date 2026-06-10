# AI Agent Skill Project

Claude Code 的完整 agent skill 骨架，包含 rules、skills、subagents、hooks、memory。

用於收集、整理、管理 AI coding agent 的行為規範與工作流程 skill。

---

## 目錄結構

```
.
├── CLAUDE.md                          # 頂層入口（Claude Code 自動讀取）
├── setup.sh                           # 一鍵連結 skills 到 ~/.claude/skills/
├── inject.sh                          # 在目標專案注入常駐 skill 設定
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
│   ├── design/                        # UI/UX 設計規劃 skills（按需）
│   │   ├── wireframing.md             # 頁面版面結構規劃
│   │   ├── ui-visual-design.md        # 視覺風格選定與規格輸出
│   │   └── information-architecture.md # 導航層級與 API 路由規劃
│   ├── productivity/
│   │   ├── handoff.md                 # 交接文件生成
│   │   ├── smart-init.md              # Session 初始化
│   │   └── version-log.md             # 版本紀錄更新
│   └── learning/                      # 學習 / 練習導向 skills（按需）
│       ├── feedback-loop.md           # 刻意練習立即回饋循環
│       └── concrete-example.md        # 具體情境舉例（A/B 方案）
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
├── sources/
│   └── registry.md                    # GitHub skill 來源登記清單
│
└── memory/
    └── project-context.md             # 架構決策歷史
```

---

## 快速開始

### 1. Clone 並執行 Setup

```bash
git clone https://github.com/Pito0713/Agent_skill.git
cd Agent_skill
bash setup.sh
```

Setup 會將 `skills/` 連結到 `~/.claude/skills/`，讓本機所有專案都能引用。

---

### 2. 在目標專案注入 CLAUDE.md

進入你要開發的專案目錄，執行 inject.sh：

```bash
cd ~/my-project
bash ~/Agent_skill/inject.sh
```

**inject.sh 的行為：**

| 情境 | 行為 |
|------|------|
| 專案沒有 CLAUDE.md | 自動生成含常駐 skill 的模板 |
| 專案已有 CLAUDE.md | 顯示預覽，詢問確認後注入到最上方 |
| 已注入過 | 跳過，不重複注入 |

注入後的 CLAUDE.md 會包含：
- **常駐載入**：`coding-standards`、`security`、`coding-workflow-core`（自動生效）
- **按需載入**：其餘 skills 以註解列出，移除 `#` 即可啟用

---

### 3. 更新 Skills

```bash
cd Agent_skill
git pull
```

Symlink 指向原始檔，`git pull` 後**立即生效**，不需重新執行 setup。

---

### 4. 新增 GitHub Skill（可選）

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
| 按需 | `skills/design/*` | UI/UX 設計規劃（wireframe、視覺、IA）|

---

## 版本紀錄

| 版本 | 日期 | 主要變更 |
|------|------|---------|
| v1.0 | 2026-06-01 | 初始化專案：rules、skills、agents、hooks 基礎骨架 |
| v1.1 | 2026-06-09 | 修復 pre-commit.sh 語法錯誤；補強 frontend-engineer、python-expert agents |
| v1.2 | 2026-06-09 | 重構 skills 分類（engineering / marketing / productivity）；新增 GitHub skill 收集系統 |
| v1.3 | 2026-06-09 | 新增 smart-init、.claudeignore；拆分 coding-workflow-core / ref；CLAUDE.md 常駐/按需架構 |
| v1.4 | 2026-06-09 | 新增 skills/learning/ 分類；建立 feedback-loop skill；更新 README 與 CLAUDE.md 結構 |
| v1.5 | 2026-06-09 | 新增 skills/design/ 分類；收錄 wireframing、ui-visual-design、information-architecture |
| v1.6 | 2026-06-09 | 新增 concrete-example skill（具體情境舉例 + A/B 方案框架）|
| v1.7 | 2026-06-09 | 移除 hooks/ 目錄（Claude Code 已內建危險指令防護）|
| v1.8 | 2026-06-09 | 新增 setup.sh（一鍵 symlink 到 ~/.claude/skills/）；更新 README 安裝與更新說明 |
| v1.9 | 2026-06-09 | 新增 inject.sh（自動生成或注入 CLAUDE.md 到目標專案）|
