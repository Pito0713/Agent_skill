# 執行力分層設計（Enforcement Layers）

> **狀態：v1 已實作（2026-07-10，使用者核准第 4 節清單後動工，決策記錄 ADR-010）**。觀察期驗收標準見 §6。
> **⚠️ 2026-07-31 更新（ADR-015，取代下方 ADR-014 註記）**：第 4 節 #1 的 Stop hook 與 #3 的接線 **永久移除，非暫時停用**。`hooks/stop-handoff-check.sh` 已刪除（`hooks/` 目錄隨之消失），7 個下游掛載全部清除完畢（2026-07-31 驗證：全機 grep 無殘留）。**L2 對「交接必落地」這條規則永久放棄**——理由不是實作缺陷，而是原理性的：Stop hook 的觸發源是 harness 生命週期事件（一輪回應結束），而「收工」是使用者的意圖宣告，hook 觀測不到後者。改由純 L1 承擔：使用者說「handoff / 收工 / 交接」才寫，模型只在段落完成時提醒一次、不攔截。
> **歷史（ADR-014, 2026-07-27）**：當時決定停用並「保留 dormant」，但**移除下游掛載的動作從未執行**——hook 續活 4 天、6 次 BLOCK 橫跨 3 個專案。教訓見 lessons.md 2026-07-31 條目。
> 動機：現行防呆全靠文字制度，仰賴模型自主遵守——模型發散或遺忘時規則就失效。本文件規劃把高風險規則**下沉**到確定性腳本（hooks）與乾淨 context 守門員（cop agents）。

---

## 1. 三層執行力模型

與 `skills/unknown-matrix-navigation/SKILL.md` §3 的去相關階梯同構——層級越高，與主模型推理的相關性越低，越不會被主模型的盲點帶著走：

| 層 | 機制 | 強制力來源 | 生效範圍 | 對 AI 判讀的作用 |
|----|------|-----------|---------|----------------|
| L1 | 文字制度（rules/ + governance/ + 索引檔） | 模型自主遵守 | **三 harness 全部** | 建立判讀框架；會隨 context 稀釋而失效 |
| L2 | Hooks（PreToolUse / PostToolUse / Stop） | harness 程式碼層，模型無法繞過 | 僅 Claude Code | 見第 2 節兩型 |
| L3 | Cop agents（乾淨 context 守門員） | hook 強制喚醒 + 獨立 context | 僅 Claude Code（Codex/agy 用派工模板模擬） | 去除推理相關性：主模型說服自己的那套推理，cop 沒看過 |

**鐵則：L2/L3 是 L1 的加固層，不是取代層。** Hooks 只在 Claude Code 生效——Codex 與 agy 不吃 `.claude/settings.json`，文字正本是跨 harness 的唯一底線。**禁止因為某規則已有 hook 就從 rules/ 或索引刪掉該規則**（否則另外兩個 harness 立即裸奔）。

---

## 2. Hook 的兩型（對判讀的作用相反）

| 型 | 行為 | 對判讀的作用 | 例 |
|----|------|-------------|-----|
| **攔截型**（guard） | 不合規直接 block 該次 tool call | **不擴充判讀，補償判讀失敗**。價值在零智能：確定性腳本不共享模型盲點 | 攔 force-push、secret 樣式、界外 rm -rf |
| **注入型**（inject） | 在決策點自動執行並把疆域事實灌回 context | **真正擴充判讀**。規則從「模型要記得」變成「疆域自己出現在決策點」——反射，不是自律 | git mutation 前自動跑 `git status` 並注入輸出（鐵律 5 的反射化） |

「強制喚醒 cop」是第三種組合技：**強制力只能來自 hook，不能來自 agent 定義檔**。agent 寫得再鐵面，主模型不叫它就沒用。正確接法：Stop / PostToolUse hook 偵測條件 → 擋下並回饋指令 → 主模型被迫喚醒 cop。hook 出強制力，agent 出判讀力。

> **既有設施（2026-07-10 盤點）**：`~/.claude/settings.json` 已掛全域 PreToolUse hook（`~/WakaWaka/cost-aware-approval/hooks/pretooluse.mjs`，matcher `*`），PreToolUse 層的攔截由它承擔。**本設計不再新建 pre-tool-use 腳本**——若日後要擴充攔截規則，改在該既有 hook 內擴充，避免兩支 PreToolUse 疊加造成行為難以追蹤。

---

## 3. 分工判準：哪條規則落到哪層

依序問三題：

1. **機械可判定且低誤報嗎？**（regex / 檔案存在性 / 指令樣式）→ 是：下沉到 **L2 攔截型**
2. **是「決策點缺事實」而非「行為違規」嗎？** → 是：**L2 注入型**（餵事實，不攔截）
3. **需要語意判斷嗎？**（「吞錯誤」「交接檔內容夠不夠」「這算不算 scope creep」）→ 是：**L3 cop agent**。禁止硬寫成 regex hook——誤報摩擦會讓使用者關掉整個 hook 層

任何情況下該規則的文字版**保留在 L1 正本**（跨 harness 需要）。

---

## 4. 第一批實作清單（待核准，未動工）

| # | 產物 | 型 | 內容 | 誤報風險 |
|---|------|-----|------|---------|
| 1 | ~~`hooks/stop-handoff-check.sh`~~ **已廢止（ADR-015）** | ~~L2 注入~~ | ~~Stop hook：本 session 有 repo 寫入但 latest.md 未更新 → 擋一次~~。實測誤報風險不是「中」而是**必然**：`wrote_repo` 掃整份 transcript、一旦為真就永遠為真，而防重複的 `stop_hook_active` 只在單次 Stop 續跑內有效、跨輪重置 → 每一輪對話結束都再擋一次。檔內「每 session 僅出現一次」的宣稱為假 | ~~中~~ **實為必然誤報** |
| 2 | `agents/06-governance/handoff-verifier.md` | L3 | 乾淨 context 查核 latest.md：格式合規（maintenance-protocol §6）、與 `git log` 事實對帳、下一步可執行性。**回傳必附證據**（引用行號與 git hash），防主模型抄結論 | — |
| 3 | ~~接線~~ **已廢止（ADR-015）** | — | ~~專案 `.claude/settings.json` 掛 Stop hook；`inject.sh` 增 `install_stop_hook()`~~。`install_stop_hook()` 已於 ADR-012 重構時移除、ADR-013 拆分後未恢復，**不再恢復**。「指向正本、不複製」的設計本身是對的——正是它讓 ADR-015 能靠一行 kill-switch 同時停掉 7 個掛載。但**不安裝 ≠ 移除既有的**：政策改變後無反注入機制，是 ADR-014 殘留 4 天的根因。改由 `bin/scan-downstream.sh` 唯讀掃描承擔偵測 | — |

**明確不做**（本批）：
- **PreToolUse 層攔截／注入**（`~/.claude/settings.json` 已有全域 pretooluse.mjs，擴充攔截規則進該 hook，不另建腳本）
- 空 catch block regex 攔截（語意規則，交給 code-review / cop）
- governance-auditor agent（等 handoff-verifier 跑順再擴）
- Codex/agy 側的等效機制（先驗證 Claude Code 層值不值得）

---

## 4b. 現行實際存在的 L2（2026-07-31 起）

第 4 節整批已全數廢止。目前唯一活著的自建 L2 是：

| 產物 | 型 | 觸發條件 | 為什麼這個可以用 L2 |
|------|-----|---------|-------------------|
| `hooks/pre-commit-audit.sh` | L2 攔截 | staged 的**新增行**含個人絕對路徑或本機 file URL → 擋 commit（實際 pattern 見腳本內 awk） | 觸發條件是 **regex 命中，客觀可判定、零意圖推斷**。對照 ADR-015 廢除 Stop hook 的理由——那個要判斷「使用者是否宣告收工」，是 hook 在原理上觀測不到的主觀意圖。兩者不同類，不要因為廢了一個 hook 就對所有 hook 過敏 |

設計要點（全部是 2026-07-31 當天的教訓）：

- **下游用 exec wrapper 指向正本，不複製**。git 只認 `.git/hooks/<固定檔名>`，沒有
  「填路徑」的欄位，所以 wrapper 是 git hook 唯一能達成「指向正本」的方式：
  ```bash
  #!/usr/bin/env bash
  CANON="$HOME/Agent_skill/hooks/pre-commit-audit.sh"
  [ -x "$CANON" ] || exit 0   # fail-open：正本遺失/不可執行/$HOME 失效 → 放行
  exec "$CANON" "$@"
  ```
  `exec` 取代 process，正本的 exit code 直接成為 hook 的 exit code。已刪除的
  post-commit hook 是 5 份實體副本，改正本對它們毫無作用——正是要避開的反模式。
- **`[ -x ]` 那道守衛不可省**。初版直接 `exec`，正本忘了 `chmod +x` 時回 126，
  git 把 6 個 repo 的**所有** commit 都擋掉——與正本自稱的 fail-open 直接矛盾。
  **fail-open 的宣稱寫在正本裡，不會自動繼承到 wrapper**：兩者是不同檔案，
  各自都要有放行路徑。
- **只掃 staged 新增行**，不翻舊帳、不掃工作區。
- **旁路**：`git commit --no-verify`（git 原生）或該行加**獨立 token** 的
  `audit-ok` 標記（子字串不算——初版用子字串比對，`audit-oklahoma` 這類路徑會
  靜默旁路）。
- **fail-open**：git 指令失敗、無 staged 內容等一律放行。
- **已知限制**（刻意接受，理由見腳本檔頭）：binary 檔不掃；個人目錄底下只有單一
  segment 時會誤報（同名的 REST 路由會中）——**不收窄，因為漏掉洩漏不可逆、誤報
  只需加 `audit-ok`，成本不對稱**；`file://<host>/` 不命中；rename 未加 `-M`。

已接進 `inject.sh`（commit `7227931`，走 `bin/install-git-hooks.sh` 的
`--preflight` / `--install`），新專案注入時自動裝。

**已安裝（2026-08-04 現算）**：`Agent_skill` / `AG_knowledge` / `shopee` /
`WakaWaka` 四個維護中的 repo，wrapper md5 均為 `e69bca9c…`。

> 本清單是**手抄快照**，會漂移——2026-08-04 就實測到原記載的「6 份已安裝」實際為
> 0 份。要確認現況一律現跑：
> ```bash
> for p in Agent_skill AG_knowledge shopee WakaWaka; do
>   printf '%s: ' "$p"; md5 -q "$HOME/$p/.git/hooks/pre-commit" 2>/dev/null || echo "未安裝"
> done
> ```

---

## 5. 失敗模式與防線

- **過度攔截自毀**：誤報多 → 摩擦 → 使用者關掉 hook → 比純文字更糟。防線：第一批只收「高風險 + 低誤報」；每個攔截都要能用環境變數一鍵旁路（`AGENT_SKILL_HOOK_BYPASS=1`），旁路事件寫 log 供事後審
- **hook 與正本漂移**：改了 rules/ 沒改 hook（或反之）。防線：hook 腳本頭部註明對應正本條文；維護協議健康檢查（§5）加一項「hooks 對應條文仍存在」
- **cop 形式化**：主模型引用 cop 結論但 cop 沒真的查。防線：cop 產出必附可驗證證據（行號、hash、指令輸出），無證據的核可視為未核可
- **Stop hook 死循環**：擋收工 → 模型重試 → 再擋。防線：以 marker 檔保證每 session 只擋一次

---

## 6. 驗收標準（實作後觀察一週）

- Stop hook：誤報（無 repo 寫入卻被擋）≤ 1 次／週，否則收窄偵測條件；交接檔漏寫率下降（基線：2026-07-07 曾發現 latest.md 落後 repo 3 commits）
- cop：至少抓到一次主模型自驗漏掉的問題，否則檢討 prompt

---

## 相關文件

- 去相關階梯原理：`skills/unknown-matrix-navigation/SKILL.md` §3
- 委派與模型選擇：`governance/model-orchestration.md`
- 下游注入模式與路徑教訓：`inject.sh`、`governance/lessons.md`（2026-07-07 兩條）
