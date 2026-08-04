# Project Context

> 專案架構、技術選型、重要決策的完整記錄。  
> 這是「為什麼這樣設計」的真相文件。

---

## 跨專案進度追蹤（v5.4，2026-08-04 更新）

- 快照路徑：`~/.agent-sessions/<project>/latest.md`（該目錄自 2026-08-04 起是 git repo，見 ADR-017）
- **唯一寫入觸發**：`handoff` skill，且只在使用者說出「handoff / 收工 / 交接」時（ADR-015）
- **無自動寫入路徑**：`version-log`（commit）已解耦（ADR-014）；post-commit hook 已刪除（ADR-016）；Stop hook 已永久移除（ADR-015）
- 聚合 skill：`skills/productivity/project-dashboard/SKILL.md`（`最後 commit`／`分支` 等衍生欄位改讀取時現跑 git，不存檔）

---

## RAG 知識庫（v3.0）

- 採用 Grep-based 檢索，不引入外部 vector DB
- 知識庫路徑：`knowledge/`，分三類：engineering / security / workflow
- 搜尋 skill：`skills/productivity/rag-search/SKILL.md`
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

## 為什麼沒有「架構概覽 / 技術選型 / 環境設定」等欄位

2026-08-04 刪除。這些是通用專案模板帶來的空欄位（17 處「（填入）」），在本 repo
**永遠不會有內容**——這裡是制度倉庫，沒有前端框架、資料庫、認證方案可選，也沒有
`DATABASE_URL` 之類的環境變數。它們留著唯一的效果是每次有人接手就被當成待辦掃到
一次（實際發生過至少 4 次，見 `memory/handoff-2026070*.md` 與
`letter-to-future-sessions.md` 的「未完成事項」）。

**不要加回來。** 真的有東西要記時，直接寫一個有內容的段落即可，不需要先鋪空模板。

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

### ADR-010：執行力分層——Stop hook 收工守門 + handoff-verifier cop

**日期**：2026-07-10

**背景**：文字制度仰賴模型自主遵守，模型發散即失效（實例：2026-07-07 發現 latest.md 落後 repo 3 commits，鐵律 1 被靜默跳過）。設計分析見 `governance/enforcement-layers.md`（三層執行力模型，與 unknown-matrix skill §3 去相關階梯同構）。

**決策**（使用者 2026-07-10 核准，明確要求不建 PreToolUse 腳本——`~/.claude/settings.json` 已有全域 cost-aware-approval hook 承擔該層）：
1. `hooks/stop-handoff-check.sh`：Stop hook 偵測「本 session 寫過 repo 但 latest.md 未更新」→ 擋一次收工。fail-open（hook 內部錯誤一律放行）；`stop_hook_active` 防死循環；`AGENT_SKILL_HOOK_BYPASS=1` 旁路（留檔 `~/.agent-sessions/hook.log`）
2. `agents/06-governance/handoff-verifier.md`：乾淨 context 查核員，三查（格式合規 / git 事實對帳 / 下一步可執行性），回傳必附證據，無證據核可視為未核可
3. 接線：本 repo `.claude/settings.json` 掛 Stop hook；inject.sh 增 `install_stop_hook()` 供下游掛載——**settings.json 指向正本腳本、不複製**（偏離設計稿原文「複製到下游」，理由：杜絕下游副本漂移，即 2026-07-07 lessons 教訓）

**後果**：
- 正面：鐵律 1 從自律變反射；查核與主對話推理去相關。實測 10 案例通過（block/放行×4/旁路/合併/冪等/拒裝/壞 JSON 拒改）
- 負面/注意：僅 Claude Code 生效（Codex/agy 仍靠文字制度）；transcript 掃描是字串比對啟發式，harness transcript 格式變動可能靜默失效（fail-open 設計下失效 = 不擋，退回純文字制度）；驗收與觀察期見 enforcement-layers.md §6

---

### ADR-011：skill frontmatter 標準化——結構化 description + 示例觸發 + 版本戳

**日期**：2026-07-22

**背景**：借鏡外部 repo `liusai0820/Stock-Analysis-Skill` 的文件工程。其 frontmatter 把「具體使用者話術例句」寫進 description、並帶 skill 級版本戳——正好對準本 repo 兩個痛點：鐵律 3「不猜意圖」需要例句才好消歧，而近期 lessons 全在講漂移、缺可稽核的陳舊信號。刻意不採其執行期做法（往 /tmp 寫腳本 + 即時 `pip install`、零測試——按本 repo security/coding 標準是反例）。

**決策**（使用者核准，先單檔試點 unknown-matrix 再全面推廣）：所有 skill frontmatter 統一格式——
1. `description` 用 `|` 多行：能力簡述 +「觸發場景：」+「示例觸發：」（≥3 個逐字使用者話術例句）
2. `metadata` 區塊：`trigger`（一行簡短情境）、`version`、`last_updated`
3. `last_updated` 一律填**該檔實質最後變更日**（本批用 git 最後 commit 日為誠實基準，非套用當天）；日後只有動到 skill 實質內容才 bump
4. **不加** `allowed-tools`（Claude Code 中它是功能性限制欄，會綁死疊加型判斷 skill 的可用工具）

**執行**：37 檔一次到位（36 檔派 5 個 sonnet subagent 平行改 + 1 檔範本手做）；Claude 主對話做終審（python 驗證：正文與 HEAD 逐字比對 / name 未改 / 日期正確 / YAML 合法 / 無 allowed-tools / llms.txt 未動）。同批修掉 `gemini-assist` → `agy-assist` 不完整改名（見 lessons 2026-07-22）。

**後果**：
- 正面：模糊指令（「優化一下」「重構讓它更好」）更穩定命中對應 skill；`grep last_updated` 可盤陳舊 skill
- 負面/注意：SKILL.md 的 description 與 `llms.txt` 的 description 是兩份人工摘要，本就不逐字同步（maintenance-protocol §7 已知極限），新增 skill 時兩處都要照此標準寫
- `convert-skill.md` 產出模板已同步更新為新標準（Step 3 frontmatter + Step 4 checklist + 轉換範例，含 metadata 區塊、示例觸發、不加 allowed-tools）——日後新 skill 自動符合本標準

---

## ADR-012：跨 harness 共用 SKILL.md package 與 machine index（2026-07-23）

**決策**：所有 indexed skill 統一為 `category/name/SKILL.md`；`skills/index.json`
是 machine-readable coverage 正本，`skills/llms.txt` 保留自然語言觸發說明並由
validator 檢查 coverage。因 Claude/Codex native discovery 都要求 root 下一層直接
出現 `<name>/SKILL.md`，`setup.sh` 與 `inject.sh` 在各自 skills root 建立單層
per-skill symlink link farm，target 仍是分類正本，不複製內容。

**原因**：舊式散落 `.md` 可供 Claude 文字引用，但 Codex native discovery 只能
發現既有的兩個 package，造成同一制度在不同 harness 的 coverage 不一致。

**安全邊界**：寫入前完整 preflight 所有 indexed names；同名實體 entry 或異源
symlink 視為衝突並在零寫入狀態停止，非同名 `.system`／第三方 entries 保留。入口
只替換自身 managed block 並保留使用者內容。`.codex/hooks.json` 暫不分發；
`~/.agents/skills` 是 legacy 且不在本次管理範圍。

**後果**：Claude/Codex 都可 native discover 全部 indexed packages；舊路徑屬 breaking
change，活引用已同步，歷史 ADR/changelog 保留原文。

---

## ADR-013：接線腳本按 harness 拆分（2026-07-23）

**決策**：`setup.sh` / `inject.sh` 降為總入口，實作拆成 `bin/lib-skill-farm.sh`
（共用核心，唯一正本）＋ `bin/{setup,inject}-<harness>.sh`（薄 adapter）。
harness 腳本內禁止出現 `ln -sfn` 等接線動作——出現即代表核心被複製了第二份。
總入口採**兩階段全有全無**：先跑完所有 harness 的 preflight，全數通過才進 install。

**原因**：三個 harness 的需求本就不對稱（Claude 需要 `rules`/`governance` 掛進
farm 才能讓 `@` 常駐 resolve、Codex 需保留 `.system` 且未來可能遷往官方
`~/.agents/skills`、agy 只吃一條 GEMINI.md），硬塞進同一個函式導致每次單一
harness 的變動都要動共用檔案。實務上也造成兩個 session 平行作業時撞車
（2026-07-23 已發生一次）。

**安全邊界**：preflight 只做檢查與 `mkdir -p` 父目錄（冪等無破壞性），install 才
建 symlink；孤兒清理只刪「readlink 指向本 repo `skills/` 但不在 index」的 entry，
第三方 entry、Codex `.system`、以及指向 `repo/rules`、`repo/governance` 的 extra
entry 因前綴不符而豁免。

**已知取捨（不對等的常駐強制力）**：Claude 的 managed block 用 `@` 常駐載入
`rules/coding-standards.md` 與 `rules/security.md`，是機制保證；Codex 沒有 `@`
語法且 AGENTS.md 有 32KiB 上限，只能寫成「開工必讀」的文字要求，agy 同理。
安全底線在 Claude 是強制、在 Codex/agy 是紀律。要讓 Codex 也成為硬保證需走 hook
或內嵌精簡規範，屬未來議題。

**後果**：單一 harness 的變更（如 Codex 遷往官方 discovery root）只需改一個檔案；
半接線中間態由架構消除；`~/.claude/skills/{rules,governance}` 兩條 entry 讓
v4.6/v4.7 建立的舊 `@` 路徑重新生效。舊下游專案的
`@~/.claude/skills/<category>/<name>.md` 仍需 `bin/migrate-downstream-paths.sh`
一次性改寫（link farm 是扁平的，symlink 救不回分類層路徑）。

---

## ADR-014：latest.md 觸發收緊為明確指令 + 停用 Stop hook（2026-07-27）

**決策**：`~/.agent-sessions/<專案>/latest.md` 的寫入觸發從「收工必寫」（模型自主
判斷）收緊為**只由使用者明確「收工/交接」指令觸發**。連帶三項：① 從
`.claude/settings.json` 移除 Stop hook 掛載（`hooks/stop-handoff-check.sh` 保留
dormant，不刪）；② `version-log`（commit）不再寫 latest.md，commit 與交接檔解耦；
③ latest.md 唯一合法寫入路徑收斂為 `handoff` skill。開工先讀不變。

**原因**：實務觀察到模型把「完成一段 content」誤判為「收工」，同一 session 中途就
反覆寫 latest.md，造成交接檔過度觸發、內容過早定稿。根因是「收工」定義太鬆——
既靠模型自主判斷、又有 Stop hook 在每次 session 結束自動逼寫，兩條都是「非使用者
指令」的自動觸發源。使用者要的是「除非我說 commit 或收工，否則不動 latest.md」。

**部分回退 ADR-010**：ADR-010 的 L2 Stop hook 守門層本項失效，回退為純 L1 文字約束
（鐵律 7 + maintenance-protocol §6 已同步改）。handoff-verifier cop 不再由 Stop hook
自動喚醒，改為使用者說收工時手動委派。ADR-010 的其餘設計（cop 附證據、三層模型）
不受影響。

**已知取捨**：失去「session 結束漏寫交接」的自動防線——使用者若忘記說收工，latest.md
可能落後 repo（正是 2026-07-07 觀察到的失敗模式）。這是使用者明確選擇：寧可承擔漏
寫風險，也要消除過度觸發。跨 harness 一致性由文字正本（4 份索引鐵律 + §6）保證，
Codex/agy 本就不吃 `.claude/settings.json`、原本就只有 L1 約束，不受停用 hook 影響。

**後果**：latest.md 只在使用者明說收工/交接時更新；commit、完成一段工作、session
自然結束都不再觸發。維護者若日後想恢復自動防線，實作與待辦見 `governance/TODO.md`
與 `enforcement-layers.md` §4（已標註本項停用）。

---

## ADR-015：交接觸發權全歸使用者，L2 Stop hook 永久移除（2026-07-31）

**決策**：`~/.agent-sessions/<專案>/latest.md` 的觸發權**全數歸還使用者**，模型與
harness 都沒有自動觸發路徑。四項：① 唯一觸發詞收斂為「handoff」「收工」「交接」；
② 近似說法（「今天到這」「明天繼續」「總結一下進度」）一律**反問確認**，不自動執行；
③ 模型可在完成可交付段落且本 session 有 repo 寫入時**提醒一次**「要 handoff 嗎？」
（每 session 至多一次，除非之後又有新 commit），僅止於提醒；④ `hooks/stop-handoff-check.sh`
**永久移除**（非 ADR-014 的「保留 dormant」），下游掛載一併清除。

**原因（原理性，非實作缺陷）**：Stop hook 的觸發源是 harness 生命週期事件——一輪
回應結束——而「收工」是使用者的**意圖宣告**。hook 收到的 input 只有 `cwd` /
`transcript_path` / `stop_hook_active`，裡面沒有「使用者是否宣告收工」這個欄位；要
取得只能 grep transcript，那正是 ADR-014 剛廢掉的「模型自主判斷收工」的更笨版本。
把觸發條件收窄成「只在收工時擋」之後，hook 唯一還會開火的場合恰恰是 L1 已在正常
運作的場合，而它想防的「使用者忘了說收工」按定義不觸發——**與存在理由互斥**。

**取代 ADR-014 的取捨**：ADR-014 承認「失去 session 結束漏寫交接的自動防線」。本
ADR 用 ③ 的主動提醒補回，但改**提醒**而非**攔截**——失敗方向從此安全：模型忘了
提醒只是漏寫一次（可補救），hook 誤判則是擋住使用者（不可補救）。

**連帶發現（本次實地核對）**：真正的過度觸發源不只 hook，還有 `handoff` skill 自身
的自然語言觸發詞（「總結一下目前進度，我明天繼續」「這個 session 先做到這」）。hook
拿掉後那條路徑仍活著且更隱蔽——不是擋人，是自作主張直接寫。已同步收窄
SKILL.md / llms.txt / index.json 三處。

**後果**：本規則回退為純 L1 文字約束，三 harness 一致（Codex/agy 本就只有 L1）。
`enforcement-layers.md` §4 #1 與 #3 標為廢止。反注入偵測改由 `bin/scan-downstream.sh`
唯讀掃描承擔（待實作）。

---

## ADR-016：刪除 post-commit hook，改由讀取時現算；新增 pre-commit 個人路徑 lint（2026-07-31）

**決策**：① 刪除 `bin/post-commit-hook.sh` 與 5 份下游副本；② `latest.md` 的
`最後 commit` / `分支` 等衍生欄位改由 `project-dashboard` **讀取時現跑 git**；
③ 新增 `hooks/pre-commit-audit.sh`（個人絕對路徑洩漏 lint），下游以 exec wrapper
指向正本，已裝 6 個 repo。

**post-commit 為什麼該刪**：它每次 commit 自動改寫 `latest.md` 前 7 行，屬
ADR-014「commit 與交接檔解耦」與 ADR-015「唯一合法寫入路徑是 handoff skill」
明文禁止的自動寫入路徑——與 Stop hook 同類，只是沒人執行下游反注入（2026-07-31
清 Stop hook 掛載時，我自己在 AG_knowledge / WakaWaka 的兩個 commit 當場觸發了
它，寫入時戳 14:52 即為實證）。它還有第二層傷害：改寫「最後更新」等於**每次
commit 都對其他 session 發出假的並發訊號**，污染 maintenance-protocol §6 的無鎖
規約——是 TODO「交接檔並發控制」的噪音源之一。

**為什麼不需要有人接手那些欄位**：`latest.md` 的唯一程式化消費者是
`project-dashboard`，它只讀 狀態 / 最後更新 / 觸發來源 / 當前焦點 / blocker。
`最後 commit` / `分支` **零讀者**，且是衍生資料——讀取時 `git -C <path> log -1`
又快又準，存進檔案反而必然過期（hook 只裝在部分 repo）。

**意外收穫**：dashboard 改為現跑 git 後，可比對「latest.md 最後更新」與
「repo 之後的 commit 數」，得出**交接落後**。ADR-015 接受的取捨是「使用者忘了說
收工 → latest.md 落後 repo，失去自動防線」——這一欄把該代價從不可見變成查得到。
**攔截 → 偵測，寫入時 → 讀取時，強制 → 資訊**，且只在使用者主動叫 dashboard 時跑。

**pre-commit lint 為什麼可以用 L2**（對照 ADR-015 廢 Stop hook）：本檢查的觸發
條件是 regex 命中，**客觀可判定、零意圖推斷**；Stop hook 廢除的原因是它要觀測
「使用者是否宣告收工」這種主觀意圖。兩者不同類。且洩漏不可逆（git 歷史刪不掉），
攔截點必須在 commit 之前——事後掃描只能告訴你「已經寫進歷史了」。前提成立：6 個
repo 全部有 GitHub remote，AG_knowledge commit `9cac18f` 就是在補這個坑。

**已知缺口**：~~未接進 `inject.sh`~~ → 已於 commit `7227931` 接入
（`bin/install-git-hooks.sh`）。

**2026-08-04 補記**：實測發現本 ADR 宣稱的成果**兩項都沒真正落地**——既有 repo 的
wrapper 一份都不存在（文件寫「已裝 6 個 repo」），`shopee` 的 post-commit 副本也
還活著（文件寫「刪除 5 份下游副本」）。當日已補裝四份（`Agent_skill` /
`AG_knowledge` / `shopee` / `WakaWaka`，md5 一致）並刪除該 post-commit，四象限
行為測試通過。防復發待辦見 `governance/TODO.md`。

**2026-07-31 補記（獨立 review 後）**：依鐵律 2「驗證不自驗」把
`hooks/pre-commit-audit.sh` 交冷啟動 subagent 對抗式審查（delegation-templates T5）。
**我自己的 9 項測試全綠，reviewer 仍找出 7 個實測可重現的缺陷**，逐條複驗後 3 個修掉：

- **wrapper 沒有 fail-open**（最嚴重）：原版直接 `exec`，正本不可執行時回 126，
  6 個 repo 的所有 commit 都會被擋。**fail-open 的宣稱寫在正本裡不會自動繼承到
  wrapper——兩個檔案各自都要有放行路徑**。已加 `[ -x "$CANON" ] || exit 0`。
- **`audit-ok` 用子字串比對**：`/Users/x/audit-oklahoma/secret.json` 靜默放行。
  改為獨立 token 比對。
- **非 ASCII 檔名歸屬錯置**：`core.quotepath` 讓 git 輸出 `+++ "b/\350...`，
  前置雙引號使檔頭 regex 失配，洩漏被歸到上一個檔名。改用 `-c core.quotepath=false`
  並容忍引號。

不修的 4 項（binary 不掃、`/Users/<單一 segment>` 誤報、`file://<host>/` 漏網、
rename 重掃）已寫進腳本檔頭與 `enforcement-layers.md §4b` 當已知限制。誤報那項
**刻意不收窄**：漏掉洩漏不可逆（git 歷史刪不掉），誤報只需加 `audit-ok`——成本不對稱。

回歸測試 12/12 通過（原 9 項 + 3 條缺陷回歸），6 份 wrapper 已更新且 md5 一致。
---

## ADR-017：交接檔納入版本控制（TODO Phase D 單獨落地，2026-08-04）

**決策**：`~/.agent-sessions` 執行 `git init`，`handoff` skill 寫完 `latest.md`
在**同一個使用者觸發流程內**立刻 commit；latest.md 標頭新增 `> 寫入者：claude |
codex | agy` 必填欄。三條紅線寫入 `~/.agent-sessions/README.md`：不加 remote、
不裝 `pre-commit-audit.sh`、commit 不掛任何 git hook。

**為什麼只做這一段**：TODO 的完整方案（per-session `entries/` 拆檔 + 聚合器）解的是
「並發覆蓋」，實際基率是**單人使用、2 個追蹤中的專案、歷史發生 1 次且零損失**；
而 git 化解的是「**覆蓋即永久丟失**」——此前該目錄無版控、無 `.bak`，被整檔覆蓋
後物理上救不回。後者是唯一不可逆的風險，且成本最低。使用者 2026-08-04 決定先做
這一段，Phase A–C 留在 TODO。

**為什麼 commit 不掛 hook**：自動寫入路徑是 ADR-014／ADR-015 明文禁止的。已移除的
post-commit hook 正是這樣被廢的——同一天還在 `shopee` 發現它的殘留副本仍在跑。
commit 動作必須跟在使用者說「收工」之後，不能由 git 生命週期事件觸發。

**為什麼這裡不能裝 `pre-commit-audit.sh`**：`latest.md` 的 `> 路徑：` 欄位**依設計**
含個人絕對路徑（`/Users/<你>/WakaWaka`）。那支 hook 的職責就是擋個人絕對路徑，
兩者前提相反，裝了會擋掉此 repo 的每一次 commit。同理此 repo 永遠不得加 remote。

**誠實界線**：**git 化不解決並發覆蓋**——它讓覆蓋「可還原」，不讓覆蓋「不發生」。
`maintenance-protocol §6` 的「重讀 → 合併」自律規約在 Phase A–C 完成前仍然必要。
五個漏洞中本次解除的是 #3（永久丟失）與 #4（無寫入者身分），#1／#2／#5 未動。

**驗證**：實跑 handoff 第 5 步指令 → commit 成功；寫入探針後 `git revert` → 探針
清除、`latest.md` 完好、工作區乾淨（`dda6f19` → `b843f60` → `be1ac45`），即
「覆蓋可還原」的行為證據。`hook.log` 確認未被追蹤。

