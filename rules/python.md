# Python Rules

> 適用所有 Python 專案。預設 Python 3.11+，強制 type hints。

---

## 工具鏈

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "UP", "ANN", "S", "B", "C4", "RET", "SIM"]
ignore = ["ANN101", "ANN102"]

[tool.ruff.per-file-ignores]
"tests/**" = ["S101", "ANN"]  # 允許 assert，不強制測試函式型別

[tool.mypy]
strict = true
python_version = "3.11"
```

執行順序：`ruff check` → `ruff format` → `mypy`

---

## 型別標注

所有函式必須有完整型別標注：

```python
# ❌
def get_user(user_id):
    return db.query(user_id)

# ✅
from typing import Optional
from uuid import UUID

async def get_user(user_id: UUID) -> Optional[User]:
    return await db.query(User, user_id)
```

### 常用型別工具

```python
from typing import (
    Optional,      # Optional[T] = T | None
    Union,         # Union[A, B] = A | B（Python 3.10+ 可用 A | B）
    Sequence,      # 只讀序列
    Mapping,       # 只讀 dict-like
    TypeVar,       # 泛型
    TypedDict,     # dict 型別定義
    Protocol,      # 結構性子型別（duck typing）
    Annotated,     # 加 metadata（配合 Pydantic）
    Final,         # 不可重新賦值的常數
    ClassVar,      # class 變數
    overload,      # function overload
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .models import User  # 避免循環 import
```

---

## 資料驗證：Pydantic

所有外部輸入（API、env、config）使用 Pydantic v2：

```python
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r'^[\w.+-]+@[\w-]+\.[a-z]{2,}$')
    age: int = Field(ge=0, le=150)

    @field_validator('name')
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if v.strip() == '':
            raise ValueError('name cannot be blank')
        return v.strip()

class Settings(BaseSettings):
    database_url: str
    secret_key: str = Field(min_length=32)
    debug: bool = False

    model_config = {'env_file': '.env'}
```

---

## 非同步（async/await）

```python
# ✅ 平行執行
import asyncio

async def fetch_dashboard_data(user_id: UUID) -> DashboardData:
    user, posts, stats = await asyncio.gather(
        get_user(user_id),
        get_user_posts(user_id),
        get_user_stats(user_id),
    )
    return DashboardData(user=user, posts=posts, stats=stats)
```

- 禁止在 async 函式中呼叫 blocking I/O（用 `asyncio.run_in_executor` 包裝）
- 使用 `asynccontextmanager` 管理 async 資源

---

## 錯誤處理

```python
# ✅ 具體的 Exception 類別
class UserNotFoundError(Exception):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id

# ✅ 只 catch 預期的錯誤
try:
    user = await get_user(user_id)
except UserNotFoundError:
    raise HTTPException(status_code=404, detail="User not found")
except DatabaseError as e:
    logger.error("DB error fetching user", extra={"user_id": str(user_id), "error": str(e)})
    raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 專案結構（FastAPI）

```
src/
├── main.py               # FastAPI app 入口
├── config.py             # Settings（pydantic-settings）
├── dependencies.py       # FastAPI dependencies
├── routers/
│   ├── users.py
│   └── posts.py
├── services/             # 業務邏輯層
│   ├── user_service.py
│   └── post_service.py
├── repositories/         # 資料存取層
│   └── user_repository.py
├── models/               # ORM models（SQLAlchemy）
│   └── user.py
├── schemas/              # Pydantic schemas
│   └── user.py
└── utils/
    └── logger.py

tests/
├── conftest.py
├── unit/
└── integration/
```

---

## 禁止事項

- 裸 `except:`：禁止，至少 `except Exception:`
- `print()`：禁止進 production，使用 `structlog` 或 `logging`
- mutable default 參數：禁止（`def f(items=[])`）
- 直接 `import *`：禁止
- 未使用的 `type: ignore`：需加說明
