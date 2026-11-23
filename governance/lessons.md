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

## 已歸納移除的條目（2026-11-20，第二次精簡，計劃書 T2，使用者同意）

43 條移除 29 條。分類依據 `enforcement-layers.md` §3b：先看是否已下沉成檢查，再歸納到規則
**被用到的那個檔案**（不一律塞進 rubrics）。全文同樣用 `git log -p governance/lessons.md` 取回。

| 群 | 移除的條目日期 | 現在在哪 |
|----|--------------|---------|
| 已下沉成檢查 | 07-03（索引重複）、07-07 ×2（個人路徑）、08-08（diff 內文 ≠ 作用目標）、08-25（停用 skill）、08-25（regex 漏 `$`）、11-09（`--allowedTools`） | `validate-skill-index.py`、`hooks/pre-commit-audit.sh`、`test-skill-usage.sh`、`test-skill-health-b.sh` |
| 完成判準 | 08-08（對抗式評估）、08-25（寫死期望值）、10-07（原始值重算）、10-21（exit code） | `judgment-rubrics.md` **R2** |
| 停下來問 | 07-03（多 session 覆蓋，原已在 R3）、10-31（recalc-all） | `judgment-rubrics.md` **R3** |
| 動手前盤點既有 | 07-10、08-08（自我遞迴）、08-10（既有 parser）、08-21、09-01、10-12 | `judgment-rubrics.md` **R7**（新增） |
| 資料與數字真實性 | 07-23、08-10（守恆）、08-17（payload 形狀）、08-18、10-14 | `judgment-rubrics.md` **R8**（新增） |
| 派工 | 08-31 ×2（diff 快照、目的不寫手段） | `delegation-templates.md` §通用檢查 |
| executor 寫權 | 07-27（codex sandbox） | `model-orchestration.md` §2 |
| 交接品質 | 09-23（全部測試組）、09-29（免查清單判準） | `skills/productivity/handoff/SKILL.md` 品質標準 |

> 2026-11-23 補正（codex 審查 R1）：上表 10-07（原始值重算）、10-21（外部日期格式）的規則實際落在 **R8**；
> 08-25（停用前掃委派點）、07-07（副本先回寫獨有內容）的規則補進 **R7**；10-12（交接候選附理由）補進 handoff skill 品質標準。
> 精簡時這 5 條只保留了部分規則，其餘於本日補回。

**保留的 14 條**：6 條可下沉但尚未實作（07-22、07-31、09-30、11-09、11-10、11-20 push email）、
2 條屬下游專案的下沉（10-23 hook defer、11-20 AppKit，原文保留、不另開 TODO）、
6 條不適合歸納（07-04、07-27 觸發詞、10-08 含未結項、10-23 TUI、10-24、10-31 zsh）。

---

## 2026-07-04 制度檔把單一 harness 的工具參數寫成通用規則，跨 harness 執行即撞牆

- 情境：Antigravity session 依 tech-lead-mode / model-orchestration 委派 subagent，照抄 `subagent_type: "general-purpose"` / `isolation: "worktree"`，該環境只認 `TypeName` / `Workspace`，工具層直接報錯；Phase 0 的 shell 偵測在逐次核准 shell 的 harness 把開局卡成人工點擊
- 錯誤/風險：模型越忠實遵守制度檔，撞牆越硬；且「整批替換成新環境參數」的直覺修法只會反向弄壞主環境
- 修正：model-orchestration §2 改 harness 雙欄適配表；tech-lead-mode Phase 2 標註語法歸屬；coding-workflow-core Phase 0 原生工具優先（ADR-008）
- 規則：制度檔寫工具參數時必須標註適用 harness；通用原則與 harness 語法分離，執行前以當前工具 schema 為準，不照抄他 harness 參數名

## 2026-07-22 skill 改名只改了 name 欄，檔名與 30 處引用全留舊名

- 情境：`gemini-assist.md` 的底層工具早已從 gemini CLI 換成 agy，某次把 frontmatter `name` 改成 `agy-assist` 就收手，但檔名、`llms.txt` path、inject.sh、CLAUDE.md 路由、10 個 skill 的委派表共約 30 處仍是 gemini-assist——放了數週沒人發現，直到這次批量升 frontmatter 才撞出 name 與檔名不一致
- 錯誤/風險：不完整改名 = 懸空引用未爆彈（llms.txt path 指向的檔名與 name 不一致，靠檔名對應 name 的流程會斷）；且改名時若無腦全域 sed，會連 README 版本表 / memory ADR / handoff 這些**歷史紀錄**一起竄改，違反「不改史」
- 修正：先 `grep -rn` 全 repo 盤點所有引用，切成「活引用（路由指標 / 委派表 / skill 名標籤 → 改）」與「dated 歷史敘述（README changelog / memory ADR / handoff / 診斷快照 → 保留）」兩類分別處理；改完跑 §7 索引防漂移四查確認路由 resolve
- 規則：改 skill / 工具名是**原子操作**——`name` 欄、檔名、`llms.txt`(name+path)、所有活引用必須同一次全改；動手前先 `grep -rn` 全 repo 盤點，並區分活引用（改）vs 歷史紀錄（不改史，保留）

## 2026-07-27 「收工必寫」定義太鬆，latest.md 在 session 中途被過度觸發

- 情境：交接檔 `~/.agent-sessions/<專案>/latest.md` 的鐵律寫成「開工先讀、收工必寫」。使用者觀察到模型把「完成一段 content」就當成「收工」，同一 session 中途反覆寫 latest.md，交接檔內容過早定稿。另有 Stop hook 在每次 session 結束自動逼寫，是第二條非使用者指令的自動觸發源
- 錯誤/風險：「收工」是主觀詞，交給模型自主判斷必然發散——模型傾向把任何階段性完成解讀成收工。制度用「必寫」這種強制語氣配上模糊的觸發條件，等於預設模型會過度觸發。自動化防線（Stop hook）在使用者要的是「明確指令才動」時反而變成雜訊
- 修正：ADR-014 把觸發收緊為「只由使用者明確『收工/交接』指令觸發」，寫進 4 份索引鐵律 + maintenance-protocol §6；停用 Stop hook（settings.json 移除掛載，hook 檔留 dormant）；version-log 與 latest.md 解耦
- 規則：制度裡凡是「必做 X」配上主觀觸發詞（收工、告一段落、完成、差不多好了），要嘛把觸發詞換成客觀可判定的條件，要嘛把觸發權收回給使用者明確指令。不要用強制語氣（必寫/必做）去約束一個模型會自行擴大解釋的模糊邊界——那只會保證它過度執行

## 2026-07-31 bash 變數後接全形標點會被吃進變數名，配 set -u 直接崩

- 情境：`bin/install-git-hooks.sh` 寫 `echo "...core.hooksPath=$hp，.git/hooks 不會被執行..."`。`$hp` 後面緊接全形逗號「，」，bash 把多位元組字元一起當成變數名的一部分，`set -u` 判定 unbound variable，腳本當場非零退出——警告沒印出來，而且整個 preflight 失敗
- 錯誤/風險：**這條路徑平常跑不到**（只有 repo 設了 `core.hooksPath` 才進），所以不寫測試就永遠不會發現。更陰險的是它會讓測試「假通過」：另一處同類寫法（`$CANON_ABS（需 chmod +x）`）在「preflight 應該失敗」的測試裡回傳 exit 1，剛好符合預期——**測試綠燈，但失敗原因是崩潰而非預期的檢查邏輯**
- 修正：改用 `${hp}` / `${CANON_ABS}` 大括號。並用 `grep -rnP '\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7F])'` 掃全 repo 找同類寫法（另兩處在註解、一處是跳脫的字面 `\$HOME`，無害）。測試補上「訊息內容正確」的斷言，不只斷言 exit code
- 規則：**中文訊息裡的 shell 變數一律寫 `${VAR}`**，不要裸 `$VAR`——中文標點緊跟變數是這個 codebase 的常態。另：**斷言 exit code 不等於斷言行為**，預期失敗的測試要一併斷言錯誤訊息內容，否則崩潰與正常失敗無法區分

## 2026-09-30 寫了「必跑」卻沒接上 gate 的檢查，等於沒有檢查
- 情境：`maintenance-protocol.md` §8.6 寫明新增或修改 skill 時必跑 `token-budget.sh --strict`，
  也寫了「`--strict` 是給 pre-commit 與 CI 用的」，但 hook 一直沒呼叫它（2026-08-10 handoff
  就記了，TODO 懸置到 09-30）。9/14 新增 tw-market-rotation 時沒人跑，description 以 425 bytes
  （門檻 400）、無 waiver 直接進了 main。
- 錯誤/風險：同一個超標同時讓 `bin/test-token-budget.sh` 轉紅（`over == []` 斷言失敗），
  紅了兩週半沒人看到——檢查工具與它自己的測試都存在，只是沒有任何東西會自動執行它們。
  修的時候又連撞兩個寫死的現況常數（`pass == 22`、`23,171 bytes`），任何合法的新增 skill
  都會讓測試紅，紅成常態後就沒人當真。我第一版的「導出」寫法用 pass 自己加回去算總數，
  斷言恆真，等於把檢查拆掉——自己讀回時才抓到，改成從 `index.json` 獨立取數。
- 修正：tw-market-rotation 壓到 393 bytes（使用者裁決不補 waiver）；`--strict` 掛進
  `hooks/pre-commit-audit.sh`（staged 碰 `skills/` 才跑，非 0 即擋），clone 實測四情境；
  測試裡兩個現況常數改由 index / baseline 導出，baseline 在 clean tree 重量。
- 規則：**制度檔寫「必跑」的檢查，當天就要接上會自動執行它的地方（pre-commit / CI / 測試入口），
  接不上就改寫成「建議跑」並記 TODO——不要讓文件承諾一個沒人執行的 gate。**
  導出常數時，導出來源必須獨立於被驗證的值；用受測值自己算期望值的斷言恆真，比寫死更糟。

## 2026-10-08 交易所的標記符號要讀官方註解，不要用直覺解讀
- 情境：tw-stock-tracker 全市場日線把上市 `MI_INDEX`「漲跌(+/-)」欄的 X 當成除權息標記
  （逐檔流程也這樣用），上櫃則以「漲跌」欄數字反推除權息金額。
- 錯誤/風險：sync 回報 1,667 個除權息日金額未知。查官方回應的 notes 才知道 X 是「不比價」，
  涵蓋前一日無收盤價、除權息、新上市、恢復交易——冷門股前一天沒成交就會被標 X，
  被誤當成除權息後還原價與 `has_unadjusted_exdiv` 旗標全部失真。上櫃全市場表在除權息日
  的「漲跌」填的是「除息」文字而非數字，同樣推不出金額。測試全綠，因為 fixture 是照我的錯誤理解寫的。
- 修正：上市前一交易日無行情且查無事件者清掉旗標（725 筆）；上櫃改用官方除權除息計算結果表
  `exDailyQ` 的參考價比例（991 筆）。未知數 1,667 → 1。
- 規則：**解析外部資料的代碼、符號、特殊值前，先讀回應裡的 notes／欄位說明並抽查幾筆原始列；
  fixture 要用實際抓到的原始資料，不要用自己對格式的想像。** 數字異常大（如未知事件上千筆）
  時先懷疑解讀，不要先懷疑資料源。逐檔流程 `fetch_twse.py` 的 X 判讀可能有同樣問題，尚未處理。

## 2026-10-23 全螢幕 TUI 不能在 Claude Code 的 `!` 裡驗證
- 情境：SwarmTide（rich Live 全螢幕動畫）。agent 叫使用者「在終端機跑」，使用者用 `! python3 ...` 在 Claude Code 內執行。
- 錯誤/風險：`!` 走的是非互動 shell，不是 TTY，畫面完全不出現；程式無限迴圈，120 秒後被移到背景常駐，使用者以為壞掉。同一 session 發生兩次。
- 修正：TaskStop 停掉背景程序；README 註明 `!` 看不到動畫；agent 驗證一律用 `--snapshot` 印單張畫面。
- 規則：**交付全螢幕／互動式 TUI 時，明說「要在另一個終端機視窗執行，不要用 `!`」**，並提供不需 TTY 的驗證模式（snapshot / 單幀輸出）；使用者回報「看沒出來」先查是否在非 TTY 環境跑。

## 2026-10-23 PreToolUse hook 的 `defer` 不是「不表態」，會讓背景 subagent 卡死
- 情境：WakaWaka 的 `pretooluse.mjs` 在 Claude Code auto mode 下，想把呼叫交給 classifier 審，回了 `permissionDecision: "defer"`。SwarmTide session 通報背景 subagent 一碰工具就結束。
- 錯誤/風險：主 session 收到 `defer` 會落回正常權限流程，看起來完全正常；背景 subagent 收到則把呼叫掛起等 resume，Agent tool 不會 resume，subagent 沒有 tool_result 也沒有回報就結束。本機 transcript：主 session 約 2,000 次全數正常，subagent 16 次全數掛起。問題存在超過一個月才被發現。
- 修正：要「交還 Claude Code」時 exit 0、stdout 不輸出任何東西（WakaWaka `dbf9613`）。
- 規則：**hook 不表態就什麼都不輸出，不要回 `defer`**；改了 hook 的決策行為，除了主 session，也要在背景 subagent 裡實測一次（transcript 出現 `hook_deferred_tool` 就是被掛起）。

## 2026-10-24 TUI 回報「沒更新 / 沒看到」，先查程序啟動時間、暫停與捲動狀態
- 情境：SwarmTide（rich Live 全螢幕儀表板）一天內三次被回報「畫面沒即時更新 / 沒看到新功能」。
- 錯誤/風險：三次原因都不是資料讀取——(1) 使用者在 Terminal.app 用觸控板往上捲，全螢幕畫面中滾輪捲的是一般畫面的緩衝區，上方露出 shell 舊內容、畫面像凍住；(2) 誤按空白鍵，暫停連帶停掉真實資料輪詢；(3) 程式碼改了，但使用者還在跑改版前啟動的程序。另外 rich Live 期間 `sys.stdout` 被換成代理，直接寫跳脫序列（開滑鼠回報）會被吃掉。
- 修正：開滑鼠回報（1000+1006）接管滾輪、序列寫 `sys.__stdout__`；暫停只作用在模擬；請使用者 `q` 重開。
- 規則：**收到「TUI 沒更新」先 `ps -o lstart` 比對程序啟動時間與最後 commit 時間**，再看截圖 / 錄影的 HUD（PAUSED？）與畫面是否被捲動；全螢幕 TUI 要接管滾輪，資料輪詢不要掛在使用者可暫停的時鐘上。

## 2026-10-31 zsh 不會對未加引號的變數做 word splitting
- 情境：Bash tool（zsh）裡用 `j='-H Content-Type:application/json'; curl $j ...` 送 API 寫入。
- 錯誤/風險：zsh 把 `$j` 當成單一參數，header 沒送出，7 個 POST/PATCH 全部無聲失敗（`curl -s` 也沒有輸出），差點誤以為已寫入。
- 修正：改用 shell function 並直接寫出 `-H 'Content-Type: application/json'`，加 `-w '%{http_code}'` 確認狀態碼。
- 規則：**zsh 下不要把多個參數塞進一個變數**（要拆就用 array `${=var}` 或 function）；寫入型 curl 一律帶 `-sS -w '%{http_code}'`，寫完再查 DB 確認。

## 2026-11-09 worktree 隔離的 subagent 不是從本地 HEAD 開分支
- 情境：tech-lead-mode 派 Ticket B（`isolation: worktree`），本地 main 已 ff 到 Ticket A 的 `51d0ee8`（未 push）。
- 錯誤/風險：executor 的 worktree 基底是 `a31b6df`（origin/main），沒有 A 層檔案；它依工單停下回報。之後用 SendMessage 授權 ff，但該 worktree 因「無變更」已被自動清掉，無處可做，只能重派。Round 2 也一樣是從 `a31b6df` 開始。
- 修正：工單加「第 0 步」：`git log -1` 確認基底，不符就 `git merge --ff-only <sha>`（預先授權），再 `git diff --name-only` 核對帶進來的檔案。
- 規則：**本地 main 領先 origin 時派 worktree executor，工單必含基底確認 + 預授權 ff**；executor 未改檔就停下時，worktree 會消失，補授權要重派，不要用 SendMessage 續跑。

## 2026-11-10 worktree 快照跑測試，依賴自身絕對路徑的測試會誤報
- 情境：project-review L1 在 HEAD 的 git worktree 快照跑檢查；冒煙測試拿 Agent_skill 跑 `bin/test-skill-usage.sh`。
- 錯誤/風險：原地跑通過、快照裡失敗 3 項——測試讀真實 `~/.codex/skills` farm，symlink 指回 `~/Agent_skill`，換到快照路徑就對不上。沙盒測試全綠也抓不到，只有對真實 repo 實跑才現形。
- 修正：試點專案避開此類測試（使用者選 a）；Floating `swift test` 在快照實跑 390 tests 全過才登記。
- 規則：**把專案登記進 project-review 前，先用 scratchpad 的登記表與報告目錄在快照上實跑一次**；原地過、快照不過 = 測試不 hermetic，不是專案壞了。

## 2026-11-20 push 到公開 repo 前沒檢查 commit author email
- 情境：使用者建好 GitHub 空 repo 要求搬入專案，直接 commit + push；事後使用者問「有沒有私人資料」才掃描。
- 錯誤/風險：檔案內容乾淨，但 commit author/committer 帶全域 git config 的個人 Gmail，已 push 到 public repo；要清除只能改寫歷史 + force push。
- 修正：回報使用者，提供「改 noreply + 改寫歷史」選項，未經同意不動。
- 規則：**第一次 push 到新 remote 前，先查 repo 是否 public，並跑 `git log --format='%ae %ce' @{u}..HEAD`（或全歷史）確認不是個人信箱；不是 noreply 就先問使用者。**
- 下沉：script——pre-push 檢查：`git log --format='%ae%n%ce' <range> | grep -v 'users.noreply.github.com\|noreply@anthropic.com'` 有輸出就警告並要求確認

## 2026-11-20 AppKit 選單列 App 沒有主選單時 ⌘V 無效
- 情境：SwiftPM 手刻的 accessory（LSUIElement）App，SwiftUI TextField 無法貼上。
- 錯誤/風險：⌘C/⌘V/⌘A/⌘Z 是靠主選單 Edit 項目的 key equivalent 送進 responder chain；沒設 `NSApp.mainMenu` 就全部失效，編譯與基本測試都抓不到。
- 修正：補 Edit 主選單（cut/copy/paste/selectAll/undo/redo）。
- 規則：**不用 Xcode 範本自建 AppKit App 時，啟動就裝 Edit 主選單**；驗收要實際測貼上。
- 下沉：架構——之後的 menu-bar App 範本內建 `installEditMenu()`；驗收清單加「⌘V 貼上」一項

## 2026-11-22 背景執行 codex exec 沒給 stdin，卡在等輸入 40 分鐘
- 情境：三路 codex 交叉驗證用 `&` 背景並行，其中一路沒有 pipe 輸入也沒有 `</dev/null`。
- 錯誤/風險：codex 印出「Reading additional input from stdin...」後一直等，外層 `wait` 跟著卡住；另兩路早已完成，整批結果被拖了 40 分鐘才拿到。沒有任何錯誤訊息，只看得到「沒有新輸出」。
- 修正：停掉該 task，補 `</dev/null` 重跑，數分鐘內完成。
- 規則：**非互動呼叫 codex exec 時 stdin 一定要有來源**——要嘛 pipe 資料，要嘛 `</dev/null`；背景並行時尤其要檢查每一路。
- 下沉：架構——T6 C4 的 `bin/codex-ro.sh` wrapper 在沒有 pipe 輸入時自動接 `</dev/null`，並固定帶唯讀旗標；文字規則擋不住，因為每次手寫指令都可能漏，只有讓所有呼叫都經過同一個入口才能讓錯誤不可能發生

## 2026-11-23 精簡 lessons 時只按「主題」歸納，條目裡的次要規則被丟掉
- 情境：T2 把 43 條教訓歸納進 R2／R7／R8 等去處，歸納表也逐條標了去處；codex 結案審查逐句比對後發現 5 條只搬了主規則。
- 錯誤/風險：10-07 被標在 R2，但 R2 引用它的是「先弄壞一次」，真正的規則「換規則重算要回到原始值」不見了；10-21、08-25、07-07、10-12 也各掉了半句。歸納表看起來每條都有去處，反而讓遺失更難被發現。
- 修正：五條補回 R7／R8／handoff 品質標準，歸納表下加補正註記（`396f2a5`）。
- 規則：**移除一條教訓前，它「規則」欄的每一個子句都要能在去處 grep 到對應文字**；只確認「主題對得上」不算歸納完成。
- 下沉：cop——歸納是語意比對（同一規則常被改寫成不同字句），regex 判不出；架構層也無法讓「刪除前比對」不可能被跳過。做法：精簡時對「移除條目 × 去處檔案」派冷啟動 reviewer 逐子句比對，本次 codex R1 即此形式

## 2026-11-23 NSPopover 關掉後 SwiftUI timer 動畫照跑，debug build 閒置吃 15–20% CPU
- 情境：WakaWaka 的 popover 閒置畫面有 Pac-Man 動畫（`Timer.publish(every: 0.14)` 推進 `@State frame`）。popover 關掉後 hosting view 還活著。
- 錯誤/風險：每秒約 7 次重新 layout 一個不在畫面上的視窗，開機 2.5 天累積 88 分鐘 CPU。看程式碼時以為 1 秒 poll 那類 timer 才是成本，實際上 `sample` 顯示 app 自己的 code 不到 1%，全在 SwiftUI display cycle。
- 修正：view model 加 `isPopoverShown`（`NSPopoverDelegate` 更新），timer tick 時不可見就不改 state（`bfb877c`），閒置 CPU 降到 <1%。
- 規則：**常駐 app 的 CPU 問題先 `sample <pid>` 再看 code**；另外，任何 timer 驅動的 SwiftUI 動畫都要綁可見性，popover／隱藏視窗裡的 view 不會自己停。
- 下沉：無——屬 SwiftUI 實作細節，靠 code review 時注意 `Timer.publish` + `@State` 是否有可見性守門
