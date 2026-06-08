# Git Rules

> Git workflow 規範。確保歷史可讀、PR 可審查、rollback 可靠。

---

## Branch 命名

```
<type>/<ticket-id>-<short-description>

feat/CC-123-user-authentication
fix/CC-456-login-redirect-loop
chore/CC-789-upgrade-dependencies
refactor/CC-101-extract-auth-middleware
docs/CC-202-update-api-readme
```

| 類型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修復 |
| `chore` | 維護、工具、設定 |
| `refactor` | 重構（不改行為） |
| `docs` | 文件更新 |
| `test` | 測試新增/修改 |
| `perf` | 效能優化 |

---

## Commit Message（Conventional Commits）

```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

### 規則

- subject 使用**現在式**（不是 "added"，是 "add"）
- subject 不超過 72 字元
- 不加句號
- Breaking change 加 `!` 或在 footer 寫 `BREAKING CHANGE:`

### 範例

```
feat(auth): add JWT refresh token rotation

Implements sliding window refresh token strategy.
Old tokens are invalidated on use to prevent replay attacks.

Closes #123

---

fix(api): handle null user in profile endpoint

Previously threw 500 when user had no profile record.
Now returns 404 with descriptive error message.

---

refactor(db)!: rename users table to accounts

BREAKING CHANGE: database migration required before deployment.
Run: npm run db:migrate

---

chore(deps): upgrade Next.js to 15.3.0
```

---

## PR 規範

### PR 大小

| 大小 | 檔案數 | 建議 |
|------|--------|------|
| ✅ 小 | < 10 | 理想 |
| ⚠️ 中 | 10-20 | 可接受，拆分邏輯清楚 |
| ❌ 大 | > 20 | 必須拆分 |

### PR Description 模板

```markdown
## 什麼變動

簡短說明這個 PR 做了什麼。

## 為什麼

背景說明、解決什麼問題、票號連結。

## 怎麼測試

1. 步驟 1
2. 步驟 2
3. 預期結果

## Screenshot（如有 UI 變動）

## Checklist

- [ ] 有對應的測試
- [ ] 文件已更新（如有需要）
- [ ] 無 console.log
- [ ] 無 hardcoded secrets
```

---

## Merge 策略

- `main` / `production`：禁止直接 push，必須 PR + review
- 使用 **Squash and Merge**（feature branch → main）
- Hotfix 使用 **Merge Commit** 保留歷史

---

## Commit 習慣

### 原子性 commit

每個 commit 只做一件事，讓 `git bisect` 有效：

```bash
# ❌ 一個 commit 做太多
git commit -m "fix login, add tests, update readme, refactor auth"

# ✅ 分開 commit
git commit -m "fix(auth): handle expired session on login"
git commit -m "test(auth): add cases for expired session"
git commit -m "docs: update auth flow in readme"
```

### 本地 rebase 整理

```bash
# 推送前整理 commit 歷史
git rebase -i HEAD~5

# 常用操作：
# pick   保留
# squash 合併到前一個
# reword 修改 message
# drop   刪除
```

---

## .gitignore 必含項目

```gitignore
# Secrets
.env
.env.local
.env.*.local
*.pem
*.key

# 依賴
node_modules/
__pycache__/
.venv/
*.egg-info/

# 建置產物
.next/
dist/
build/
*.pyc

# IDE
.vscode/settings.json
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# 測試
coverage/
.pytest_cache/
```

---

## 禁止事項

- force push 到共用 branch（`main`、`develop`）：禁止
- commit 未測試的 broken code：禁止
- 空 commit message 或 "fix"、"wip"、"asdf"：禁止
- 大型 binary 檔案進 repo（> 10MB）：使用 Git LFS
