# Security Rules

> 安全規範，所有任務均適用，優先度最高。OWASP Top 10 為基準。

---

## Secrets 管理

### 絕對禁止

```ts
// ❌ hardcode secrets
const apiKey = 'sk-proj-abc123...'
const dbUrl = 'postgresql://user:password@localhost/db'

// ❌ 放入 git（即使是 .env 檔）
```

### 正確做法

```ts
// ✅ 從環境變數讀取，並做 runtime validation
const apiKey = process.env.OPENAI_API_KEY
if (!apiKey) throw new Error('OPENAI_API_KEY is required')
```

- `.env` 進 `.gitignore`
- 使用 `.env.example`（不含真實值）作為文件
- CI/CD secrets 使用 GitHub Secrets / Vault

---

## 輸入驗證（Injection 防禦）

所有外部輸入視為不可信任：

```ts
// ❌ SQL Injection
const query = `SELECT * FROM users WHERE id = ${userId}`

// ✅ Parameterized query
const user = await db.query('SELECT * FROM users WHERE id = $1', [userId])

// ✅ ORM（Prisma / SQLAlchemy 自動處理）
const user = await prisma.user.findUnique({ where: { id: userId } })
```

```ts
// ❌ XSS
element.innerHTML = userInput

// ✅ 使用 textContent 或 sanitize
element.textContent = userInput
// 或
import DOMPurify from 'dompurify'
element.innerHTML = DOMPurify.sanitize(userInput)
```

---

## 認證與授權

### 認證

```ts
// ✅ JWT 驗證範例
import { verify } from 'jsonwebtoken'

function verifyToken(token: string): JWTPayload {
  try {
    return verify(token, process.env.JWT_SECRET!) as JWTPayload
  } catch {
    throw new UnauthorizedError('Invalid or expired token')
  }
}
```

- 密碼必須使用 bcrypt / argon2 hash（最低 cost factor 12）
- JWT 有效期最長 24h，refresh token 最長 30d
- 禁止在 URL 中傳遞 token

### 授權（RBAC 模式）

```ts
// ✅ 每個 API route 明確檢查權限
async function deletePost(req: Request, postId: string) {
  const user = await getAuthenticatedUser(req)      // 1. 認證
  const post = await getPost(postId)
  if (!post) throw new NotFoundError()
  if (post.authorId !== user.id && user.role !== 'admin') {
    throw new ForbiddenError('Not authorized to delete this post')  // 2. 授權
  }
  await deletePost(postId)
}
```

---

## CSRF 防護

```ts
// Next.js Server Actions 內建 CSRF 防護
// API Routes 需要手動實作

// ✅ Double Submit Cookie 模式
import csrf from 'csrf'
const tokens = new csrf()

// 生成 token
const secret = await tokens.secret()
const token = tokens.create(secret)

// 驗證
if (!tokens.verify(secret, req.headers['x-csrf-token'])) {
  throw new ForbiddenError('CSRF validation failed')
}
```

---

## Rate Limiting

所有公開 API endpoint 必須有 rate limit：

```ts
// ✅ 使用 @upstash/ratelimit（Edge 環境）
import { Ratelimit } from '@upstash/ratelimit'
import { Redis } from '@upstash/redis'

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, '10 s'),  // 10 requests per 10s
})

const { success, limit, reset } = await ratelimit.limit(ip)
if (!success) {
  return Response.json(
    { error: 'Too many requests' },
    { status: 429, headers: { 'Retry-After': String(reset) } }
  )
}
```

---

## HTTP Security Headers

```ts
// next.config.ts
const securityHeaders = [
  { key: 'X-DNS-Prefetch-Control', value: 'on' },
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'origin-when-cross-origin' },
  { key: 'Content-Security-Policy', value: cspHeader },
]
```

---

## 依賴安全

```bash
# 定期執行
npm audit
pip-audit  # Python
```

- 依賴更新頻率：安全漏洞 24h 內，一般 monthly
- 使用 Dependabot 或 Renovate 自動化更新

---

## 敏感資料處理

- 禁止 log 密碼、token、信用卡號、身分證號
- PII 資料（email、電話）在 log 中遮罩
- 資料庫密碼欄位必須 hash 儲存
- 傳輸中使用 TLS 1.2+

```ts
// ✅ Log 遮罩範例
logger.info('User login attempt', {
  email: maskEmail(user.email),  // user***@example.com
  ip: req.ip,
  // 禁止 log: password, token, secret
})
```

---

## 安全審查 Checklist

PR 合併前確認：
- [ ] 無 hardcoded secrets
- [ ] 所有外部輸入有驗證
- [ ] 所有 DB query 使用 parameterized
- [ ] 認證/授權邏輯正確
- [ ] 依賴無已知 CVE
- [ ] 錯誤訊息不洩漏 stack trace 到 client
