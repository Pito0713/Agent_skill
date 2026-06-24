# 錯誤處理最佳實踐

## 不得吞錯誤

catch 內必須有處理邏輯或 re-throw，空 catch 是嚴重反模式。

```ts
// ❌ 吞掉錯誤，問題消失但不解決
try {
  await saveUser(user)
} catch (e) {}

// ✅ 記錄後 re-throw
try {
  await saveUser(user)
} catch (error) {
  logger.error('saveUser failed', { userId: user.id, error })
  throw new DatabaseError('Failed to save user', { cause: error })
}
```

## 錯誤分層

| 層級 | 類型 | 範例 |
|------|------|------|
| Domain Error | 業務規則違反 | `InsufficientFundsError`, `UserAlreadyExistsError` |
| Infrastructure Error | 外部系統失敗 | `DatabaseError`, `NetworkTimeoutError` |
| Application Error | 請求格式問題 | `ValidationError`, `AuthenticationError` |

每層只處理自己職責內的錯誤，跨層拋出時要包裝（wrap）：

```ts
// Repository 層
async function findUser(id: string): Promise<User> {
  try {
    return await db.query('SELECT * FROM users WHERE id = $1', [id])
  } catch (error) {
    throw new DatabaseError('findUser failed', { cause: error })  // 包裝，不洩漏 DB 細節
  }
}

// Service 層
async function getUser(id: string): Promise<User> {
  const user = await findUser(id)  // DatabaseError 向上傳遞
  if (!user) throw new UserNotFoundError(id)  // Domain error
  return user
}
```

## async/await 規範

統一使用 `try/catch`，不混用 `.catch()`，避免錯誤處理邏輯分散。

```ts
// ❌ 混用
async function process() {
  const data = await fetchData().catch(e => null)  // 吞掉了
  try {
    await saveData(data)
  } catch (e) {
    throw e
  }
}

// ✅ 統一 try/catch
async function process() {
  try {
    const data = await fetchData()
    await saveData(data)
  } catch (error) {
    if (error instanceof NetworkError) {
      throw new ServiceUnavailableError('fetch failed', { cause: error })
    }
    throw error
  }
}
```
