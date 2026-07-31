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

## `pre-commit-audit` 尚未接進 `inject.sh`

**狀態**：🟡 待決（2026-07-31，ADR-016 落地後的唯一缺口）

**背景**：`hooks/pre-commit-audit.sh` 已在 6 個 repo 以 exec wrapper 安裝並實測
生效，但 `inject.sh` 不會自動裝——新專案注入後沒有這道 lint。

**待辦**：
- [ ] 決定是否讓 `bin/inject-claude.sh`（或新的 harness 中立步驟，因為 git hook
      與 harness 無關）安裝 wrapper。注意 `inject.sh` 是 🟡 級，動之前要問使用者
- [ ] 部分 repo 的 `.git/hooks/` 目錄不存在（Agent_skill 自己就是），安裝前要
      `mkdir -p`——commit `6170e81` 曾修過同一個問題，別再踩

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

---

## inject 殘留偵測與下游 stale：FIX-3 已落地，尚有後續

**狀態**：🟡 部分完成（FIX-3 已落地，餘項無時效壓力）

**已完成（2026-07-27，FIX-3）**：`warn_legacy_content_outside_managed_block`（preflight 偵測 block 外死引用、只警告不刪）+ `bin/scan-downstream.sh`（唯讀掃下游 farm dangling）+ `bin/test-fix-3.sh`。

**尚未做**：
- [ ] 改名後**自動重跑下游 farm**仍未實作——目前 skill 改名後，各下游要人工跑 `inject.sh` 才會清 dangling（實例：WakaWaka 停在改名前，靠本次手動修）。可做：`setup` 後選擇性掃已知下游 + 提示重跑。
- [ ] **冗餘但功能正常的舊 body 偵測不到**（保守設計，避免 false-positive）：如 shopee/CLAUDE.md 仍有 6 條 `@` 當代格式常駐（能 resolve、但新設計已改由 on-demand），FIX-3 不會警告。要清得人工判斷。
- [ ] **加 deprecated-mount 掃描**（ADR-015 遺留）：列出下游指向已刪除 / 已停用 hook
      的掛載。動機是 ADR-014 的殘留掛載活了 4 天沒人發現——`inject.sh` 只有「安裝」
      沒有「移除」，**不安裝 ≠ 移除既有的**。不做通用反注入（會動下游未知設定，風險
      不對稱），沿用 FIX-3「只警告不刪」。
- [ ] 可選：加 opt-in `inject.sh --clean-legacy`，**只在 body 逐字比對到已知舊自動生成模板時**才移除，其餘一律保留——唯一能安全自動化清 body 的路徑。

**已知硬邊界（見 lessons 2026-07-27）**：farm 安裝寫 `.codex/`，Codex exec sandbox 擋、不能當此類 executor。
