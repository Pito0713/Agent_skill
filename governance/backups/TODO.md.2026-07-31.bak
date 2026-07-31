# TODO — 待辦與暫緩項目

> 記錄「已知但決定先不做」與「已知缺陷待修」。做完就刪除該項，不留已完成紀錄（歷史查 git log）。
> 格式：`## 標題` + 狀態 / 背景 / 待辦 / 決策者與日期。

---

## 交接檔並發控制：改 per-session 分檔 + git 化

**狀態**：🔴 已設計待實作（使用者 2026-07-23 決定方案，時機延後——避免與當時仍活躍的
WakaWaka session 撞規則）

**問題**：`~/.agent-sessions/<專案>/latest.md` 是**單一共享可變檔案**，Claude 與 Codex
並行時靠 `maintenance-protocol §6`「讀 → 比對最後更新 → 合併 → 寫」的自律規約保護。
2026-07-23 20:05–20:08 WakaWaka 真實發生一次並發寫入（該輪交接檔自留「併發註記」，
`hook.log` 有 `20:07:22 BLOCK repo=/Users/wits/WakaWaka`），該次靠時間錯開才沒出事。

五個漏洞：

1. **TOCTOU**：讀與寫之間有時間窗。兩個 agent 都讀到同一舊版、各自合併、先後寫入 →
   後寫者連同對方的合併成果一起覆蓋，而且它「有照規則做」
2. **只有 L1 強制力**：規則寫在 markdown 給模型讀，忘了執行就是靜默整檔覆蓋，無機制阻擋
3. **覆蓋即永久丟失**：`~/.agent-sessions` 不是 git repo，也無任何 `.bak`
4. **無寫入者身分**：所有 `latest.md` 都沒有 harness 欄位，事後查不出誰蓋掉誰
5. **「開工時間」對模型是主觀的**：沒有客觀時戳，實務上憑印象判斷「這比我記得的新」

**方案**：消除共享可變狀態，而非加鎖。每輪收工只**建一個新檔案**，檔名含時戳與
harness，天然不碰撞——兩個 agent 同時收工也不碰同一個檔案，沒有失敗模式。

```
~/.agent-sessions/<專案>/
├── latest.md                          # 聚合產物，不手改
└── entries/
    ├── 20260723-155300-claude.md
    └── 20260723-200800-codex.md
```

- 檔名：`<YYYYMMDD>-<HHMMSS>-<harness>.md`（秒級 + harness 名，碰撞機率可忽略）
- `latest.md` = 最新一筆 entry 全文 + 檔尾附歷史 entries 索引（含時間、harness、
  一行焦點）。任何時候重跑聚合都得到一致結果
- entry 標頭增設 `> 寫入者：claude | codex | agy` 欄位（補漏洞 4）
- `~/.agent-sessions` 執行 `git init`，寫入後 auto-commit（補漏洞 3；不解決並發，
  但這是目前最大的實質風險，且成本最低）。`hook.log` 進 `.gitignore`

**待辦**：

- [ ] 新增 `bin/rebuild-latest.sh`：讀 `entries/` 重建 `latest.md`（冪等）
- [ ] `skills/productivity/handoff/SKILL.md` Phase 最終：改為「寫新 entry + 跑聚合」，
      移除「重讀 / 比對時間 / 合併」那套規約（不再需要）
- [ ] `hooks/stop-handoff-check.sh`：檢查對象從 `latest.md` mtime 改為
      `entries/` 是否有本 session 之後的新檔
- [ ] `skills/productivity/project-dashboard/SKILL.md`：確認讀 `latest.md` 仍可用
      （聚合後格式不變的話可不改）
- [ ] `governance/maintenance-protocol.md §6`：改寫並發段落
- [ ] 遷移既有 7 份：`latest.md` → `entries/<其最後更新時戳>-legacy.md`，再跑聚合。
      `WakaWaka/bug-menubar-white-flash.md` 這類額外檔案不在 `entries/` 下，不動

**取捨**：讀取多一層聚合；`entries/` 會累積（定期歸檔或只保留最近 N 筆全文）。
換來的是寫入端完全無衝突——不需要鎖、CAS、時間比對，也不依賴模型記得合併。

**實作前提**：三個 harness 讀同一份 handoff skill 正本，改完即全域生效；動手前確認
沒有其他 harness 的 session 正在跑，否則它會讀到改到一半的規則。

---

## Stop hook 下游分發：暫緩

**狀態**：🟡 暫緩（使用者決定，2026-07-23）

**背景**：ADR-010 執行力分層 v1 的接線方式是 `inject.sh` 的 `install_stop_hook()`，
在下游專案 `.claude/settings.json` 掛指向正本的 Stop hook。ADR-012 重構
`inject.sh` 時該函式連同 `install_hook()`（post-commit）、`audit_personal_paths()`
一併移除；ADR-013 拆分後仍未恢復。`.codex/hooks.json` 也明確不分發。

**暫緩原因**：Stop hook 的收工攔截會與其他需求衝突，先關閉不恢復。

**待辦（解除暫緩時才做）**：
- [ ] `governance/enforcement-layers.md` §4 第 3 列仍寫著「`inject.sh` 增
      `install_stop_hook()`」——文件與實作不一致，恢復或永久放棄時都要一併更新
- [ ] 恢復的話實作位置是 `bin/inject-claude.sh`（不是總入口 `inject.sh`）
- [ ] 決定 post-commit hook 與 `audit_personal_paths()`（下游 CLAUDE.md 個人絕對
      路徑審計）是否一併恢復，或確認已由其他機制承擔

---

## ADR-014 停用 Stop hook 未落實到下游：4 個專案仍會被擋收工

**狀態**：🔴 待執行（決策早已存在，只是從未執行；2026-07-31 於 AG_knowledge 實地撞到）

**背景**：ADR-014（2026-07-27）已決定**停用** `hooks/stop-handoff-check.sh`——
`enforcement-layers.md:4` 寫明「從 `.claude/settings.json` 移除掛載，hook 檔保留
dormant」，理由正是它與收緊後的觸發政策直接衝突。但**「移除掛載」這個動作從沒真的做**，
下游專案的 settings.json 至今原封不動，hook 仍在正常擋收工。

2026-07-31 在 AG_knowledge 整理筆記 + commit 後，Stop hook 如期擋下收工，要求補寫
`latest.md` 並用 Agent tool 喚醒 handoff-verifier——而使用者全程沒說過「收工」。
模型依鐵律 1 拒絕照做，形成「制度文件說 A、執行層強制 B」的對撞。

**衝突的精確形狀**（不是模糊地帶，是字面相反）：

| | 說法 |
|---|---|
| `CLAUDE.global.md` 鐵律 1 / `Agent_skill/CLAUDE.md` 鐵律 6 | 「**只在使用者明確說「收工/交接」時才寫**，完成一段工作或 session 自然結束都不算收工、不主動寫」 |
| `hooks/stop-handoff-check.sh` 觸發條件 | `wrote_repo`（session 內有 Write/Edit/NotebookEdit 落在 repo，或 Bash 跑過 `git commit`）+ Stop 時機 |

hook 檔頭第 5 行自稱對應「鐵律 1『交接必落地』」，但它的實際觸發條件
（session 自然結束 + 有寫入）**正好是鐵律 1 明文排除的情況**。引用的條文與實作的
行為相反，而不只是嚴格一點。

**次要衝突**：hook 回饋訊息第 2 步要求「用 Agent tool 喚醒查核員」。多數 harness
的預設指示是「未經使用者要求不主動開 subagent」，照做等於未經授權開銷 token；不照做
則 hook 的補救路徑走不完。ADR-014 已把 handoff-verifier 改為「使用者說收工時手動委派」，
但 hook 內的訊息文字沒同步更新。

**殘留清單**（2026-07-31 掃 `~` 得出，全部指向正本腳本、非副本）：

`.claude/settings.json`：
- [ ] `~/AG_knowledge`
- [ ] `~/shopee`
- [ ] `~/WakaWaka`
- [ ] `~/tabetemiru`

`.codex/hooks.json`：
- [ ] `~/AG_knowledge`
- [ ] `~/Agent_skill`（正本自己也掛著）
- [ ] `~/WakaWaka`

**`hook.log` 實證（ADR-014 之後仍持續擋人）**：

```
2026-07-29 17:30:31  BLOCK repo=~/WakaWaka
2026-07-29 17:32:19  BLOCK repo=~/WakaWaka      ← 同 session 相隔 2 分鐘再擋
2026-07-29 22:36:41  BLOCK repo=~/shopee
2026-07-30 11:47:47  BLOCK repo=~/AG_knowledge
2026-07-31 11:51:07  BLOCK repo=~/AG_knowledge
2026-07-31 13:45:47  BLOCK repo=~/AG_knowledge  ← 同 session 相隔 2 小時再擋
```

ADR-014 是 2026-07-27 停用的，之後仍有 6 次 BLOCK 橫跨 3 個專案——停用完全沒生效。

**額外缺陷：「每 session 僅出現一次」是假的**。hook 回饋訊息結尾聲稱
「本提醒每 session 僅出現一次」，但防死循環靠的是 `stop_hook_active`，那只在
**單次 Stop 續跑內**為真；跨使用者輪次會重置。而 `wrote_repo` 是掃整份 transcript，
一旦本 session 有過 commit 就永遠為真。結果是**只要使用者不寫 latest.md，
每一輪對話結束都會再擋一次**（上表 07-29 與 07-31 的成對紀錄即為實證）。
使用者若照鐵律 1 拒寫，就會被無限重複騷擾。

**待辦**：

- [ ] 逐一從上列 7 個檔案移除 Stop hook 掛載（settings.json 若移除後只剩空 `hooks`
      物件，一併清掉避免留空殼）
- [ ] 若最終決定保留 dormant 而非刪檔：修掉訊息中「每 session 僅出現一次」的錯誤宣稱，
      或改成真正的 once-per-session（需落地標記，如 `hook.log` 比對 transcript 路徑）
- [ ] `hooks/stop-handoff-check.sh` 檔頭第 5 行的「對應正本條文」已失真——標為
      dormant 並註明 ADR-014 停用，或直接刪檔（`enforcement-layers.md` 說保留 dormant，
      但保留就得同步修檔頭，否則下次有人看檔頭會以為它仍是鐵律 1 的執行層）
- [ ] hook 訊息第 2 步的「用 Agent tool 喚醒查核員」與 ADR-014「改為手動委派」不一致，
      若保留 dormant 檔則一併修
- [ ] 決定 `inject.sh` 是否需要**主動反注入**：目前 ADR-013 重構後 inject 不再安裝
      Stop hook（見下方「Stop hook 下游分發：暫緩」），但**不安裝 ≠ 移除既有的**。
      沒有反注入機制的話，這類「政策已改、下游殘留」會反覆發生
- [ ] 補一條 lessons：**停用決策要含「下游反注入」步驟才算完成**。ADR-014 只改了正本
      文件就結案，L2 執行層實際上活著又跑了 4 天

**牽連**：AG_knowledge 於 2026-07-31 commit `96e9342` 把 `.claude/settings.json` 與
`.codex/hooks.json` 納入版控（當時未察覺 ADR-014 已停用），等於把殘留掛載寫進該 repo
歷史。清理時該專案要一併從版控移除或改內容。

**相關**：下方「Stop hook 下游分發：暫緩」談的是**不再由 inject 分發**（2026-07-23），
本項談的是**既有掛載未移除**（ADR-014, 2026-07-27）。兩者同主題但不同動作，前者做了、
後者沒做。

**決策者與日期**：待使用者裁示（2026-07-31 由 AG_knowledge session 提出）

---

## 7 個下游專案的舊 `@` 路徑尚未遷移

**狀態**：🔴 待執行（工具已就緒，等使用者確認才動別人的 repo）

**背景**：link farm 是扁平的，舊式 `@~/.claude/skills/<category>/<name>.md` 救不回，
必須改寫。`rules/` 三條已由 `setup-claude.sh` 的 extra entry 自動復活，不需改。

**待遷移清單**（掃描 `~/*/CLAUDE.md`、`~/*/*/CLAUDE.md` 得出）：

- [ ] `~/AG_knowledge`
- [ ] `~/gps_position`
- [ ] `~/quant_platform`
- [ ] `~/shopee`
- [ ] `~/Stock_model`
- [ ] `~/tabetemiru`
- [ ] `~/WakaWaka`

（`~/SavingsApp` 已注入但無舊路徑，不需處理）

**做法**：`bash bin/migrate-downstream-paths.sh <專案路徑>` 先看 dry-run，確認後
加 `--apply`（會留 `CLAUDE.md.pre-migrate.bak`）。遷移後該專案要重跑
`bash ~/Agent_skill/inject.sh` 才會拿到新的 managed block 與 adapter。

---

## Codex discovery root 遷往官方路徑

**狀態**：🟡 待評估

**背景**：官方 manual 記載的穩定 roots 是 `$HOME/.agents/skills` 與 repo
`.agents/skills`；本機 Codex v0.145.0 實測亦支援目前使用的 `$CODEX_HOME/skills`
與 repo `.codex/skills`。目前等於依賴相容行為。

**待辦**：
- [ ] 確認官方 roots 在當前版本的實際行為（`~/.agents/skills` 現為 legacy 目錄，
      本流程不讀寫）
- [ ] 遷移時**只需改 `bin/setup-codex.sh` 與 `bin/inject-codex.sh`**，不影響
      Claude / agy——ADR-013 拆分的主要動機之一

---

## Codex / agy 側的常駐強制力不對等

**狀態**：🟡 已知取捨（ADR-013 記載，非缺陷）

**背景**：Claude 的 managed block 用 `@` 常駐載入 `rules/coding-standards.md` 與
`rules/security.md`，模型沒得選；Codex 沒有 `@` 語法且 AGENTS.md 有 32KiB 上限，
agy 同理，只能寫成「開工必讀」的文字要求。安全底線在 Claude 是機制保證、在
Codex/agy 是紀律要求。

**待辦（想讓 Codex 也變硬保證時）**：
- [ ] 評估走 hook（`.codex/hooks.json` 目前不分發）或把安全規範精簡後內嵌進
      AGENTS.md managed block（受 32KiB 上限約束，現況 AGENTS.md 約 5KB）

## inject 殘留偵測與下游 stale：FIX-3 已落地，尚有後續

**已完成（2026-07-27，FIX-3）**：`warn_legacy_content_outside_managed_block`（preflight 偵測 block 外死引用、只警告不刪）+ `bin/scan-downstream.sh`（唯讀掃下游 farm dangling）+ `bin/test-fix-3.sh`。

**尚未做**：
- [ ] 改名後**自動重跑下游 farm**仍未實作——目前 skill 改名後，各下游要人工跑 `inject.sh` 才會清 dangling（實例：WakaWaka 停在改名前，靠本次手動修）。可做：`setup` 後選擇性掃已知下游 + 提示重跑。
- [ ] **冗餘但功能正常的舊 body 偵測不到**（保守設計，避免 false-positive）：如 shopee/CLAUDE.md 仍有 6 條 `@` 當代格式常駐（能 resolve、但新設計已改由 on-demand），FIX-3 不會警告。要清得人工判斷。
- [ ] 可選：加 opt-in `inject.sh --clean-legacy`，**只在 body 逐字比對到已知舊自動生成模板時**才移除，其餘一律保留——唯一能安全自動化清 body 的路徑。

**已知硬邊界（見 lessons 2026-07-27）**：farm 安裝寫 `.codex/`，Codex exec sandbox 擋、不能當此類 executor。
