# 計劃書：skill 定期體檢（每週二、五，只出報告）

> **性質**：一次性執行工單，非制度檔
> **建立**：2026-11-05
> **發起人**：使用者（wits）
> **基準 commit**：`a83f644`（本機 main；origin/main 另有 12 個 tw-stock-tracker commit 未 pull，與本計劃無檔案重疊）
> **狀態**：§7 已裁決，T1–T5 未開工

---

## 0. 需求與定位

**原始需求**：定期檢查 skill 制度是否漂移，每週二、五出一份體檢報告。

使用者已裁決（2026-11-05）：

| 問題 | 裁決 |
|------|------|
| 做法 | 三選一中的「1. 定期體檢、只出報告」 |
| 頻率 | 每週二、五 |

**硬性定位**：體檢**只讀不寫**。不改 repo 任何檔案、不 commit、不開 PR、不自動修。
發現問題 → 寫進報告 → 使用者看完決定要不要修、怎麼修（修的時候照 `maintenance-protocol.md` 的 🟢／🟡 分級走）。
跑幾輪確認報告品質穩定後，才另案討論是否升級成「自動出 PR」。

---

## 1. 為什麼在本機跑，不用雲端 `/schedule`

| 檢查需要的東西 | 雲端 agent 看得到嗎 |
|---------------|-------------------|
| `~/.claude/CLAUDE.md` 等全域 symlink（§7 第 2 查） | ❌ |
| 下游專案的 skill farm（`scan-downstream.sh`） | ❌ |
| 本機 transcript（`skill-usage.py`） | ❌ |
| 本機尚未 push 的最新制度檔 | ❌（只看得到 GitHub 版本） |

一半以上的檢查需要本機狀態，所以改用 **macOS launchd**。repo 已經有這樣做的前例：
tw-stock-tracker 的 `scheduled_update.sh`（ADR-027 更新，2026-10-12）。plist 放
`~/Library/LaunchAgents/`，屬於每台機器自己的設定，**不進 repo**。

launchd 的 `StartCalendarInterval` 在排定時間如果電腦在睡眠，醒來後會補跑一次，不會整次漏掉。

---

## 2. 檢查項目

分兩層。A 層是確定性腳本，不花 token；B 層要模型判斷，會花 token（剛好拿來消化平時用不完的額度）。

### A 層：腳本檢查（零 token，全部重用現有工具）

| # | 檢查 | 工具 | 判定 |
|---|------|------|------|
| A1 | `index.json` ↔ `llms.txt` ↔ 各 SKILL.md frontmatter 一致 | `bin/validate-skill-index.py` | exit ≠ 0 即 ❌ |
| A2 | 三份索引行數 ≤150、AGENTS.md ≤16KB | `maintenance-protocol.md` §7 第 1 查 | 超過即 ❌ |
| A3 | 全域 symlink 指向 `~/Agent_skill/` | §7 第 2 查 | 斷線即 ❌ |
| A4 | AGENTS.md／GEMINI.md 四個 inline 段逐字相同 | §7 第 3 查 | 有 diff 即 ❌ |
| A5 | 路由指向的檔案都存在 | §7 第 4 查 | 缺檔即 ❌ |
| A6 | 固定開場成本、description 超過 400 bytes、失效 waiver | `bin/token-budget.sh --json` | `over_budget`、超標未 waiver、`stale_waivers` 非空即 ⚠️ |
| A7 | 下游 skill farm 有沒有 dangling symlink | `bin/scan-downstream.sh` | 有即 ⚠️ |
| A8 | `skills/`、`bin/` 下的程式檔超過 300 行 | `wc -l`（新寫，幾行而已） | 列出清單，⚠️ |
| A9 | SKILL.md 內引用的 repo 相對路徑不存在 | 新寫：抽出 `skills/…`、`governance/…`、`rules/…` 路徑逐一檢查 | 有即 ⚠️ |
| A10 | repo 狀態：未 commit 變更、與 origin 的 ahead／behind | `git status -sb`（不 fetch，只讀本地追蹤資訊） | 只陳述，不判定 |

A10 刻意不 `git fetch`：fetch 會寫 `.git/`，違反「只讀」；要知道最新 origin 狀態由使用者自己 pull。

### B 層：模型判斷（`claude -p` 無頭模式，唯讀工具）

| # | 檢查 | 輸入 |
|---|------|------|
| B1 | 不同 skill 的觸發詞重疊、可能誤觸發 | `skills/llms.txt` |
| B2 | 上次報告之後 `governance/lessons.md` 新增的教訓，有沒有寫回對應的 skill | lessons.md 的 git diff（以上份報告記錄的 commit 為起點）+ 相關 SKILL.md |
| B3 | skill 使用觀測：近 4 週零調用的 skill | `bin/skill-usage.py` 輸出 |

B3 **只陳述觀測值，不給「建議退場」之類的結論**。理由：`plans/skill-usage-and-self-correction.md`
已規定退場分層要累積 ≥8 個活躍週才啟用，Phase 2 也已由使用者裁決不做（2026-10-02）。本計劃不得繞過該裁決。

B 層模型的工具權限限定 `Read`、`Grep`、`Glob`，**不給 `Edit`、`Write`、`Bash`**。
報告檔由外層 shell 腳本寫，不是模型寫。

---

## 3. 報告

- **位置**：`~/.agent-reports/skill-health/YYYY-MM-DD.md`（repo 外）
  - 不放 repo 內：報告會含個人絕對路徑，`hooks/pre-commit-audit.sh` 會擋；而且每週兩份會把 git 歷史塞滿
  - 保留最近 26 份（約 3 個月），更早的自動刪除
- **格式**：

```markdown
# Skill 體檢 2026-11-11（二）
> 基準 commit：<sha> · A 層 ✅ 8 / ⚠️ 1 / ❌ 1 · B 層 已執行｜略過（原因）

## 需要處理
- ❌ A4 inline 段漂移：「溝通規範」段 AGENTS.md 與 GEMINI.md 不同（diff 附後）
- ⚠️ A8 超過 300 行：skills/investing/tw-stock-tracker/scripts/fetch_market_daily.py（381）

## 與上次相比
- 新增：A4
- 已解決：A7（WakaWaka dangling symlink）
- 仍未處理：A8（第 3 次出現）

## 全部檢查明細
…
```

- **「與上次相比」是重點**：同一個問題連續出現 3 次以上要標出來，否則報告會變成每次都一樣、沒人看的背景雜訊
- **失敗也要出報告**：某項檢查本身跑失敗（腳本壞掉、`claude -p` 逾時）→ 標 `💥 檢查失敗` 並附錯誤訊息，不得當作通過，也不得靜默跳過

---

## 4. 工單

### T1：A 層腳本 `bin/skill-health.sh`

- 新增 `bin/skill-health.sh`：依序跑 A1–A10，輸出 Markdown 到 stdout；每項獨立，一項失敗不中斷其他項
- A9 路徑抽取若邏輯超過 30 行，拆成 `bin/skill_health_paths.py`
- 新增 `bin/test-skill-health.sh`：至少涵蓋全部通過、單項 ❌、單項 💥 三種情境（用暫存目錄造假 repo）
- **禁區**：不修改任何既有 `bin/` 腳本；需要的行為既有工具沒有 → 回報，不順手改

### T2：B 層 prompt 與執行

- 新增 `bin/skill-health-review.md`：B1–B3 的 prompt，要求逐項輸出「發現／證據（檔案:行）／信心」
- 在 `skill-health.sh` 加 `--with-review` 旗標：呼叫
  `claude -p --allowedTools "Read,Grep,Glob" < bin/skill-health-review.md`，逾時 10 分鐘
- `claude` 不在 PATH、未登入、逾時 → B 層標 💥，A 層照常出報告

### T3：「與上次相比」與報告保留

- 讀上一份報告的檢查結果（報告末尾附一段 HTML 註解存機器可讀的結果 JSON），算新增／已解決／連續次數
- 保留最近 26 份，多的刪除
- 報告寫完發 macOS 通知（`osascript -e 'display notification …'`），標題「Skill 體檢」，內容為摘要行；通知失敗只記 log，不影響報告

### T4：launchd 排程

- 新增 `bin/install-skill-health-schedule.sh`：產生 `~/Library/LaunchAgents/local.agent-skill.health.plist` 並 `launchctl load`
  - `StartCalendarInterval`：週二、週五 10:00 各一筆
  - PATH 用絕對路徑（launchd 的 PATH 極簡，同 `scheduled_update.sh` 的做法）
  - `--uninstall` 可移除
- plist 不進 repo
- **本次只寫腳本、不執行安裝**（§7 第 3 項）

### T5：文件

- 在本計劃書末尾補「使用方式」：手動跑一次、看報告、安裝／移除排程
- **不改** `maintenance-protocol.md`、`CLAUDE.md`、索引檔。若之後要把體檢寫進制度，另案走 🟡 流程

---

## 5. 完成判準

- [ ] `bash bin/test-skill-health.sh` 全過（貼輸出）
- [ ] 手動跑 `bash bin/skill-health.sh --with-review` 一次，產出的報告由使用者看過、確認格式可讀
- [ ] 故意製造一個漂移（暫存分支改 GEMINI.md 一個字）→ 報告出現 ❌ A4 → 還原後下一份報告列在「已解決」
- [ ] 跑完後 `git status` 乾淨（證明真的只讀）
- [ ] 手動跑完會跳出 macOS 通知
- [ ] 安裝腳本以 `--dry-run` 印出的 plist 內容正確（週二、五 10:00、絕對路徑）；**實際安裝延後**，裝的時候再驗 `launchctl list | grep agent-skill.health` 與第一份自動報告
- [ ] 實作經 codex 冷啟動審查（驗證不自驗）

---

## 6. 風險

| 風險 | 處理 |
|------|------|
| 報告每次都一樣，最後沒人看 | 「與上次相比」+ 連續次數標記；全綠時報告只有一行 |
| B 層模型誤報（把不重疊的觸發詞判成重疊） | 每條發現必附證據與信心；B 層結果只是線索，不是結論 |
| B 層花的 token 超出預期 | 先量一次實際用量寫進本計劃；超過預期就降成每週一次或只跑 A 層 |
| 兩台機器都裝排程，各出一份 | 只在一台裝（安裝時再決定是哪台） |
| 檢查腳本本身漂移（例如 §7 新增第 5 查，腳本沒跟上） | A 層腳本開頭註明「對應 maintenance-protocol §7 的版本」；之後改 §7 時要一起改 |

---

## 7. 使用者裁決（2026-11-05）

| # | 問題 | 裁決 |
|---|------|------|
| 1 | 每次跑的時間 | 週二、週五 **10:00** |
| 2 | 要不要 B 層（模型判斷，花 token） | **要** |
| 3 | 排程安裝 | **先不安裝**：T4 寫好安裝腳本但不執行，裝在哪台機器之後再決定 |
| 4 | 出報告後要不要通知 | **要**：macOS 通知（`osascript`），內容只放摘要那一行（✅／⚠️／❌ 數量）與報告路徑；不寄信 |
| 5 | 報告位置 `~/.agent-reports/skill-health/` | **OK** |

---

## 8. 使用方式

以下指令都在 repo 根目錄執行。

### 手動跑一次

```bash
bash bin/skill-health.sh                  # 只跑 A 層（零 token）
bash bin/skill-health.sh --with-review    # A 層 + B 層（呼叫 claude -p，花 token，最長 10 分鐘）
```

- 唯讀：不改 repo、不 fetch；唯一的寫入是報告目錄。發現問題仍 exit 0，只出報告。
- 完成時發 macOS 通知（標題「Skill 體檢」，內容為摘要行與報告路徑）。
- B 層模型只有 `Read`、`Grep`、`Glob`；`git diff` 與 `skill-usage.py --days 28` 由外層先算好放進 prompt。
  prompt 在 `bin/skill-health-review.md`。
- B 層失敗（`claude` 不在 PATH、非 0 exit、逾時、輸出為空）→ 報告標 `💥 檢查失敗` 與原因，摘要行 B 層欄位也會反映；A 層照常出報告。

### 看報告

- 位置：`~/.agent-reports/skill-health/YYYY-MM-DD.md`（保留最近 26 份）；stdout 也會印出同一份。
- 全綠 = 標題單行；有問題 = 「需要處理」「B 層模型審查」「與上次相比」「全部檢查明細」。
  有跑 B 層而 A 層全綠時，單行後會附 B 層段落。
- B 層輸出是線索不是結論，每條附證據（檔案:行）與信心，請自行核對。
- 通知的發送記錄與失敗訊息在 `~/.agent-reports/skill-health/notify.log`。

### 環境變數（皆可選）

| 變數 | 預設 | 用途 |
|------|------|------|
| `SKILL_HEALTH_REPO` | 本腳本所在 repo | 要檢查的 repo 根 |
| `SKILL_HEALTH_HOME` | `$HOME` | A3 symlink 與 A7 下游掃描用的 HOME |
| `SKILL_HEALTH_REPORT_DIR` | `$HOME/.agent-reports/skill-health` | 報告目錄 |
| `SKILL_HEALTH_DATE` | 今天 | 報告日期 `YYYY-MM-DD`（測試用） |
| `SKILL_HEALTH_SKIP_DOWNSTREAM` | 未設 | 設為 `1` 略過 A7 |
| `SKILL_HEALTH_NOTIFY` | `on` | 設為 `off` 停用通知 |
| `SKILL_HEALTH_NOTIFY_CMD` | `osascript` | 取代通知指令，以「標題 內容」呼叫 |
| `SKILL_HEALTH_KEEP` | `26` | 保留份數 |
| `SKILL_HEALTH_CLAUDE_CMD` | `claude` | B 層（與安裝腳本解析路徑）用的 claude 指令 |
| `SKILL_HEALTH_REVIEW_TIMEOUT` | `600` | B 層逾時秒數 |
| `SKILL_HEALTH_LAUNCH_AGENTS_DIR` | `~/Library/LaunchAgents` | 安裝腳本的 plist 目錄（測試用） |
| `SKILL_HEALTH_LAUNCHCTL` | `launchctl` | 安裝腳本的 launchctl 指令（測試用） |

### 安裝／移除排程

```bash
bash bin/install-skill-health-schedule.sh --dry-run    # 只印 plist，不寫檔、不 load（可另存後 plutil -lint）
bash bin/install-skill-health-schedule.sh              # 寫 ~/Library/LaunchAgents/local.agent-skill.health.plist 並 launchctl load
bash bin/install-skill-health-schedule.sh --uninstall  # launchctl unload 並刪除 plist
launchctl list | grep agent-skill.health               # 確認已載入
```

- 排程：每週二、週五 10:00，執行 `/bin/bash <repo>/bin/skill-health.sh --with-review`；睡眠中錯過會在喚醒後補跑一次。
- 安裝時以 `command -v claude` 解析 `claude` 所在目錄並寫進 plist 的 `PATH`；找不到 `claude` 會報錯、不安裝。
- launchd 的 stdout／stderr 寫到 `~/.agent-reports/skill-health/launchd.log`。
- 只在一台機器安裝（見 §6）。更新 repo 位置後要重裝，因為 plist 內是絕對路徑。
- 測試：`bash bin/test-skill-health.sh`（含 `bin/test-skill-health-b.sh`，全用假 claude／假 launchctl）。
