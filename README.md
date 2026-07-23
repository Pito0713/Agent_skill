# AI Agent Skill Project

**三個 AI coding harness 的共用制度正本**（v5.0 起）：Claude Code / Codex / Antigravity（agy）各持一份薄索引，經 symlink 指向本 repo——任何規則只有一個 source of truth。

包含 rules、skills、agents、governance 制度層、memory。
支援 Orchestrator 模式：單一入口協調多個 skills / agents，完成完整開發流程。

```
                    ~/Agent_skill（唯一正本）
                   /          |            \
      CLAUDE.md(+global)   AGENTS.md      GEMINI.md
            ↓                 ↓               ↓
   ~/.claude/CLAUDE.md  ~/.codex/AGENTS.md  ~/.gemini/GEMINI.md
      （Claude Code）      （Codex）        （Antigravity）
```

---

## 目錄結構

```
.
├── CLAUDE.md                          # Claude Code 索引（本 repo 內自動讀取）
├── CLAUDE.global.md                   # Claude Code 全域極薄指標（symlink 到 ~/.claude/CLAUDE.md）
├── AGENTS.md                          # Codex 索引（symlink 到 ~/.codex/AGENTS.md，全域生效）
├── GEMINI.md                          # Antigravity/agy 索引（symlink 到 ~/.gemini/GEMINI.md，全域生效）
├── setup.sh                           # 全域接線總入口（串接 bin/setup-<harness>.sh）
├── inject.sh                          # 下游注入總入口（串接 bin/inject-<harness>.sh）
│
├── bin/                               # 接線實作（ADR-013：一份共用核心 + 各 harness 薄 adapter）
│   ├── lib-skill-farm.sh              # 共用核心：讀 index / preflight / 建 farm / 清孤兒
│   ├── setup-claude.sh                # Claude 全域：skill farm + rules/governance entry + CLAUDE.md
│   ├── setup-codex.sh                 # Codex 全域：skill farm + AGENTS.md
│   ├── setup-agy.sh                   # agy 全域：GEMINI.md
│   ├── inject-claude.sh               # 下游 .claude/skills + CLAUDE.md managed block（含 @ 常駐）
│   ├── inject-codex.sh                # 下游 .codex/skills + AGENTS.md managed block
│   ├── validate-skill-index.py        # index / llms.txt / package / adapter 四方一致性
│   └── migrate-downstream-paths.sh    # 舊下游 @ 路徑一次性遷移（預設 dry-run）
├── .claudeignore                      # Claude 工具掃描排除清單
│
├── governance/                        # 制度層（v4.5）：調度守則、判斷 rubrics、派工模板、維護協議
│   ├── harness-diagnosis.md           # 診斷依據（為什麼這樣設計）
│   ├── model-orchestration.md         # 模型調度守則（指揮官不下場、派工三件套、升降級）
│   ├── judgment-rubrics.md            # 判斷力外化（R1-R5，附正反例）
│   ├── delegation-templates.md        # 五種任務型態派工模板
│   ├── maintenance-protocol.md        # 制度檔修改權限分級（🟢🟡🔴）
│   ├── lessons.md                     # 踩坑教訓日誌（append-only）
│   └── letter-to-future-sessions.md   # 交接與退化預防
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
│   ├── index.json                     # Machine-readable coverage 正本
│   ├── llms.txt                       # 自然語言 triggers / description
│   ├── convert-skill/SKILL.md         # GitHub → 標準格式轉換 SOP
│   ├── _inbox/                        # 待處理的原始收集素材
│   ├── engineering/<name>/SKILL.md    # 工程與品質 workflow packages
│   ├── design/<name>/SKILL.md         # UI/UX 規劃 packages
│   ├── productivity/<name>/SKILL.md   # 交接與知識工作 packages
│   ├── learning/<name>/SKILL.md       # 學習與 mentor packages
│   └── investing/<name>/SKILL.md      # 投資分析 packages
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

`setup.sh` 是總入口，依序呼叫 `bin/setup-{claude,codex,agy}.sh`。**兩階段全有全無**：
先跑完三個 harness 的 preflight，全數通過才進 install；任一 preflight 失敗就零寫入中止，
不會留下「Claude 接好了、agy 沒接」的半接線狀態。可用
`AGENT_SKILL_HOME=/tmp/test-home bash setup.sh` 做隔離 dry-run，也可單獨執行某個 harness
（`bash bin/setup-codex.sh`）。

| Symlink | 供誰讀 | 由誰建 |
|---------|--------|--------|
| `~/.claude/skills/<name> → repo/skills/<category>/<name>` | Claude Code 單層 native discovery | `setup-claude.sh` |
| `~/.claude/skills/rules → repo/rules` | Claude `@~/.claude/skills/rules/*.md` 常駐路徑 | `setup-claude.sh` |
| `~/.claude/skills/governance → repo/governance` | Claude 舊路徑相容 | `setup-claude.sh` |
| `~/.claude/governance → repo/governance` | Claude Code（制度層）| `setup-claude.sh` |
| `~/.claude/CLAUDE.md → repo/CLAUDE.global.md` | Claude Code 全域（未 inject 的專案也有極薄路由）| `setup-claude.sh` |
| `~/.codex/skills/<name> → repo/skills/<category>/<name>` | Codex 單層 native discovery；保留 `.system` 與第三方 entries | `setup-codex.sh` |
| `~/.codex/AGENTS.md → repo/AGENTS.md` | Codex 全域 | `setup-codex.sh` |
| `~/.gemini/GEMINI.md → repo/GEMINI.md` | Antigravity（agy）全域 | `setup-agy.sh` |

> `rules` / `governance` 兩條**只掛在 Claude**：`@` 常駐語法只認 `~/.claude/skills/` 前綴，
> Codex / agy 走絕對路徑讀正本，不需要。這是拆分後 harness 差異各自收斂的實例。

---

### 2. 在目標專案注入 Claude / Codex adapters

進入你要開發的專案目錄，執行 inject.sh：

```bash
cd ~/my-project
bash ~/Agent_skill/inject.sh
```

`inject.sh` 同樣是總入口，兩階段呼叫 `bin/inject-{claude,codex}.sh`（agy 無下游 adapter，
只吃全域 GEMINI.md）。會在 `.claude/skills` 與 `.codex/skills` 建立單層 per-skill link farm，
並在 `CLAUDE.md`、`AGENTS.md` 最上方維護帶 marker 的薄區塊。既有內容保留；
若任一同名 entry 已被其他內容占用，腳本會在寫入前停止；非同名第三方內容保留。

**常駐載入**：Claude 的 managed block 含兩行 `@` 常駐（`rules/coding-standards.md`、
`rules/security.md`），安全底線不靠模型自覺。Codex 沒有 `@` 語法且 AGENTS.md 有 32KiB 上限，
只能寫成「開工必讀」的文字要求——**兩者強制力不對等**，已知取捨見 ADR-013。

**舊專案遷移**：v5.x 之前注入的專案，其 `@~/.claude/skills/<category>/<name>.md` 路徑在
package 化之後全部失效，且 Claude Code 對不存在的 `@` 路徑靜默略過。用
`bash bin/migrate-downstream-paths.sh <專案路徑>`（預設 dry-run，加 `--apply` 寫入）改寫。

所有 indexed skill 都採 `category/name/SKILL.md` package。`skills/index.json`
是 machine-readable coverage 正本；`skills/llms.txt` 保留自然語言觸發說明，
`bin/validate-skill-index.py` 負責防止兩者 coverage 漂移。

`.codex/hooks.json` 不分發到下游：目前 hook 契約未穩定，避免覆蓋專案設定。
`~/.agents/skills` 視為 legacy discovery root，本流程不讀寫或刪除。

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

參考 `sources/registry.md` 登記來源，再依照 `skills/convert-skill/SKILL.md` 流程轉換格式。

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
| 常駐 | `skills/engineering/coding-workflow-core/SKILL.md` | Phase 0-4 實作守則（含自動偵測）|
| 按需（v4.5 起）| `skills/engineering/agy-assist/SKILL.md` | 搜尋 / 掃大檔 / 交叉驗證時載入（原常駐，降級原因見 governance/harness-diagnosis.md）|
| 自動偵測 | `rules/typescript.md` | tsconfig.json 存在時 |
| 自動偵測 | `rules/react.md` / `nextjs.md` | package.json 含 react / next 時 |
| 自動偵測 | `rules/python.md` | requirements.txt / pyproject.toml 存在時 |
| 自動偵測 | `rules/testing.md` | *.test.* / jest.config.* / pytest.ini 存在時 |
| 自動偵測 | `rules/git.md` | 任務涉及 commit / PR / branch 時 |
| 自動偵測 | `rules/frontend-security.md` | package.json 含 react / vue / next 時 |
| 按需 | `skills/engineering/coding-workflow-ref/SKILL.md` | 查實作模式時 |
| 按需 | `skills/engineering/tech-lead-mode/SKILL.md` | 卡關 / 跨檔案 / 高風險任務容易 scope creep 時（工單化 + executor 委派 + close gate）|
| 按需 | `skills/engineering/lazyengineer/SKILL.md` | 精簡程式碼 / 反 over-engineering 時（實測 -65–90% output tokens）|
| 按需 | `skills/engineering/lazyengineer-review/SKILL.md` | 掃描過度設計 / 找可刪的程式碼時 |
| 按需 | `skills/learning/feedback-loop/SKILL.md` | 刻意練習 / 改進特定能力時 |
| 按需 | `skills/learning/concrete-example/SKILL.md` | 邏輯看不懂 / 反覆出錯時 |

---

## 注入後的 CLAUDE.md 規格

注入區塊的**單一事實來源是 `bin/inject-claude.sh` 的 `MANAGED_BLOCK`**（Codex 側在
`bin/inject-codex.sh`），本節不重複維護完整清單（避免漂移）。結構摘要：

```markdown
<!-- agent-skill:begin -->
## Agent Skill adapter（claude）

@~/.claude/skills/rules/coding-standards.md
@~/.claude/skills/rules/security.md

其餘 skill 優先使用 native discovery；未命中時讀 index.json 再載入 SKILL.md。
<!-- agent-skill:end -->

（marker 之後為專案原有內容，注入時原樣保留）
```

> 只有安全底線兩條走 `@` 常駐，其餘一律 native discovery——說出觸發詞即可，不需要在此列出。
> 重跑 inject 只會替換 marker 內的區塊，marker 外的內容不動。
> `rules/` 與 `governance/` 由 `setup-claude.sh` 掛進 link farm（`~/.claude/skills/rules`、
> `~/.claude/skills/governance`），下游 `@~/.claude/skills/rules/...` 路徑因此有效；
> `~/.claude/governance` 一級 symlink（v4.9）保留，兩條路徑皆可用。

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
| v2.7 | 2026-06-22 | 對標 gsap-skills 架構：新增 skills/llms.txt（25 個 skill 統一索引）；新增多平台 agent 入口（AGENTS.md / GEMINI.md / .github/copilot-instructions.md）；5 個核心 skill 加入 ✅/❌ 對照區塊（debug-flow / code-review / security-review / new-feature / lazyengineer）；CLAUDE.md 快速入口大表精簡為 llms.txt 單行引用 |
| v2.8 | 2026-06-22 | gemini-assist 模式 C 加入 Claude Subagent Fallback：agy 不可用時強制走冷啟動 subagent 審查，交叉驗證不得直接跳過；補充 Subagent prompt 模板與輸出標示規範 |
| v2.9 | 2026-06-23 | gemini-assist 三個模式加入明確 timeout 機制：模式 A agy 90s/Bash 120s、模式 B agy 4m/Bash 270s、模式 C agy 3m/Bash 210s；修正 agy 預設 5m 與 Bash 預設 2m 衝突導致靜默 kill 的問題 |
| v3.0 | 2026-06-24 | 新增 RAG 知識庫（knowledge/）與 rag-search skill；Grep-based 檢索，零外部依賴 |
| v3.1 | 2026-06-25 | 新增跨專案進度追蹤：~/.agent-sessions/ 快照機制、project-dashboard skill、inject.sh 安裝 post-commit hook |
| v3.2 | 2026-06-25 | inject.sh 全面升級（heredoc 修復、prompt_productivity 互動、Python 保留使用者啟用項）；git.md / handoff.md / version-log.md 升常駐；convert-skill.md 四處同步 checklist；version-log 加前置判斷 |
| v3.3 | 2026-06-29 | 新增 Obsidian 整合：obsidian-query（搜尋歷史筆記）+ obsidian-save（寫入知識） |
| v3.4 | 2026-06-30 | VAULT_PATH 改為 .env 讀取（移除 hardcode）；新增 .env.example 範本與 .gitignore；skill 內建 .env 缺失教學，適合公開專案 |
| v3.5 | 2026-06-30 | 新增 academic-mentor skill：學術導師模式，四段結構（機制→文獻→社會影響→深化提問），確定性分級（✅⚠️❓🚫），主動糾正常見迷思，絕不捏造文獻 |
| v3.6 | 2026-06-30 | obsidian-save 新增 academic-mentor 專屬學術模板（Phase 0 自動偵測來源、欄位對應、存入 knowledge/<領域>/ 而非 inbox/）|
| v3.7 | 2026-06-30 | academic-mentor 強化規格：介入確定性上限原則（機制確定性不移轉介入）、解剖範圍聲明規則、期刊改名標注、Checklist 擴充至 12 項 |
| v3.8 | 2026-07-01 | gemini-assist 模式 A 搜尋/格式化分離（agy 只取英文原始資料，Claude 負責翻譯與整合）；全模式 timeout 拉到 Bash 上限：A agy 5m/Bash 360s、B/C agy 9m/Bash 570s |
| v3.9 | 2026-07-01 | 新增 mentor-neuro 神經科學專屬導師：Phase 0 自動讀取 knowledge/neuro/ vault 上下文、六區塊回覆結構（定位聲明→機制鏈→文獻定錨→行為橋接→知識圖譜節點）、神經迷思雷達（7 條）、確定性三鐵律（fMRI≠因果 / 動物跨物種降級 / 機制不移轉介入）|
| v4.0 | 2026-07-01 | 新增 mentor-society 社會科學專屬導師：確定性天花板 ⚠️（觀察性研究為主流）、七區塊結構（研究方法盤點→競爭解釋框架→脈絡聲明）、社會科學四鐵律（相關≠因果 / 單一文化≠普遍 / 短期≠長期 / 高異質 meta 降級）、社會迷思雷達（7 條）|
| v4.1 | 2026-07-01 | 新增 mentor-science 自然科學專屬導師：定律/理論/模型/假說嚴格區分、第一原理推導鏈、適用範圍與邊界條件聲明、科學三鐵律（模型≠現實 / 自然≠安全 / 相關≠因果）、科學迷思雷達（8 條）、概念層次知識圖譜 |
| v4.2 | 2026-07-02 | 新增 mentor-tech 科技與工程專屬導師：tradeoff 矩陣為核心、技術知識七分類（標準/演算法/benchmark/模式/慣例/趨勢/廠商宣稱）、三鐵律（效能比較附條件 / Best Practice 有時效 / 技術可行≠工程適合）、工程迷思雷達（8 條）、與 coding-workflow 的概念/實作分工界線 |
| v4.3 | 2026-07-02 | 新增 mentor-invest 投資策略專屬導師：行為偏誤掃描優先於策略討論、四鐵律（過去報酬≠未來 / 報酬附風險 / 時間軸改變結論 / 市場預測永遠❓）、7 條行為偏誤表（含 Nobel 研究）、投資迷思雷達（7 條）、跨域連結 neuro/society、個人情境聲明與免責說明 |
| v4.4 | 2026-07-03 | 新增 tech-lead-mode 執行策略 skill：工單化（範圍/禁區/驗收條件）、executor 委派（subagent worktree / agy 臨時授權）、reviewer 發現逐條仲裁、close gate 三選一（CLOSE/REOPEN/ESCALATE）；接線至 coding-workflow-core / new-feature / debug-flow |
| v4.5 | 2026-07-03 | 新增 governance/ 制度層（7 檔）：harness 診斷、模型調度守則、判斷力 rubrics（R1-R5）、派工模板、維護協議、lessons 日誌、給未來 session 的信；CLAUDE.md 精簡為 48 行純路由；gemini-assist 由常駐降為按需；經冷啟動 subagent 對抗審查修正 7 項 |
| v4.6 | 2026-07-04 | 全面功能性 review：修復 rules/ 斷鏈（新增 skills/rules → ../rules symlink，下游 @~/.claude/skills/rules/... 路徑恢復有效）；code-review Phase 5 改冷啟動交叉驗證（對齊 governance 獨立性原則）；5 個 orchestrator 內嵌 agy 指令補 $CLI_CMD 偵測與 timeout；orchestrator Phase 0 偵測表去重複（指向 coding-workflow-core 單一事實來源）；convert-skill 移除 CLAUDE.md 同步項（對齊 maintenance-protocol）；obsidian-save 補專科 mentor 偵測與 tech/invest 目錄；agents frontmatter 過時模型名更新；deploy-prep Phase 6 diff 範圍改 release tag..HEAD；rag-search 補 frontmatter；llms.txt 補 debug 索引與 onboarding/smart-init 歧義樹；README/setup.sh 過時常駐清單同步 |
| v4.7 | 2026-07-04 | governance/ 分發到下游：新增 skills/governance → ../governance 相對 symlink（比照 v4.6 rules/ 模式，零腳本改動）；inject.sh INJECT_BLOCK 加「制度層路由」段（用到才讀，不 @ 常駐）；既有下游專案重跑 inject.sh 即取得路由 |
| v4.8 | 2026-07-04 | harness 適配層：model-orchestration §2 改 Claude Code / Antigravity 雙欄參數適配表（subagent 類型 / 隔離 / model 逐次指定差異）+ 派發後等待紀律；tech-lead-mode Phase 2 標註語法歸屬並附 Antigravity 等價參數；coding-workflow-core Phase 0 改原生唯讀工具優先、shell 降 fallback（避免核准制 harness 開局卡點擊）；ADR-008 |
| v4.9 | 2026-07-06 | governance 分發改一級路徑：setup.sh 直建 `~/.claude/governance` symlink、inject.sh 路由改指 `~/.claude/governance/...`（原 skills/governance 巢狀路徑保留相容）；修復 setup.sh 檢查順序缺陷（實體目錄擋路時半途退出會刪掉 skills symlink 未重建 → 檢查全部前置）；ADR-007 修訂 |
| v5.0 | 2026-07-07 | 三 harness 制度統一（ADR-009）：setup.sh 增建 `~/.codex/AGENTS.md`、`~/.gemini/GEMINI.md` 全域 symlink；AGENTS.md / GEMINI.md 改寫為薄索引（絕對路徑 + harness 專屬區塊）；agy 升級完整 harness（excludeTools 解鎖）；model-orchestration 補 Codex 欄 + 三 harness 型號表 + 跨 harness 分工；maintenance-protocol §6 記憶回寫正本表（交接正本 = ~/.agent-sessions/）+ §7 索引防漂移四查；harness-diagnosis 三家差異診斷 |
| v5.0.1 | 2026-07-07 | agy 對抗審查修正（8 條發現：6 修 / 1 駁回 / 1 已知取捨）：三索引鐵律加「專案規則優先、安全底線不得放寬」；交接檔 `<專案>` 定義與無鎖併發合併規約；§7 補 16KB 大小檢查；lessons 精簡觸發時機 |
| v5.0.2 | 2026-07-07 | Claude 全域載入點補齊：新增 CLAUDE.global.md（18 行極薄指標，不常駐載入），setup.sh 第五條 symlink `~/.claude/CLAUDE.md`——三家全域覆蓋對稱 |
| v5.1 | 2026-07-23 | skill package 化（ADR-012）：38 個 skill 統一 `category/name/SKILL.md`；新增 `skills/index.json` machine coverage 正本與 `bin/validate-skill-index.py`；Claude/Codex 改單層 link farm native discovery |
| v5.2 | 2026-07-23 | 接線腳本按 harness 拆分（ADR-013）：`bin/lib-skill-farm.sh` 共用核心 + `bin/{setup,inject}-<harness>.sh` 薄 adapter，`setup.sh`/`inject.sh` 降為總入口並改**兩階段全有全無**（先全 preflight 再全 install）；修復三缺陷——① `rules`/`governance` 掛回 Claude farm，舊 `@` 常駐路徑不再靜默斷鏈 ② 半接線中間態改零寫入中止 ③ 孤兒 entry 自動清除且 validator 會 FAIL；新增 `bin/migrate-downstream-paths.sh` 遷移舊下游專案；inject 恢復兩條安全底線常駐 |
