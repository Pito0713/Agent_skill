---
name: convert-skill
description: |
  將 GitHub 上收集的原始 workflow/prompt 文件轉換為本專案標準 skill 格式：
  1. 讀取 skills/_inbox/ 中的原始文件，識別類型與核心用途
  2. 決定分類（engineering / marketing / productivity）與命名
  3. 轉換為標準 frontmatter + 內容格式
  4. 品質確認（frontmatter 完整、觸發關鍵字、步驟清單）
  5. 歸檔並同步更新 skills/index.json、skills/llms.txt

  觸發場景：內部維護動作——有新的原始 workflow/prompt 文件放入 skills/_inbox/，需要轉換為本專案標準 skill 格式時。
  示例觸發：「把剛丟進 _inbox 的這份 prompt 轉成 skill」「新增這個 GitHub skill 進來」「幫我把這份收集到的 workflow 轉成標準格式」
metadata:
  trigger: skills/_inbox/ 有新原始文件待轉換為標準 skill 格式時觸發
  version: "1.0"
  last_updated: "2026-07-04"
---

# Convert Skill（原始文件 → 標準格式）

將任意 workflow/prompt 文件轉換為 Claude Code 可呼叫的標準 skill 格式。

---

## Step 1：讀取原始文件

```
[ ] 讀取 skills/_inbox/ 中的目標檔案
[ ] 確認文件類型：
    □ Prompt 模板（直接給 AI 的指令）
    □ Workflow 流程（步驟說明）
    □ Checklist（清單型）
    □ 混合型
[ ] 識別文件的核心用途（一句話）
```

---

## Step 2：決定分類與命名

依照核心用途對應到分類：

| 用途 | 分類 |
|------|------|
| 寫程式、debug、測試、部署、架構、文件 | `engineering/` |
| 行銷文案、SEO、廣告、社群、報告 | `marketing/` |
| 任務管理、會議、記憶、溝通、規劃 | `productivity/` |

命名規則：package 目錄用 `<動詞>-<對象>`，內容檔固定為 `SKILL.md`，
例如：`review-pr/SKILL.md`、`write-changelog/SKILL.md`

---

## Step 3：轉換為標準格式

```markdown
---
name: <kebab-case 名稱>
description: |
  <能力簡述，若有明確步驟可用 1. 2. 3. 編號列出>

  觸發場景：<什麼情況下該喚起這個 skill>
  示例觸發：「<逐字使用者話術1>」「<話術2>」「<話術3>」
metadata:
  trigger: <一行簡短情境描述，勿整串複製 llms.txt 觸發詞>
  version: "1.0"
  last_updated: "<YYYY-MM-DD，新建填轉換當日>"
  source: <原始 GitHub URL，如有>
---

# <標題>

<原始內容重新整理，保留核心邏輯，補充以下要素：>

## 觸發條件

<什麼情況下使用這個 skill>

## 執行步驟

<有序的步驟清單，使用 [ ] checklist 格式>

## 輸出格式

<說明這個 skill 產出什麼，格式是什麼>

## 範例

<如有必要，補充使用範例>
```

---

## Step 4：品質確認

```
[ ] frontmatter 完整（name、多行 description、metadata: trigger/version/last_updated）
[ ] description 含「觸發場景」+「示例觸發」（≥3 個逐字使用者話術例句，讓 Claude 知道何時啟動）
[ ] 不加 allowed-tools（Claude Code 中為功能性限制欄，會綁死疊加型判斷 skill）
[ ] 步驟清單明確可執行（不模糊）
[ ] 有輸出格式說明
[ ] 無原始文件中的冗餘說明或廣告文字
[ ] 技術詞彙保留英文，其餘繁體中文
```

---

## Step 5：歸檔與同步

```bash
# 移動到對應分類
mkdir -p skills/<category>/<new-name>
mv skills/_inbox/<filename>.md skills/<category>/<new-name>/SKILL.md
```

完成後必須同步更新以下兩個索引並執行 validator，缺一不可：

```
[ ] skills/index.json            → 加入唯一 name / package path（machine coverage 正本）
[ ] skills/llms.txt              → 在對應分類區塊加入 name / path / triggers / description
[ ] python3 bin/validate-skill-index.py
```

> 🔴 **禁止**同步往 CLAUDE.md / AGENTS.md 加列。兩個 harness 的 adapter
> 都連到完整 `skills/` 正本，入口檔只保留 index 指標。

---

## 轉換範例

**原始（_inbox/raw-prompt.md）**：
```
You are a code reviewer. Review the following code and find bugs.
Focus on: security, performance, readability.
Output a list of issues with severity.
```

**轉換後（engineering/review-code/SKILL.md）**：
```markdown
---
name: review-code
description: |
  審查程式碼品質與安全性，依序檢查安全性 / 效能 / 可讀性三面向並輸出分級問題清單。

  觸發場景：使用者要求審查一段程式碼的品質或安全性。
  示例觸發：「幫我 review 這段」「檢查這段程式碼有沒有問題」「code review 一下」
metadata:
  trigger: 程式碼品質 / 安全性審查時觸發
  version: "1.0"
  last_updated: "2026-07-22"
  source: https://github.com/example/repo
---

# Code Review

## 執行步驟

[ ] 讀取目標程式碼
[ ] 依序檢查三個面向：
    - 安全性（OWASP Top 10）
    - 效能（時間複雜度、不必要的 re-render）
    - 可讀性（命名、函式長度、註解）

## 輸出格式

每個問題一條，格式：
`[嚴重度] 問題描述 → 建議修改方式`

嚴重度：CRITICAL / HIGH / MEDIUM / LOW
```
