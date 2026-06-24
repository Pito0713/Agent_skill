# Git 規範與 Commit 格式

## Commit 格式

遵循 Conventional Commits 規範：

```
type(scope): subject

[body]

[footer]
```

### type 列表

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修復 bug |
| `refactor` | 重構（不改行為） |
| `chore` | 工具、設定、依賴更新 |
| `docs` | 文件更新 |
| `test` | 測試新增或修改 |
| `perf` | 效能優化 |
| `ci` | CI/CD 流程修改 |

### 範例

```
feat(auth): add OAuth2 Google login
fix(cart): prevent duplicate item on rapid click
refactor(user): extract address validation to separate module
chore: upgrade typescript to 5.4
```

### 禁止事項

```
❌ fix bug          → 太模糊
❌ WIP              → 不應進 main
❌ 修改了一些東西    → 無資訊
❌ 超過 72 字的 subject line
```

## Branch 命名

```
feature/<ticket-id>-<short-description>
fix/<ticket-id>-<short-description>
chore/<description>
hotfix/<description>
```

範例：
```
feature/AUTH-123-google-oauth
fix/CART-456-duplicate-item
chore/upgrade-deps-q2
hotfix/payment-null-pointer
```

## PR 規範

- **title**：遵循 commit 格式，上限 70 字
- **body**：必須包含以下三個區塊

```markdown
## Summary
- 這個 PR 做了什麼（1-3 bullet points）

## Test Plan
- [ ] 手動測試：XXX 流程
- [ ] 單元測試：新增 X 個 test cases
- [ ] 確認無 regression

## Related Issues
Closes #123
```

- 每個 PR 只做一件事，避免 scope creep
- Draft PR 用於 WIP，不得 merge 直到標記為 Ready
- 至少一個 reviewer approve 後才能 merge
