# API 設計常見模式

## REST 命名規範

資源名稱使用複數名詞，動詞由 HTTP method 表達。

```
✅ GET    /users          列出所有使用者
✅ GET    /users/:id      取得單一使用者
✅ POST   /users          建立使用者
✅ PATCH  /users/:id      更新部分欄位
✅ DELETE /users/:id      刪除使用者

❌ GET  /getUser
❌ POST /createUser
❌ GET  /user（單數）
```

巢狀資源只允許一層：`/users/:id/posts`，不做 `/users/:id/posts/:id/comments`。

## 分頁模式

### Cursor-based（推薦）

適合大資料集、即時資料，不會因為插入導致「跳頁」。

```ts
// Request
GET /posts?cursor=eyJpZCI6MTAwfQ&limit=20

// Response
{
  "data": [...],
  "nextCursor": "eyJpZCI6MTIwfQ",
  "hasMore": true
}
```

### Offset-based

適合小資料集、需要跳頁的情境（如後台報表）。

```ts
// Request
GET /posts?page=3&pageSize=20

// Response
{
  "data": [...],
  "total": 500,
  "page": 3,
  "pageSize": 20
}
```

## 錯誤回傳格式

統一使用以下結構，HTTP status code 要正確對應：

```json
{
  "error": "RESOURCE_NOT_FOUND",
  "code": 404,
  "message": "User with id 123 does not exist",
  "details": {}
}
```

| HTTP Status | 使用時機 |
|-------------|---------|
| 400 | 參數格式錯誤、業務規則違反 |
| 401 | 未登入或 token 無效 |
| 403 | 已登入但無權限 |
| 404 | 資源不存在 |
| 409 | 衝突（如 email 已存在） |
| 422 | 參數格式正確但語意錯誤 |
| 500 | 伺服器內部錯誤（不要洩漏 stack trace） |
