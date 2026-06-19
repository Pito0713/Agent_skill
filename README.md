# AI Agent Skill Project

Claude Code 的完整 agent skill 骨架，包含 rules、skills、subagents、memory。

用於收集、整理、管理 AI coding agent 的行為規範與工作流程 skill。
支援 Orchestrator 模式：單一入口協調多個 skills / agents，完成完整開發流程。

---

## 目錄結構

```
.
├── CLAUDE.md                          # 頂層入口（Claude Code 自動讀取）
├── setup.sh                           # 一鍵連結 skills 到 ~/.claude/skills/
├── inject.sh                          # 在目標專案注入常駐 skill 設定
├── .claudeignore                      # Claude 工具掃描排除清單
│
├── rules/                             # Coding 規範（自動偵測載入）
│   ├── coding-standards.md            # 通用規範（常駐）
│   ├── security.md                    # 安全規範 OWASP（常駐）
│   ├── frontend-security.md           # 前端資安：XSS / CSP / CORS / PII（按需）
│   ├── typescript.md                  # TypeScript strict 規範（自動偵測）
│   ├── react.md                       # React functional component 規範（自動偵測）
│   ├── nextjs.md                      # Next.js App Router 規範（自動偵測）
│   ├── python.md                      # Python 3.11+ 規範（自動偵測）
│   ├── testing.md                     # 測試規範（自動偵測）
│   └── git.md                         # Git workflow / commit 規範（自動偵測）
│
├── skills/                            # 工作流程 skills
│   ├── convert-skill.md               # GitHub → 標準格式轉換 SOP
│   ├── _inbox/                        # 待處理的原始收集素材
│   ├── engineering/
│   │   ├── coding-workflow-core.md    # 核心流程守則（常駐，Phase 0-4）
│   │   ├── coding-workflow-ref.md     # 實作模式速查（按需）
│   │   ├── coding-workflow.md         # 完整版（參考用）
│   │   ├── gemini-assist.md           # AI 分工協作 — Antigravity CLI（常駐實驗）
│   │   ├── code-review.md             # ★ Code Review 協調器（Orchestrator）
│   │   ├── new-feature.md             # ★ 新功能開發協調器（Orchestrator）
│   │   ├── debug-flow.md              # ★ 除錯流程協調器（Orchestrator）
│   │   ├── deploy-prep.md             # ★ 上線前檢查協調器（Orchestrator）
│   │   ├── security-review.md         # ★ 安全審查協調器（Orchestrator）
│   │   ├── lazyengineer.md            # Lazy Senior Dev 模式（決策梯 + token 節省）
│   │   ├── lazyengineer-review.md     # Over-Engineering 偵測（可刪清單）
│   │   ├── debug.md                   # 系統性除錯流程（被 debug-flow 協調）
│   │   ├── testing-strategy.md        # 測試策略規劃，只輸出計畫（被 Orchestrator 協調）
│   │   └── documentation.md           # 文件撰寫模板（被 Orchestrator 協調）
│   ├── marketing/                     # 行銷相關 skills（待填充）
│   ├── design/                        # UI/UX 設計規劃 skills
│   │   ├── ui-design-flow.md          # ★ UI 設計規劃協調器（Orchestrator）
│   │   ├── wireframing.md             # 頁面版面結構規劃（被 Orchestrator 協調）
│   │   ├── ui-visual-design.md        # 視覺風格選定與規格輸出（被 Orchestrator 協調）
│   │   └── information-architecture.md # 導航層級與 API 路由規劃（被 Orchestrator 協調）
│   ├── productivity/
│   │   ├── onboarding.md              # ★ 接手新專案協調器（Orchestrator）
│   │   ├── handoff.md                 # 交接文件生成
│   │   ├── smart-init.md              # Session 初始化
│   │   └── version-log.md             # 版本紀錄更新
│   └── learning/                      # 學習 / 練習導向 skills（按需）
│       ├── feedback-loop.md           # 刻意練習立即回饋循環
│       └── concrete-example.md        # 具體情境舉例（A/B 方案）
│
├── agents/                            # 專責 subagents（被 Orchestrator 協調）
│   ├── 01-core-development/
│   │   ├── api-architect.md           # API 設計專家
│   │   ├── backend-engineer.md        # 後端工程師
│   │   └── frontend-engineer.md       # 前端工程師（Tailwind / Form / Routing）
│   ├── 02-language-specialists/
│   │   ├── typescript-expert.md       # TS 型別系統專家
│   │   └── python-expert.md           # Python 專家（FastAPI / pytest）
│   ├── 04-security/
│   │   ├── security-auditor.md        # 後端快速安全掃描（PR/commit 前）
│   │   ├── owasp-reviewer.md          # OWASP 整體合規報告（上線前 / security sprint）
│   │   └── frontend-security-auditor.md # 前端資安審計（XSS / CORS / CSP / PII）
│   └── 05-quality-assurance/
│       ├── test-engineer.md           # 測試工程師（依計畫實作，不設計策略）
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
| 專案已有 CLAUDE.md，未注入過 | 顯示預覽，詢問確認後注入到最上方 |
| 已注入過舊版 | 顯示現有 vs 新版對比，詢問確認後精確替換區塊 |

注入後的 CLAUDE.md 會包含：
- **常駐載入**：`coding-standards`、`security`、`coding-workflow-core`、`gemini-assist`（自動生效）
- **按需載入**：其餘 skills 以註解列出，移除 `#` 即可啟用

---

### 3. 更新 Skills

```bash
cd Agent_skill
git pull
```

Symlink 指向原始檔，`git pull` 後**立即生效**，不需重新執行 setup。

---

### 4. 安裝 Antigravity CLI（agy）

本專案使用 `agy` 進行 AI 分工協作（網路搜尋 / 大檔掃描 / 交叉驗證）：

```bash
# 安裝
curl -fsSL https://antigravity.google/cli/install.sh | bash

# 加入 PATH
echo 'export PATH="$PATH:/Users/$USER/.local/bin"' >> ~/.zshrc
source ~/.zshrc

# 驗證
agy --version

# 初次認證
agy
```

> **注意**：Gemini CLI 已於 2026-06-18 停止服務，請務必遷移至 `agy`。

---

### 5. 新增 GitHub Skill（可選）

參考 `sources/registry.md` 登記來源，再依照 `skills/convert-skill.md` 流程轉換格式。

---

## Orchestrator 架構

本專案採用 **Orchestrator Skill** 模式：一個入口 skill 協調多個 skills / agents，完成端到端流程。

```
使用者說出觸發詞
      ↓
Orchestrator Skill（入口）
      ↓
Phase 0 → Phase 1 ──→ Phase N
   ↓          ↓     ↑       ↓
rules      agents  ⏭       agy 交叉驗證
載入       委派   跳過條件   最終輸出
              ↓
           🚫 CRITICAL GATE
         （發現嚴重問題 → 停止）
```

每個 Phase 開頭皆標注 **⏭ 跳過條件**，滿足條件時自動略過該 phase，避免不必要的 token 消耗。安全相關 Phase 額外設有 **🚫 CRITICAL GATE**，發現 CRITICAL 問題時強制詢問是否繼續。

### 可用 Orchestrators

| Orchestrator | 觸發詞 | 協調資源 |
|------|------|------|
| `new-feature.md` | 「新增功能」、「實作 X」 | api-architect、backend/frontend-engineer、testing-strategy、documentation、agy |
| `code-review.md` | 「code review」、「PR review」 | security-auditor、frontend-security-auditor、lazyengineer-review（Phase 1.5）、testing、git、agy |
| `debug-flow.md` | 「bug」、「為什麼錯」、「找不到原因」 | debug、concrete-example、agy 模式B/C |
| `deploy-prep.md` | 「要上線了」、「deploy 前」 | code-review、security-auditor、e2e-tester、version-log、agy |
| `security-review.md` | 「安全審查」、「OWASP」、「XSS」、「前端安全」 | security-auditor、frontend-security-auditor、owasp-reviewer |
| `ui-design-flow.md` | 「規劃 UI」、「設計這個頁面」 | information-architecture、wireframing、ui-visual-design、frontend-engineer、agy |
| `onboarding.md` | 「接手專案」、「幫我了解這個 repo」 | agy 模式B、information-architecture、handoff |

---

## Lazy Engineer 模式

靈感來自 [Ponytail](https://github.com/DietrichGebert/ponytail)，針對本專案重新設計的「最小化實作」規範。

### 決策梯

每次生成程式碼前，AI 必須依序通過六關：

```
1. 這個需要存在嗎？       → YAGNI
2. stdlib 有提供嗎？      → 用標準庫
3. 平台原生功能有嗎？     → 用內建
4. 現有套件能做嗎？       → 複用依賴
5. 一行能搞定嗎？         → 最小化
6. 才寫最小必要程式碼
```

### 實測 Token 節省（agy 實際測量）

| 任務類型 | 正常模式 | lazyengineer | 節省 |
|---|---|---|---|
| Email 驗證 | 590 行（含測試）/ ~4,500 tokens | 9 行 / ~425 tokens | **↓ 90%** |
| Debounce 函式 | 168 行 / ~1,844 tokens | 89 行 / ~954 tokens | **↓ 48%** |
| 加權平均 | — | — | **↓ 65–70%** |

> Output token 比 input token 貴 3–5 倍，此數字直接反映 API 費用節省。

### 使用方式

```
說出「lazyengineer」或「精簡一下」→ 啟用決策梯（full 模式）
說出「有沒有過度設計」或「可以刪什麼」→ 啟用 lazyengineer-review

lazyengineer [lite|full|ultra|off]
```

### 適用場景

| ✅ 適合 | ❌ 不適合 |
|---|---|
| Prototype / MVP | 上線功能（邊界條件要完整）|
| 內部工具 / script | 對外 library（型別需完整）|
| 需求明確的小功能 | 安全敏感功能 |

---

## 常駐 vs 按需 vs 自動偵測

| 類型 | 內容 | 說明 |
|------|------|------|
| 常駐 | `rules/coding-standards.md` | 語言無關，每次都適用 |
| 常駐 | `rules/security.md` | 安全規範，不可省略 |
| 常駐 | `skills/engineering/coding-workflow-core.md` | Phase 0-4 實作守則（含自動偵測）|
| 常駐（實驗）| `skills/engineering/gemini-assist.md` | AI 分工協作（agy）|
| 自動偵測 | `rules/typescript.md` | tsconfig.json 存在時 |
| 自動偵測 | `rules/react.md` / `nextjs.md` | package.json 含 react / next 時 |
| 自動偵測 | `rules/python.md` | requirements.txt / pyproject.toml 存在時 |
| 自動偵測 | `rules/testing.md` | *.test.* / jest.config.* / pytest.ini 存在時 |
| 自動偵測 | `rules/git.md` | 任務涉及 commit / PR / branch 時 |
| 自動偵測 | `rules/frontend-security.md` | package.json 含 react / vue / next 時 |
| 按需 | `skills/engineering/coding-workflow-ref.md` | 查實作模式時 |
| 按需 | `skills/engineering/lazyengineer.md` | 精簡程式碼 / 反 over-engineering 時（實測 -65–90% output tokens）|
| 按需 | `skills/engineering/lazyengineer-review.md` | 掃描過度設計 / 找可刪的程式碼時 |
| 按需 | `skills/learning/feedback-loop.md` | 刻意練習 / 改進特定能力時 |
| 按需 | `skills/learning/concrete-example.md` | 邏輯看不懂 / 反覆出錯時 |

---

## 注入後的 CLAUDE.md 規格

`inject.sh` 在目標專案生成的 CLAUDE.md 包含以下結構：

```markdown
## 常駐載入（Agent Skill）

@~/.claude/skills/rules/coding-standards.md
@~/.claude/skills/rules/security.md
@~/.claude/skills/engineering/coding-workflow-core.md
@~/.claude/skills/engineering/gemini-assist.md

## 按需載入（視任務加入）

# @~/.claude/skills/rules/typescript.md         # TypeScript 專案
# @~/.claude/skills/rules/python.md             # Python 專案
# @~/.claude/skills/rules/git.md                # commit / PR 時
# @~/.claude/skills/engineering/coding-workflow-ref.md   # 查實作模式
# @~/.claude/skills/learning/feedback-loop.md            # 刻意練習
# @~/.claude/skills/learning/concrete-example.md         # 邏輯舉例說明
# @~/.claude/skills/design/wireframing.md                # 頁面規劃
# @~/.claude/skills/design/ui-visual-design.md           # 視覺風格
# @~/.claude/skills/design/information-architecture.md   # 導航架構
```

> 移除 `#` 即可啟用對應按需 skill。Orchestrator skills 不需要在此列出，說出觸發詞即可自動執行。

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
| v2.0 | 2026-06-12 | 新增 gemini-assist skill（AI 分工協作：網路搜尋 / 大檔掃描 / 對抗式審查）；設為常駐實驗性載入 |
| v2.1 | 2026-06-15 | 新增 frontend-security rule + auditor agent；coding-workflow-core 加入 Phase 0 自動偵測堆疊 |
| v2.2 | 2026-06-15 | 新增 5 個 Orchestrator skills（code-review / new-feature / debug-flow / deploy-prep / ui-design-flow / onboarding）|
| v2.3 | 2026-06-15 | Gemini CLI → Antigravity CLI（agy）全面遷移；新增 agy 安裝說明；更新 README 架構說明 |
| v2.4 | 2026-06-16 | 為全部 6 個 Orchestrator 加入 Phase 跳過條件（17 條）及 CRITICAL Gate（5 個）；agy 交叉驗證確認設計合理性；預估節省 15–20% token 消耗 |
| v2.5 | 2026-06-17 | 新增 lazyengineer / lazyengineer-review skill（靈感來自 Ponytail）；gemini-assist 加入三層 CLI 偵測（agy → ~/.local/bin/agy → gemini）；code-review 加入 Phase 1.5 over-engineering 掃描；實測節省 65–90% output token |
| v2.6 | 2026-06-20 | 修復三個工程邊界問題：新增 security-review orchestrator 統一安全審查入口；釐清 security-auditor（快速掃描）vs owasp-reviewer（合規報告）職責邊界；切分 testing-strategy（只輸出計畫）vs test-engineer（只負責實作）；修正 CLAUDE.md 雙路徑委派問題 |
