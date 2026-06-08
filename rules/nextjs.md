# Next.js Rules

> 適用 Next.js 13+ App Router 專案。預設 TypeScript + Server Components。

---

## Server vs Client Components

**預設使用 Server Components**，只在需要時改為 Client。

| 需要 Client Component 的情境 |
|-------------------------------|
| `useState` / `useReducer` |
| `useEffect` / lifecycle |
| 瀏覽器 API（window、document） |
| Event handlers（onClick 等） |
| Custom hooks 使用上述功能 |

```tsx
// ✅ Server Component（預設，不需標注）
// app/users/page.tsx
async function UsersPage() {
  const users = await db.user.findMany()  // 直接存取 DB
  return <UserList users={users} />
}

// ✅ Client Component（明確標注）
'use client'
// components/SearchInput.tsx
export function SearchInput({ onSearch }: { onSearch: (q: string) => void }) {
  const [query, setQuery] = useState('')
  // ...
}
```

---

## 目錄結構（App Router）

```
app/
├── (auth)/               # route group，不影響 URL
│   ├── login/page.tsx
│   └── register/page.tsx
├── (dashboard)/
│   ├── layout.tsx        # 共用 layout
│   ├── page.tsx          # / 首頁
│   └── users/
│       ├── page.tsx      # /users
│       └── [id]/
│           └── page.tsx  # /users/:id
├── api/
│   └── users/
│       └── route.ts      # API Route Handler
├── globals.css
└── layout.tsx            # Root layout

components/
├── ui/                   # 無狀態 UI 元件
├── features/             # 業務功能元件
└── providers/            # Context providers

lib/
├── db.ts                 # DB client
├── auth.ts               # Auth utilities
└── utils.ts

types/
└── index.ts              # 共用型別
```

---

## Data Fetching

### Server Component 直接 fetch

```tsx
// ✅ async Server Component
async function ProductPage({ params }: { params: { id: string } }) {
  const product = await getProduct(params.id)

  if (!product) notFound()

  return <ProductDetail product={product} />
}
```

### 平行 fetch

```tsx
// ✅ Promise.all 平行執行
async function DashboardPage() {
  const [user, posts, stats] = await Promise.all([
    getUser(),
    getPosts(),
    getStats(),
  ])

  return <Dashboard user={user} posts={posts} stats={stats} />
}
```

### Client-side fetch

```tsx
// ✅ 使用 TanStack Query
'use client'
function PostList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['posts'],
    queryFn: () => fetch('/api/posts').then(r => r.json()),
  })
  // ...
}
```

---

## Server Actions

```tsx
// ✅ 在 Server Component 或獨立檔案定義
'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'

export async function createPost(formData: FormData) {
  const title = formData.get('title') as string

  // 1. Validate
  if (!title || title.length < 3) {
    return { error: 'Title too short' }
  }

  // 2. Execute
  const post = await db.post.create({ data: { title } })

  // 3. Revalidate & redirect
  revalidatePath('/posts')
  redirect(`/posts/${post.id}`)
}
```

---

## Metadata

每個 page 必須有 metadata：

```tsx
// 靜態
export const metadata: Metadata = {
  title: 'Page Title',
  description: 'Page description',
}

// 動態
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const post = await getPost(params.id)
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: { images: [post.coverImage] },
  }
}
```

---

## 錯誤處理

```
app/
├── error.tsx          # route-level error boundary（Client Component）
├── not-found.tsx      # 404 頁面
└── loading.tsx        # Suspense loading UI
```

```tsx
// error.tsx
'use client'
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div>
      <h2>Something went wrong</h2>
      <button onClick={reset}>Try again</button>
    </div>
  )
}
```

---

## 環境變數

```ts
// ✅ 使用 @t3-oss/env-nextjs 做 runtime validation
import { createEnv } from '@t3-oss/env-nextjs'
import { z } from 'zod'

export const env = createEnv({
  server: {
    DATABASE_URL: z.string().url(),
    NEXTAUTH_SECRET: z.string().min(32),
  },
  client: {
    NEXT_PUBLIC_API_URL: z.string().url(),
  },
  runtimeEnv: {
    DATABASE_URL: process.env.DATABASE_URL,
    NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
})
```

---

## 禁止事項

- `pages/` 目錄：禁止在 App Router 專案混用
- `getServerSideProps` / `getStaticProps`：App Router 不適用
- Client Component 中直接存取 DB：禁止
- `NEXT_PUBLIC_` 前綴的 secret：禁止（會暴露到 client）
