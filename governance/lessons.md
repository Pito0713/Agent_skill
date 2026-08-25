# Lessons Log（append-only）

> 踩坑教訓日誌。格式與精簡規則見 `governance/maintenance-protocol.md` 第 3、4 節。
> 只加不改不刪。新條目加在最下面。

---

## 已歸納移除的條目（2026-08-21，走 §4 精簡流程，使用者同意）

13 條反覆踩同一件事的教訓已升級為可勾選判準，**規則沒有消失，換了地方**。
完整案例全文用 **`git log -p governance/lessons.md`** 取回（本檔的備份不進版控——
條目內文本身在講個人絕對路徑，整份備份會被 pre-commit-audit 判為洩漏，
見 `.gitignore`；`governance/backups/lessons.md.2026-08-21.bak` 只存在於當時那台機器）：

| 群 | 移除的條目日期 | 現在在哪 |
|----|--------------|---------|
| 靜默失效 / 宣稱 ≠ 實際 | 07-04、07-06、07-07、07-23、07-24、07-31（下游反注入）、08-04、08-17（hook trust hash） | `judgment-rubrics.md` **R6** |
| 驗收假訊號 | 07-22、07-31（攔截器假通過）、08-10、08-17（codex 繼承制度） | `judgment-rubrics.md` **R2**（後 4 條 checkbox） |
| codex 委派環境 | 08-17（`--search` / `timeout`） | `skills/engineering/cli-delegate/SKILL.md`（規則早已落地）＋ `delegation-templates.md` §通用檢查 |

**未移除的近似條目**：`2026-07-31 bash 變數後接全形標點` 的後半（斷言 exit code
≠ 斷言行為）雖已進 R2，但前半（中文訊息裡 shell 變數一律寫 `${VAR}`）在 `rules/`
沒有任何落地處——移除會讓規則消失，故整條保留。

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

## 2026-07-04 制度檔把單一 harness 的工具參數寫成通用規則，跨 harness 執行即撞牆

- 情境：Antigravity session 依 tech-lead-mode / model-orchestration 委派 subagent，照抄 `subagent_type: "general-purpose"` / `isolation: "worktree"`，該環境只認 `TypeName` / `Workspace`，工具層直接報錯；Phase 0 的 shell 偵測在逐次核准 shell 的 harness 把開局卡成人工點擊
- 錯誤/風險：模型越忠實遵守制度檔，撞牆越硬；且「整批替換成新環境參數」的直覺修法只會反向弄壞主環境
- 修正：model-orchestration §2 改 harness 雙欄適配表；tech-lead-mode Phase 2 標註語法歸屬；coding-workflow-core Phase 0 原生工具優先（ADR-008）
- 規則：制度檔寫工具參數時必須標註適用 harness；通用原則與 harness 語法分離，執行前以當前工具 schema 為準，不照抄他 harness 參數名

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

## 2026-07-23 遷移腳本只覆蓋「當下看得到的」路徑，漏掉註解與舊名

- 情境：寫 `bin/migrate-downstream-paths.sh` 時，改寫規則是照我自己驗證案例裡的常駐 6 條逐條列舉。實際跑第一個真實專案（WakaWaka）才發現：還有 14 條被 `#` 註解掉的按需載入路徑、以及一條 ADR-011 改名前的舊名 `gemini-assist`（且未被註解、是啟用中的）。真實專案共 21 條需改寫，我只處理 5 條
- 錯誤/風險：① 用「逐條列舉」而非「通用規則」處理結構性改名，覆蓋率取決於樣本而非規則 ② 把註解掉的引用當成不存在——使用者取消註解那天才會發現斷鏈，且一樣是靜默失敗 ③ 只拿自己造的 fixture 測，沒先掃真實資料的全部變體
- 修正：改成通用 regex（`<category>/<name>.md` → `<name>/SKILL.md`，rules/governance 白名單排除）＋ 舊名映射；並加「改寫後逐條驗證新路徑真的存在，否則不寫入」的防呆
- 規則：寫批次改寫腳本前，先 `grep -oE ... | sort -u` 掃出真實資料的**所有變體**再設計規則；改寫結果一律用「目標是否真的存在」驗證，不能只看 diff 好不好看。註解掉的引用要照改——它是待啟用狀態，不是不存在

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

## 2026-07-31 bash 變數後接全形標點會被吃進變數名，配 set -u 直接崩

- 情境：`bin/install-git-hooks.sh` 寫 `echo "...core.hooksPath=$hp，.git/hooks 不會被執行..."`。`$hp` 後面緊接全形逗號「，」，bash 把多位元組字元一起當成變數名的一部分，`set -u` 判定 unbound variable，腳本當場非零退出——警告沒印出來，而且整個 preflight 失敗
- 錯誤/風險：**這條路徑平常跑不到**（只有 repo 設了 `core.hooksPath` 才進），所以不寫測試就永遠不會發現。更陰險的是它會讓測試「假通過」：另一處同類寫法（`$CANON_ABS（需 chmod +x）`）在「preflight 應該失敗」的測試裡回傳 exit 1，剛好符合預期——**測試綠燈，但失敗原因是崩潰而非預期的檢查邏輯**
- 修正：改用 `${hp}` / `${CANON_ABS}` 大括號。並用 `grep -rnP '\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7F])'` 掃全 repo 找同類寫法（另兩處在註解、一處是跳脫的字面 `\$HOME`，無害）。測試補上「訊息內容正確」的斷言，不只斷言 exit code
- 規則：**中文訊息裡的 shell 變數一律寫 `${VAR}`**，不要裸 `$VAR`——中文標點緊跟變數是這個 codebase 的常態。另：**斷言 exit code 不等於斷言行為**，預期失敗的測試要一併斷言錯誤訊息內容，否則崩潰與正常失敗無法區分

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

## 2026-08-10 把「我發現的坑」寫進計劃書之前，先查同一份資料源的既有 parser 怎麼處理

- 情境：規劃 WakaWaka token 活動分佈時，原型踩到 Claude transcript 的 requestId 去重問題（一次 API 回應拆成多筆記錄、streaming 時 usage 遞增），我把它當成新發現寫進計劃書 §1，還斷言「不能直接照抄 `usage-calculator.ts`」。送 Codex 評估後才發現：`usage-calculator.ts:82` 的去重鍵早就是 `` `${requestId}|${message.id}` ``，註解明寫「keeps the LAST occurrence (latest state of a streaming response is the most complete)」，`daily-usage.test.ts` 甚至有一條測試叫 `same requestId|msgId deduped, last-write-wins (streaming)`，用的正是 100→150→200 的情境
- 錯誤/風險：不只是白做工。我的原型取**第一筆** usage（既有實作取最後一筆），實測會系統性低估 1.62% 的 output，而且計劃書叫下一個 agent「不要照抄既有實作」——等於主動把一個已經被正確解決的問題重新引入。同一個 codebase 裡出現兩套對同一份資料的不同解讀，之後兩張報表的數字對不起來，除錯時沒人會想到根因在去重鍵
- 修正：v2 §1 改為「去重鍵與 last-write-wins 必須重用既有實作，只有 content 聯集是新的」，並把「既有 codebase 早就解決了」寫進修訂摘要，避免下一個 agent 又繞回去
- 規則：**動手處理某份資料源之前，先 grep 既有程式碼有沒有人處理過同一份資料**（`grep -rn "requestId\|dedup\|last-write"`）。尤其當你在原型階段「發現」一個資料格式的陷阱時——那種陷阱通常不是第一次有人踩，既有實作的註解與測試名稱就是最好的文件。把「這個既有模組怎麼處理同一份輸入」列進計劃書的必讀清單，而不是等審查者來指出

## 2026-08-10 原型用寬鬆比對 + 沒有守恆檢查，會產出討喜的假數字並被寫進規格

- 情境：同一份計劃書的分類原型，Bash 指令分類用 `'ls' in command` 這種 substring 比對。得到「理解 21.1% / 開發 44.5% / 驗證 11.4%」看起來很合理的分佈，我把它當成可行性證據寫進 v1，還拿來論證「主指標該用 output token」。Codex 指出四個桶只加到 88.7% 不守恆後重算，改成嚴格 `startswith` 並補上守恆檢查，同一份資料變成「理解 **2.7%** / 其他 **41.6%**」——`'ls'` 命中的是 `tools`、`false` 這類字
- 錯誤/風險：寬鬆比對的誤判**永遠是把東西塞進某個具名分類**，不會塞進「未分類」，所以它的偏誤方向固定是「看起來分類得很好」。少了守恆檢查（各桶總和是否等於全體），這個偏誤沒有任何自動訊號會揭露。結果是拿一組討喜的假數字去支撐架構決策，而且那些數字已經進了要交給下一個 agent 執行的規格文件
- 修正：v2 把「五桶總和 == segment total、excluded 不計入任何桶」列為必須有測試的 invariant，並把完成判準寫成「未分類率須降到 25% 以下，否則停下來重新檢視分類法」。真實數字（other 41.6%）誠實寫進計劃書，連帶揭露分類法本身需要 shell chain 解析與 MCP mapping 才可用——那是 v1 沒認清的範圍
- 規則：**任何分類/歸因原型，第一件事是加守恆檢查（各類總和 == 全體），第二件事是看「未分類」桶有多大**。未分類率是分類器品質的唯一誠實訊號；一個未分類率為 0 的分類器不是完美，是它在亂塞。另：原型用的比對規則若比正式實作寬鬆，它產出的數字不得當成可行性證據寫進規格——要嘛原型就用正式規則，要嘛在文件標明「此為寬鬆比對上界」

## 2026-08-17 從防禦性程式碼反推外部 payload 形狀，推出來的是作者的不確定性不是事實
- 情境：同上。判斷 Codex 的 hook payload 長什麼樣，依據是同 repo 的 `permissionrequest-codex.mjs` 寫著 `input?.session_id ?? input?.sessionId`。
- 錯誤/風險：我據此斷定「Codex 送 camelCase `sessionId`」，寫了修法、寫了測試、還把這個「原因」寫進交接與說明。真實 payload 抓下來是 snake_case `session_id`——那個 `??` 只是原作者的防禦性寫法。更關鍵的是真相完全不同：Codex payload **沒有任何欄位表明自己是 Codex**，所以舊邏輯不是「認不出欄位」而是「把 Codex 歸成 claude-code」。錯的診斷會導出錯的修法（見上一條，那個修法還會把 hook 全關掉）。
- 修正：在 hook 最前面裝 5 行臨時探針把 payload 原封不動 append 到 scratchpad，跑一次真實 `codex exec`，拿到 ground truth 後重寫判別邏輯與測試，並把測試 fixture 換成抓到的真實 payload。探針用完立刻移除並 grep 確認無殘留。
- 規則：**外部程式送進來的資料形狀，只有攔截到的真實樣本算數**。`a ?? b` 這種相容寫法是作者不確定，不是規格；從它反推等於把別人的猜測當事實。抓一份真的比推論便宜——本例是 5 行探針 + 一次 30 秒的執行。

## 2026-08-18 「結構重複」不等於「token 可省」——抽取的淨值會被參數化成本吃掉大半
- 情境：五個 `mentor-*` skill 有七個段落逐字重複，抽出共用骨架。我先估「每份省 350–400 tok」，向使用者報「每個能砍 1,000+」。
- 錯誤/風險：實測只有 −123～−228／份（合計 −969）。原因是重複的段落各自帶著**不可合併的參數**——五個 domain 的關係詞、箭頭標籤、迷思符號、文獻來源全都不同，要保住這些，取代用的摘要就要價約 300 tok，把刪掉的 450–500 抵掉大半。第一次的「1,000+」還多算了一層：那是 SKILL.md 的體積縮減，不是淨 token 節省，若採「執行時讀共用檔」的引用式做法，單次呼叫幾乎不省。
- 修正：實測後立刻在共用檔、ADR-022、README 版本列三處都改成實測值並寫明落差原因，不留樂觀估計。
- 規則：**估重構收益要先估「替代物的成本」，不要只算刪掉多少行。** 判斷式：重複段落裡每有一個隨情境變動的參數，就有一份參數化成本要付回；參數多到摘要壓不下去時，收益主要是「消除重複、建立模板」而非省 token——這時要照實說，不要用體積縮減的數字冒充執行成本節省。另：抽出的共用檔若不是 SKILL.md，`bin/token-budget.sh` 不會統計它，維護 inventory 會少算。

## 2026-08-21 舊分析記下的待辦清單，執行前必須重掃一次實際檔案
- 情境：執行 `_shared/mentor-protocol.md` §10 三天前記下的「兩段冗餘」待辦（ADR-023）。
- 錯誤/風險：照清單刪完才發現冗餘是**三段**——§10 寫的「與其他 mentor 的根本差異表」在
  【角色定位】段，而我先刪的是【觸發條件】段裡另一張講同一件事的路由表。差一點只做半套，
  而且會在 ADR 裡把處置對象寫錯（第一版 §10 改寫確實寫錯了，量測前還先填了估計數字）。
- 修正：重新 grep 五份實際檔案，補刪【角色定位】的五張表，§10／ADR 改為記錄「三段」並附實測值。
- 規則：待辦清單是**當時的觀察**不是規格。動手前先對實際檔案重跑一次掃描，確認範圍與清單一致；
  數字一律先量測再寫進文件，不准先寫估計值等回填。

## 2026-08-25 停用 skill 必須移出索引，加 lifecycle 標記等於沒停用
- 情境：依使用統計停用 7 個 skill、合併 5 個（ADR-025）。第一直覺是在 `skills/` 下開
  `_deprecated/` 子目錄並標 `lifecycle: deprecated`。
- 錯誤/風險：兩層都不成立。① `bin/validate-skill-index.py` 用 `(repo/"skills").rglob("SKILL.md")`
  比對 index，`skills/` 底下任何一份 SKILL.md 不在 index 就直接 FAIL；② 就算加進 index 標
  lifecycle，`bin/lib-skill-farm.sh` 照樣把它 symlink 進 `~/.claude/skills/`，模型仍然掃得到——
  **標記改變不了可見性**。
- 修正：停用資料夾放 repo 根目錄 `deprecated/`（在 `skills/` 樹外），同時從 index.json 與
  llms.txt 移除該筆；`bash setup.sh` 的 `prune_orphan_entries` 會清掉兩個 farm 的舊 symlink。
- 規則：**判斷「某個東西還會不會被讀到」，看的是索引與 symlink，不是檔案裡的標記。**
  停用前先 `grep -rn "<name>" skills/` 掃現存委派點，決定內聯或移除；改完必跑
  `validate-skill-index.py` + `token-budget.sh --strict` + `setup.sh`，三者缺一都留得下殘骸。

## 2026-08-25 寫死期望值的守門測試，會在「數量下降」時才暴露
- 情境：同一批停用作業連續打爆三處寫死的斷言——`test-skill-usage.sh` 的 `38`、
  該檔用已停用 skill 當 fixture、`test-token-budget.sh` 的 waiver 清單與 `5000` bytes padding。
- 錯誤/風險：這些斷言在「只增不減」的期間全部安靜通過（新增 skill 時 38→39 才紅一次），
  真正的失效模式是**移除**：fixture 指向的檔案消失、padding 不再足以越過門檻——後者尤其危險，
  它讓「超標是勸告不是硬牆」這條測試變成永遠測不到那個分支，卻不會報錯。
- 修正：能導出的一律改導出（skill 數從 index.json 讀、padding 由 `30000 - subtotal + 1000` 算）；
  真正要當守門的（waiver 清單、成本 baseline）保留寫死，但同步換上新 baseline 並在 ADR 記明。
- 規則：測試裡的常數分兩種——**「描述現況」的要導出**（數量、路徑、fixture 名稱），
  **「守門檻」的才寫死**（預算 baseline、核准清單）。寫死前先問：這個數字變了，我是想被擋下來，
  還是只是懶得算？後者一律改導出。

## 2026-08-25 正規表達式的字元類漏一個 `$`，把絕對路徑降級成相對路徑
- 情境：`bin/skill-usage.py` 的 unresolved 桶長期有 `HOME/.codex/skills/<name>/SKILL.md` 三筆，
  看起來像「外部 skill」，實際是本 repo 的 `coding-workflow-core` / `code-review` / `cli-delegate`。
- 錯誤/風險：`SKILL_PATH_PATTERN` 的字元類 `[\w./~-]` 不含 `$`，所以 `$HOME/...` 的比對**從
  第二個字元開始**，抓到的 `HOME/...` 沒有前導斜線 → `is_absolute()` 為 False → 被接到 workdir
  後面變成不存在的路徑 → 靜默進 unresolved。三個 skill 的真實用量因此被系統性低估，
  而報表看起來完全正常——**沒有任何錯誤訊息**，只是數字偏小。
- 修正：把 `$HOME` / `${HOME}` 提成明確的前綴群組（不污染主體字元類），resolve 時只展開 HOME
  一個變數（展開任意環境變數等於用掃描器的環境冒充當時 session 的環境）；補 fixture 測試並
  **實測「移除修正後測試會紅」**，確認不是空轉的斷言。
- 規則：**統計工具的「無法歸類」桶要定期看內容，不是只看總數。** 一筆本該歸戶的資料掉進
  unresolved 不會報錯，只會讓結論偏一點——這種偏差正是靠人工掃一次桶內清單才抓得到。
  另：寫路徑比對的 regex 前，先列出真實輸入裡可能出現的前綴形式（`~`、`$HOME`、`${HOME}`、
  相對路徑），字元類漏一個就是靜默降級。
