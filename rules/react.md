# React Rules

> 適用所有 React 專案。預設 TypeScript + functional components。

---

## 元件設計原則

- 只使用 **functional components**，禁止 class components
- 每個元件單一職責，props 超過 5 個要考慮拆分
- 元件命名 PascalCase，檔名與元件名一致
- 每個檔案只 export 一個主要元件

---

## Props 型別

```tsx
// ✅ 使用 interface，不用 React.FC
interface ButtonProps {
  label: string
  onClick: () => void
  variant?: 'primary' | 'secondary' | 'ghost'
  disabled?: boolean
  children?: React.ReactNode
}

export function Button({ label, onClick, variant = 'primary', disabled = false }: ButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={styles[variant]}
    >
      {label}
    </button>
  )
}
```

---

## Hooks 規範

### 自訂 Hook

- 命名以 `use` 開頭
- 只在元件頂層呼叫，不在條件/迴圈內呼叫
- 分離 UI 邏輯與副作用

```ts
// ✅ 封裝 fetch 邏輯
function useUser(userId: string) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)

    fetchUser(userId)
      .then(data => { if (!cancelled) setUser(data) })
      .catch(err => { if (!cancelled) setError(err) })
      .finally(() => { if (!cancelled) setIsLoading(false) })

    return () => { cancelled = true }
  }, [userId])

  return { user, isLoading, error }
}
```

### useEffect 規範

```tsx
// ❌ 缺少 cleanup，可能造成 memory leak
useEffect(() => {
  fetchData().then(setData)
}, [id])

// ✅ 有 cleanup flag
useEffect(() => {
  let cancelled = false
  fetchData(id).then(data => {
    if (!cancelled) setData(data)
  })
  return () => { cancelled = true }
}, [id])
```

---

## 狀態管理

| 狀態類型 | 建議方案 |
|----------|----------|
| 本地 UI 狀態 | `useState` |
| 複雜本地邏輯 | `useReducer` |
| 跨元件共享 | `Context` + `useReducer` |
| Server 狀態 | TanStack Query / SWR |
| 全域 Client 狀態 | Zustand（輕量）|

- 禁止在 Context 中存放高頻更新的狀態（效能問題）
- Server 狀態不使用 `useState` 手動管理，一律用 TanStack Query

---

## 效能優化

只在有效能問題時才做優化，不過早優化。

```tsx
// memo：只在 profiling 後確認有 re-render 問題時使用
const ExpensiveList = React.memo(function ExpensiveList({ items }: { items: Item[] }) {
  return <>{items.map(item => <Item key={item.id} {...item} />)}</>
})

// useCallback：只在 callback 作為 memo 元件的 prop 時使用
const handleSubmit = useCallback(() => {
  onSubmit(formData)
}, [formData, onSubmit])

// useMemo：只在計算確實昂貴時使用
const sortedItems = useMemo(() =>
  [...items].sort((a, b) => b.score - a.score),
  [items]
)
```

---

## 條件渲染

```tsx
// ❌ 容易出現 0 渲染問題
{count && <Component />}

// ✅ 明確 boolean
{count > 0 && <Component />}

// ✅ 三元（短）
{isLoading ? <Spinner /> : <Content />}

// ✅ 獨立變數（長）
const content = (() => {
  if (isLoading) return <Spinner />
  if (error) return <ErrorMessage error={error} />
  return <Content data={data} />
})()
```

---

## 錯誤邊界

每個 route/page 層級必須有 Error Boundary：

```tsx
// 使用 react-error-boundary
import { ErrorBoundary } from 'react-error-boundary'

function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try again</button>
    </div>
  )
}

// 使用
<ErrorBoundary FallbackComponent={ErrorFallback} onReset={reset}>
  <FeatureComponent />
</ErrorBoundary>
```

---

## 禁止事項

- `React.FC`：禁止（不自動推斷 generic，且含隱式 children）
- index 作為 key：禁止（除非列表永不重排）
- 直接 mutate state：禁止
- `dangerouslySetInnerHTML`：禁止，除非 sanitize 後並加 comment
