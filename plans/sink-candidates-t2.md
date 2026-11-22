# 計劃書：T2 下沉候選實作（6 張工單）

> **性質**：一次性執行工單，非制度檔
> **建立**：2026-11-22
> **發起人**：使用者
> **基準 commit**：`59bc198`（main，工作區乾淨）
> **狀態**：W1–W6 未開工
> **來源**：`plans/agent-env-trust-pyramid.md` T2 ① 候選表（6 條）；W3 另併入 T3 真模型二跑的發現（`test-skill-*.sh` 無自動執行入口，2026-11-22 已核實）

---

## 0. 共同約束

- 全部是 **L2 確定性檢查**（`enforcement-layers.md` §3b 第 2 層）。新檢查先**警告級**，觀察兩週誤報率再決定是否升攔截——W6 除外（見該單）
- 每支新檢查必附測試，fixture 放 `mktemp -d` 臨時 repo；不得讀真實 `~` 或真實 repo 狀態（11-10 教訓：不 hermetic 的測試會在快照誤報）
- 掛進 `hooks/pre-commit-audit.sh` 的規則要能用既有 `audit-ok` 旁路
- 完成後回 `governance/lessons.md` 對應條目，在 T2 歸納表標「已下沉（commit）」——**只改歸納表，不改條目原文**（§4 只加不改）
- 動 `hooks/` = 影響所有下游專案 → 🟡，commit 前跑 `bash bin/test-skill-health.sh` 與新測試

---

## 1. 工單

### W1　改名殘留檢查　🟢（來源：lessons 07-22）

- **改**：`bin/validate-skill-index.py` canonical 檢查加「`Path(entry["path"]).parent.name == entry["name"]`」（T3 一跑 B2 發現：現在只比 frontmatter name）
- **選做**：從 `git log -M --diff-filter=R` 取最近改名的 skill 舊名，grep `skills/` `governance/` `inject.sh` `CLAUDE.md` `AGENTS.md` `GEMINI.md` 活引用；README 版本表 / `memory/` / handoff 屬歷史，排除
- **驗收**：測試補「目錄名 ≠ name」fixture → validator 非 0；現有 repo 跑 validator 仍通過
- **風險**：選做部分的「活引用 vs 歷史」邊界靠路徑白名單，誤報先警告

### W2　中文標點緊接 shell 變數　🟢（來源：lessons 07-31）

- **改**：`hooks/pre-commit-audit.sh` 對 staged `*.sh` 的**新增行**跑
  `grep -nP '\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7F])'`，命中列出、警告不擋
- **排除**：以 `#` 開頭的註解行、`\$` 跳脫字面（原教訓記錄的兩類誤報）
- **驗收**：`bin/test-pre-commit-audit.sh`（若 T5 尚未建立則本單建立）≥3 案例：`$hp，` 命中 / `${hp}，` 不命中 / 註解行不命中
- **備註**：T3 一跑模型把這條標成 `cop`，正確是 `script`

### W3　「必跑」檢查沒接上自動執行　🟡（來源：lessons 09-30 + T3 二跑發現）

- **做（兩段）**：
  1. **實例修補**：`bin/test-skill-usage.sh`、`bin/test-skill-health.sh` 目前沒有任何自動入口（hooks / launchd / CI 都無）。依 `pre-commit-audit.sh` 既有 token-budget 的模式，staged 碰到對應 `bin/` 檔才跑
  2. **通用檢查（警告級）**：新增 `bin/check-required-gates.sh`：從 `governance/` `skills/` `rules/` 抽「必跑」後的 `bash bin/...` / `python3 bin/...` 指令，比對 `hooks/` 與 `bin/install-*-schedule.sh` 有無呼叫，沒有就列出
- **驗收**：段 1 實測 staged 改 `bin/lib_skill_usage.py` → hook 有跑測試；段 2 在現有 repo 跑出清單，逐條人工確認無誤報後才掛進 skill-health A 層
- **風險**：段 1 讓 commit 變慢（量測兩支測試耗時寫進 commit message；>30s 改成只跑相關子集）。段 2 是啟發式，只警告

### W4　派 worktree 前的基底檢查　🟡（來源：lessons 11-09）

- **架構優先**：先評估能否讓 `tech-lead-mode` 派工前固定執行 `git rev-parse main origin/main`，不一致就自動在工單插入「第 0 步」（`git log -1` 確認基底 + 預授權 `git merge --ff-only <sha>`）
- **落地形式**：`bin/worktree-base-check.sh` 輸出「第 0 步」文字塊；`skills/engineering/tech-lead-mode/SKILL.md` Phase 2 派工處改為「先跑此 script，輸出原樣貼進工單」
- **驗收**：script 測試兩案例（main == origin → 無輸出 / main 領先 → 輸出含 sha 與 ff-only）；SKILL.md 改動跑 `bash bin/token-budget.sh --strict && python3 bin/validate-skill-index.py`
- **風險**：skill 層仍靠模型記得呼叫（L1）；若 harness 有 PreToolUse hook 可攔 `isolation: worktree`，記為後續架構選項，本單不做

### W5　project-review 登記前快照實跑　🟡（來源：lessons 11-10）

- **現況**：沒有登記指令，登記表 `~/.config/agent-review/projects.json` 是手動編輯（`bin/project-review.py:9`），所以無處可攔
- **改**：`bin/project-review.py` 新增 `--preflight <專案路徑>`：在 scratchpad 建 HEAD worktree 快照，用臨時登記表 / 報告目錄跑一次 L1，失敗就非 0 並列出失敗項；`project-review.py` 檔頭說明與登記表格式說明改為「登記前必跑 `--preflight`」
- **架構選項（評估後再定）**：改成只能透過 `--register` 寫入登記表、內含 preflight，才算真正讓錯誤不可能發生；本單先做 preflight，`--register` 視改動量決定
- **驗收**：`bin/test-project-review.sh` 補兩案例：hermetic 測試專案 → preflight 通過 / 依賴自身絕對路徑的測試專案 → 非 0 且訊息含「不 hermetic」
- **依賴**：先確認 11-10 遺留的 P1 觀察結果（11/11–11/17），P1 未過不動登記流程
- **風險**：快照實跑耗時，登記是低頻操作可接受

### W6　push 前檢查 author email　🟡（來源：lessons 11-20；隱私風險最高）

- **改**：新增 `hooks/pre-push-email-audit.sh`：`git log --format='%ae%n%ce' <remote>/<branch>..<local>`（新 remote 無 upstream 時查全歷史）過濾 `users.noreply.github.com` / `noreply@anthropic.com` 後有輸出 → **非 0 擋下**並印出可用的修法與旁路（`git push --no-verify`）
- **為何直接攔截**：一旦 push 到 public，清除只能改寫歷史 + force push，事後警告沒有意義
- **改**：`bin/install-git-hooks.sh` 一併安裝 pre-push（沿用 core.hooksPath 偵測與「不覆蓋非本專案 hook」邏輯）
- **驗收**：測試三案例：noreply-only → 放行 / 含個人信箱 → 擋 / 無 upstream 新 remote → 查全歷史；本 repo 實裝後 `git push --dry-run` 驗證
- **風險**：本 repo 現有歷史若已含個人信箱，裝上後第一次 push 就會擋——先跑一次掃描，結果給使用者裁決（allowlist 或改寫歷史），不自行處理

---

## 2. 執行順序

```
W6（隱私風險、獨立）→ W2（最小）→ W1 → W3 段 1 → W4 → W3 段 2 → W5（等 P1 觀察結果）
```

W2 與 T5 都會建立 `bin/test-pre-commit-audit.sh`：先做的那張建檔，後做的補案例。
