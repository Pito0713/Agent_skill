---
name: deploy-prep
description: |
  上線前檢查協調器，執行完整的安全、測試、效能、設定檢查以確保上線品質：
  1. 確認上線範圍、目標環境、是否有 DB migration / breaking change
  2. Phase 0 偵測專案類型與必要上線條件
  3. Phase 1 Code Review、Phase 2 安全合規審查（CRITICAL 問題設 gate）
  4. Phase 3 測試驗證（含 migration 正向/回滾確認）
  5. Phase 4 設定與環境確認、Phase 5 Git / Release 確認
  6. Phase 6 agy 最終交叉驗證，輸出上線前確認清單

  觸發場景：使用者準備將變更推上 staging 或 production，需要系統性上線前確認。
  示例觸發：「這個功能要上線了，幫我做上線前檢查」「準備 deploy 到 production」「release 前確認一下有沒有遺漏」
metadata:
  trigger: 上線 / deploy / release 前系統性檢查
  version: "1.0"
  last_updated: "2026-07-04"
---

# Deploy Prep — Orchestrator

## 觸發後第一步：確認上線範圍

詢問使用者（若未說明）：
> 1. 這次 deploy 的範圍？（新功能 / bug fix / 全量更新）
> 2. 目標環境？（staging / production）
> 3. 有沒有 DB migration 或 breaking change？

確認後進入 Phase 0。

---

## Phase 0：偵測專案類型

```bash
ls tsconfig.json next.config.* requirements.txt pyproject.toml 2>/dev/null
grep -s '"react"\|"vue"\|"next"' package.json 2>/dev/null
```

並確認以下上線必要條件存在：
```bash
ls .env.example Dockerfile docker-compose.yml 2>/dev/null
git log --oneline -5  # 確認最近變更
git status            # 確認無未提交的變更
```

---

## Phase 1：Code Review

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 2
> - 本 session 已完成 code-review，且發現的問題已全數修正
> - 使用者確認「上週已做過 code-review，問題已修正」
> - 純設定檔 / 環境變數變更（無邏輯修改）

觸發 `skills/engineering/code-review/SKILL.md`（精簡模式）：

```
[ ] 邏輯與可讀性（Phase 1）
[ ] 安全審查（Phase 2）
[ ] 測試覆蓋（Phase 3）
```

---

## Phase 2：安全合規審查

> ⚡ **Staging 精簡模式**：若目標環境為 staging
> → 只執行 secrets / .env 洩漏檢查，跳過完整合規審查，直接進入 Phase 3
>
> 🚫 **CRITICAL GATE**：若發現 CRITICAL 安全問題（如 hardcoded secret / SQL injection）
> → 強制停止，輸出問題清單，**不建議繼續上線程序直到修正完成**

依專案類型執行：

```
後端 → agents/04-security/security-auditor.md
前端 → agents/04-security/frontend-security-auditor.md
合規 → agents/04-security/owasp-reviewer.md（重大版本上線時執行）
```

重點確認：
```
[ ] 無 hardcoded secrets / API keys
[ ] .env 未進入 git
[ ] 所有外部輸入有驗證
[ ] JWT / session 有效期設定正確
[ ] Rate limiting 已啟用（公開 API）
[ ] HTTP Security Headers 已設定
```

---

## Phase 3：測試驗證

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 4
> - 純設定檔 / 環境變數變更（無邏輯修改，無需重跑測試）
> - 目標為 staging 且使用者確認「CI 已通過，主流程手動驗證完畢」
>
> ⚡ **無 DB Migration 精簡模式**：跳過 migration 相關 checklist 三項

委派 `agents/05-quality-assurance/e2e-tester.md`：

```
[ ] 所有現有測試通過
[ ] 關鍵 user journey E2E 測試通過
[ ] staging 環境手動驗證主要 flow
```

若有 DB migration：
```
[ ] migration 可正向執行
[ ] migration 可回滾（rollback）
[ ] staging 已執行 migration 確認無誤
```

---

## Phase 4：設定與環境確認

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 5
> - 使用者確認「.env 未異動，無新增第三方服務，CORS 未更動」
> - 純 bug fix，無任何環境設定變動

```
[ ] production .env 所有必要變數已設定
[ ] .env.example 是否與 production 同步（無多餘 / 缺少的 key）
[ ] 第三方服務 API key 是否為 production 版本（非 sandbox）
[ ] CORS origin 是否指向正確的 production domain
[ ] Log level 是否調整為 production 等級（非 debug）
[ ] CDN / cache 設定是否正確
```

---

## Phase 5：Git / Release 確認

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 6
> - 目標環境為 staging（無需打 tag / 更新 CHANGELOG）
> - 緊急 hotfix，使用者確認「先上線，事後補 changelog」

依據 `rules/git.md`：

```
[ ] main / master branch 是最新狀態
[ ] 無未解決的 merge conflict
[ ] CHANGELOG 或版本紀錄已更新（version-log.md）
[ ] 已打 release tag（git tag v[version]）
[ ] PR 已 approved（若有 review 流程）
```

---

## Phase 6：agy 交叉驗證

詢問使用者：「是否啟用 agy 最終交叉驗證？(y/n)」

**y：**（$CLI_CMD 依 `agy-assist.md` 前置確認；agy 不可用時走模式 C 的 Claude Subagent Fallback）
```bash
# 審查範圍：上次 release 到現在的全部變更，不是只有最後一個 commit
# 無 tag 時改用使用者指定的範圍（例：main..release-branch）
RANGE="$(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~1)..HEAD"

# Bash tool timeout: 570s（agy --print-timeout 9m + 30s 緩衝，模式 C）
git diff "$RANGE" | $CLI_CMD --print-timeout 9m -p "
這是準備上線的最終 diff。請從上線風險角度審查：
1. 是否有可能導致 production 中斷的問題
2. 是否有資料遺失風險（DB / 狀態）
3. 是否有效能問題（N+1、大量資料操作）
4. 是否有安全漏洞尚未修補

格式：[風險等級] 位置：描述 → 影響
風險等級：BLOCKER / HIGH / MEDIUM / LOW
無問題輸出：「未發現上線風險」
繁體中文。"
```

**BLOCKER** → 必須修正才能上線
**HIGH** → 強烈建議修正
**MEDIUM 以下** → 記錄後可評估是否延後處理

---

## 最終輸出：上線前確認清單

```
## Deploy Prep 報告
上線範圍：[功能 / 修正]
目標環境：[staging / production]
檢查時間：[timestamp]

### ✅ 通過項目
- Code Review：通過
- 安全審查：通過
- 測試驗證：通過
- 環境設定：通過
- Git / Release：通過

### ⚠️ 注意事項
- [需要上線後監控的項目]

### 🚫 阻擋項目（BLOCKER）
- [若有，必須修正後重新確認]

agy 驗證：[通過 / 發現 N 個風險，已處理 N 個 / 未啟用]

---
結論：[✅ 可以上線 / ⚠️ 建議處理後上線 / 🚫 不建議上線]
```

---

## 分工原則

| 角色 | 負責 Phase |
|------|------|
| Orchestrator（本 skill）| 全流程控制、BLOCKER 裁決 |
| `code-review.md` | Phase 1 完整 code review |
| `security-auditor` | Phase 2 後端安全合規 |
| `frontend-security-auditor` | Phase 2 前端安全合規 |
| `owasp-reviewer` | Phase 2 合規報告（重大版本）|
| `e2e-tester` | Phase 3 關鍵 journey 驗證 |
| `version-log` | Phase 5 版本記錄 |
| `agy-assist` 模式 C | Phase 6 上線風險交叉驗證 |
