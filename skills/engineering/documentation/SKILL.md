---
name: documentation
description: |
  撰寫技術文件，支援 README / API docs / runbook / inline 說明。 觸發：幫我寫文件、更新 README、API docs、建立 runbook、寫 API docs
metadata:
  trigger: 撰寫 README / API docs / runbook / ADR 時觸發
  version: "1.0"
  last_updated: "2026-06-08"
---

# Documentation Skill

好的文件回答三個問題：**什麼**（what）、**為什麼**（why）、**怎麼用**（how）。

---

## 文件類型與模板

### README.md

```markdown
# <Project Name>

一句話說明這個專案是什麼、解決什麼問題。

## 快速開始

\`\`\`bash
# 最少步驟讓專案跑起來
npm install
npm run dev
\`\`\`

## 目錄結構

\`\`\`
src/
├── ...
\`\`\`

## 環境設定

| 環境變數 | 必填 | 說明 | 預設值 |
|---------|------|------|--------|
| DATABASE_URL | ✅ | PostgreSQL 連線字串 | - |
| PORT | | HTTP port | 3000 |

## 開發

\`\`\`bash
npm run dev      # 開發模式
npm run test     # 執行測試
npm run build    # 建置
\`\`\`

## 部署

[部署步驟或連結到 runbook]

## 貢獻

[貢獻指南或連結]
```

---

### API 文件（OpenAPI / JSDoc）

```ts
/**
 * 建立新使用者
 *
 * @route POST /api/users
 * @access Public
 *
 * @param {Object} body - Request body
 * @param {string} body.name - 使用者名稱（1-100 字元）
 * @param {string} body.email - 電子信箱
 *
 * @returns {201} 建立成功，回傳使用者資料
 * @returns {400} 輸入驗證失敗
 * @returns {409} Email 已存在
 *
 * @example
 * // Request
 * POST /api/users
 * Content-Type: application/json
 * {
 *   "name": "Alice",
 *   "email": "alice@example.com"
 * }
 *
 * // Response 201
 * {
 *   "id": "uuid",
 *   "name": "Alice",
 *   "email": "alice@example.com",
 *   "createdAt": "2026-01-01T00:00:00Z"
 * }
 */
```

---

### Runbook（操作手冊）

```markdown
# Runbook：<事件名稱>

**版本**：v1.0  
**最後更新**：YYYY-MM-DD  
**負責人**：@team

---

## 症狀

- 用戶回報 ...
- 監控警報：...

## 嚴重程度

P1 / P2 / P3（說明標準）

## 初步確認

\`\`\`bash
# 確認服務狀態
kubectl get pods -n production

# 查看最近 log
kubectl logs <pod> --tail=100

# 確認 DB 連線
psql $DATABASE_URL -c "SELECT 1"
\`\`\`

## 處理步驟

### 情況 A：[特定症狀]

1. 執行 `<指令>`
2. 確認 `<預期結果>`
3. 如果沒有改善，繼續情況 B

### 情況 B：[另一症狀]

1. ...

## 升級條件

以下情況升級到 on-call：
- 超過 X 分鐘無法解決
- 影響超過 Y% 用戶

## 事後

- 建立 incident report
- 更新此 runbook

## 相關連結

- Dashboard：<url>
- Alert 定義：<url>
- 上次事件：<url>
```

---

### Architecture Decision Record（ADR）

```markdown
# ADR-<NNN>：<決策標題>

**狀態**：草稿 / 已接受 / 已棄用  
**日期**：YYYY-MM-DD  
**決策者**：@name

---

## 背景

描述問題背景，為什麼需要做這個決策。

## 考慮的選項

### 選項 A：<名稱>

**優點**：
- ...

**缺點**：
- ...

### 選項 B：<名稱>

**優點**：
- ...

**缺點**：
- ...

## 決策

選擇**選項 X**，原因：...

## 後果

### 正面影響
- ...

### 負面影響 / 風險
- ...

### 需要的後續行動
- [ ] ...
```

---

## 文件品質 Checklist

```
[ ] 有 code example（不只是說明）
[ ] 範例可以直接複製執行
[ ] 說明了為什麼，不只是是什麼
[ ] 列出了已知限制和邊緣情況
[ ] 有更新日期
[ ] 沒有過時的資訊
[ ] 術語一致（同一概念用同一詞）
```

---

## 禁止事項

- 把 code comment 當文件（說了 what 但沒說 why）
- 沒有範例的純文字說明
- 不維護的文件（設 reminder 定期更新）
