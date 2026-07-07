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

---

### ADR-007：governance/ 分發到下游（symlink + 路由指標，不 @ 常駐）

**狀態**：已接受
**日期**：2026-07-04

**背景**：v4.5 建立的 governance/ 制度層只有本 repo 的 CLAUDE.md 路由得到，下游專案（經 inject.sh 注入者）完全讀不到，letter-to-future-sessions 列為未完成交接事項（🟡 級，需使用者同意）。使用者於 2026-07-04 指示執行分發。

**決策**：比照 ADR-006 rules/ 的做法：
- 新增 `skills/governance → ../governance` 相對 symlink（git 追蹤），下游 `~/.claude/skills/governance/...` 路徑立即可達，setup.sh / 既有 symlink 零改動
- `inject.sh` INJECT_BLOCK 末尾加「制度層路由」段：**純文字路由指標（用到才讀），不用 `@` 常駐載入**——governance 四檔合計約 2 萬字，常駐會重演 v4.5 修掉的 901 行常駐問題
- 路由只收下游高頻四項：model-orchestration / judgment-rubrics / delegation-templates / lessons；harness-diagnosis、maintenance-protocol 屬制度倉庫內部事務，不下放

**驗證**：`~/.claude/skills/governance/judgment-rubrics.md` head 實測可讀（遵守 lessons 2026-07-04「宣告路徑必須實測」）；inject.sh 情境 1（新生成）與情境 2（區塊更新）於 scratchpad 實跑通過，更新流程無重複注入。

**後果**：
- 正面：下游 session 可查判準與派工模板；lessons.md 經 symlink 全專案共用（踩坑教訓集中一處）
- 負面/注意：既有下游專案需重跑 `inject.sh` 才會取得路由段（symlink 部分則立即生效）；下游多 session 同時 append lessons.md 有理論上的寫入競態，現況單人使用風險低，記錄備查；governance/backups/ 亦隨 symlink 對下游可見，屬無害冗餘

**修訂（2026-07-06，v4.9）**：分發機制改為 setup.sh 直建 `~/.claude/governance` 專屬 symlink（即本 ADR 當初的落選方案「setup.sh 加第二條 symlink」），inject.sh 路由改指 `~/.claude/governance/...`。改變理由：governance 以一級路徑對外、不再借道 skills/ 巢狀路徑，語意更清楚；代價是各機器需重跑一次 setup.sh（本機已於 2026-07-06 完成並實測可達）。原 `skills/governance → ../governance` symlink 保留為 v4.7 舊路徑相容層，已注入舊路徑的下游不受影響。同批修復 setup.sh 檢查順序缺陷：實體目錄擋路時腳本半途 exit，會留下「skills 舊鏈已刪、新鏈未建」的斷鏈中間態——存在性檢查全部前置後，隔離環境四組測試（首跑/冪等/兩種實體目錄邊界）全數通過。

---

### ADR-008：制度檔 harness 適配層（通用原則與 harness 語法分離）

**狀態**：已接受
**日期**：2026-07-04

**背景**：一個 Antigravity（agy harness）session 依 tech-lead-mode / model-orchestration 執行委派時發現：制度檔明文的 `subagent_type: "general-purpose"` / `isolation: "worktree"` / `model: sonnet` 是 Claude Code 專屬參數，Antigravity 只認 `TypeName: "self"|"research"` / `Workspace: "branch"|"share"` 且不支援逐次指定 model——模型越忠實遵守制度檔，工具層報錯越硬。另外 Phase 0 的 shell 偵測在逐次核准 shell 的 harness 會把每個 session 開局卡在人工點擊。

**決策**：不採用該 session 提議的「參數整批替換成 Antigravity 規格」——本 repo 未遷移，Claude Code 仍是主要環境，單邊替換只是反向撞牆。改為建立 harness 適配層：
- `model-orchestration.md` §2 重寫為 Claude Code / Antigravity 雙欄適配表，附鐵律「先認環境、查表取參數、禁止照抄他 harness 參數名」；§6 註明逐次指定 model 僅 Claude Code 支援，其他環境升級 = 帶失敗軌跡提示使用者
- `tech-lead-mode.md` Phase 2 標註範例為 Claude Code 語法、附 Antigravity 等價參數，並新增「派發後等待紀律」（事件驅動喚醒，禁止輪詢空轉）
- `coding-workflow-core.md` Phase 0 改原生唯讀工具優先（Glob / Grep 類），shell 降為 fallback

**後果**：
- 正面：同一份制度可被多 harness 忠實執行而不撞工具層；Phase 0 在核准制 harness 不再卡人工點擊
- 負面/注意：Antigravity 參數規格來自該 session 的實際回報，本 repo 無法在 Claude Code 環境下直接驗證，若 agy harness 改版需照 maintenance-protocol 🟢 級事實修正更新適配表；新增 harness（如 Codex）時需自行補欄

---

### ADR-009：三 harness 制度統一——單一正本 + 三薄索引 + 全域接線

**日期**：2026-07-07

**背景**：使用者長期以三個 harness（Claude Code / Codex / Antigravity agy）+ 弱模型日常運作。盤點發現：制度只接上了 Claude（`~/.claude/` symlink），Codex 全域 `~/.codex/AGENTS.md` 與 agy 全域 `~/.gemini/GEMINI.md` 從不存在——repo 索引檔只在人位於本 repo 時生效，其他專案的 Codex / agy 完全沒讀到制度。記憶亦分裂三處（Claude 專案記憶已過時、Codex sqlite 0 筆、agy brain 二進位）且無單一真相來源。

**決策**（使用者 2026-07-07 逐項核准）：
1. **正本選址**：沿用 `~/Agent_skill` repo 為唯一正本，不新建 `~/.agents/institution/`（該目錄實查只有 excludeTools 鎖檔，非既有正本）
2. **全域接線**：setup.sh 增建 `~/.codex/AGENTS.md → repo/AGENTS.md`、`~/.gemini/GEMINI.md → repo/GEMINI.md` 兩條檔案 symlink；索引檔內路徑全部改為 `~/Agent_skill/...` 絕對路徑，任何專案都可達
3. **agy 升級為完整 harness**：GEMINI.md 從「唯讀協作者」改寫為對等薄索引；移除 `~/.gemini/settings.json`、`~/.agents/settings.json` 的 excludeTools 全域唯讀鎖（備份 `*.2026-07-07.bak`）；「被委派模式」保留 A/B/C 唯讀約定
4. **記憶收斂**（maintenance-protocol §6）：交接正本 = `~/.agent-sessions/<專案>/latest.md`、教訓正本 = lessons.md、決策正本 = 本檔 ADR；Codex Memories 保持關閉、agy brain 不作為制度記憶
5. **索引防漂移**（maintenance-protocol §7）：四項可執行檢查（行數 ≤150 / symlink 指向 / AGENTS-GEMINI inline 段逐字 diff / 路由可達），改索引必跑
6. model-orchestration 補 Codex 欄與三 harness 模型選擇表（型號 2026-07-07 查證：Codex 文件查證未實測、agy 本機 `agy models` 實測、Claude 官方文件）

**後果**：
- 正面：三 harness 任何專案任何 session 都讀到同一份制度；升降級與委派在三家都有具體型號可查；記憶有唯一回寫點
- 負面/注意：Codex 欄零本機實測（首個 Codex session 需校準）；agy 解鎖後具寫檔能力（誤寫事故的根因候選）；其他機器需重跑 setup.sh，否則 Codex/agy 靜默無制度

---

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
