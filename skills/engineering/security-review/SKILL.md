---
name: security-review
description: |
  安全審查協調器，依情境判斷委派哪個安全 agent，本身不直接執行審查：
  1. 快速掃描（PR/commit 前）→ security-auditor
  2. 前端漏洞（XSS/CSRF/token 儲存）→ frontend-security-auditor
  3. 完整合規報告（上線前 / security sprint）→ owasp-reviewer

  觸發場景：需要安全審查、懷疑有 OWASP 相關漏洞、想確認前端安全機制或 token 儲存方式是否安全。
  示例觸發：「幫我做一次安全審查」「這支 API 有沒有 OWASP 漏洞」「這個前端 token 怎麼存比較安全」
metadata:
  trigger: 安全審查 / OWASP 疑慮 / 前端安全機制詢問時觸發
  version: "1.0"
  last_updated: "2026-06-22"
---

# Security Review — Orchestrator

## 觸發後第一步：判斷審查類型

依使用者描述，對應到以下三種情境之一：

| 情境 | 委派對象 |
|------|---------|
| PR/commit 前掃描、懷疑某功能有後端漏洞 | `agents/04-security/security-auditor.md` |
| 前端程式碼、React component、XSS / CSRF / token 儲存 | `agents/04-security/frontend-security-auditor.md` |
| 上線前完整合規、security sprint、全面 OWASP 評估 | `agents/04-security/owasp-reviewer.md` |

## 意圖不明確時詢問使用者

> 「請問這次安全審查的目的是：
> A. **快速掃描**（PR/commit 前，找後端漏洞）→ security-auditor
> B. **前端程式碼審查**（XSS/CSRF/token 儲存）→ frontend-security-auditor
> C. **完整合規報告**（上線前或 security sprint）→ owasp-reviewer」

若使用者同時提到前後端，先執行 A 或 C，完成後追加執行 B。

## 分工原則

| Agent | 定位 | 輸出 |
|-------|------|------|
| `security-auditor` | 後端快速掃描，不修改程式碼 | 問題清單（CRITICAL/HIGH/MEDIUM/LOW）|
| `frontend-security-auditor` | 瀏覽器端漏洞，不修改程式碼 | 前端漏洞清單 |
| `owasp-reviewer` | 整體合規評估，可使用 WebSearch 查最新 OWASP | OWASP 合規報告表格 |

---

## ✅ 正確做法 / ❌ 常見錯誤

```
✅ 依前後端分類，各用正確的審查角度（不用後端視角審查 CSP / CORS 設定）
✅ 每個問題對應 OWASP 項目（A01-A10），讓修復有明確標準
✅ 只回報問題清單，不直接提修法（修法由 Claude 與使用者決定）
✅ 確認後端 API 是否真的有做伺服器端驗證，不只看前端有沒有擋

❌ 只掃表面語法（有沒有 eval、innerHTML），忽略業務邏輯的授權流程
❌ 把「建議優化」（效能、UX）和「安全漏洞」混為一談
❌ 沒有確認 token / secret 是否進了 git history 或 log
❌ 審查範圍只看新增程式碼，忽略被修改的現有安全邊界
```
