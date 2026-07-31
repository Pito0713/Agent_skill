# 計劃書：制度層 Token 成本量測與優化

> **性質**：一次性派工單，非制度檔。執行完畢後可歸檔或刪除。
> **建立日期**：2026-07-31
> **發起人**：使用者（wits）
> **執行者**：其他 agent harness（Codex / agy / Claude Code subagent 皆可，本文件 harness 中立）
> **狀態**：待執行

---

## 1. 需求背景（接手者必讀）

使用者正在設計與維護這套 skill 制度倉庫（`~/Agent_skill`，三 harness 共用正本）。目前累積 38 個 skill。

**使用者的原始問題**：「我怎樣才能知道，我設計一個 skill 消耗的 token 是多少，然後用這個基準參考值去做優化。」

也就是說，這件事的本質不是「把檔案改小」，而是要建立**可重複量測的基準線**，讓每次新增或修改 skill 時，都能回答「這次動作讓每個 session 的固定成本增加了多少」。優化是量測的下游產物，量測工具才是主要交付物。

---

## 2. 現況實測數據（2026-07-31 量測，作為優化基準線）

量測方式：`bytes ÷ 3.5 ≈ tokens`（繁中 UTF-8 為 3 bytes/字，Claude tokenizer 對 CJK 約 1 字 ≈ 1 token，中英混排後落在 ÷3～÷4 之間）。

| 帳目 | 何時付費 | bytes | ≈ tokens |
|---|---|---|---|
| 常駐 rules（CLAUDE.md + coding-standards + security + coding-workflow-core） | 每 session 開場 | 15,182 | ~4.3K |
| **38 個 SKILL.md 的 frontmatter description** | **每 session 開場** | **32,492** | **~9.3K** |
| SKILL.md body（38 檔） | 僅觸發時 | 225,320 | ~64K |

### 核心發現

1. **frontmatter description 是最大的常駐成本**，比整套常駐 rules 還貴一倍以上。所有 skill 的 description 都會被載入 system prompt 供路由判斷，不論該 session 是否用到。
2. **body 不是優化對象**。`tech-lead-mode` body 有 13KB，但只在觸發時付一次，寫詳細是划算的。**本計劃不得刪減 body 內容。**
3. **description 現況過長**：平均 855 bytes（~245 tokens），最大 `unknown-matrix-navigation` 1,259 bytes。每份都寫了「5 條編號步驟 + 觸發場景 + 3 個示例觸發」，其中**編號步驟對路由決策沒有貢獻**——那些資訊屬於 body。description 的唯一職責是讓路由判斷「要不要載入我」。

### 順帶發現的既有違規

`skills/llms.txt` 目前 **17,578 bytes，已超過 `governance/maintenance-protocol.md` §7 規定的 16KB 上限**（該上限是 Codex 全域+專案層合併 32KiB 的安全邊際，超過會被靜默截斷）。`skills/index.json` 為 15,939 bytes，逼近上限。本計劃需一併修正。

---

## 3. 交付目標

### 目標 A：可重複的量測工具（主要交付物）

建立 `bin/token-budget.sh`，執行後輸出上述三本帳的當前數字與各 skill 明細。

需求：
- 預設用 `bytes ÷ 3.5` 估算，**零外部依賴**（使用者環境目前沒有 `ANTHROPIC_API_KEY`、也沒安裝 `anthropic` SDK）
- 偵測到 `ANTHROPIC_API_KEY` 存在時，自動改用 Anthropic `POST /v1/messages/count_tokens` 取得精確 `input_tokens`（該 endpoint 免費、不計費）
- 輸出需含：三本帳總計、各 skill 的 description bytes 排行、超出預算門檻的項目標記
- 支援與前次結果比對（例：存一份 baseline，再跑時顯示 delta），讓使用者能看出「這次改動增加了多少常駐成本」

### 目標 B：把預算門檻寫進制度

在 `governance/` 適當位置（執行者判斷，建議 `maintenance-protocol.md` 新增一節）加入：
- **常駐總預算**：目前基準 ~13.6K tokens，設定上限與超標時的處理原則
- **單 skill description 上限：≤ 400 bytes**
- 新增 skill 時必須跑 `bin/token-budget.sh` 確認未超標

### 目標 C：依門檻精簡 38 個 skill 的 description

把每份 SKILL.md 的 frontmatter description 壓到 ≤ 400 bytes。預估可省下約 6K tokens/session。

**精簡原則**：
- 保留：一句話定位 + 觸發場景 + 1～2 個示例觸發（這些是路由判斷的依據）
- 移除：編號步驟清單（移到 body，若 body 已有則直接刪）
- **不得**因為要壓縮而讓兩個 skill 的觸發邊界變模糊

### 目標 D：修正 llms.txt 超標

把 `skills/llms.txt` 壓回 16KB 以下，`skills/index.json` 亦需留出安全邊際。

---

## 4. 範圍與禁區

**允許修改**：
- 新增 `bin/token-budget.sh`
- 38 個 `skills/**/SKILL.md` 的 **frontmatter 區塊**
- `skills/index.json`、`skills/llms.txt`
- `governance/maintenance-protocol.md`（新增預算章節）

**禁區（即使看起來相關也不能碰）**：
- ❌ 任何 SKILL.md 的 **body**（`---` 之後的正文）——body 是按需成本，不是優化對象
- ❌ `CLAUDE.md`、`AGENTS.md`、`GEMINI.md`（三 harness 薄索引，動它們屬於 🟡 級，需另行請示使用者）
- ❌ `rules/` 下任何檔案
- ❌ `memory/`、`knowledge/`、`sources/`
- ❌ 不得刪除任何 skill，不得合併 skill

**開工前必做**：
先跑 `git status`。目前已知 `skills/index.json`、`skills/llms.txt`、`skills/productivity/project-dashboard/SKILL.md` 處於 modified 狀態，可能有其他 session 正在編輯。**若發現非預期變更，停下來問使用者，不要默默覆蓋。**

---

## 5. 驗收條件（全部達成才算完成，缺一回報「進行中」）

- [ ] `bin/token-budget.sh` 可執行並輸出三本帳數字，**貼出實際執行輸出**
- [ ] 該 script 在無 API key 環境下正常運作（不得因缺 key 而失敗）
- [ ] 38 個 skill 的 description **全部** ≤ 400 bytes，貼出驗證指令輸出
- [ ] `skills/llms.txt` < 16KB、`skills/index.json` < 16KB，貼出 `wc -c` 輸出
- [ ] **路由準確度未退化**（最重要，見下方說明）
- [ ] `governance/maintenance-protocol.md` §7 索引防漂移四查**全部通過**，貼出四項輸出
- [ ] 常駐成本前後對比：貼出優化前 32,492 bytes → 優化後實際數字

### 關於路由準確度驗證

這是本計劃唯一可能造成實質損害的地方。壓縮 description 若壓掉了關鍵觸發詞，會導致 skill 該觸發時不觸發。

驗證方式：從每個 skill 原本的「示例觸發」句子中各取 1 句（共 38 句），對照精簡後的 description 集合，逐句判斷「僅憑新 description，能否唯一指向正確的 skill」。有歧義或指不到的，該 skill 的 description 必須改回來或重寫，**不得為了達成 400 bytes 目標而犧牲路由準確度**。

若某個 skill 確實無法在 400 bytes 內保持路由清晰（例如 `unknown-matrix-navigation` 觸發條件本身就複雜），**允許超標，但必須在回報中列出並說明原因**。門檻是工具，不是教條。

---

## 6. 執行順序建議

1. `git status` 確認工作區乾淨（有異常先問使用者）
2. 先做**目標 A**（量測工具）——後續每一步都要靠它驗證，且它會產出優化前的 baseline
3. 存下 baseline
4. 做**目標 C**（精簡 description），每改幾個就跑一次 script 看 delta
5. 做路由準確度驗證，回頭修正壓過頭的項目
6. 做**目標 D**（llms.txt / index.json）
7. 跑 §7 四查
8. 做**目標 B**（把最終確定的門檻寫進制度）——放最後，因為門檻數字要等實際做完才知道合不合理

---

## 7. 不允許

- 不重構範圍外程式碼
- 不放寬既有測試或檢查
- 不「順便」修其他發現的問題——記下來回報，不處理
- 不自行 commit（除非使用者另行指示）；完成後回報，由使用者決定是否提交

---

## 8. 回報格式

1. **plan**：你打算怎麼做（≤5 行）
2. **`git diff --stat` 輸出**
3. **每條驗收條件的證據**（實際指令輸出貼出，不接受「已確認」這類無憑據敘述）
4. **路由準確度驗證結果**：38 句測試的通過/失敗明細，失敗項如何處理
5. **超標例外清單**：哪些 skill 的 description 未壓到 400 bytes，原因為何
6. **剩餘風險**（無也要寫「無」）

---

## 9. 給執行者的補充脈絡

- 本 repo 是三 harness（Claude Code / Codex / agy）共用的制度正本，唯一 source of truth 在 `~/Agent_skill`
- 動制度檔前請先讀 `governance/maintenance-protocol.md`，特別是 §1 權限分級與 §7 索引防漂移檢查
- 本 repo 的設計哲學是「用到才讀，讀完就動手」——不要預先載入所有檔案
- 溝通用繁體中文，技術詞彙保留英文
