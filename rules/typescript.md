# TypeScript Rules

> 適用所有 TypeScript 專案。strict 模式為預設，不得降級。

---

## tsconfig 基準

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

---

## 型別定義

### 禁止 any

```ts
// ❌
function parse(data: any): any {}

// ✅ 使用 unknown + type guard
function parse(data: unknown): ParsedData {
  if (!isValidData(data)) throw new TypeError('Invalid data shape')
  return data as ParsedData
}
```

### 優先 interface，需要 union/intersection 才用 type

```ts
// ✅ interface for objects
interface User {
  id: string
  name: string
  role: UserRole
}

// ✅ type for unions / computed
type UserRole = 'admin' | 'editor' | 'viewer'
type ApiResponse<T> = { data: T; error: null } | { data: null; error: ApiError }
```

### 明確 return type

```ts
// ❌
async function fetchUser(id: string) {
  return db.user.findUnique({ where: { id } })
}

// ✅
async function fetchUser(id: string): Promise<User | null> {
  return db.user.findUnique({ where: { id } })
}
```

---

## Null / Undefined 處理

- 使用 optional chaining `?.` 與 nullish coalescing `??`
- 禁止非空斷言 `!`，除非有 invariant comment 說明
- 函式參數使用 `T | null`（明確意圖）而非 `T?`

```ts
// ❌
const name = user!.profile!.name

// ✅
const name = user?.profile?.name ?? 'Anonymous'
```

---

## Enum 替代方案

禁止使用 `enum`（編譯結果不直觀），改用 const object：

```ts
// ❌
enum Status { Active, Inactive }

// ✅
const Status = {
  Active: 'active',
  Inactive: 'inactive',
} as const
type Status = typeof Status[keyof typeof Status]
```

---

## 泛型

- 泛型名稱有意義：`TData`、`TError`、`TInput` 優於 `T`、`U`
- 使用 `extends` 約束泛型

```ts
// ❌
function merge<T, U>(a: T, b: U) {}

// ✅
function merge<TBase extends object, TOverride extends Partial<TBase>>(
  base: TBase,
  override: TOverride
): TBase & TOverride {}
```

---

## 工具型別

優先使用內建 utility types：

```ts
Partial<T>        // 所有欄位可選
Required<T>       // 所有欄位必填
Readonly<T>       // 不可變
Pick<T, K>        // 挑選欄位
Omit<T, K>        // 排除欄位
Record<K, V>      // key-value map
ReturnType<F>     // 函式回傳型別
Parameters<F>     // 函式參數型別
```

---

## Zod 整合（runtime validation）

所有外部輸入（API response、env、user input）必須過 Zod schema：

```ts
import { z } from 'zod'

const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  role: z.enum(['admin', 'editor', 'viewer']),
})

type User = z.infer<typeof UserSchema>

// 使用
const user = UserSchema.parse(rawData) // 失敗時 throw
const result = UserSchema.safeParse(rawData) // 失敗時 result.success === false
```

---

## 禁止事項

- `@ts-ignore`：禁止，改用 `@ts-expect-error` 並說明原因
- `as unknown as T`：禁止（型別洗白）
- `Function` 型別：禁止，使用具體簽名
- `Object`（大寫）：禁止，使用 `object` 或具體 interface
