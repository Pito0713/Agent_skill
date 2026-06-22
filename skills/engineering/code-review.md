---
name: code-review
description: Code Review 協調器。當使用者說「幫我 code review」、「審查這段 code」、
  「PR review」、「有沒有問題」、「幫我看一下」、「merge 前檢查」時觸發。
  自動偵測專案類型，依序執行各審查階段，輸出統一報告。
---

# Code Review — Orchestrator

## 觸發後第一步：確認審查範圍

詢問使用者（若未說明）：
> 「請問要審查的範圍是？」
> 1. 當前 git diff（`git diff HEAD`）
> 2. 特定檔案（請提供路徑）
> 3. 貼上的程式碼片段

確認後進入 Phase 0。

---

## Phase 0：偵測專案類型

```bash
ls tsconfig.json next.config.* requirements.txt pyproject.toml 2>/dev/null
grep -s '"react"\|"vue"\|"next"' package.json 2>/dev/null
```

| 偵測結果 | 載入規則 |
|---------|---------|
| `tsconfig.json` 存在 | `rules/typescript.md` |
| `package.json` 含 react / next | `rules/react.md` 或 `rules/nextjs.md` |
| `package.json` 含 react / vue / next | `rules/frontend-security.md` |
| `requirements.txt` / `*.py` 存在 | `rules/python.md` |
| 任何專案 | `rules/coding-standards.md`（常駐）|
| 任何專案 | `rules/security.md`（常駐）|

**輸出**：「偵測到：[技術堆疊]，載入對應規則」

---

## Phase 1：邏輯與可讀性審查

依據 `rules/coding-standards.md`：

- [ ] 函式單一職責，長度 < 50 行
- [ ] 命名是否揭示意圖
- [ ] 有無巢狀地獄（應改用提前 return）
- [ ] 錯誤處理是否完整（無空 catch）
- [ ] 有無 hardcoded values / console.log

---

## Phase 1.5：Over-Engineering 掃描（可選）

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 2
> - 使用者未提到「精簡」、「過度設計」、「可以刪什麼」
> - 審查範圍為 hotfix / 微小變更（< 20 行）

若使用者有提到「lazyengineer」或「太複雜了」，觸發 `skills/engineering/lazyengineer-review.md`：

```
[ ] 掃描五種 over-engineering 類型（delete / stdlib / native / yagni / shrink）
[ ] 輸出每筆：L行號: [tag] 描述。替換方案。
[ ] 最終輸出：net: -N lines possible
```

此 phase 輸出**不影響**後續 Phase 2-5 的安全 / 測試審查。

---

## Phase 2：安全審查

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 3
> - 審查範圍只有文件檔（.md / .txt / .json 靜態設定）
> - 審查範圍只有測試檔案（*.test.* / *.spec.*）
> - 使用者明確說「只看邏輯可讀性，跳過安全審查」
>
> 🚫 **CRITICAL GATE**：若發現 CRITICAL 安全問題
> → 詢問「發現 CRITICAL 安全問題，是否繼續？(y 繼續記錄 / n 停止並輸出問題清單）」

依專案類型選擇 agent：

```
前端專案 → agents/04-security/frontend-security-auditor.md
後端專案 → agents/04-security/security-auditor.md
全端專案 → 兩者都執行
```

---

## Phase 3：測試覆蓋審查

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 4
> - 審查範圍本身就是測試檔案
> - 純 refactor，無新增/修改公開 API 或業務邏輯
> - 使用者明確說「不需要測試覆蓋意見」

依據 `rules/testing.md`：

- [ ] 新增功能是否有對應測試
- [ ] 是否涵蓋 happy path + error case
- [ ] 有無測試邊界條件（null、空陣列、極大值）
- [ ] 若無測試 → 標記 MEDIUM，建議補測試範圍

---

## Phase 4：Git / PR 格式審查（有 PR 時）

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 5
> - 審查範圍為貼上的程式碼片段（非 git diff，無 PR 脈絡）
> - 使用者未提及 PR / commit / 分支合併
> - 使用者明確說「只看程式碼邏輯」

依據 `rules/git.md`：

- [ ] commit message 是否清楚描述 why
- [ ] PR 是否過大（建議單次 PR < 400 行）
- [ ] 有無不應進入 PR 的檔案（.env、log、dist）

---

## Phase 5：Gemini 交叉驗證

將 Phase 1–4 初步報告 + 完整程式碼一併送交 Gemini 獨立複審。

### Step 1：整合初步報告

將 Phase 1–4 所有發現整理成結構化文字：

```
[初步審查報告]
邏輯問題：...
安全問題：...
測試缺口：...
PR 格式：...
```

### Step 2：依審查範圍選擇送交方式

**範圍為 git diff：**
```bash
git diff HEAD | agy -p "
以下是另一個 reviewer 的初步審查報告：
---
[貼入初步報告]
---
以上 diff 是對應的完整程式碼變更，請你：
1. 同意 / 不同意報告中每個問題（說明原因）
2. 補充報告遺漏的問題

每個項目格式：
[同意 / 不同意 / 補充] 類別：描述 → 潛在影響

只回報問題，不提供修改方案。繁體中文。"
```

**範圍為特定檔案：**
```bash
cat [filepath] | agy -p "
以下是另一個 reviewer 的初步審查報告：
---
[貼入初步報告]
---
以上是對應的完整程式碼，請你交叉驗證並補充遺漏問題。
格式同上。繁體中文。"

# 多檔案
cat src/a.ts src/b.ts | agy -p "..."
```

### Step 3：Claude 裁決 Gemini 輸出

收到 Gemini 結果後：
- **Gemini「不同意」** → 重新評估，決定保留或移除，記錄原因
- **Gemini「補充」** → 驗證後決定是否納入最終報告
- **雙方一致** → 信心提升，直接納入

---

## 最終輸出：統一審查報告

```
## Code Review 報告
專案類型：[TypeScript / React / Python / ...]
審查範圍：[git diff / 檔案名稱]
交叉驗證：Claude 初審 + Gemini 複審 ✅

### 🔴 CRITICAL
- [位置] 問題描述 → 潛在影響
  來源：[Claude / Gemini / 雙方確認]

### 🟠 HIGH
- [位置] 問題描述 → 潛在影響
  來源：[Claude / Gemini / 雙方確認]

### 🟡 MEDIUM
- [位置] 問題描述 → 建議
  來源：[Claude / Gemini / 雙方確認]

### 🟢 LOW / 建議
- [位置] 可選改善項目

### ✅ 通過項目
- 無發現問題的審查面向

### ⚖️ 爭議項目（Claude 與 Gemini 意見不同）
- [問題] Claude：[觀點] vs Gemini：[觀點]
  → 最終採用：[誰的判斷，原因]

---
結論：[可合併 / 建議修改後合併 / 需要大幅修改]
```

---

## 分工原則

| 角色 | 負責 |
|------|------|
| Orchestrator（本 skill）| 流程控制、phase 排序、最終裁決 |
| `security-auditor` | 後端安全深度審查（Phase 2）|
| `frontend-security-auditor` | 前端安全深度審查（Phase 2）|
| `gemini-assist` | 獨立交叉驗證，持有完整程式碼脈絡（Phase 5）|
| 各 rules | 各 phase 審查標準基準 |

---

## ✅ 正確做法 / ❌ 常見錯誤

```
✅ 先確認審查維度（邏輯 / 安全 / 測試 / PR 格式）再開始，不一次全掃
✅ 每個問題標明嚴重度 CRITICAL / HIGH / MEDIUM / LOW 與具體位置
✅ 邏輯 bug 和 style 建議分開列，不放在同一嚴重度層級
✅ 看修改後對現有程式碼的影響（regression risk），不只看新增的部分

❌ 把命名格式、indent 等 style 問題列為 HIGH（應為 LOW 或 suggestion）
❌ 只說「這裡有問題」，沒有說明根因與潛在影響
❌ 沒有說明根因就直接建議修法（應先確認問題再討論修法）
❌ 只看當前 diff，沒有確認修改是否破壞現有行為
```
