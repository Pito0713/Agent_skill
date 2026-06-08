---
name: testing-strategy
description: 為功能或專案設計測試策略。當使用者說「幫我寫測試」、「這個要怎麼測」、「test plan」時觸發。輸出測試計畫與實際測試代碼。
---

# Testing Strategy

先策略，後實作。避免為了覆蓋率寫無意義的測試。

---

## Step 1：分析被測目標

```
[ ] 這是什麼類型的程式碼？
    □ 純函式（工具/計算）→ Unit test 為主
    □ 有副作用（DB/API/外部服務）→ Integration test 為主
    □ UI 元件 → Component test + E2E
    □ API endpoint → API test + Integration

[ ] 有哪些 critical paths？（失敗代價最高的）
[ ] 有哪些 edge cases？（空值、邊界、concurrent）
[ ] 有哪些已知 bug 需要防止 regression？
```

---

## Step 2：決定測試分佈

依照 rules/testing.md 中的金字塔原則，輸出：

```
測試計畫：
- Unit tests: X 個（覆蓋：...）
- Integration tests: Y 個（覆蓋：...）
- E2E tests: Z 個（覆蓋：critical paths）

預估覆蓋率：~X%
```

---

## Step 3：輸出測試代碼

### Pure Function 模板

```ts
describe('<FunctionName>', () => {
  // Happy paths
  it('should <expected output> when <normal input>', () => {})

  // Edge cases
  it('should <handle gracefully> when <empty/null/undefined>', () => {})
  it('should <handle gracefully> when <boundary value>', () => {})

  // Error cases
  it('should throw <ErrorType> when <invalid input>', () => {})
})
```

### Service / Business Logic 模板

```ts
describe('<ServiceName>', () => {
  let service: ServiceName
  let mockDependency: MockType

  beforeEach(() => {
    mockDependency = createMock<DependencyType>()
    service = new ServiceName(mockDependency)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('<methodName>', () => {
    it('should <success case>', async () => {
      // Arrange: setup mocks
      // Act: call method
      // Assert: verify result AND verify mock calls
    })

    it('should propagate error when dependency fails', async () => {
      mockDependency.someMethod.mockRejectedValue(new Error('DB error'))
      await expect(service.method(input)).rejects.toThrow('DB error')
    })
  })
})
```

### React Component 模板

```tsx
describe('<ComponentName>', () => {
  // Render tests
  it('should render without crashing', () => {
    render(<Component {...defaultProps} />)
    expect(screen.getByRole('...')).toBeInTheDocument()
  })

  // Interaction tests
  it('should call <handler> when <action>', async () => {
    const handler = vi.fn()
    const user = userEvent.setup()
    render(<Component onAction={handler} />)
    await user.click(screen.getByRole('button', { name: '...' }))
    expect(handler).toHaveBeenCalledWith(expectedArgs)
  })

  // State tests
  it('should show <state> when <condition>', async () => {})

  // Accessibility
  it('should be accessible', async () => {
    const { container } = render(<Component {...defaultProps} />)
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
```

### API Endpoint 模板

```ts
describe('<METHOD> <path>', () => {
  describe('success cases', () => {
    it('should return 200 with <data> when <valid request>', async () => {})
  })

  describe('validation errors', () => {
    it('should return 400 when <missing required field>', async () => {})
    it('should return 400 when <invalid format>', async () => {})
  })

  describe('auth errors', () => {
    it('should return 401 when no token provided', async () => {})
    it('should return 403 when insufficient permissions', async () => {})
  })

  describe('not found', () => {
    it('should return 404 when resource does not exist', async () => {})
  })
})
```

---

## Step 4：測試工具選擇

| 場景 | 工具 |
|------|------|
| Unit/Component (TS) | Vitest + @testing-library/react |
| Unit (Python) | pytest + pytest-asyncio |
| API (TS) | Supertest / @hono/testing |
| API (Python) | httpx + pytest |
| E2E | Playwright |
| Visual regression | Playwright screenshots |
| Accessibility | axe-core / @axe-core/playwright |

---

## Step 5：CI 整合建議

```yaml
# GitHub Actions 片段
- name: Run tests
  run: |
    npm run test:ci
    npm run test:e2e

- name: Check coverage
  run: npm run test:coverage -- --reporter=json
  
- name: Coverage threshold check
  run: |
    coverage=$(cat coverage/coverage-summary.json | jq '.total.lines.pct')
    if (( $(echo "$coverage < 70" | bc -l) )); then
      echo "Coverage $coverage% is below 70% threshold"
      exit 1
    fi
```
