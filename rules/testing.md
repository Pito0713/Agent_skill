# Testing Rules

> 測試規範。目標：有意義的覆蓋率，而非追求數字。

---

## 測試策略

採用**測試金字塔**：

```
       /\
      /E2E\        少量（5-10%）：關鍵 user journey
     /------\
    / Integ  \     適量（20-30%）：API、DB、服務整合
   /----------\
  /    Unit    \   大量（60-70%）：業務邏輯、工具函式
 /--------------\
```

---

## 覆蓋率基準

| 類型 | 最低覆蓋率 |
|------|------------|
| 業務邏輯（services/utils） | 80% |
| API routes / handlers | 70% |
| UI 元件 | 60%（關鍵互動） |
| 整體 | 70% |

覆蓋率是工具，不是目標。不為了湊數字寫沒意義的測試。

---

## 命名規範

```ts
// 格式：should [expected behaviour] when [condition]
describe('UserService', () => {
  describe('createUser', () => {
    it('should create user when valid data provided', async () => {})
    it('should throw ValidationError when email is invalid', async () => {})
    it('should throw ConflictError when email already exists', async () => {})
  })
})
```

---

## Unit Tests（Vitest / Jest）

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ✅ AAA 模式：Arrange → Act → Assert
describe('calculateDiscount', () => {
  it('should apply 20% discount when user is premium', () => {
    // Arrange
    const price = 100
    const user: User = { id: '1', tier: 'premium' }

    // Act
    const result = calculateDiscount(price, user)

    // Assert
    expect(result).toBe(80)
  })

  it('should return original price when user is free tier', () => {
    const price = 100
    const user: User = { id: '1', tier: 'free' }
    expect(calculateDiscount(price, user)).toBe(100)
  })
})
```

### Mock 規範

```ts
// ✅ Mock 外部依賴，不 mock 被測邏輯本身
vi.mock('@/lib/db', () => ({
  db: {
    user: {
      findUnique: vi.fn(),
      create: vi.fn(),
    },
  },
}))

beforeEach(() => {
  vi.clearAllMocks()  // 每次測試前重置
})

it('should return null when user not found', async () => {
  vi.mocked(db.user.findUnique).mockResolvedValue(null)
  const result = await userService.getUser('non-existent')
  expect(result).toBeNull()
})
```

---

## Integration Tests

```ts
// ✅ 使用真實 DB（test container 或 in-memory）
import { createTestDatabase } from '@/test/helpers/db'

describe('UserRepository', () => {
  let db: TestDatabase

  beforeAll(async () => {
    db = await createTestDatabase()
  })

  afterAll(async () => {
    await db.cleanup()
  })

  afterEach(async () => {
    await db.reset()  // 每次測試後清空資料
  })

  it('should persist user to database', async () => {
    const repo = new UserRepository(db.client)
    const created = await repo.create({ name: 'Alice', email: 'alice@example.com' })

    expect(created.id).toBeDefined()
    expect(created.name).toBe('Alice')

    const fetched = await repo.findById(created.id)
    expect(fetched).toEqual(created)
  })
})
```

---

## API Tests（Supertest / httpx）

```ts
// TypeScript + Supertest
import request from 'supertest'
import app from '@/app'

describe('POST /api/users', () => {
  it('should return 201 with created user', async () => {
    const response = await request(app)
      .post('/api/users')
      .send({ name: 'Alice', email: 'alice@example.com' })
      .set('Authorization', `Bearer ${testToken}`)
      .expect(201)

    expect(response.body).toMatchObject({
      name: 'Alice',
      email: 'alice@example.com',
    })
    expect(response.body.id).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('should return 400 when email is invalid', async () => {
    await request(app)
      .post('/api/users')
      .send({ name: 'Alice', email: 'not-an-email' })
      .expect(400)
  })
})
```

---

## React 元件 Tests

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

describe('LoginForm', () => {
  it('should call onSubmit with credentials when form is submitted', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()

    render(<LoginForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('Email'), 'alice@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        email: 'alice@example.com',
        password: 'password123',
      })
    })
  })

  it('should show error message when email is empty', async () => {
    const user = userEvent.setup()
    render(<LoginForm onSubmit={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Login' }))

    expect(screen.getByText('Email is required')).toBeInTheDocument()
  })
})
```

---

## TDD 模式

新功能或 bug fix 優先採用 TDD：

1. 寫一個失敗的測試（Red）
2. 寫最少的程式碼讓測試通過（Green）
3. 重構（Refactor）

---

## 禁止事項

- 測試之間有依賴（順序影響結果）：禁止
- 測試中 sleep/wait 固定時間：禁止，用 `waitFor` / `eventually`
- 測試生產環境 API：禁止，使用 mock 或 test 環境
- snapshot test 用於動態資料：禁止
