# CLAUDE.md — AI Agent Skill Project

> 這是 Claude Code 的專案頂層指令。所有 rules、skills、agents、hooks 均從此檔載入。

---

## 專案概覽

這是一個用於管理 AI coding agent 行為規範的標準化專案骨架，涵蓋：
- **Rules**：coding 規範（語言、框架、安全、測試、git）
- **Skills**：可呼叫的工作流程（coding、debug、testing、docs、handoff）
- **Agents**：專責子任務的 subagent 定義
- **Hooks**：自動化觸發器（pre-commit、安全攔截）
- **Memory**：跨 session 的工作記憶

---

## 常駐載入（每次 session 自動生效）

@rules/coding-standards.md
@rules/security.md
@skills/engineering/coding-workflow-core.md
@skills/engineering/gemini-assist.md

---

## 按需載入（視任務手動引入）

| 情境 | 載入 |
|------|------|
| TypeScript 專案（自動偵測）| `@rules/typescript.md` |
| React 專案（自動偵測）| `@rules/react.md` |
| Next.js 專案（自動偵測）| `@rules/nextjs.md` |
| Python 專案（自動偵測）| `@rules/python.md` |
| 撰寫 / 執行測試（自動偵測）| `@rules/testing.md` |
| 提到 commit / PR（自動偵測）| `@rules/git.md` |
| 前端審查 / review / XSS / CORS / PII | `@rules/frontend-security.md` |
| 查實作模式 | `@skills/engineering/coding-workflow-ref.md` |
| 練習 / 刻意改進 | `@skills/learning/feedback-loop.md` |
| 學術深度解析 / 科學根據查詢 | `@skills/learning/academic-mentor.md` |
| 神經科學 / 大腦機制 / neuro vault 主題 | `@skills/learning/mentor-neuro.md` |
| 社會現象 / 科技與社會 / 傳播 / 教育制度 | `@skills/learning/mentor-society.md` |
| 物理 / 化學 / 生物 / 自然科學原理 | `@skills/learning/mentor-science.md` |
| 技術架構 / 系統設計 / 技術選型 / 工程權衡 | `@skills/learning/mentor-tech.md` |
| 投資策略 / 資產配置 / 行為偏誤 / 財務規劃 | `@skills/learning/mentor-invest.md` |
| UI/UX 設計規劃 | `@skills/design/ui-design-flow.md` |
| 精簡程式碼 / 反 over-engineering | `@skills/engineering/lazyengineer.md` |
| 過度設計掃描 / 找可刪的程式碼 | `@skills/engineering/lazyengineer-review.md` |
| 查詢內部規範 / knowledge base | `@skills/productivity/rag-search.md` |
| 查看跨專案進度 | `@skills/productivity/project-dashboard.md` |
| 從 Obsidian 搜尋歷史筆記 | `@skills/productivity/obsidian-query.md` |
| 將對話重點存入 Obsidian | `@skills/productivity/obsidian-save.md` |

---

## 規則索引

```
rules/
├── coding-standards.md   # 通用 coding 規範（常駐）
├── security.md           # 安全規範（常駐）
├── typescript.md         # TypeScript 規範（按需）
├── react.md              # React 規範（按需）
├── nextjs.md             # Next.js App Router 規範（按需）
├── python.md             # Python 規範（按需）
├── testing.md            # 測試規範（按需）
└── git.md                # Git workflow 規範（按需）
```

## 行為準則

1. **回應前先讀 rules/**：所有 coding 任務執行前必須確認適用的 rule 檔
2. **優先使用 skills/**：重複性工作流程使用對應 skill，不要重新發明
3. **委派 subagent**：遇到專業子任務時，優先委派對應 agent
4. **更新 memory/**：每次重要決策或架構選型後更新 project-context.md

## 歧義處理規則

當使用者訊息**同時命中多個觸發詞**時，禁止自行猜測意圖，執行以下流程：

1. 列出所有命中的 skill 與各自用途差異
2. 詢問使用者選擇後才執行

**範例：**

> 使用者：「幫我新增這個畫面的功能」
> 命中：`new-feature`（功能開發）+ `ui-design-flow`（UI 設計規劃）
>
> Claude 回應：
> 「偵測到兩個可能的流程，請選擇：
> A. **直接開發功能**（new-feature）— 已知 UI 設計，直接進入實作
> B. **先規劃 UI 再開發**（ui-design-flow → new-feature）— 需要先確認畫面架構
> C. **兩個都做**（ui-design-flow 完成後接 new-feature）」

**常見歧義情境：**

| 使用者說 | 命中 skill | 詢問重點 |
|------|------|------|
| 「新增這個畫面的功能」 | new-feature + ui-design-flow | 要先設計 UI 還是直接實作？ |
| 「review 這個 component 有沒有安全問題」 | code-review + security-review | 走完整 review 還是只做安全審查？ |
| 「這個 bug 我看不懂」 | debug-flow + concrete-example | 要除錯還是要解釋邏輯？ |
| 「準備 commit / commit 之前確認一下」 | version-log + git.md | 有提到版本號 / README / 變更記錄 → version-log；只確認 commit 格式 / branch 命名 → 只載入 git.md |
| 「我看不懂 / 為什麼還是錯」 | debug-flow + concrete-example | 有 error message / stack trace / 測試失敗 → debug-flow；沒有具體錯誤、想理解邏輯 → concrete-example；兩者都有 → 詢問使用者 |
| 「跟我解釋 / 這原理是什麼 / 為什麼會這樣」 | mentor-neuro + mentor-society + mentor-science + mentor-tech + concrete-example + debug-flow | 主題是神經科學 / 大腦機制 → mentor-neuro；主題是社會現象 / 傳播 / 教育 → mentor-society；主題是物理 / 化學 / 生物 → mentor-science；主題是技術架構 / 系統設計 → mentor-tech；主題是程式邏輯 → concrete-example；主題是 bug → debug-flow；無法判斷 → 詢問使用者 |

## 意圖不明確處理規則

當使用者說出**模糊意圖詞**（無法直接對應觸發詞），禁止自行假設，執行以下詢問：

```
「請問你希望：
  A. 找出問題並修復（debug-flow）
  B. 審查程式碼品質（code-review）
  C. 補強 / 新增功能邏輯（new-feature）
  D. 只需要改進建議（feedback-loop）」
```

**觸發此詢問的模糊詞：**
「完善」、「優化」、「讓它更好」、「改進這個功能」、「怎麼讓這個更好」、「有什麼可以加強的」

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 回應給極短摘要，再給可執行內容
- 指出邏輯漏洞、不為友善而同意
- 涉及數字與風險時先看基率

## Skill 索引

所有可用 skill、觸發詞與說明詳見 [`skills/llms.txt`](skills/llms.txt)。

歧義處理與意圖不明確時的詢問邏輯，詳細範例定義在本檔上方（第「歧義處理規則」節），精簡版亦同步於 `skills/llms.txt` 末段。
