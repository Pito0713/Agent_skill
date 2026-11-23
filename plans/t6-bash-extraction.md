# 計劃書：T6 skill 內嵌 bash 抽成 bin/ script（C1 / C3 / C4 / C5）

> **性質**：一次性執行工單，非制度檔
> **建立**：2026-11-23
> **發起人**：使用者
> **基準 commit**：`2d5399e`（main，工作區乾淨，與 origin 同步至 `8176f5c`）
> **狀態**：C4 / C1 / C3 / C5 未開工（C2 已於 `3cb0f90` 完成）
> **來源**：`plans/agent-env-trust-pyramid.md` T6 候選表；C4 同時是 `governance/lessons.md` 2026-11-22（codex stdin 卡住）的下沉形式

---

## 0. 共同約束

- 抽出的 script 一律放 `bin/`，skill 以 `~/Agent_skill/bin/<script>` 呼叫（三 harness 與下游 skill farm 共用正本）
- 每支 script 附 `bin/test-<script>.sh`：fixture 在 `mktemp -d`、hermetic（`GIT_CONFIG_GLOBAL=/dev/null`、不讀真實 `~`）、關鍵分支做變異驗證
- 新測試加進 `hooks/pre-commit-audit.sh` 的 `TEST_MAP`
- 動 skills/ 必跑 `bash bin/token-budget.sh --strict && python3 bin/validate-skill-index.py`；SKILL.md bytes 變化寫進 commit message
- 行為與舊內嵌版不同的地方，明列在該單「行為變更」
- 審查：codex 唯讀審查（用量已恢復時）；不可用時 Claude subagent 冷啟動 fallback 並標註

---

## 1. 工單

### C4　`bin/codex-ro.sh`：codex 唯讀委派的唯一入口　🟡（動 8 份 SKILL.md）

- **目標**：讓「漏帶安全旗標」與「沒給 stdin 卡住」都不可能發生（架構層下沉，lessons 11-22）
- **介面**：`codex-ro.sh [--web] [--stdin] [-o 輸出檔] [--] "<prompt>"`
  - 固定帶 `-s read-only -c project_doc_max_bytes=0`；`--web` 才加 `-c tools.web_search=true`
  - **沒帶 `--stdin` 一律 `</dev/null`**；要餵資料必須明寫 `--stdin`（顯式優於偵測：背景執行時 `[ -t 0 ]` 判不準）
  - 拒絕任何其他 codex 旗標（尤其 `-s`、`--dangerously-*`、`--full-auto`）→ exit 2
  - 找不到 codex → exit 127，訊息提示走 cli-delegate 的 Claude subagent fallback
- **改**：14 處 `codex exec` 呼叫改用 wrapper——ui-design-flow:125、debug-flow:58,130、code-review:141、cli-delegate:105,114,165,169,207,218、tech-lead-mode:118、deploy-prep:156、new-feature:165、onboarding:52。cli-delegate「Step 2 安全預設」段改寫為「一律經 wrapper」，旗標表保留作說明
- **驗收**：假 codex（PATH 注入）記錄參數與 stdin：① 無 `--stdin` 時 stdin 為空且不阻塞 ② `--stdin` 時資料完整傳入 ③ 兩個安全旗標每次都在 ④ `--web` 才有 web_search ⑤ 危險旗標被拒 ⑥ 無 codex → 127。`grep -rn "codex exec" skills/` 只剩 cli-delegate 說明文字
- **行為變更**：`git diff | codex exec ...` 這類 pipe 寫法改為 `git diff | codex-ro.sh --stdin ...`
- **風險**：漏改的呼叫點仍可直接 `codex exec`——驗收的 grep 擋；之後可在 W2 同類的 pre-commit 警告加「skills/ 新增行含 `codex exec`」

### C1　`bin/vault-env.sh`：讀 Obsidian vault 設定　🟢（動 4 份檔）

- **介面**：`vault-env.sh [--optional]` → stdout 印 vault 絕對路徑
  - 預設（必須有）：`.env` 不存在 / 未填 / 目錄不存在 → exit 1，stderr 印設定步驟（沿用 obsidian-save 較完整的版本）
  - `--optional`：任何一種缺設定 → 無輸出、exit 0（靜默降級）
  - **不 `source` `.env`**：只解析 `OBSIDIAN_VAULT_PATH=` 那一行（去引號、展開 `~`），避免執行 `.env` 內任意指令
- **改**：obsidian-save:20-52、knowledge-search:37-57（必須）；`skills/learning/_shared/mentor-protocol.md:54`、cooking-flow:57（`--optional`）
  - skill 端寫法：`OBSIDIAN_VAULT_PATH=$(~/Agent_skill/bin/vault-env.sh) || <停止並轉述 stderr>`
- **驗收**：測試涵蓋 .env 缺 / 空值 / 引號 / `~` / 目錄不存在 / `--optional` 四種降級 / `.env` 含 `$(...)` 不被執行；knowledge-search 與 C2 `knowledge-grep.sh` 串接仍通過
- **行為變更**：`.env` 其他變數不再被 source 進 shell（目前只有這一個變數，無影響）

### C3　`bin/project-dashboard.sh`：跨專案總覽　🟢（動 1 份 SKILL.md）

- **介面**：`project-dashboard.sh [--sessions-dir DIR]` → 輸出 SKILL Phase 3 的 markdown 表（專案 / 狀態 / 交接更新 / 落後 / 分支 / 未 commit / 當前焦點 / Blocker）
  - 落後 = `git log --since=<最後更新>` 筆數；`>5` 加 ⚠️；路徑不存在 → `STALE`
  - 欄位解析容錯：缺欄位顯示 `—`，不中斷其他專案
- **改**：project-dashboard SKILL.md Phase 1–3 的 bash 改為呼叫 script；Phase 4（展開有問題的專案）仍由模型判斷
- **驗收**：fixture sessions 目錄含 4 種專案（同步 / 落後 >5 / 路徑不存在 / 缺欄位舊檔）；輸出逐欄比對；對真實 `~/.agent-sessions` 實跑一次貼輸出
- **行為變更**：數字由 script 算，模型不再逐專案跑 git

### C5　`bin/detect-stack.sh`：Phase 0 fallback 偵測　🟡（常駐 skill）

- **介面**：`detect-stack.sh [專案目錄]` → 每行印一個應載入的 rules 檔（`rules/typescript.md` 等），依 Phase 0 表
- **改**：`coding-workflow-core/SKILL.md:38-43` fallback 區塊換成一行呼叫；**原生工具優先**的規則不變
- **驗收**：fixture 涵蓋 Phase 0 表每一列（ts / react / next / python / test / vue）＋空目錄；`token-budget.sh` 量常駐成本變化（預估省 ~195 bytes）寫進 commit message
- **注意**：Phase 0 表本身仍在 SKILL.md（模型用原生工具時要看表）；script 與表的對應要有測試把關，避免兩邊漂移

---

## 2. 執行順序

```
C4（安全、架構下沉）→ C1 → C3 → C5（常駐，最後做、單獨 commit）
```
