# 計畫書 v2：Skill 使用次數歸類 + 自我修正機制

> 狀態：待使用者核准後實作
> 日期：2026-08-08
> 專案：`~/Agent_skill`（三 harness 共用制度倉庫）
> 審查：v1 由 Codex 冷啟動對抗式審查（6 BLOCKER / 8 SHOULD / 5 NIT），本版為整合後結果

---

## 0. v2 相對 v1 的變更（審查整合結果）

| # | v1 的問題 | v2 的處理 | 來源 |
|---|----------|----------|------|
| 1 | 把「路徑出現次數」當成「使用次數」 | 拆成三個互不合併的指標；統計單位改 tool call 不是 path | Codex BLOCKER 1 |
| 2 | skill 名稱直接採原值，namespace / 舊名會變幽靈項目 | 強制 realpath 解析 + 對照 `index.json`，無法對應者進 `unresolved` | Codex BLOCKER 2（**建議的 alias 合併已駁回**，見 §9） |
| 3 | 用 cwd/workdir 分 usage vs maintenance | 改用「寫入目標是否在 skill 路徑內」判定；明確調用一律算 usage；缺 workdir 進 `unknown` | Codex BLOCKER 3 |
| 4 | 自稱「比照 lessons.md」自行取得 governance/ 的 🟢 append 權 | **這是自行擴權**。改為：先明文修改 `maintenance-protocol §1` 增列例外（🟡 需核准），才有權自主 append | Codex BLOCKER 4 |
| 5 | feedback 狀態機求不出目前狀態 | 改事件溯源，定義合法 transition，Markdown 一律由 JSONL 現算 | Codex BLOCKER 5 |
| 6 | evidence 可能把原文 / 絕對路徑寫進倉庫 | 只存 locator + hash + 摘要；**已實證 `pre-commit-audit.sh` 會擋個人絕對路徑** | Codex BLOCKER 6 |
| 7 | 腳本自稱唯讀卻要寫兩個 governance 產物 | scanner 改 stdout-only；持久化只在使用者觸發週檢時發生，且寫 immutable 週檔 | Codex SHOULD 6 |
| 8 | 首版就貼退場標籤，會把半數 skill 判死 | 首版只輸出觀測值，退場分層需累積 ≥8 個活躍週才啟用 | Codex SHOULD 3 |
| 9 | 「前 33%」未定義取整與同分 | 改 67th percentile + 同分同層 + 最小樣本數守門 | Codex SHOULD 4 |
| 10 | 分鐘去重會漏算真實事件（259→224） | 改 call_id → canonical path → turn 三層去重 | Codex SHOULD 5 |
| 11 | 一次到位蓋 10 個檔 | 改三階段 + 決策 gate，Phase 1 只做 scanner | Codex SHOULD 8 |
| 12 | 「40 個已安裝 skill」 | 實際 **38**（`~/.claude/skills` 另有 `governance/`、`rules/` 兩個非 skill 掛載）| Codex NIT 1（已自行複驗） |
| 13 | 時區與時間窗未定義 | 一律 UTC 解析、`Asia/Taipei` ISO week 切週 | Codex NIT 3 |
| 14 | 未考慮 transcript schema 演進、sidechain、fork | 列入 fixture 必測項 | Codex NIT 5 |
| 15 | —（審查雙方都沒抓到）| **自我污染防護**：本機制產出的報告本身會把 skill 名寫進 transcript，下一輪掃描若用鬆散比對會計入自己 | 本輪自行發現，見 §4.5 |

---

## 1. 需求

1. **使用次數歸類**：統計每個 skill 被用了幾次，分出熱門 / 冷門，依分層做維護處理
2. **自我修正機制**：使用過程中記錄可優化之處與缺陷，週末 review 判斷能否再優化

---

## 2. 實測基率（設計的事實基礎）

### 2.1 Claude Code

來源：`~/.claude/projects/**/*.jsonl`（1052 份，2026-06-08 → 2026-08-08，39 個活躍日）

| 訊號 | 數量 | 涵蓋 skill 數 |
|------|------|--------------|
| `tool_use` name=`Skill`（明確調用） | **25** | 12 |
| `tool_use` name=`Read` 且 path 結尾 `SKILL.md` | **11** | 5 |

原始值分布（**未正規化，這正是問題所在**）：

```
anthropic-skills:coding-workflow  9    ← 帶 namespace，無法對應本 repo index
code-review                       3
handoff                           2
artifact-design                   2    ← 外部 skill
project-dashboard                 2
coding-workflow                   1    ← 本 repo 的，與上面第一列不是同一個
```

### 2.2 Codex

來源：`~/.codex/sessions/**/*.jsonl`（94 份 rollout）

Codex **沒有 `Skill` tool**，工具只有 `exec` / `exec_command` / `apply_patch` 等。skill 的使用型態是**用 shell 讀檔**（實例：`sed -n '1,240p' .../skills/productivity/onboarding/SKILL.md`）。

| 指標 | 數值 |
|------|------|
| 含 `SKILL.md` 的 tool call | **151** |
| 其中出現的 path occurrences | **261** |
| 分布日期 | 2026-07-23 ~ 2026-08-07，共 9 天 |

> ⚠️ **261 ≠ 261 次使用**。一個 command 可一次讀多份 SKILL.md。v1 把這個數字當使用次數是錯的。
> ⚠️ **更不可用 raw grep**：對 rollout 直接 grep 得 14561 筆，因為每個 session 的 system prompt 都列出全部 skill 清單（每個 skill baseline 約 199）。**只能從 tool call 的 arguments 結構化抽取**。
> ⚠️ 抽出的項目含非本 repo 的 skill：`openai-docs` 10、`control-in-app-browser` 4、`artifact-design` 2、`vendor-skill` 1。必須過濾。

### 2.3 agy（Antigravity CLI）

對話存於 `~/.gemini/antigravity-cli/conversations/*.db`（sqlite，`steps` / `trajectory_metadata_blob` 為 blob）。

- `grep -rl "SKILL.md"` 命中 **0**
- `strings` 硬撈最新一份 db 得 10 筆，且混雜他專案（`spec-flow`、`unit-testing`）

與 `maintenance-protocol §6` 既有結論一致（「agy brain / conversations——二進位不可回寫」）。

### 2.4 已安裝 skill 數

`skills/index.json` = **38** 筆；`~/.claude/skills/` 有 40 個項目，多出的 `governance/`、`rules/` 是 farm 掛載的非 skill 目錄（已複驗）。

### 2.5 四個直接影響設計的結論

1. **Codex 是主要使用端**（151 calls vs Claude 25 invocations）。只做 Claude 那半邊會嚴重低估。
2. **絕對閾值不可用**。38 個 skill、兩個月合計數百個 event，任何「≥5 次/週 = 熱門」的門檻會讓全部判冷。
3. **「讀到」不等於「選用」**。使用 `code-review` 時會連帶讀 `coding-workflow-core` 與 rules；純讀取次數會系統性獎勵「篇幅長、交互引用多、要求反覆 read-back」的 skill。這是本設計最大的效度威脅。
4. **agy 是已知盲區**，不硬撈，報告需明示涵蓋範圍。

---

## 3. 設計決策

| 決策 | 選擇 | 理由 |
|------|------|------|
| 資料採集方式 | **事後挖掘 transcript / rollout**，不裝 hook | 零 runtime 成本；可回溯歷史；不新增自動寫入路徑；Codex 的 `hooks.json` 為空且不分發，hook 路線在 Codex 側無法對等 |
| 涵蓋 harness | Claude + Codex，**agy 排除** | §2.3，訊號不可靠。排除是明示限制不是遺漏 |
| 指標結構 | **三個指標永不合併**：`explicit_invocation` / `inferred_read` / `maintenance_edit` | §2.5 第 3 點。合成單一 usage 數就是把效度問題藏起來 |
| 分層依據 | 67th percentile + 同分同層，且**首版不貼退場標籤** | §2.5 第 2 點 + 樣本不足 |
| 統計持久化 | 每週 immutable 檔，**只在使用者觸發週檢時寫** | scanner 保持唯讀；JSON 整檔 read-modify-write 中斷會毀檔 |
| feedback 誰寫 | Agent 自主 append，**但需先明文修改權限協議** | 使用者已裁決自主 append；然而 v1 的「比照 lessons.md」是自行擴權，必須走正式修改 |
| 週檢觸發 | 使用者說「skill review」才跑 | 使用者已裁決，沿用 ADR-014/015 |
| review 是否自動改 SKILL.md | **否**，只輸出建議，逐條待使用者裁決 | 鐵律 2；skill 是三 harness 共用正本 |

---

## 4. Part 1：使用統計

### 4.1 三個互不合併的指標

| 指標 | 定義 | 可信度 |
|------|------|--------|
| `explicit_invocation` | Claude `tool_use` name=`Skill` | **高**——模型明確選用了它 |
| `inferred_read` | Claude Read / Codex exec 讀取 `SKILL.md` | **中**——可能是連帶讀取，非選用 |
| `maintenance_edit` | 寫入目標為 `SKILL.md` 或 skill 目錄內檔案 | 不算使用 |

Codex 側**沒有** `explicit_invocation`（無 Skill tool），其最強訊號只到 `inferred_read`。因此：

> **跨 harness 的分層一律只用 `inferred_read + explicit_invocation` 的合併排名做「觀測」，但退場決策禁止只憑 `inferred_read`。**

### 4.2 名稱正規化（canonicalization）

1. 從 event 取出路徑 → `realpath` 解析（跟隨 symlink，farm 是 symlink）
2. **必須落在 `~/Agent_skill/skills/` 之內**，否則丟棄
3. 取父目錄名 → 必須能對應 `skills/index.json` 的 `name`
4. 對應不到 → 進 `unresolved` 桶，**列出但不計入任何分層**

Claude 的 `input.skill` 沒有路徑，處理方式：

- 值與 index 完全相符 → 計入
- 帶 namespace（如 `anthropic-skills:coding-workflow`）或不在 index → **`unresolved`**
- **不做 alias 合併**（駁回 Codex 建議，理由見 §9）

舊版扁平檔（`skills/engineering/gemini-assist.md`）：路徑已不存在，`realpath` 會失敗 → 自動落入 `unresolved`，符合預期。

### 4.3 去重（三層，取代 v1 的分鐘窗）

1. `tool_use.id` / `call_id` 相同 → 同一事件（消除 transcript 重播、fork 複製）
2. 同一 call 內相同 canonical path → 計 1（一個 `sed` 讀三份就是三個不同 skill，不是三次）
3. 聚合單位 = `(session_id, skill, event_class)`，每個 session 每個 skill 每類最多計 1 次「被使用」+ 另記 raw 次數

> v1 的分鐘窗在實測中一次去掉 35 筆（259→224），且無法區分「同 command 重複路徑」與「同分鐘兩次獨立使用」。

### 4.4 usage vs maintenance（取代 v1 的 cwd 判定）

實測 v1 判定法的誤判規模：

```
含 SKILL.md 的 call: 158
 有 workdir:        138
 缺 workdir:         20
 session cwd ≠ workdir: 21
```

改為：

| 判定 | 規則 |
|------|------|
| `maintenance` | 事件是寫入類（`Edit`/`Write`/`apply_patch`）**且**目標路徑在 canonical skill 路徑內 |
| `usage` | `explicit_invocation` 一律算 usage（即使 cwd 在 `Agent_skill`，另加 `project=self` 標記） |
| `usage` | 讀取類事件且 workdir 可解析且不在 `Agent_skill` 內 |
| `unknown` | workdir 缺失或解析失敗 —— **不預設歸類**，單獨一欄 |

> 具體反例（Codex 提供，成立）：Codex 這次就是在 `~/Agent_skill` 內真的使用 `code-review` 審查本計畫書，v1 規則會判成 maintenance。

### 4.5 自我污染防護（v1 與審查都遺漏）

本機制的產出（週檢報告、本計畫書、對話中的分析輸出）**會把 skill 名稱與路徑寫進往後的 transcript**。實例：`anthropic-skills:coding-workflow` 這個字串目前出現在 3 個 session，其中一個就是產出本計畫的這次對話。

防護：

1. **只解析結構化欄位**（`tool_use` / `function_call` 的 `arguments`），**永不對整行做 grep**
2. 排除工具為 `Read`/`exec` 但目標是 `plans/`、`governance/skill-*` 的事件
3. fixture 必須包含一個「transcript 內容含 skill 名但非 tool call」的陰性案例

### 4.6 lifecycle 標記

部分 skill 結構上不會被調用，需標記以免每週被提議退場。`skills/index.json` 每筆加選填欄位 `lifecycle`：

| 值 | 意義 | 例 |
|----|------|-----|
| `resident` | 常駐載入，必被讀但不代表被選用 | `coding-workflow-core` |
| `reference` | 明示不直接觸發的參考文件 | `coding-workflow` |
| `meta` | 制度維護專用，usage 必然為 0 | `convert-skill` |
| `critical-on-demand` | **低頻但高風險，零使用不代表該退場** | `deploy-prep`、`security-review` |

`critical-on-demand` 是 Codex 提出的，接受：目前 17 個零紀錄項目裡含 `deploy-prep`、`security-review`，只用三種豁免不足以擋住錯誤退場建議。

需同步更新 `bin/validate-skill-index.py` 讓新欄位不被判 schema 違規。

### 4.7 分層規則（首版停在觀測層）

**Phase 1（前 8 個活躍週）**：只輸出觀測值，**不貼任何退場標籤**。

輸出排序表 + 三指標分欄 + `unresolved` / `unknown` 桶大小。

**Phase 3（累積 ≥8 個活躍週後才啟用）**：

| 層 | 判定 |
|----|------|
| 🔥 熱門 | 合併排名 ≥ 67th percentile。**同分同層**（不因名稱排序被切開） |
| 🌤 常態 | 有使用紀錄但未達熱門 |
| 🧊 沉睡 | 近 8 週 0，但更早有紀錄 |
| ⚰️ 零紀錄 | 全期 0 且無 lifecycle 標記 |
| ⚙️ 豁免 | 有 lifecycle 標記，單獨列表 |

守門條件：有使用紀錄的 skill **少於 10 個時不分熱門層**（樣本不足，排名無意義）。

Codex 用 v1 規則實算的結果，作為「為什麼首版不能貼標籤」的證據：

```
熱門 6 / 常態 12 / 沉睡 0 / 零紀錄 17 / 豁免 3
零紀錄含 deploy-prep, security-review, academic-mentor, mentor-* ...
```

半數 skill 進退場評估、且「沉睡」層完全空置（四層退化成三層）——這個分佈證明門檻與樣本量都還不成立。

### 4.8 分層對應的維護處理（Phase 3 才啟用）

| 層 | 處理 |
|----|------|
| 🔥 熱門 | 值得投資：檢查是否過長該拆、步驟是否冗餘。優先消化其 feedback |
| 🌤 常態 | 維持，只處理有 feedback 的 |
| 🧊 沉睡 | 先判斷「觸發詞沒命中」vs「真的沒需求」。前者改觸發詞後觀察兩週 |
| ⚰️ 零紀錄 | 退場評估：合併或移入 `skills/_archive/`。**不直接刪** |
| ⚙️ 豁免 | 只看 `maintenance_edit` 是否異常歸零 |

「沉睡」的判別**明定為人工／模型輔助判讀，不是 deterministic script**：腳本只輸出候選 user turn，由 review 時人判。理由：`grep` 只能字面比對，中文同義詞漏抓率高，不可據以下「沒需求」的結論。

### 4.9 產物與寫入紀律

- `bin/skill-usage.py`：**stdout-only，完全不寫檔**（`--json` / `--table` 兩種輸出）
- 持久化只發生在使用者觸發 `skill review` 時，寫 `governance/skill-usage/YYYY-Www.json`
  - **immutable**：檔已存在預設拒絕覆寫（`--force` 才覆蓋）
  - 寫 temp + `mv` 原子換檔
  - 每檔含 `window_start` / `window_end` / `timezone` / `scanner_version`
- 時間處理：transcript timestamp 一律當 UTC 解析，報表邊界用 `Asia/Taipei` 的 ISO week

---

## 5. Part 2：自我修正機制

### 5.1 前置條件：權限協議必須先改（BLOCKER）

`maintenance-protocol §1` 現行明定「`governance/` 下除 `lessons.md` 以外的所有檔案」屬 🟡（動前必須先問使用者）。唯一的 🟢 append 例外是 `lessons.md`。

v1 寫「比照 `lessons.md` 的 🟢 級權限」——**這是模型自行擴權，不成立**。

正確路徑：把 `governance/skill-feedback.jsonl` 明文加進 §1 的 🟢 表格，並寫死邊界：

```
| 往 governance/skill-feedback.jsonl append 一筆 skill 缺陷紀錄 | 只加不改不刪；
  欄位須合 §5.2 schema；evidence 只准存 locator 與摘要，禁存原文（見 §5.4）；
  一次任務至多 3 筆 |
```

這項修改本身是 🟡，需使用者核准。**沒有這步就不得實作自主 append。**

### 5.2 `governance/skill-feedback.jsonl`（事件溯源）

每行是一個**事件**，不是一筆狀態：

```json
{"event_id":"01K9...","feedback_id":"01K9...","ts":"2026-08-08T07:04:00Z",
 "event":"opened","actor":"claude","skill":"debug-flow","type":"trigger-miss",
 "severity":"med","summary":"失敗描述未命中觸發詞","locator":"claude:695b816e:msg#142",
 "evidence_hash":"sha256:9f2c..."}
```

`type` 列舉：`defect`（步驟錯／指令跑不動）、`friction`（囉嗦／順序不順／格式不合用）、`trigger-miss`（命中場景但沒觸發）、`overlap`（與他 skill 職責重疊）、`improve`（具體改進想法）

**合法 transition**（validator 重播驗證）：

```
opened ─→ deferred ─→ reopened ─→ opened
   │                                 │
   └──────→ applied | rejected ←─────┘
```

規則：

- 每個事件都要 `event_id`（唯一）、`feedback_id`（串同一議題）、`ts`、`actor`
- `applied` **只能在變更實際套用且驗證通過後才寫**（防「先寫 applied 再失敗」）
- `deferred` 必須含 `review_after` 日期，到期自動回 review 清單
- 禁止：orphan `resolves`、重複 `event_id`、自我 resolve、跨 skill resolve
- **目前狀態一律由重播 JSONL 現算**，Markdown 報告不保存第二份狀態正本
- `event_id` 用 ULID（含時戳且單調），不用「秒級時戳 + skill 名」（多 agent 同秒會撞號）

### 5.3 與 `lessons.md` 的分工

- `skill-feedback.jsonl` = 特定 skill 的具體缺陷（有 skill 名、可對應到某幾行）
- `governance/lessons.md` = 跨任務通用教訓（門檻：下次還會有人踩）
- 週檢時若某條升級成通用規則 → 才寫進 `lessons.md`，並在結案事件註明

### 5.4 隱私與洩漏防線（BLOCKER）

本 repo **是公開的**（`github.com/Pito0713/Agent_skill`），且已裝 `hooks/pre-commit-audit.sh`，職責就是擋 staged 內容裡的個人絕對路徑——已實測確認。因此 evidence 存原文會在 commit 當下被擋，或更糟：擋不住的部分（token、email、他專案內容）被推上公開倉庫。

硬性規則：

- evidence **只存 locator（`harness:session_id:訊息序號`）與 sha256 摘要**，不存原文
- `summary` 限 120 字以內、且必須是改寫過的描述，不得貼使用者原話
- 禁止欄位內容：secret / token / email / 完整 shell command / 個人絕對路徑 / 未脫敏 user message
- 寫入前跑 deterministic redaction（`$HOME` → `~`、`/Users/<name>` → `~`）
- **transcript 本身永不複製進 repo**

### 5.5 `skills/productivity/skill-review/SKILL.md`

觸發詞：`skill review`、`skill 週檢`、`skill 健檢`

流程：

1. 跑 `bin/skill-usage.py`（stdout），與上一份週檔 diff
2. **唯讀挖掘候選 feedback**（Codex 建議，採納為補網）：掃 tool 失敗、同一指令重試、使用者糾正語句，列為候選——這是自主 append 漏記時的安全網
3. 讀 `skill-feedback.jsonl`，重播求出目前為 `opened` 的議題，依 skill 分組；`deferred` 到期者一併列出
4. 熱門 skill：逐條提出具體修改（指明檔案與行段，附改法）
5. 沉睡 / 零紀錄 skill（Phase 3 才做）：輸出候選證據 + 「改觸發詞 / 合併 / 歸檔」建議，**不下斷言**
6. 輸出 `governance/skill-reviews/YYYY-Www.md`（由 JSONL 現算，非狀態正本）
7. **停在這裡等使用者逐條裁決**
8. 裁決後：套用 → 驗證 → 才 append `applied`；若改到 `index.json` / `llms.txt` 則跑 `bin/validate-skill-index.py`

---

## 6. 實作階段與決策 gate

Codex 指出 v1 一次蓋 10 個檔屬過度設計（本專案有 `lazyengineer` 傳統）。採納，改三階段：

### Phase 1 — 只做量測 ✅ 已完成（2026-08-08）

- `bin/skill-usage.py`（CLI 與呈現）+ `bin/lib_skill_usage.py`（抽取與聚合，因 300 行上限拆模組），stdout-only
- `bin/test-skill-usage.sh`：20 項斷言涵蓋 §8 全部陰性案例，加 missing-root 不 traceback 檢查
- `skills/index.json` 加 `lifecycle` 欄（6 個 skill 標記）+ `bin/validate-skill-index.py` 支援
  - validator 改為只比對 `ROUTING_FIELDS` 四欄，讓 index 可帶非路由 metadata 而不與 llms.txt 衝突

**實作中發現的計數錯誤（已修，並入 lessons 2026-08-08）**：第一版對 tool call arguments 全文抓路徑，
`apply_patch` 改 `AGENTS.md` / `index.json` 時，patch **內文**列出的 18–38 條 SKILL.md 路徑全被當成編輯事件，
一次假造數十筆。改為只認 `*** Update/Add/Delete File:` 標頭的作用目標，並補回歸測試。

**交叉驗證（鐵律 2）**：`handoff` inv=3、`code-review` inv=2（全期）、`coding-workflow-core` read=20 三項
以獨立 grep 複算一致；第三項對照組算出 21，差的 1 筆是文件範例裡的字面 `HOME/Agent_skill/...`，
掃描器正確歸入 `unresolved`。`bin/test-fix-3.sh` 與 validator 均無回歸。

**產出**：一張觀測表。不分層、不退場、不寫 governance/。

### 決策 gate（跑滿兩週後）

問三題，答不出來就不做 Phase 2：

1. 這張表有沒有導出**至少一項**具體的 skill 修正？
2. `unresolved` / `unknown` 兩桶佔比是否低到讓數字可信？
3. `inferred_read` 的連帶讀取污染有沒有嚴重到讓排名失真？

### Phase 2 — 自我修正機制（gate 通過才做）

- 修改 `maintenance-protocol §1`（🟡，前置條件）
- `governance/skill-feedback.jsonl` + schema validator
- `skills/productivity/skill-review/SKILL.md`
- 三份索引檔鐵律 6 各加一句（🟡）

### Phase 3 — 分層與退場（累積 ≥8 個活躍週才做）

- 啟用 §4.7 分層與 §4.8 維護處理
- 用實際分布回頭校準 percentile 門檻，並把校準結果寫回本文件

---

## 7. 檔案清單與權限分級

| 檔案 | 動作 | 分級 | 階段 |
|------|------|------|------|
| `bin/skill-usage.py` | 新增（唯讀、stdout-only） | 🟢 | P1 |
| `bin/test-skill-usage.sh` + fixtures | 新增 | 🟢 | P1 |
| `skills/index.json`（`lifecycle` 欄） | 更新 | 🟢，須跑 validator | P1 |
| `bin/validate-skill-index.py` | 更新 | 🟢 | P1 |
| `governance/maintenance-protocol.md §1` | 增列 🟢 append 例外 | 🟡 **需核准** | P2 |
| `governance/skill-feedback.jsonl` | 新增 | 🟡 **需核准** | P2 |
| `governance/skill-reviews/` | 新增目錄 | 🟡 **需核准** | P2 |
| `governance/skill-usage/` | 新增目錄（週檔） | 🟡 **需核准** | P2 |
| `skills/productivity/skill-review/SKILL.md` | 新增 | 🟢 | P2 |
| `skills/llms.txt` | 更新 | 🟢 | P2 |
| `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` 鐵律 6 | 各加一句 | 🟡 **需核准** + 跑 §7 四查 | P2 |
| `memory/project-context.md` | 追加 ADR-018 | 🟢 | P2 |

紅線遵守：**不往三份索引的路由表加新列**，只在既有鐵律 6 句尾擴充；三份 inline 段須逐字一致，否則 §7 第 3 查報漂移。

---

## 8. 驗收方式（鐵律 2：不自驗）

1. 數字與手動 `grep` 交叉比對至少 3 個 skill
2. **fixture 陰性案例必測**（`lessons.md` 2026-07-31 條）：
   - 零 event 的 skill 仍須出現在報告
   - 壞掉 / 截斷的 jsonl 行略過而非中斷
   - transcript 目錄不存在 → 可讀訊息，不 traceback
   - **同一 `call_id` 重播只計 1**
   - **一個 call 讀多份 SKILL.md → 各計 1，不是合併成 1**
   - **Claude sidechain / fork 產生的重複事件只計 1**
   - Codex `function_call` 與 `custom_tool_call` 兩種 schema 都要認
   - 缺 `workdir` → 進 `unknown` 桶，不預設歸類
   - 外部 / plugin skill（`openai-docs`、`anthropic-skills:*`）→ 進 `unresolved`，不計入
   - **transcript 內文提到 skill 名但非 tool call → 不計入**（自我污染，§4.5）
3. Phase 2 的 feedback validator 須能重播偵測：orphan resolve、非法 transition、重複 event_id
4. 委派冷啟動 subagent 對抗式審查最終產出

---

## 9. 對審查意見的駁回與更正

三處不採納或需更正，記錄理由：

1. **駁回：alias 合併 `anthropic-skills:coding-workflow → coding-workflow`**
   Codex 建議建立 canonical mapping 把帶 namespace 的名稱映射到本 repo skill。**不採納**——已查 `~/.claude/plugins/` 無對應項目，無法證明兩者是同一個 skill；`anthropic-skills:` 是外部 marketplace 命名空間，與本 repo farm（無 namespace）不同來源。合併等於把外部 skill 的 9 次使用記到本 repo 頭上，比少算更糟。改為一律進 `unresolved` 並列出，由人判。

2. **更正：「`openai-docs` 有 10 筆卻沒出現在計畫書 Top，表示總數與 Top 用了不同篩選口徑」**
   事實有誤。原始探測輸出中 `openai-docs` 確實在列（第 4 名，10 筆），只是 v1 散文摘要只列了本 repo 的前 5 名。口徑一致，但**摘要沒標示已過濾外部 skill** 是真的缺陷——v2 §2.2 已補上完整清單。

3. **部分採納：「不改三份索引檔就好」**
   Codex 主張放棄自主 append、全靠週檢唯讀挖掘，可省下索引修改與四查。使用者已明確裁決要自主 append，不重新翻案。但採納其備援設計：**週檢加一步唯讀挖掘候選 feedback**（§5.5 步驟 2），當作自主記錄漏記時的安全網。同時採納其核心指控——自主 append 需先正式修改權限協議（§5.1）。

---

## 10. 已知限制與非目標

- **不涵蓋 agy**：訊號不可靠（§2.3），報告需明示
- **統計是行為的代理指標，不是價值指標**：一年用一次但每次都救命的 skill 會被判冷。分層只作為 review 的輸入，`critical-on-demand` 標記與「不直接刪」是防呆
- **`inferred_read` 有系統性偏差**：獎勵篇幅長、交互引用多的 skill。這是已接受但未解的效度威脅，退場決策禁止只憑它
- **不裝 hook**、**不排程自動跑**、**不自動改 SKILL.md**
- **不做通用 telemetry**：只算 skill，不算 token / 成本 / 模型分布
