# Project Context

> 專案架構、技術選型、重要決策的完整記錄。  
> 這是「為什麼這樣設計」的真相文件。

---

## 跨專案進度追蹤（v3.1）

- 快照路徑：`~/.agent-sessions/<project>/latest.md`
- 完整寫入觸發：`handoff` skill、`version-log` skill（commit）
- 輕量寫入觸發：git post-commit hook（metadata only，無 Claude）
- 聚合 skill：`skills/productivity/project-dashboard.md`
- hook 安裝方式：`inject.sh` 執行時自動安裝至 `.git/hooks/post-commit`

---

## RAG 知識庫（v3.0）

- 採用 Grep-based 檢索，不引入外部 vector DB
- 知識庫路徑：`knowledge/`，分三類：engineering / security / workflow
- 搜尋 skill：`skills/productivity/rag-search.md`
- 決策原因：符合現有 Bash + Markdown 架構，零依賴，可立即使用

### TODO：評估升級至 Embedding + Vector DB

**觸發條件（滿足任一才考慮做）：**
- `knowledge/` 文件超過 30-50 個，關鍵字搜尋開始難以管理
- 出現「明明有這個規範但 grep 找不到」的回報
- 使用者問法多變、中英混用導致命中率低

**技術選項（已評估）：**
- Option A 本地：Chroma + Ollama `nomic-embed-text`（零費用、資料不出去）
- Option B 雲端：OpenAI `text-embedding-3-small` + Pinecone 免費方案（快速驗證）
- Option C DB 整合：PostgreSQL + pgvector extension（已有 PG 時首選）

**現況判斷（2026-06-24）：** 4 個文件，Grep 已足夠，暫不執行。

---

## 架構概覽

```
（填入系統架構圖或文字描述）

例：
Frontend (Next.js) → API Layer (Next.js API Routes / FastAPI)
                          ↓
                   Service Layer（業務邏輯）
                          ↓
                   Repository Layer（資料存取）
                          ↓
                   PostgreSQL + Redis Cache
```

---

## 技術選型記錄

### 前端框架

**選擇**：（填入）  
**考慮過**：（填入其他選項）  
**選擇原因**：（填入）  
**日期**：（填入）

---

### 資料庫

**選擇**：（填入）  
**考慮過**：（填入）  
**選擇原因**：（填入）  
**日期**：（填入）

---

### 認證方案

**選擇**：（填入）  
**考慮過**：（填入）  
**選擇原因**：（填入）  
**日期**：（填入）

---

## 重要架構決策（ADRs）

### ADR-001：採用 Orchestrator Skill 模式

**狀態**：已接受  
**日期**：2026-06-15

**背景**：原本的 skills 各自獨立，使用者需要手動決定呼叫哪個 skill，流程零散。

**決策**：建立 6 個 Orchestrator（code-review / new-feature / debug-flow / deploy-prep / ui-design-flow / onboarding），各自作為單一入口，協調多個子 skill / agent 完成端到端流程。

**後果**：
- 正面：使用者只需說出觸發詞，不需了解底層 skill 結構
- 負面/注意：Orchestrator 本身的維護成本較高，Phase 定義需保持一致

---

### ADR-002：Phase 跳過條件（Skip Conditions）

**狀態**：已接受  
**日期**：2026-06-16

**背景**：所有 Orchestrator 在早期版本中無論情境如何都執行全部 Phase，造成不必要的 token 消耗。

**決策**：為 6 個 Orchestrator 的可選 Phase 各加入 `⏭ 跳過條件`（共 17 條）與 `🚫 CRITICAL GATE`（5 個）。agy 交叉驗證確認設計合理性。

**後果**：
- 正面：預估節省 15–20% token，CRITICAL GATE 強制安全問題不被跳過
- 負面/注意：條件判斷依賴使用者輸入的明確程度

---

### ADR-003：引入 Lazy Engineer 模式

**狀態**：已接受  
**日期**：2026-06-17

**背景**：分析 Ponytail 專案後，發現其「決策梯」概念可以在生成程式碼前有效減少 over-engineering。實測顯示 65–90% output token 節省。

**決策**：以 Ponytail 概念為基礎，設計 `lazyengineer.md`（核心模式）與 `lazyengineer-review.md`（over-engineering 掃描），命名改為 lazyengineer 以貼近本專案語境。整合進 code-review Orchestrator 的 Phase 1.5。

**後果**：
- 正面：大幅降低 output token；輸出更可預期（不偷寫檔案、不自行跑測試）；取捨透明化（`lazyengineer: skip until` 標記）
- 負面/注意：AI 對「需求邊界」的判斷可能與開發者不一致；不適合上線功能或需要完整規格的場景

---

### ADR-004：引入 Tech Lead Mode（Orchestrator / Executor / Reviewer 分層）

**狀態**：已接受
**日期**：2026-07-03

**背景**：參考社群一篇實測文章（以強模型當 orchestrator 切工單、弱模型當 executor 執行、第三方模型當 reviewer 挑毛病、人類終審），發現本專案既有的 Orchestrator 架構與 `gemini-assist.md` Mode C 已部分具備這個分工雛形，但缺兩塊：(1) Claude 自己身兼 orchestrator 與 executor，沒有真正委派實作；(2) 沒有「讀 diff 不讀完工報告」的 close gate，容易出現卡關/scope creep 收不了尾的狀況。

**決策**：新增 `skills/engineering/tech-lead-mode.md` 作為執行策略 mode（比照 `lazyengineer.md` 的掛載方式，不做成新 Orchestrator，避免與既有 7 個 Orchestrator 的觸發詞產生歧義）。核心設計：
- Executor 身分不預先綁死，Ticket 模板留 `executor_type` 欄位，預設走 `Agent` tool subagent + `isolation: worktree`；若任務明確需要異質模型執行，才走 agy（需臨時放寬 `~/.agents/settings.json` 的 `excludeTools`，且用畢立即還原，不得變成永久設定）。
- Reviewer 沿用既有 `gemini-assist.md` Mode C，發現一律經 Orchestrator 逐條查證（CONFIRMED / REJECTED / ESCALATE），不全信也不全部忽略。
- Close Gate 讀 diff 本身而非 executor 的完工報告，結果只能 CLOSE / REOPEN（窄工單）/ ESCALATE 三選一，禁止「大致完成之後再說」的模糊結案。
- 已接線至 `coding-workflow-core.md`（Phase 2.5）、`new-feature.md`（Phase 3.5）、`debug-flow.md`（Phase 2.5）作為進入實作前的條件分支；`CLAUDE.md` 按需載入表與 `skills/llms.txt` 已收錄。

**後果**：
- 正面：高風險 / 易卡關任務有結構化的收斂機制；executor 委派降低 orchestrator 自己動手造成的重工
- 負面/注意：小任務套用會拖慢流程（已在啟用條件明訂門檻）；agy 當 executor 的臨時權限放寬若忘記還原會變成長期安全設定漂移，需要人工留意

---

### ADR-005：governance/ 制度層（CLAUDE.md 精簡路由 + 判斷力外化）

**狀態**：已接受
**日期**：2026-07-03

**背景**：實測常駐載入達 901 行（gemini-assist 一檔佔 38%），路由資訊三處重複（CLAUDE.md / llms.txt / README）會漂移；且既有規則多處依賴「經驗判斷」（嚴重度分級、何時算完成），較小模型執行時會編造或漏判。使用者要求趁高階模型 session 把判斷力轉成制度，供之後較小模型長期沿用。

**決策**：新增 `governance/` 目錄，七份制度檔：harness-diagnosis（診斷依據）、model-orchestration（指揮官不下場 + 派工三件套 + 升降級路徑 + 驗證不自驗）、judgment-rubrics（R1-R5 可勾選判準，各附正反例）、delegation-templates（五種任務型態派工模板）、maintenance-protocol（🟢🟡🔴 三級修改權限 + lessons 格式與精簡門檻）、lessons.md（append-only 教訓日誌）、letter-to-future-sessions（交接與退化預防）。CLAUDE.md 重寫為 48 行精簡路由；gemini-assist 從常駐降為按需；路由單一事實來源定為 skills/llms.txt。

**後果**：
- 正面：常駐 token 大幅下降；判斷判準可被弱模型執行；制度修改有權限分級防腐化
- 負面/注意：inject.sh 常駐清單未同步（下游專案模板仍列 gemini-assist 為常駐）；AGENTS.md / GEMINI.md 未跟進精簡；均記錄於 letter-to-future-sessions 交接節

---

### ADR-006：rules/ 以 skills/rules → ../rules 相對 symlink 對外提供（v4.6 全面 review）

**狀態**：已接受
**日期**：2026-07-04

**背景**：全面功能性 review 發現 setup.sh 只 symlink `skills/` 到 `~/.claude/skills/`，但 inject.sh 常駐注入的 `@~/.claude/skills/rules/...` 路徑（coding-standards / security / git / typescript / python）實際不存在——下游專案的核心 rules 自 v1.9 起從未真正載入，且因無報錯而長期未被發現。

**決策**：在 repo 內新增 `skills/rules → ../rules` 相對 symlink 並納入 git 追蹤。三個候選方案中選此案的原因：(a) 零腳本改動、所有既有宣告路徑立即生效；(b) rules/ 實體位置不變，CLAUDE.md 的 `@rules/...` 與 30+ 處檔內引用免同步；(c) 相對 symlink 隨 repo clone 位置移動仍有效。落選方案：實體搬移 rules/ 進 skills/（改動面過大）、setup.sh 加第二條 symlink（下游需重跑 inject.sh 才修復）。

同批 review 的其他制度對齊：code-review Phase 5 改冷啟動交叉驗證（消除錨定偏誤，對齊 delegation-templates T5 / gemini-assist 模式 C）；orchestrator Phase 0 偵測表去重複改指向 coding-workflow-core（單一事實來源）；convert-skill Step 5 移除「往 CLAUDE.md 加列」（對齊 maintenance-protocol 🔴 禁令）。

**後果**：
- 正面：下游 rules 載入恢復；review 哲學（冷啟動）全 repo 一致；同步負擔再降一處
- 負面/注意：Windows 環境 git symlink 需 `core.symlinks=true` 才有效（本專案目前僅 macOS 使用，記錄備查）；`skills/` 目錄掃描工具（如 setup.sh 的 find）預設不跟隨 symlink，rules 不會重複列出，此為預期行為

> 知道不完美但有意為之的設計，避免新人重複質疑

| 限制 | 原因 | 預計改善時間 |
|------|------|------------|
| （填入） | （填入） | （填入） |

---

## 禁止改動的部分

> 有特殊原因不能動的程式碼或設定

- （填入）：原因 = （填入）

---

## 外部依賴

| 服務 | 用途 | 文件 |
|------|------|------|
| （填入） | （填入） | （填入） |

---

## 環境設定

### 必要環境變數

| 變數名 | 用途 | 取得方式 |
|--------|------|----------|
| `DATABASE_URL` | PostgreSQL 連線 | （填入） |
| `NEXTAUTH_SECRET` | Auth 加密 | `openssl rand -base64 32` |
| （填入） | （填入） | （填入） |

### 本地開發設定

```bash
# 初始化步驟（新成員照這個跑）
（填入）
```

---

## 版本歷史

| 版本 | 日期 | 變更摘要 |
|------|------|----------|
| v0.1 | （日期） | 初始建立 |
