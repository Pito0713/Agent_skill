# TODO — 待辦與暫緩項目

> 記錄「已知但決定先不做」與「已知缺陷待修」。做完就刪除該項，不留已完成紀錄（歷史查 git log）。
> 格式：`## 標題` + 狀態 / 背景 / 待辦 / 決策者與日期。

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
