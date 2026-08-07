# 計劃書 v3：制度層 Token 成本量測 + frontmatter 正本化

> **性質**：一次性執行工單，非制度檔。長期規約另行寫入 `governance/`（見 §7）
> **建立**：2026-07-31（v1）· **改版**：2026-08-07（v3）
> **發起人**：使用者（wits）· **執行者**：harness 中立
> **基準 commit**：`b4a0f40`
> **審查歷程**：v1 → 提案 → Codex 0.146.0 對抗審查 → v2 → Codex 複審 + 冷啟動 subagent 審查 → v3
> **狀態**：待執行（目標 E 已於 2026-08-07 提前完成，見 §4）

---

## 0. 需求背景

**使用者的原始問題**：「我怎樣才能知道，我設計一個 skill 消耗的 token 是多少，然後用這個
基準參考值去做優化。」

本質不是「把檔案改小」，而是建立**可重複量測的基準線**，讓每次新增或修改 skill 都能回答
「這次動作讓每個 session 的固定成本增加了多少」。**量測工具是主要交付物，優化是下游產物。**

### 0.1 範圍決策（v2 → v3 的最大變更）

v2 想讓 `skills/index.json` 成為 `llms.txt` 與 frontmatter 兩路的正本。**`llms.txt` 那一路
已證實做不到**，v3 砍掉它。

```
index.json 的 skill 物件欄位：['description', 'name', 'path', 'triggers']  ← 無 category
llms.txt 總計        18,001 bytes
可由 index 逐字生成   13,909 bytes
無來源               4,092 bytes（22%）
  └ 9 個人工分類標題（## Engineering — 核心工程 …）+ 歧義樹 3,371 bytes + 檔頭
```

分類歸屬與歧義樹**只存在於 `llms.txt`**。要生成它就得替 `index.json` 加 `category` 欄並升
`schema_version`，牽動 `validate-skill-index.py` 與 `lib-skill-farm.sh`——成本與收益不成比例。

**v3 範圍**：

- ✅ `index.json` → 38 份 SKILL.md frontmatter `description`（生成規則已驗證 38/38 成立）
- ✅ 量測工具
- ❌ `llms.txt` 生成——維持人工維護，沿用既有的 `index.json ↔ llms.txt` 兩向 validator

**正名**：`index.json` 是 **frontmatter description 的 canonical source**，不是「全域單一正本」。
`llms.txt` 的分類與歧義樹、38 份的 `metadata.trigger` 都是它涵蓋不到的語意資料。

---

## 1. 現況（2026-08-07 實測，v1 數字一律作廢）

| 項目 | v1 記載 | 實測 | 測法 |
|---|---|---|---|
| 常駐 rules（CLAUDE.md + coding-standards + security + coding-workflow-core） | 15,182 | **14,671 bytes** | `wc -c` 四檔加總 |
| 38 份 frontmatter description | 32,492 | **10,761 bytes** | 見 §1.1 |
| 38 份 SKILL.md body | 225,320 | **194,051 bytes** | 見 §1.1 |
| `skills/llms.txt` | 17,578 | **18,001 bytes** | `wc -c` |
| `skills/index.json` | 15,939 | **16,117 bytes** | `wc -c` |
| description ≤ 400 bytes | 未評估 | **30 / 38** | 見 §4 目標 C |

> v1 的 32,492 → 現在 10,761，是另一 session 於 `f1ad25a` 完成的精簡（−67%）。
> v2 曾在成本模型表沿用 v1 的 15,182，與自己「全部重測」的宣告矛盾，v3 已訂正。

### 1.1 量測規格（v1/v2 皆未定義，不同 parser 會差數十 bytes）

- **frontmatter 邊界**：第 1 行 `---` 之後的**第一個獨立 `---` 行**為結束。
  **不得**用 `split('---')`——body 內有 **276 條**獨立 `---` 行
- **description 值**：YAML block scalar `|` 解析後的內容，**strip 尾隨換行**，不含 2 空格縮排
- **description bytes / body bytes**：上述值 / closing delimiter 之後全部內容的 UTF-8 byte 數
- 此規格須寫進 `bin/token-budget.sh` 註解，作為唯一權威定義

---

## 2. 成本模型（三類，禁止相加）

| 類別 | 定義 | 現值 | 優化價值 |
|---|---|---|---|
| **固定開場成本** | 每 session 必付 | 14,671 + 10,761 = **25,432 bytes** | **高** |
| **按需載入成本** | 觸發時才付 | **本計劃不量測** | 中 |
| **維護 inventory** | 人與工具要維護的總量，非執行成本 | body 194,051 bytes | 非 token 議題 |

**按需成本的處置**：本計劃**不量測**，工具**不輸出**期望成本。理由：需要「每 session 平均
觸發幾個 skill」的分布，該數字無 transcript 或 telemetry 支撐。工具只報 inventory 總量與
per-skill body 大小。若日後要做，需先取得實測分布，列為獨立工單。

**不得宣稱**：「一個 session 通常觸發 1–2 個 skill」「38 份全部載入永遠不會發生」——
skill 可鏈式觸發，兩句都無證據。

**`llms.txt` / `index.json` 的開場成本**：靜態接線顯示兩者僅被四份索引「指向」、未被 inline，
`bin/lib-skill-farm.sh` 只讀不注入 → 開場成本為 0。**此為目前接線下的推論**，缺三個 harness
的 runtime 注入實證，不得寫成永久保證。

### 2.1 撤銷 v1 目標 D（前提為事實錯誤）

v1 稱 `llms.txt` 超過 §7 的 16KB 上限。不成立：

1. §7 的上限約束**會被注入 prompt 的 harness 索引檔**（理由 v1 自己引述：Codex 合併 32KiB 的安全邊際）
2. §7 的 `wc -c` 只對 `AGENTS.md` 執行
3. 四份索引實測：CLAUDE 3,643 / CLAUDE.global 1,678 / AGENTS 5,620 / GEMINI 6,734——全部遠低於 16KB
4. `llms.txt` 與 `index.json` 皆未被 inline

> 附帶：v2 曾稱 `index.json` 有「267 bytes 餘量」。該算術基於同一個不適用的上限；且 v1 寫的是
> 模糊的「16KB」——按十進位 16,000 解讀，16,117 反而**超標 117**。結論：不設 16KB 硬牆，
> 但成長策略仍需訂（理由是按需讀取的單次成本與維護負擔）。

---

## 3. 生成器實作規格

### 3.1 已驗證的前提

```
frontmatter.description == index.description + " 觸發：" + index.triggers      → 38/38 成立
38 份 frontmatter 結構完全一致：行1 `---` / 行2 name / 行3 `description: |` /
                                 行4 值（2 空格縮排，單行）/ 行5 metadata: / 行6-8 / 行9 `---`
```

**生成器的本質是「替換第 4 行」**，不是 YAML 重寫。

### 3.2 強制規約

- **禁用 YAML round-trip**。本機無 `yaml`／`ruamel.yaml`（實測 `ModuleNotFoundError`）。
  若自行安裝並用 `safe_load` + `dump`，會同時造成三項禁區違規：`description: |` block 樣式
  被改成引號字串、key 順序被重排、`metadata` 的 `version: "1.0"` 轉 float、
  `last_updated: "2026-06-30"` 轉 `datetime.date` → **只做純文字行替換**
- **禁止用「觸發」當 regex 錨點**。`metadata.trigger` 就在 description 下方兩行且同樣含
  「觸發」二字，誤中即違反禁區
- **只寫 canonical path**，寫入前 `assert not os.path.islink(path)`。38 份 SKILL.md 同時是
  `~/.claude/skills/` symlink farm 的目標，用 `os.replace()` 原子寫入會把 symlink 換成實體檔、
  farm 斷裂
- **`--dry-run` 為預設**，輸出 diff 供人工確認後才實際寫入

### 3.3 必過的 edge case 測試

| # | 案例 | 為什麼會爆 |
|---|---|---|
| 1 | `lazyengineer-review` | description 值含裸 ASCII 冒號加空格（`輸出 net: -N lines。`）。若寫成 plain scalar 而非保留 `\|` block，YAML 語法歧義 |
| 2 | body 內 276 條 `---` | 任何 `split('---')` 或未 anchor 的 DOTALL regex 切爛檔案 |
| 3 | `\|` 的尾隨換行 | `\|`（非 `\|-`）解析值結尾帶 `\n`，index 衍生字串沒有。逐字比對需先 strip |
| 4 | 多行 description | 目前 38/38 皆單行，此路徑**完全未測**。續行掃描若寫成「遇到第一個非 2 空格開頭就停」，遇到值內空行會**靜默截斷**且仍是合法 YAML |
| 5 | 分隔符唯一性 | 反向 split 依賴「index 的 triggers/description 無一含『觸發：』」（現況 38/38 成立）。validator 須把此唯一性列為顯式檢查 |
| 6 | symlink | 見 §3.2 |

---

## 4. 交付目標

### 目標 A：`bin/token-budget.sh`（主要交付物）

- 依 §1.1 規格輸出三類成本，**分開呈現、不加總**
- bytes 為精確值，零外部依賴
- token 數僅供參考顯示，**必須標註估算法與 provider**。預設沿用 `bytes ÷ 3.5` 並在輸出寫明
  「Anthropic 估算，非 Codex/agy 的 token 數」
- 偵測到 `ANTHROPIC_API_KEY` 時可選用 `count_tokens`；**無 key 必須正常運作**（此為驗收條件，
  API 路徑本身不是）
- baseline 存 **`plans/baselines/`**，非 `governance/`（後者全域屬 🟡，寫入需事前同意）
- baseline 檔須記錄產出時的 **git revision**，避免跨 working tree 互相覆蓋

### 目標 B：門檻與規約寫進 `governance/`（🟡，需事前同意）

- 單 skill description **預設上限 400 bytes + 具名 waiver 規則**
  > v2 同時寫「硬門檻」與「允許例外」，制度上矛盾。v3 定案為預設門檻 + 具名 waiver：
  > 超標者須具名列出並附理由，非默許
- **門檻數字本身待檢討**：400 是在任何人量測路由準確度之前拍的。目標 A 產出分布後，
  回頭決定 400 是否合理，或是否該為「承載跨 skill 分流條款」的 skill 另訂級距
- 固定開場成本總預算上限（數字待目標 A 產出後決定）
- `index.json` / `llms.txt` 成長策略
- 新增／修改 skill 時必須跑 `bin/token-budget.sh` 與 validator

### 目標 C：description 精簡收尾 — **使用者已裁決：8 個全部列 waiver，不壓縮**

| skill | bytes | | skill | bytes |
|---|---|---|---|---|
| `academic-mentor` | 655 | | `tw-stock-tracker` | 586 |
| `mentor-invest` | 655 | | `mentor-neuro` | 536 |
| `mentor-society` | 616 | | `mentor-science` | 509 |
| `unknown-matrix-navigation` | 613 | | `mentor-tech` | 601 |

**共同 waiver 理由**（2026-08-07 使用者裁決）：這 8 個承載**跨 skill 分流條款**。其中 6 個是
`mentor-*`，加上 `academic-mentor` 構成七方互相競爭的路由；`tw-stock-tracker` 靠「操作層 vs
概念層」與 `mentor-invest` 分家；`unknown-matrix-navigation` 是 v1 自己點名的合理例外。

已有直接證據顯示此族群正處邊緣：2026-08-07 的 A/B 路由測試中，「社群媒體對青少年的影響，
研究怎麼說」在新版從確定選擇退化為反問，原因正是 `academic-mentor` 與 `mentor-society` 的
觸發詞重疊。再壓只會惡化已知最脆弱的一處。

**執行影響**：description 零變動 → §8 的 A/B 路由驗證退化為新舊相同的空跑 → **本輪跳過**。
§8 方法保留供日後真正動到 description 時使用。

> 若日後有人要壓這 8 個：只改 `index.json`，再跑生成器。**禁止手改 frontmatter。**

### 目標 D'：frontmatter 正本化

- `bin/gen-skill-frontmatter.py`：依 §3 規格實作
- 擴充 `bin/validate-skill-index.py`：
  - 新增 `index.json ↔ frontmatter` 檢查（既有 `index.json ↔ llms.txt` 保留不動）
  - **順帶回報 pre-commit hook 是否實際掛上**——讓「你手動跑的工具」自己告訴你「自動防線在不在」，
    不需另做 `check-hook-install.sh`
- **接進 pre-commit**（使用者已裁決）：`.git/hooks/pre-commit` 已是 wrapper、邏輯在正本
  `hooks/pre-commit-audit.sh`，所以這是**在正本裡多呼叫一支 validator**，不是部署新 hook，
  不新增部署漂移面。**時序排在 D' 完成之後**——沒有生成器就先接驗證會擋住正常工作

### ~~目標 E：修正 `convert-skill` 的已廢除格式~~ — **已完成**

2026-08-07 `b4a0f40` 提前獨立完成。該檔 Step 3 模板與 Step 4 checklist 原本仍要求
「多行 description + 觸發場景 + 示例觸發（≥3 個逐字話術例句）」——正是 `f1ad25a` 廢除的格式，
不修則每個新建 skill 一出生即違規。已改為「一句話定位 + 觸發：清單」、加上 400 bytes 門檻與
「觸發段須與 index.json 逐字一致」，Step 5 並改為「先寫 index.json 再導出 frontmatter」。

---

## 5. 範圍與禁區

**允許修改**：
- 新增 `bin/token-budget.sh`、`bin/gen-skill-frontmatter.py`
- 擴充 `bin/validate-skill-index.py`、`hooks/pre-commit-audit.sh`
- `skills/index.json`
- 38 份 SKILL.md 的 frontmatter **`description` 欄（第 4 行）**
- `governance/maintenance-protocol.md`（新增預算章節，🟡，須事前同意 + 走 §7）

**禁區**：
- ❌ SKILL.md 的 **body**
- ❌ frontmatter 的 `metadata:` 區塊（`metadata.trigger` 與 index **38/38 全部不同**，
  為既有狀態，本計劃不處理也不得順手統一——見 §10）
- ❌ `skills/llms.txt` 的生成（§0.1 已排除；人工維護照舊）
- ❌ `CLAUDE.md`／`AGENTS.md`／`GEMINI.md`／`CLAUDE.global.md`
- ❌ `rules/`、`memory/`、`knowledge/`、`sources/`
- ❌ 不得刪除或合併任何 skill

**開工前**：`git status` 確認乾淨（鐵律 5），確認 HEAD 為 `b4a0f40` 或其後代。

---

## 6. 執行順序

```
1. git status；記下 base commit
2. 目標 A：量測工具（唯讀、零風險，產出 baseline）
3. 目標 D'：生成器 + validator 擴充
     └ 驗證：第一次跑完 git diff 必須為空
        （現況已 38/38 成立，這是免費的正確性證明）
4. 目標 D' 後段：validator 接進 hooks/pre-commit-audit.sh
5. 目標 B：門檻寫進 governance（數字要等 A 產出，故最後；須走 §7 四步）
```

> 目標 C 已裁決為全 waiver、description 零變動，故原 v3 的「C 在 D' 之後」相依已消失，
> §8 本輪跳過。**若日後撤銷 waiver 要真的壓縮，必須先做 D' 再改 index.json**——
> 先手改 38 份再導入生成器，等於先製造漂移再導入防漂移機制。

**Rollback**：任一步驟失敗 → `git checkout -- skills/` 還原（工作區乾淨是前提，步驟 1 不可省）。

---

## 7. Governance 修改程序（🟡）

`governance/` 下除 `lessons.md` 外全為 🟡：**動之前必須先取得使用者同意**，然後走 §2 四步：

```
1. 備份：cp <檔案> governance/backups/<檔名>.<YYYY-MM-DD>.bak
2. 修改
3. read-back：重新讀取確認內容完整、無誤刪段落
4. 重大變更追加 ADR 到 memory/project-context.md
```

> `governance/backups/` 曾因 `f8d23f9` 清空後 git 不追蹤空目錄而消失，導致 §2 第 1 步必然失敗。
> 2026-08-07 `739d079` 已補回並放 `.gitkeep`。

**本計劃至少產生一則 ADR**：frontmatter 正本化改變了「skill description 從哪裡來」的機制。

**本文件處置**：完成後**提請使用者決定**歸檔或刪除。刪檔屬 🟡，執行者不得自行決定。

**commit 政策**：不自行 commit，除非使用者另行指示。

---

## 8. 路由準確度驗證（本輪跳過，方法保留）

> 目標 C 裁決為全 waiver、description 零變動，本節新舊輸入完全相同，跑了證明不了任何事。
> **本輪跳過**。任何日後真正改動 description 的工單必須執行本節。

**v1 方法的兩個缺陷**：(1) 測資取自「示例觸發」，而那正是被刪掉的內容——用答案的一部分測
「刪掉答案後準不準」，系統性高估；(2) 無陰性案例，測不出誤觸發，而壓縮後 description 變短變泛，
誤觸發風險反而上升。

**正確方法**——三類測資，新舊 A/B 對照：

| 類別 | 內容 | 判準 |
|---|---|---|
| (a) 正向 | **不從示例觸發抄**的自然說法 | 命中正確 skill |
| (b) **陰性** | 不該觸發任何 skill 的句子（閒聊、事實查詢、一般問答） | 不觸發 |
| (c) 邊界 | 兩個 skill 都沾邊 | 反問使用者，不逕自選 |

**可重現性要求**：測資、新舊兩份輸入、判分規則、逐句結果全部落成 repo 內 fixture；固定評分
模型與 prompt，記錄重跑次數，輸出 confusion matrix。

**數字判準**：正向類新版命中率**不低於**舊版；陰性類誤觸發數新版**不高於**舊版；任一類出現
新版獨有的失敗 → 逐案檢視，不得以總分掩蓋。

> 2026-08-07 曾跑過一次 30 句代號化 A/B（38 能力匿名化、順序打亂、兩個互不知情 subagent，
> 新舊一致 28/30），但測資與結果只存在於臨時目錄、未進版控 → **不具驗收效力**。

---

## 9. 驗收條件

全部要求**貼出實際執行輸出**，不接受「已確認」這類無憑據敘述。

- [ ] `bin/token-budget.sh` 可執行，三類成本分開輸出，含 §1.1 規格註解
- [ ] 該 script 在**無 API key 環境**下正常運作
- [ ] `bin/gen-skill-frontmatter.py` **第一次**跑完 `git diff` 即為空
      （現況 38/38 成立；第二次為空是必要不充分條件，不可作為唯一判準）
- [ ] **除 description 外零變動**：貼出 `git diff -U0 -- 'skills/**/SKILL.md'`，
      證明所有 hunk 都只落在 frontmatter 第 4 行
- [ ] validator 新增 `index.json ↔ frontmatter` 檢查後通過
- [ ] **反向測試**：分別在 `index.json`、frontmatter 各製造一處差異，validator **必須失敗**，
      貼出失敗訊息（陰性案例不可省）
- [ ] §3.3 六個 edge case 各有對應測試且通過
- [ ] 38 份 SKILL.md 生成後仍為合法 YAML
      > ⚠️ 本機無 YAML parser。驗法須在執行前指定：自寫最小 parser、建 venv 裝 pyyaml
      > **僅供驗證**（不得用於寫入），或明確接受 `validate-skill-index.py` 的行前綴檢查為上限
- [ ] validator 接進 `hooks/pre-commit-audit.sh` 後，**實測**製造一處差異會擋下 commit
- [ ] validator 能正確回報 pre-commit hook 的實際安裝狀態
- [ ] 8 個 waiver 具名落地並附共同理由（見 §4 目標 C）
- [ ] 成本前後對比：以 **§1 的 2026-08-07 數字**為基準

> v2 曾列「`maintenance-protocol` §7 索引防漂移四查全通過」。**已刪除**——該四查的對象
> （CLAUDE.md / CLAUDE.global.md / AGENTS.md / GEMINI.md）全在 §5 禁區內，本計劃一個字都不會動，
> 開工前就已通過，證明不了任何事。

---

## 10. 已知未決事項

1. **`metadata.trigger` 與 index triggers 38/38 全部不同**——既有狀態，不參與路由，但是第四份
   可漂移的副本。本計劃明確不處理，記錄供日後決定：統一、刪除、或明文定義為人類備註欄
2. **`llms.txt` 的 category 與歧義樹無 machine 來源**——範圍收斂的後果。若日後要全域正本化，
   需替 `index.json` 加 `category` 並升 `schema_version`
3. **按需載入成本未量測**——需 transcript 分布，列為獨立工單
4. **400 bytes 門檻本身待檢討**——見 §4 目標 B

---

## 附錄：審查採納紀錄

| 項目 | 處置 | 來源 |
|---|---|---|
| v1 目標 D（llms.txt 壓 16KB） | 作廢，前提為事實錯誤 | Claude 提出，Codex + subagent 各自獨立複驗 |
| `llms.txt` 生成 | **移出範圍**（22% 無來源） | subagent 實測，Codex 同向 |
| 常駐 rules 15,182 | 訂正 14,671 | Codex 抓到 v2 自相矛盾 |
| body 225,320 | 訂正 194,051（v2 曾寫 193,511，為 `b4a0f40` 前的值） | Codex 抓到 v2 沿用舊值；落地前 read-back 再抓到一次 |
| 「1–2 skills/session」 | 刪除（無證據） | Codex |
| 「validator 已有三處檢查」 | 訂正為兩處 | Codex |
| 「API 驗收永遠過不了」 | 撤回（誤讀驗收條件） | Codex |
| 「index.json 僅剩 267 bytes」 | 撤回；Codex 二輪自行撤回並補「十進位解讀反而超標 117」 | Claude 反駁 Codex |
| 硬門檻 vs 例外矛盾 | 定案為預設門檻 + 具名 waiver | Codex |
| 冪等測試方向 | 改為第一次即須為空 | subagent |
| 「除 description 外零變動」驗收 | 新增 | subagent |
| §7 四查 | 刪除（空頭支票） | subagent |
| YAML round-trip 禁令 + 6 個 edge case | 新增 §3 | subagent 實地驗證 |
| symlink farm 寫穿風險 | 新增 §3.2 | subagent |
| 執行順序段 | 復原（v1 有、v2 遺漏） | subagent |
| 路由驗證數字判準 | 新增 §8 | subagent |
| baseline 寫入 governance 的權限衝突 | 改放 `plans/baselines/` | subagent |
| `governance/backups/` 不存在 | 已修（`739d079`） | subagent 發現 |
| `convert-skill` 教已廢格式 | 已修（`b4a0f40`） | subagent 發現 |
| 8 個超標項 | **裁決：全部 waiver，共同理由**；§8 本輪跳過 | 使用者 2026-08-07 |
| validator 接 pre-commit | **裁決：接**，改 `hooks/pre-commit-audit.sh` 正本即可，不新增部署面 | 使用者 2026-08-07 |
| 「開場成本為 0」 | 降級為「目前接線下的推論」 | Codex + subagent |
