# Auth & Identity 模块

> 认证与身份。JWT、本地账号、权限检查——PeerPedia 最分裂的横切关注点。

## 一句话职责

**搞清楚"你是谁"和"你能做什么"。** 两层系统（本地 + 服务器），两个 ID 空间，三种认证模式。

## C3: Auth 组件依赖

```
   用户 "alice"
        │
        ├── Tauri 桌面 ──────────────┐
        │                            │
        ▼                            ▼
   ┌──────────────┐          ┌──────────────┐
   │ local_auth   │          │ deps.py +    │
   │   .rs        │          │ auth.py      │
   │              │          │              │
   │ bcrypt 本地  │          │ JWT HS256    │
   │ UUID session │          │ 24h 过期     │
   └──────┬───────┘          └──────┬───────┘
          │                         │
          ▼                         ▼
   ┌──────────────┐          ┌──────────────┐
   │local_accounts│          │   users 表   │
   │sessions 表   │          │(服务器 SQLite)│
   │(本地 SQLite) │          └──────────────┘
   └──────────────┘
          │                         │
          │ 本地 UUID: aaaa-bbbb    │ 服务器 UUID: xxxx-yyyy
          │                         │
          └───────────┬─────────────┘
                      │ 两端 ID 不同！
                      │
                      ▼
            ┌──────────────────────┐
            │  useUserStore.ts     │  ← 桥接层
            │                      │
            │ trySyncServerAuth()  │  用本地凭据在服务器注册/登录
            │   ↓                  │
            │ 服务器不存在 → POST  │
            │  /auth/register      │
            │ 服务器存在   → POST  │
            │  /auth/login         │
            │   ↓                  │
            │ 保存服务器 JWT+UUID  │  前端用服务器 UUID 调 API
            │                      │
            │ 问题：Git commit 里  │
            │ 还是本地 UUID        │  commit email = aaaa@peerpedia
            │ rebuild_article_     │  email.split("@")[0] → aaaa
            │ authors 用 email     │  但服务器 users 里是 xxxx
            │ 前缀匹配 user_id     │  → 匹配不上 → 作者关联断裂
            └──────────────────────┘
```

箭头约定：`A ──► B` = A 依赖 B。

- **两套认证系统各自独立**——local_auth 和 deps.py 互不知道对方存在
- **useUserStore 是唯一桥接点**——负责将本地凭据映射到服务器 JWT
- **桥接只解决了前端 API 调用**——Git commit email 仍然是本地 UUID，服务器端 rebuild_article_authors 用 `email.split("@")[0]` 匹配 user_id 时会断裂

## 认证模式对比

| 模式 | 运行环境 | 用户标识 | 认证方式 | 存储 |
|------|----------|----------|----------|------|
| 服务器 JWT | Web 版本 | Server UUID | bcrypt + HS256 JWT | 服务器 SQLite |
| Tauri 本地 | 桌面端 | Local UUID | bcrypt + UUID session | 本地 SQLite |
| 浏览器本地 | 开发模式 | Local UUID | mock（无 bcrypt） | localStorage |

## 服务器认证（FastAPI）

### 注册流程

```
POST /api/v1/auth/register
  { username, password, email, name }
    ↓
  deps.hash_password(password)  →  bcrypt, cost=12
    ↓
  crud_user.create_user(...)    →  insert into users
    ↓
  deps.create_token(user.id)    →  HS256 JWT, 24h expiry
    ↓
  AuthResponse { user: UserProfile, token: "eyJ..." }
```

### 登录流程

```
POST /api/v1/auth/login
  { username, password }
    ↓
  crud_user.get_user_by_username(username)
    ↓
  deps.verify_password(password, user.password_hash)
    ↓
  deps.create_token(user.id)
    ↓
  AuthResponse { user, token }
```

### JWT 结构

```json
{
  "sub": "user-uuid",
  "iat": 1718500000,
  "exp": 1718586400
}
```

- 算法：HS256
- 密钥：`JWT_SECRET` 环境变量，默认 `"peerpedia-dev-secret"`
- 过期：24 小时

## 本地认证（Tauri Rust）

### 注册流程

```
invoke('create_account', { username, password, email, name })
    ↓
  local_auth::create_account()
    → bcrypt::hash(password, 12)
    → uuid::Uuid::new_v4() → account.id
    → INSERT INTO local_accounts
    → uuid::Uuid::new_v4() → session_token
    → INSERT INTO sessions
    ↓
  AccountWithToken { id, username, token, email, name }
```

### 登录流程

```
invoke('login', { username, password })
    ↓
  SELECT * FROM local_accounts WHERE username = ?
    ↓
  bcrypt::verify(password, stored_hash)
    ↓
  生成新 session token → INSERT INTO sessions
    ↓
  AccountWithToken
```

## 双 ID 问题

**这是 PeerPedia 最大的架构隐患。** 同一个用户在两端有不同的 ID：

```
用户 "alice" 在 Tauri 上注册
  → local UUID: "aaaa-bbbb-cccc-dddd"
  → 本地所有操作（commit、draft、bookmark）用这个 ID

同一用户 "alice" 在服务器上注册
  → server UUID: "xxxx-yyyy-zzzz-wwww"
  → 服务器所有操作用这个 ID

问题：
  "alice" 离线写了一篇文章，author = "aaaa-bbbb"
  同步到服务器后，服务器的 author = "xxxx-yyyy"
  但 DB 里 article_authors 存的是 "aaaa-bbbb"
  → 作者页面查不到文章（issue #64）
  → follow 按钮找不到用户（debug-follow-button-retrospective）
```

### 当前解决方案（不够好）

`useUserStore.trySyncServerAuth()`：
1. 本地注册成功后，用相同凭据调用 `POST /auth/register`（如果服务器上不存在）
2. 把服务器的 JWT 和 UUID 存到 localStorage
3. 前端用服务器 UUID 发 API 请求，用本地 UUID 做 commit

**但这只解决了前端的问题。** Git commit 里的 email 前缀还是本地 UUID。服务器端 `rebuild_article_authors()` 用 `email.split("@")[0]` 提取 user_id——如果邮箱前缀对不上服务器 UUID，作者关联就断了。

## 权限检查

### 服务器端

```python
# deps.py
def require_user(current_user = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(401)
    return current_user

# routes/articles.py
def update_article(article_id, current_user = Depends(require_user)):
    authors = get_author_ids(article_id)
    if current_user.id not in authors:
        raise HTTPException(403, "只有作者可以编辑")
```

权限只在路由层检查（HTTPException）。issue #88 要把权限规则搬进 core 层。

### Tauri 端

```rust
fn resolve_account(token: &str) -> Result<String, AppError> {
    let account_id = local_auth::verify_session(token)?;
    Ok(account_id)
}
```

本地所有操作通过 session token 验证。草稿和缓存在 SQLite 中按 `account_id` 隔离。

## 密码安全

| 项目 | 服务器 | 桌面 |
|------|--------|------|
| 哈希算法 | bcrypt | bcrypt |
| cost | 12（默认） | 12 |
| 最小密码长度 | 6 | 6 |
| 用户名规则 | 3-32, [a-zA-Z0-9_] | 3-32, [a-zA-Z0-9_] |
| 邮箱验证 | 正则 | 正则 |

## 已知问题

1. **双 ID 空间**。本地 UUID ≠ 服务器 UUID，作者关联容易断。
2. **权限规则在路由层**（issue #88）。HTTPException 不是业务逻辑的正确位置。应该搬进 core 的 policy 层。
3. **JWT 密钥是硬编码的默认值**。`peerpedia-dev-secret` 生产环境必须覆盖，但没有人提醒用户。
4. **没有 token 刷新机制**。24 小时后必须重新登录。
5. **Tauri session 没有过期**。UUID session token 永不过期。
6. **密码策略太宽松**。6 位密码，没有复杂度要求。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 改服务器认证 | `backend/peerpedia_api/deps.py` + `routes/auth.py` |
| 改 Tauri 认证 | `frontend/src-tauri/src/local_auth.rs` |
| 改前端认证状态 | `frontend/src/stores/useUserStore.ts` |
| 解决双 ID 问题 | issue #85（ArticleAuthor 加 role 字段）+ UUID 统一化 |
