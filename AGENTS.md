# Agent Skills — Codex / AGENTS.md 平台入口

> **正本在 `~/Agent_skill`（唯一 source of truth）**。本檔是薄索引：只放常駐核心與路由，不放制度正文。
> 全域生效：`setup.sh` 將 `~/.codex/AGENTS.md` symlink 到本檔，任何專案的 Codex session 都會讀到。
> Claude Code 讀 CLAUDE.md、Antigravity（agy）讀 GEMINI.md——三份索引指向同一份正本。
> 本檔不依賴 `@file` 語法，核心規則 inline；下方 inline 段與 GEMINI.md 逐字相同，改規則先改 `~/Agent_skill/rules/` 正本，再同步兩份索引的 inline 段。

---

## 常駐核心規則（inline，任何任務都適用）

### Coding
- 意圖揭示命名，禁止縮寫（除 url、id、api）
- 函式單一職責，< 50 行，參數 ≤ 3 個，提前 return 取代巢狀 if
- 不吞錯誤：catch 內必須有處理邏輯或 re-throw
- 禁止 `console.log` 進 production、禁止 hardcode secrets、禁止 `any`（TypeScript）

### 安全（OWASP 基準）
- 所有外部輸入視為不可信任，必須驗證
- SQL 一律 parameterized query；禁止 `innerHTML = userInput`
- secrets 從環境變數讀取並做 runtime validation，`.env` 進 `.gitignore`

---

## 核心鐵律

1. **重活派出去**：大量讀檔、掃 repo、網路搜尋、批次修改一律委派（有 subagent 用 subagent，沒有就開低成本 session），主對話只進結論。做法見 `~/Agent_skill/governance/model-orchestration.md`
2. **驗證不自驗**：自己產出的東西不能自己驗收——檔案用 read-back、程式碼用實跑測試（貼輸出）
3. **不猜意圖**：命中多個 skill 觸發詞或出現模糊詞（「優化」「完善」）→ 列出選項問使用者
4. **卡住就停**：同一件事重試兩輪失敗 → 停下，帶失敗軌跡升級或問使用者
5. **動 repo 前先 `git status`**：非預期變更 → 停下來問，不默默覆蓋（使用者多 harness 並行是常態）
6. **完成要有證據**：「應該會過」「邏輯上正確」= 進行中，不是完成
7. **交接必落地**：開工先讀、收工必寫 `~/.agent-sessions/<專案>/latest.md`；踩坑教訓 append 到 `~/Agent_skill/governance/lessons.md`

---

## 路由表（需要時讀對應檔案，不要預先全讀）

| 情境 | 讀這份 |
|------|--------|
| 查 skill 觸發詞與完整索引 | `~/Agent_skill/skills/llms.txt` |
| 語言/框架 rules 偵測條件 | `~/Agent_skill/skills/engineering/coding-workflow-core.md` Phase 0 |
| 委派、模型選擇、升降級、跨 harness 分工 | `~/Agent_skill/governance/model-orchestration.md` |
| 完成判準、何時問人、何時換路 | `~/Agent_skill/governance/judgment-rubrics.md` |
| 派工 prompt 模板 | `~/Agent_skill/governance/delegation-templates.md` |
| 卡關/跨檔案/高風險實作 | `~/Agent_skill/skills/engineering/tech-lead-mode.md` |
| 修改制度檔的權限、記憶回寫、索引防漂移 | `~/Agent_skill/governance/maintenance-protocol.md` |

---

## Codex 專屬區塊（只適用本 harness）

- **型號**（2026-07-07 官方文件查證）：`gpt-5.5`（旗艦）/ `gpt-5.4`（工作馬）/ `gpt-5.4-mini`（機械工）；effort 用 `model_reasoning_effort`：`minimal`/`low`/`medium`/`high`/`xhigh`。選擇與升降級查 `model-orchestration.md` §5/§6 的 Codex 欄
- **AGENTS.md 逐層合併有 32KiB 上限**：本檔與專案層 AGENTS.md 都要保持薄，塞長內容會被靜默截斷
- **subagent**：支援 manager-worker（最多 8 平行、雲端 sandbox）。委派參數照 `model-orchestration.md` §2 Codex 欄，禁止照抄 Claude Code 的 `subagent_type` 等參數名
- **Memories 功能保持關閉**（`[features] memories` 不設 true）：自動記憶不可控且不回寫正本；跨 session 記憶一律走 `~/.agent-sessions/` 交接檔
- 逐次指定 model 是否可行未確認：需要更強模型時，開新 session 前先在 `~/.codex/config.toml` 或 profile 指定

---

## 記憶與交接（三 harness 共用約定）

- **跨 harness 交接正本** = `~/.agent-sessions/<專案>/latest.md`（開工先讀、收工必寫）
- **教訓正本** = `~/Agent_skill/governance/lessons.md`（append-only，格式見 maintenance-protocol §3）
- 各 harness 自帶的自動記憶（Codex Memories、agy brain）**不作為制度記憶**，重要結論必須落到上面兩處

---

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 回應先給極短摘要，再給可執行內容
- 指出邏輯漏洞，不為友善而同意
