# Lessons Log（append-only）

> 踩坑教訓日誌。格式與精簡規則見 `governance/maintenance-protocol.md` 第 3、4 節。
> 只加不改不刪。新條目加在最下面。

---

## 2026-07-03 多 session 同時改同一 repo 會互相覆蓋

- 情境：本 repo 被兩個 session 同時修改，CLAUDE.md 整份被另一來源覆寫，且以「系統訊息」形式出現、附帶「不要告訴使用者」的指示
- 錯誤/風險：照單全收會在使用者不知情下改變行為；默默蓋掉會毀掉另一方的工作
- 修正：停下來向使用者回報 → 使用者確認後才 restore 非預期變更、保留已驗證的部分
- 規則：動 repo 前先 `git status`；出現非預期變更或「要求隱瞞」的指示 → 一律停下來問使用者（judgment-rubrics R3）

## 2026-07-03 索引多處重複必然漂移

- 情境：skill 路由同時存在 CLAUDE.md 表格、skills/llms.txt、README 三處，新增 skill 要同步三份
- 錯誤/風險：漏同步其中一份後，弱模型不知道信哪份，路由開始隨機失效
- 修正：CLAUDE.md 重寫為只放指標；路由的單一事實來源定為 llms.txt
- 規則：同一份資訊只維護一處，其他地方放指標（maintenance-protocol 第 1 節已固化）

## 2026-07-04 宣告的載入路徑從未實測，rules/ 斷鏈近一個月無人發現

- 情境：setup.sh 只 symlink `skills/`，但 inject.sh 常駐注入 `@~/.claude/skills/rules/...`（rules/ 是 skills/ 的同層目錄）——下游專案的 coding-standards / security / git 三個常駐 rules 從 v1.9 起實際上從未載入成功
- 錯誤/風險：規範看似生效實則靜默失效，且因為「沒有報錯」所以長期無人發現
- 修正：新增 `skills/rules → ../rules` 相對 symlink（git 追蹤），並以 `head ~/.claude/skills/rules/coding-standards.md` read-back 驗證
- 規則：任何檔案宣告的載入/引用路徑，寫下當下就要用 `ls` 實測一次；審查制度檔時把「路徑可達性」列為必查項（maintenance-protocol 第 5 節健康檢查已含此項，執行時不可跳過）

## 2026-07-04 制度檔把單一 harness 的工具參數寫成通用規則，跨 harness 執行即撞牆

- 情境：Antigravity session 依 tech-lead-mode / model-orchestration 委派 subagent，照抄 `subagent_type: "general-purpose"` / `isolation: "worktree"`，該環境只認 `TypeName` / `Workspace`，工具層直接報錯；Phase 0 的 shell 偵測在逐次核准 shell 的 harness 把開局卡成人工點擊
- 錯誤/風險：模型越忠實遵守制度檔，撞牆越硬；且「整批替換成新環境參數」的直覺修法只會反向弄壞主環境
- 修正：model-orchestration §2 改 harness 雙欄適配表；tech-lead-mode Phase 2 標註語法歸屬；coding-workflow-core Phase 0 原生工具優先（ADR-008）
- 規則：制度檔寫工具參數時必須標註適用 harness；通用原則與 harness 語法分離，執行前以當前工具 schema 為準，不照抄他 harness 參數名

## 2026-07-06 多步驟改系統狀態的腳本，中途 exit 會留下斷鏈中間態

- 情境：setup.sh 順序為「刪舊 skills symlink → 檢查 governance 目標 → 建兩條新鏈」，governance 位置若被實體目錄佔住，腳本在中途 exit 1，skills 舊鏈已刪、新鏈未建，全機下游常駐 @load 靜默斷鏈
- 錯誤/風險：與 v4.6 rules/ 斷鏈同類——無報錯的靜默失效，且觸發條件罕見，很難在事後追因
- 修正：存在性檢查全部前置，通過後才開始 rm/ln；隔離假 HOME 實測四組情境（首跑/冪等/兩種實體目錄邊界）
- 規則：腳本要動多個系統狀態時，先驗證所有前置條件再開始變更；每個 exit 路徑都要問「此刻系統停在什麼狀態」

## 2026-07-07 制度寫給三個 harness 看，卻只接線了一家

- 情境：AGENTS.md / GEMINI.md 在 repo 裡維護了多個版本，但 Codex 讀的 `~/.codex/AGENTS.md` 與 agy 讀的 `~/.gemini/GEMINI.md` 從未建立——制度自認覆蓋三 harness，實際只有 Claude 載入，其他兩家在所有非本 repo 專案裡零制度
- 錯誤/風險：與 v4.6 rules/ 斷鏈同族的靜默失效，但範圍大一級：不是一條路徑斷，是整個 harness 沒接上；且寫檔的人永遠不會發現（檔案在 repo 裡好好的）
- 修正：setup.sh 增建兩條全域檔案 symlink；索引檔路徑改絕對路徑；maintenance-protocol §7 把「全域接線健在」列入必查
- 規則：制度檔宣稱服務某個 harness 時，必須實際驗證**那個 harness 的載入點**讀得到它（`ls -l` 它真正讀的路徑），不能只驗證檔案存在於 repo

## 2026-07-07 下游公開 repo 長出制度副本與個人絕對路徑

- 情境：AG_knowledge（公開 repo）被 7/2–7/3 的 session 塞入 `.agents/rules/` 七檔制度改名副本、CLAUDE.md 加了 `file:///Users/...` 路由表、`.agents/skills/` 36 個指向本機路徑的 symlink 被 git 追蹤——根因是當時 agy 沒有全域載入點，session 只好「就地複製制度」
- 錯誤/風險：副本內容凍在 7/3 必然漂移（索引漂移的真實案例）；公開 commit 會洩漏使用者名，絕對路徑對其他協作者全部斷鏈
- 修正：副本先比對回寫再刪、CLAUDE.md 重跑 inject 回 `~` 路徑標準形、skills symlink 移出追蹤 + gitignore；inject.sh 新增 `audit_personal_paths`（注入完成後掃 `file:///` 與 `/Users/` 並警告）+ 修 `.git/hooks/` 目錄不存在時 cp 失敗的 bug
- 規則：下游專案 **committed 的檔案禁止 `/Users/<name>` 與 `file:///` 絕對路徑**，制度/skill 引用一律 `~` 形式；發現制度副本 → 回寫獨有內容後刪除，改走全域索引路由正本

## 2026-07-07 正本 repo 自己也寫死了機器特定絕對路徑

- 情境：審查下游洩漏後回頭掃正本（本 repo 亦是公開 repo），發現 governance/ 三檔 + 備份共 6 處含 `/Users/<使用者名>` 真實值（agy 的 PATH 實測記錄 ×2、`<專案>` 定義的舉例 ×1、及其歷史備份 ×3），且已隨 v4.5–v5.0 push 進公開歷史
- 錯誤/風險：洩漏使用者名（已成事實，修 live 檔是止血非抹除）；更實際的傷害是**跨機器不可攜**——其他機器照抄這條 PATH 會直接錯
- 修正：live 三處改 `~` 形式（`~/.local/bin/agy`、`~/Agent_skill`）；backups/ 不動（備份的意義是忠實快照，且歷史已公開）；未來下游由 inject.sh 的 `audit_personal_paths` 把關
- 規則：制度檔寫路徑**一律 `~` 形式，連「舉例」也不用真實使用者名**（用 `~` 或 `<name>` 占位）；寫下環境實測記錄前先問「這行被別台機器 / 公開讀者看到還成立嗎」

## 2026-07-10 設計新 hook 前未盤點既有 harness 設施

- 情境：enforcement-layers 設計稿第一批含新建 PreToolUse 攔截腳本；使用者指出 `~/.claude/settings.json` 已掛全域 PreToolUse hook（cost-aware-approval），再建即疊床架屋
- 錯誤/風險：同一 hook 事件掛兩支腳本，行為疊加難追蹤；同類攔截規則散在兩處必然漂移
- 修正：移除 PreToolUse 項（設計改為「攔截規則日後擴充進既有 hook」）；enforcement-layers.md §2 加「既有設施盤點」註記
- 規則：新增執行層設施（hook / agent / 自動化）前，先實查 harness 既有設定（`~/.claude/settings.json`、專案 `.claude/`）——同一事件層只允許一個歸屬，擴充優先於新建

## 2026-07-22 skill 改名只改了 name 欄，檔名與 30 處引用全留舊名

- 情境：`gemini-assist.md` 的底層工具早已從 gemini CLI 換成 agy，某次把 frontmatter `name` 改成 `agy-assist` 就收手，但檔名、`llms.txt` path、inject.sh、CLAUDE.md 路由、10 個 skill 的委派表共約 30 處仍是 gemini-assist——放了數週沒人發現，直到這次批量升 frontmatter 才撞出 name 與檔名不一致
- 錯誤/風險：不完整改名 = 懸空引用未爆彈（llms.txt path 指向的檔名與 name 不一致，靠檔名對應 name 的流程會斷）；且改名時若無腦全域 sed，會連 README 版本表 / memory ADR / handoff 這些**歷史紀錄**一起竄改，違反「不改史」
- 修正：先 `grep -rn` 全 repo 盤點所有引用，切成「活引用（路由指標 / 委派表 / skill 名標籤 → 改）」與「dated 歷史敘述（README changelog / memory ADR / handoff / 診斷快照 → 保留）」兩類分別處理；改完跑 §7 索引防漂移四查確認路由 resolve
- 規則：改 skill / 工具名是**原子操作**——`name` 欄、檔名、`llms.txt`(name+path)、所有活引用必須同一次全改；動手前先 `grep -rn` 全 repo 盤點，並區分活引用（改）vs 歷史紀錄（不改史，保留）

## 2026-07-22 全綠測試與 code review 都漏掉「這個函式沒人呼叫」

- 情境：tabetemiru（Swift app）修完 11 個 code review bugs、28 個單元測試全綠、冒煙啟動不 crash，使用者一開 app 卻發現首頁顯示「今日任務完成」——真因是 `SeedDataLoader.loadIfNeeded` 全專案沒有任何呼叫端，題庫從未寫進 store，所有查詢回傳 0
- 錯誤/風險：驗證方式與缺陷類型不匹配——單元測試都自建 fixture（不走真實初始化路徑）、code review 逐檔看實作（不追呼叫圖）、冒煙測試只看有沒有 crash（空資料不會 crash）。三種驗證同時盲，功能完全不可用卻一路綠燈
- 修正：補上呼叫端；驗證改為真實啟動後直接查資料層（`sqlite3 <store> "SELECT COUNT(*)..."`），確認初始化真的產生了資料
- 規則：宣告「修好了」之前，至少一項驗證必須走**真實初始化路徑並檢查副作用是否真的發生**（資料寫進去了嗎、檔案產生了嗎），不能全部依賴自建 fixture 的測試；新增或修改 service 時順手 `grep -rn "<funcName>"` 確認它有呼叫端

## 2026-07-23 同一條「rules 斷鏈」在三個月內踩第二次

- 情境：v4.6 曾修過一次 rules 斷鏈（新增 `skills/rules → ../rules` symlink，讓下游 `@~/.claude/skills/rules/...` 有效）。ADR-012 把 `~/.claude/skills` 從「整目錄 symlink」改成「per-skill link farm」後，那條相容 symlink 不再出現在 farm 下，同一批路徑再次全部失效——而且 Claude Code 對不存在的 `@` 路徑**靜默略過**，7 個下游專案會安靜失去全部常駐規範，沒有任何錯誤訊號
- 錯誤/風險：驗證只覆蓋「新架構自己的 38 個 package」，沒有一項檢查「舊架構承諾過的路徑是否仍然有效」。相容層（compatibility shim）是最容易在重構中被無聲刪掉的東西，因為它不屬於新設計的任何一部分，測試矩陣裡也沒有它的位置
- 修正：`setup-claude.sh` 把 `rules`、`governance` 掛回 farm；分類層路徑（`engineering/x.md`）因 link farm 是扁平的救不回，另寫 `bin/migrate-downstream-paths.sh` 改寫下游
- 規則：改動「對外承諾過的路徑」的產生方式時（symlink 佈局、目錄結構、URL routing），驗證清單必須包含**舊路徑仍可 resolve**，而不只是新路徑正確；靜默失敗的介面（`@` 引用、動態 import、環境變數）要特別列一條，因為它不會自己報錯

## 2026-07-23 遷移腳本只覆蓋「當下看得到的」路徑，漏掉註解與舊名

- 情境：寫 `bin/migrate-downstream-paths.sh` 時，改寫規則是照我自己驗證案例裡的常駐 6 條逐條列舉。實際跑第一個真實專案（WakaWaka）才發現：還有 14 條被 `#` 註解掉的按需載入路徑、以及一條 ADR-011 改名前的舊名 `gemini-assist`（且未被註解、是啟用中的）。真實專案共 21 條需改寫，我只處理 5 條
- 錯誤/風險：① 用「逐條列舉」而非「通用規則」處理結構性改名，覆蓋率取決於樣本而非規則 ② 把註解掉的引用當成不存在——使用者取消註解那天才會發現斷鏈，且一樣是靜默失敗 ③ 只拿自己造的 fixture 測，沒先掃真實資料的全部變體
- 修正：改成通用 regex（`<category>/<name>.md` → `<name>/SKILL.md`，rules/governance 白名單排除）＋ 舊名映射；並加「改寫後逐條驗證新路徑真的存在，否則不寫入」的防呆
- 規則：寫批次改寫腳本前，先 `grep -oE ... | sort -u` 掃出真實資料的**所有變體**再設計規則；改寫結果一律用「目標是否真的存在」驗證，不能只看 diff 好不好看。註解掉的引用要照改——它是待啟用狀態，不是不存在

## 2026-07-24 改名跑完 §7 四查全綠，skill farm 卻已經斷鏈

- 情境：`agy-assist` → `cli-delegate` 改名，照 2026-07-22 那條規則做了全 repo 盤點、活引用 vs 歷史紀錄分流、改完跑 §7 索引防漂移四查——四查全過。但 `~/.claude/skills/agy-assist` 與 `~/.codex/skills/agy-assist` 是指向舊目錄的 symlink，`git mv` 當下就變成 dangling，兩個 harness 的該 skill 實際已不可用
- 錯誤/風險：§7 四查的覆蓋範圍是「三份索引檔 + AGENTS/GEMINI 路由指標」，**不含 skill farm**。farm 由 `skills/index.json` 生成，改 index.json 只更新了正本、沒有重新 install，正本與已部署的接線之間存在一段沒有任何檢查覆蓋的落差。又是靜默失敗——harness 只是找不到該 skill，不報錯
- 修正：跑 `bin/setup-claude.sh --all` 與 `bin/setup-codex.sh --all`（`install_farm` 內建 `prune_orphan_entries`，自動清孤兒 entry 並建新連結）；agy 無 farm 機制、只吃 GEMINI.md，不受影響
- 規則：改動 `skills/index.json` 的 `name` 或 `path` 欄後，**必須重跑各 harness 的 setup 腳本**並掃一次 dangling（`for l in ~/.claude/skills/*; do [ -e "$l" ] || echo "$l"; done`），§7 四查不能替代這一步。凡是「正本改了但部署物是另一份實體」的結構（link farm、快取、複製出去的副本），驗證清單都要含一條「部署物已重新生成」

## 2026-07-27 「收工必寫」定義太鬆，latest.md 在 session 中途被過度觸發

- 情境：交接檔 `~/.agent-sessions/<專案>/latest.md` 的鐵律寫成「開工先讀、收工必寫」。使用者觀察到模型把「完成一段 content」就當成「收工」，同一 session 中途反覆寫 latest.md，交接檔內容過早定稿。另有 Stop hook 在每次 session 結束自動逼寫，是第二條非使用者指令的自動觸發源
- 錯誤/風險：「收工」是主觀詞，交給模型自主判斷必然發散——模型傾向把任何階段性完成解讀成收工。制度用「必寫」這種強制語氣配上模糊的觸發條件，等於預設模型會過度觸發。自動化防線（Stop hook）在使用者要的是「明確指令才動」時反而變成雜訊
- 修正：ADR-014 把觸發收緊為「只由使用者明確『收工/交接』指令觸發」，寫進 4 份索引鐵律 + maintenance-protocol §6；停用 Stop hook（settings.json 移除掛載，hook 檔留 dormant）；version-log 與 latest.md 解耦
- 規則：制度裡凡是「必做 X」配上主觀觸發詞（收工、告一段落、完成、差不多好了），要嘛把觸發詞換成客觀可判定的條件，要嘛把觸發權收回給使用者明確指令。不要用強制語氣（必寫/必做）去約束一個模型會自行擴大解釋的模糊邊界——那只會保證它過度執行

## 2026-07-27 codex exec 的 sandbox 擋 .codex 寫入，Codex 不能當 farm 安裝類 executor

- 情境：把「WakaWaka farm dangling 修復」派給 Codex（`codex exec`，sandbox=workspace-write）。Codex 跑 `inject.sh`，Claude farm 成功，但 Codex farm 在建 `.codex/skills/*` symlink 時 `ln: Operation not permitted` 中止——codex exec 的 sandbox 保護自己的 `.codex/` 目錄、禁止寫入。同一路徑我（Claude Code）手動建 symlink 成功，證明是 codex sandbox 專屬限制、非 FS 問題
- 錯誤/風險：多 CLI 委派時只問「executor 會不會做這件事」，沒問「它對要寫的路徑有沒有權」。farm 安裝本質要寫 `.codex/`（全域 `~/.codex/skills` 或下游 `.codex/skills`），Codex 結構性永遠做不到；盲派會派出一個註定失敗的工單
- 修正：FIX-1 的 `.codex` 半邊改由 orchestrator（Claude）直接跑 inject.sh 補完。探針策略生效——先派最低風險的 FIX-1 試水，撞牆立刻換手，沒有三份盲派
- 規則：委派前先確認 executor 對「它要寫入的路徑」有無寫權；sandbox/自我保護目錄（`.codex/`、可能還有各 harness 的 config 目錄）是比「能力」更硬的結構性邊界。凡任務會寫到某 harness 的自我保護目錄，該 harness 一律標「不可當此類 executor」，farm/接線類任務只能派 Claude 或由 orchestrator 收口

## 2026-07-31 停用決策沒含「下游反注入」就不算完成——ADR-014 的 hook 續活 4 天

- 情境：ADR-014（2026-07-27）決定停用 `hooks/stop-handoff-check.sh`，`enforcement-layers.md` 寫明「從 `.claude/settings.json` 移除掛載，hook 檔保留 dormant」。但**「移除掛載」這個動作從沒執行**——只改了正本文件就結案。7 個下游掛載原封不動，`hook.log` 顯示停用後仍有 6 次 BLOCK 橫跨 3 個專案（07-29 WakaWaka ×2、07-29 shopee、07-30～07-31 AG_knowledge ×3），直到 07-31 在 AG_knowledge 實地撞到才被發現
- 錯誤/風險：形成「制度文件說 A、執行層強制 B」的對撞——模型依鐵律拒寫 latest.md，hook 依舊擋收工，使用者被無限重複騷擾。根因是 `inject.sh` 只有「安裝」沒有「移除」：**不安裝 ≠ 移除既有的**。政策改變後沒有任何機制會回頭清理下游殘留，這類漂移會反覆發生。次要風險是殘留掛載被下游 repo 納入版控（AG_knowledge commit `96e9342`），寫進歷史
- 修正：ADR-015 改為永久移除。順序上先在正本腳本頂端加 kill-switch（`exit 0`）——因為下游全部「指向正本、不複製」，一行改動即同時停掉 7 個掛載，把清理從緊急止血降級成清潔工作；再逐一移除掛載；最後才刪檔（先刪檔會讓掛載變成 exit 127）
- 規則：**停用 / 廢止決策的完成判準包含「下游反注入」，不是改完正本文件就結案**。寫 ADR 時把「已生效的執行層在哪些下游還活著」列成 checklist 逐項打勾；若該執行層是「下游指向正本」的設計，先在正本加 kill-switch 取得即時止血，再慢慢清。另：驗收要看**行為證據**（`hook.log` 有沒有新 BLOCK），不能只看文件寫了什麼

## 2026-07-31 攔截器的測試會「假通過」——只測該擋的案例等於沒測

- 情境：寫 `hooks/pre-commit-audit.sh`（個人絕對路徑 lint），下游以 exec wrapper 指向正本。跑 7 項測試，其中「該擋的」全過、「該放行的」全掛。根因是正本忘了 `chmod +x`——`exec` 一個沒有執行權限的檔案回 126，git 收到非 0 就擋掉**所有** commit
- 錯誤/風險：**「該被擋的案例通過了」完全不能證明攔截器是對的**——一個壞掉成「擋一切」的 hook，在只測負面案例的測試裡是滿分。若當時只寫 T2/T3（該擋的），會得到 100% 通過然後把一個擋掉所有 commit 的 hook 裝到 6 個 repo。是「乾淨內容應通過」那條把它揪出來
- 修正：`chmod +x` 正本；測試補齊四象限——該擋的擋（T2/T3/T8）、該放的放（T1/T4/T5）、旁路有效（T6）、內部錯誤 fail-open（T7）。9/9 通過後才安裝，並在真實 repo 用探針檔實測一次
- 規則：**任何攔截型機制（hook、gate、validator、權限檢查）的測試必須包含「陰性案例」**——不只測「壞輸入被擋」，更要測「好輸入放行」。前者能被「擋一切」的壞實作滿足，後者不能。同理，攔截器上線後要在真實環境跑一次正常流程，確認沒有把日常工作擋死

## 2026-07-31 bash 變數後接全形標點會被吃進變數名，配 set -u 直接崩

- 情境：`bin/install-git-hooks.sh` 寫 `echo "...core.hooksPath=$hp，.git/hooks 不會被執行..."`。`$hp` 後面緊接全形逗號「，」，bash 把多位元組字元一起當成變數名的一部分，`set -u` 判定 unbound variable，腳本當場非零退出——警告沒印出來，而且整個 preflight 失敗
- 錯誤/風險：**這條路徑平常跑不到**（只有 repo 設了 `core.hooksPath` 才進），所以不寫測試就永遠不會發現。更陰險的是它會讓測試「假通過」：另一處同類寫法（`$CANON_ABS（需 chmod +x）`）在「preflight 應該失敗」的測試裡回傳 exit 1，剛好符合預期——**測試綠燈，但失敗原因是崩潰而非預期的檢查邏輯**
- 修正：改用 `${hp}` / `${CANON_ABS}` 大括號。並用 `grep -rnP '\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7F])'` 掃全 repo 找同類寫法（另兩處在註解、一處是跳脫的字面 `\$HOME`，無害）。測試補上「訊息內容正確」的斷言，不只斷言 exit code
- 規則：**中文訊息裡的 shell 變數一律寫 `${VAR}`**，不要裸 `$VAR`——中文標點緊跟變數是這個 codebase 的常態。另：**斷言 exit code 不等於斷言行為**，預期失敗的測試要一併斷言錯誤訊息內容，否則崩潰與正常失敗無法區分

## 2026-08-04 文件裡的「已安裝 N 份」是手抄快照，會靜默漂移成謊報

- 情境：`enforcement-layers.md` 記載 pre-commit-audit「已安裝 6 份 wrapper、md5 一致」，ADR-016 同樣寫「已裝 6 個 repo」。2026-08-04 現算實際安裝數是 **0**——五個現存 repo 的 `.git/hooks/pre-commit` 全部不存在。同一批還發現 ADR-016 宣稱「已刪 5 份下游 post-commit 副本」，`shopee` 那份仍在跑，而且它正是 ADR-014／015 禁止的 latest.md 自動寫入路徑
- 錯誤/風險：**文件宣稱有防護而實際沒有，比明擺著沒有更危險**——沒人會去查一個「已完成」的項目。根因不是誰偷懶，是「部署狀態」被寫成散文而非現算：手抄的當下也許是真的，之後任何一次 `.git/hooks` 重建、repo 重 clone、或收尾漏做都會讓它變謊報，且沒有任何機制會報錯。這與 2026-07-23「正本改了但部署物是另一份實體」同源，只是這次連「部署物存不存在」都是猜的
- 修正：補裝四份並刪除殘留 post-commit；把 `enforcement-layers.md` 的清單段改寫成**附一段現跑指令**，並明講「本清單是手抄快照、會漂移」；`ADR-016` 補記誠實標註兩項成果都沒落地過；防復發（`bin/check-hook-install.sh` 現算比對）進 TODO
- 規則：**凡是宣稱「已安裝 / 已部署 / 已刪除 N 份」的文件段落，一律附上現算指令，或直接改成腳本輸出**。散文只准描述設計意圖，不准描述部署狀態——部署狀態的唯一可信來源是現在跑一次。驗收同理：看行為證據（跑得出來），不看完工報告（寫得出來）

## 2026-08-08 對抗式評估「大部分是對的」正是最危險的時候——證據要自己重跑

- 情境：WakaWaka 活躍 agent 面板計劃書 v1 送 `codex exec` 做對抗式評估，回收 12 條（2 BLOCKER / 6 HIGH / 4 MEDIUM）。兩條 BLOCKER 都成立，而且比它說的更嚴重（實測 99 個 Codex rollout 有 51 個以未閉合 turn 結尾，最舊 4.9 天；Claude 側 400 檔抽樣 825 筆候選中 397 筆是 `isMeta`，48% 誤判率）。但逐條重跑驗證時發現：第 7 條稱 `~/.codex/sessions` 有 1,152 檔 / 148 MB，實測是 99 檔 / 41 MB——那個量級是 `~/.claude/projects`（1,054 檔 / 108 MB），它把兩棵樹的統計搞混；第 2 條把 slash command 列為會打破 human-message 判定的情況，實測 `isMeta ∩ slash-command = 0`，零重疊，slash command 本來就該算回合邊界
- 錯誤/風險：**評審的高嚴重度發現全中，會產生「這份評估很可靠」的月暈效應，讓人對剩下的條目降低查核標準**。錯誤的那兩條都帶著具體數字與檔案行號，外觀與正確的那十條完全一致——可信度無法從形式判斷。若照單全收，錯誤的成本估算會導致架構被過度削減（第 7 條），正確的邊界規則會被改壞（第 2 條）
- 修正：對每一條的關鍵證據都自己重跑一次（`find`/`du` 現算檔數與容量、python 掃 JSONL 現算欄位分布），在計劃書的回應表格裡逐條標「成立／方向成立數據錯誤／部分不同意」並附我自己的實測數字。推翻的兩處連同理由寫進交接文件，避免下一個 agent 又改回去
- 規則：**委派出去的審查／評估，回收後要驗證的是它的證據不是它的結論**——尤其在它大部分講對的時候。帶數字的斷言一律現算一次（檔數、容量、命中率這類最容易張冠李戴）；帶「這樣會出錯」的斷言一律找一個真實反例或正例驗證。在回應文件裡明確區分「全採納／採納結論但修正證據／部分不同意」三種處置，並把不同意的理由留給下游，否則下一輪會被改回去

## 2026-08-08 監控工具自己會呼叫被監控的 agent——裝 lifecycle hook 前先查自我遞迴

- 情境：WakaWaka（監控 Claude Code / Codex 的 menu bar app）規劃改用 lifecycle hook heartbeat 來偵測活躍 agent，SessionStart 建 registry、SessionEnd 刪除。寫計劃書時 grep 自家程式碼才發現 `ParserRunner.swift:138` 每 ~10 分鐘會執行 `claude -p "/usage"` 抓額度——裝上 SessionStart hook 之後，**WakaWaka 每 10 分鐘會把自己註冊成一個活躍 agent**，面板上閃一個不存在的 Claude session
- 錯誤/風險：這類自我遞迴在設計階段完全看不出來，因為 hook 設計與 app 的資料抓取邏輯在兩個心智模型裡。實作完才會發現，而且症狀（面板偶爾多一列、10 分鐘一次）容易被誤判成 registry 清理邏輯有 bug，往錯的方向除錯。同源風險還有：若 heartbeat 觸發 UI 更新、UI 更新又觸發資料抓取，會形成穩定的自激迴圈
- 修正：計劃書 §3.4 明列此坑，解法是 `ParserRunner.buildEnv()` 注入 `WAKAWAKA_INTERNAL=1`，所有 heartbeat hook 偵測到該變數直接 no-op，並列為測試第 2 條。**狀態：已寫進規格與測試清單，尚未實作**
- 規則：**幫某個 agent 裝 lifecycle hook 之前，先 grep 自己的程式碼有沒有在呼叫那個 agent 的 CLI**。凡是「觀測 X 的工具」同時「會呼叫 X」，就必須有一條明確的自我識別通道（env 變數最簡單，比對 pid / 命令列參數都比較脆）。這條檢查要放在設計階段，不是等實作完看到鬼影才回頭找

## 2026-08-08 路徑出現在 diff 內文 ≠ 那個檔案被動過——挖 log 統計要抓「作用目標」不是「字串命中」

- 情境：實作 `bin/skill-usage.py`（挖 Claude transcript / Codex rollout 統計 skill 使用次數）。第一版對 tool call 的 arguments 全文抓 `SKILL.md` 路徑，跑出來 12 個 mentor-* 這類幾乎沒動過的 skill 全都顯示 `edit=3`
- 錯誤/風險：查下去發現那三筆是 `apply_patch` 在改 `WakaWaka/AGENTS.md`、`shopee/CLAUDE.md`、`skills/index.json`——**patch 的內文列出了 18 / 21 / 38 條 SKILL.md 路徑**，一次就假造出數十個「編輯事件」。若沒查證直接採信，之後的冷熱分層會建立在幻影資料上，而且錯得很像真的（數字整齊、分佈合理）
- 修正：改為只從 `*** Update/Add/Delete File:` 標頭取作用目標，patch 內文一律視為內容不是目標；補一條回歸測試（patch 改別的檔但內文引用兩個 skill → 該兩個 skill 必須 0）。修正後幻影 edit 全部歸零
- 規則：**從 log／transcript 挖行為統計時，先問「這個字串是這次操作的作用目標，還是只是被順帶提到」**。寫入類操作只認宣告目標的欄位（patch 標頭、`file_path`），讀取類要防的是內文引用與工具自身的分析輸出。統計出來的數字若在「不可能常被動的項目」上呈現整齊分佈，優先假設是計數口徑錯了，不是使用習慣特別
