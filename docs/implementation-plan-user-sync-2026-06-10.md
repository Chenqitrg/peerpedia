# 本地用户服务器同步 — 实施计划

> **创建日期:** 2026-06-10  
> **分支:** main  
> **审查状态:** ENG + DESIGN CLEARED  
> **预计工期:** 2-3 小时（含测试）

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [架构概览](#2-架构概览)
3. [前置条件](#3-前置条件)
4. [任务 T1：Rust — 扩展 login 返回 email/name](#4-任务-t1rust--扩展-login-返回-emailname)
5. [任务 T2：TypeScript 类型 — 补 email/name 字段](#5-任务-t2typescript-类型--补-emailname-字段)
6. [任务 T3：Store — 重写 trySyncServerAuth](#6-任务-t3store--重写-trysyncserverauth)
7. [任务 T4：Composable — bookmark 等待同步](#7-任务-t4composable--bookmark-等待同步)
8. [任务 T4b：ArticlePage — DRY 修复，改用 useBookmarkToggle](#8-任务-t4barticlepage--dry-修复改用-usebookmarktoggle)
9. [任务 T4c：UserPage — follow 操作加 sync](#9-任务-t4cuserpage--follow-操作加-sync)
10. [任务 T5：单元测试](#10-任务-t5单元测试)
11. [任务 T6：A11y — aria-live + aria-label](#11-任务-t6a11y--aria-live--aria-label)
12. [任务 T7：大闭环测试 — SPEC-SYNC-E2E](#12-任务-t7大闭环测试--spec-sync-e2e)
13. [全局验证](#13-全局验证)
14. [手动端到端测试](#14-手动端到端测试)
15. [NOT in Scope（不在本 PR 范围）](#15-not-in-scope不在本-pr-范围)
16. [设计决策速查表](#16-设计决策速查表)

---

## 1. 背景与目标

### 问题

Tauri 桌面用户在本地注册账号后，如果服务器在注册时未启动，本地账号永远不会被同步到服务器。之后服务器上线，用户点 bookmark 会看到 "Authentication required" 错误。

### 根因

Phase 2 双栈架构（Tauri 本地 + FastAPI 服务器）要求本地用户能在服务器上拥有对应账号，但**用户同步机制从未被完整实现**。`registerLocal()` 和 `loginLocal()` 中只有裸 `try/catch`，服务器不可达时静默失败且永不重试。

### 本 PR 范围（L1-L3）

| 层 | 内容 | 状态 |
|----|------|------|
| L1: Auth token sync | Rust login 返回 email/name → trySyncServerAuth 获取服务器 JWT | ✅ 本次 |
| L2: Account mirroring | 服务器上线时自动将本地账号注册到服务器 | ✅ 本次 |
| L3: Profile sync | 本地 name/email 变更同步到服务器（PUT /users/{id}） | ✅ 本次 |
| L4: Full data sync | 文章、书签、关注的完整同步 | ❌ 下个 PR |

---

## 2. 架构概览

### 数据流

```
注册阶段:
  registerLocal(username, password, email, name)
    → Tauri IPC: create_account() → 本地 SQLite 写入
    → 内存暂存: _pendingServerCreds = { username, password, email, name }
    → 尝试: apiRegister() → 成功则清凭据 或 失败则保留凭据

登录阶段:
  loginLocal(username, password)
    → Tauri IPC: login() → 返回 { id, username, token, email, name }  ← T1 改动
    → 内存暂存: _pendingServerCreds = { username, password, email, name }
    → 尝试: apiLogin() → 成功则清凭据 或 失败则保留凭据

服务器上线:
  App.vue watch isOnline → true
    → userStore.trySyncServerAuth()
      → apiLogin(username, password)           // 先试登录（服务器可能已有该用户）
      → 失败 → apiRegister(username, password, email, name)  // 再试注册
      → 成功 → saveString('token', jwt) + syncProfileToServer()
      → 失败（用户名冲突）→ syncError = "服务器已有同名用户"

Bookmark 操作:
  useBookmarkToggle.toggle()
    → 检查 isOnline + token
    → 无 token → await trySyncServerAuth()     // 阻塞等待同步
    → 成功 → REST API addBookmark()
    → 失败 → onError("请先在服务器注册账号")
```

### 涉及的模块

```
frontend/src-tauri/src/local_auth.rs     ← Rust: 添加 email/name 到 AccountWithToken
frontend/src-tauri/src/commands.rs       ← Rust: Serde 自动序列化，无需改动
frontend/src/composables/useTauriTypes.ts ← TS: 类型补字段
frontend/src/stores/useUserStore.ts       ← 核心改动：trySyncServerAuth + syncProfileToServer
frontend/src/composables/useBookmarkToggle.ts ← bookmark 等待同步
frontend/src/pages/ArticlePage.vue        ← DRY 修复：去掉重复 toggleBookmark，改用 useBookmarkToggle
frontend/src/pages/UserPage.vue           ← follow 操作加 token 检查 + sync
frontend/src/App.vue                     ← 已就绪（watch isOnline）
backend/peerpedia_api/routes/users.py    ← 已就绪（PUT /users/{id}）
backend/tests/test_spec_user_sync.py     ← 新增大闭环 xspec 测试
```

---

## 3. 前置条件

### 环境

- Python 3.12+（后端）
- Node.js 18+（前端）
- Rust（Tauri）
- 后端 `.venv` 已安装依赖（`pip install -e ../core -e ".[dev]"`）
- 前端 `npm install` 已完成

### 启动后端（开发时保持运行）

```bash
cd backend
source .venv/bin/activate
python seed.py                              # 如果 peerpedia.db 不存在
uvicorn peerpedia_api.main:app --port 8080 --reload
```

### 启动 Tauri（测试时按需）

```bash
cd frontend
npm run tauri dev
```

---

## 4. 任务 T1：Rust — 扩展 login 返回 email/name

**优先级:** P0 | **文件:** `frontend/src-tauri/src/local_auth.rs` | **验证:** `cargo test`

### 4.1 修改 AccountWithToken 结构体

**文件:** `frontend/src-tauri/src/local_auth.rs`

找到第 20-25 行，`AccountWithToken` 结构体当前定义：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountWithToken {
    pub id: String,
    pub username: String,
    pub token: String,
}
```

改为：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountWithToken {
    pub id: String,
    pub username: String,
    pub token: String,
    pub email: String,    // 新增
    pub name: String,     // 新增
}
```

### 4.2 修改 login() SQL 查询

找到第 127 行，`login()` 函数中的 SQL SELECT：

```rust
// 改前（第 127 行）:
"SELECT id, username, password_hash FROM local_accounts WHERE username = ?1"

// 改为:
"SELECT id, username, password_hash, email, name FROM local_accounts WHERE username = ?1"
```

### 4.3 更新 row 解构

找到第 129-135 行，`row` 闭包解构：

```rust
// 改前:
|row| {
    Ok((
        row.get::<_, String>(0)?,
        row.get::<_, String>(1)?,
        row.get::<_, String>(2)?,
    ))
},

// 改为:
|row| {
    Ok((
        row.get::<_, String>(0)?,   // id
        row.get::<_, String>(1)?,   // username
        row.get::<_, String>(2)?,   // password_hash
        row.get::<_, String>(3)?,   // email  ← 新增
        row.get::<_, String>(4)?,   // name   ← 新增
    ))
},
```

### 4.4 更新 match 分支解构

找到第 139 行附近，`match result` 的 `Ok` 分支：

```rust
// 改前:
Ok((id, uname, password_hash)) => {

// 改为:
Ok((id, uname, password_hash, email, name)) => {
```

### 4.5 更新 AccountWithToken 构造

找到第 144-148 行，`AccountWithToken` 构造：

```rust
// 改前:
Ok(AccountWithToken {
    id,
    username: uname,
    token,
})

// 改为:
Ok(AccountWithToken {
    id,
    username: uname,
    token,
    email,    // 新增
    name,     // 新增
})
```

### 4.6 更新 Rust 单元测试

找到 `test_login_correct_password` 测试（约第 220 行），增加 email/name 断言：

```rust
#[test]
fn test_login_correct_password() {
    let conn = setup();
    create_account(&conn, "bob", "correcthorse", "bob@test.com", "Bob").unwrap();
    let result = login(&conn, "bob", "correcthorse").unwrap();
    assert_eq!(result.username, "bob");
    assert_eq!(result.email, "bob@test.com");    // 新增
    assert_eq!(result.name, "Bob");              // 新增
    assert!(!result.token.is_empty());
    let account_id = verify_session(&conn, &result.token).unwrap();
    assert_eq!(account_id, result.id);
}
```

### 4.7 commands.rs 检查

**文件:** `frontend/src-tauri/src/commands.rs`

`login` 命令直接返回 `local_auth::login()` 的结果。AccountWithToken 已通过 Serde `#[derive(Serialize)]` 自动序列化，新加的 `email` 和 `name` 字段会自动出现在 IPC 响应中。**无需改动 commands.rs。**

### 4.8 验证

```bash
cd frontend/src-tauri
cargo test
```

预期：所有 Rust 测试通过，`test_login_correct_password` 包含 email/name 断言。

---

## 5. 任务 T2：TypeScript 类型 — 补 email/name 字段

**优先级:** P0 | **文件:** `frontend/src/composables/useTauriTypes.ts` | **验证:** `npx vue-tsc --noEmit`

### 5.1 查找 login 返回类型

**文件:** `frontend/src/composables/useTauriTypes.ts`

找到与 login 返回值对应的 TypeScript 接口（通常命名为 `Account` 或 `LoginResult`）。当前定义形如：

```typescript
interface Account {
  id: string
  username: string
  token: string
}
```

改为：

```typescript
interface Account {
  id: string
  username: string
  token: string
  email: string    // 新增 — 来自 Rust login 返回
  name: string     // 新增 — 来自 Rust login 返回
}
```

### 5.2 验证

```bash
cd frontend
npx vue-tsc --noEmit
```

确认无类型错误。

---

## 6. 任务 T3：Store — 重写 trySyncServerAuth

**优先级:** P0 | **文件:** `frontend/src/stores/useUserStore.ts` | **验证:** SPEC-AUTH 测试通过

这是整个 PR 最核心的改动。需要完成以下子任务：

### 6.1 修改 _pendingServerCreds 类型

**文件:** `frontend/src/stores/useUserStore.ts`

找到模块级变量定义（约第 9-14 行），删除 `action` 字段：

```typescript
// 改前:
let _pendingServerCreds: {
  action: 'login' | 'register'
  username: string
  password: string
  email?: string
  name?: string
} | null = null

// 改为:
let _pendingServerCreds: {
  username: string
  password: string
  email: string
  name: string
} | null = null
```

### 6.2 修改 loginLocal() 存凭据

找到 `loginLocal()` 函数（约第 56 行）。需要从 Tauri login 返回值中捕获 email/name。

将：

```typescript
_pendingServerCreds = { action: 'login', username, password }
```

改为：

```typescript
// 从 Tauri login 结果中获取 email/name
const acct = result as { id: string; username: string; token: string; email: string; name: string }
_pendingServerCreds = {
  username,
  password,
  email: acct.email || '',
  name: acct.name || username,
}
```

同时，`apiLogin` 成功时清空凭据的一行也需要修改——删除 `_pendingServerCreds = null`（该行已在原代码中，保持不变即可，仅确认逻辑正确）。

### 6.3 修改 registerLocal() 存凭据

找到 `registerLocal()` 函数（约第 104 行）。

将：

```typescript
_pendingServerCreds = { action: 'register', username, password, email, name }
```

改为：

```typescript
_pendingServerCreds = { username, password, email, name }
```

### 6.4 重写 trySyncServerAuth()

找到 `trySyncServerAuth()` 函数（约第 179 行），整个函数重写为：

```typescript
/**
 * 用暂存的本地凭据获取服务器 JWT。
 * 策略：先 apiLogin（服务器可能已有该用户），失败则 apiRegister（创建服务器账号）。
 * 成功后清凭据并同步 profile。失败则保留凭据支持重试。
 * 返回 true 表示已获取有效服务器 token。
 */
async function trySyncServerAuth(): Promise<boolean> {
  if (!_pendingServerCreds) return false
  const creds = _pendingServerCreds

  // 第 1 步：尝试 apiLogin（用户可能已存在于服务器，如 seed 数据或多设备）
  try {
    const { token: t } = await apiLogin({
      username: creds.username,
      password: creds.password,
    })
    token.value = t
    saveString('token', t)
    _pendingServerCreds = null
    syncError.value = null
    // 登录成功后同步 profile 到服务器
    await syncProfileToServer()
    return true
  } catch (loginErr: any) {
    // apiLogin 失败 — 继续尝试 apiRegister
  }

  // 第 2 步：尝试 apiRegister（将本地用户注册到服务器）
  try {
    const { token: t } = await apiRegister({
      username: creds.username,
      password: creds.password,
      email: creds.email,
      name: creds.name,
    })
    token.value = t
    saveString('token', t)
    _pendingServerCreds = null
    syncError.value = null
    // 注册成功后同步 profile
    await syncProfileToServer()
    return true
  } catch (regErr: any) {
    // 第 3 步：分析失败原因
    const detail = regErr?.response?.data?.detail || regErr?.userMessage || ''
    if (detail.includes('already exists') || detail.includes('taken') || detail.includes('unique')) {
      // 用户名冲突
      syncError.value = `服务器上已有用户 ${creds.username}。请输入该账号的服务器密码进行关联。`
    }
    // 保留凭据，允许用户重试（不删除 _pendingServerCreds）
    return false
  }
}
```

### 6.5 新增 syncError 状态

在 store 的 ref 声明区域（约第 13-16 行附近）添加：

```typescript
const syncError = ref<string | null>(null)
```

### 6.6 新增 syncProfileToServer()

在 `trySyncServerAuth()` 下方添加新函数：

```typescript
/**
 * 将本地 profile 数据同步到服务器（L3）。
 * 静默执行 — 成功不提示，失败不影响其他操作。
 */
async function syncProfileToServer() {
  if (!token.value || !viewer.value) return
  try {
    const { updateProfile } = await import('../api/users')
    await updateProfile(viewer.value.id, {
      affiliation: viewer.value.affiliation,
      expertise: viewer.value.expertise,
    })
  } catch {
    // 静默失败 — profile sync 是 best-effort
  }
}
```

### 6.7 新增 API 函数 updateProfile

**文件:** `frontend/src/api/users.ts`（如果不存在则创建）

```typescript
import apiClient from './client'

export async function updateProfile(
  userId: string,
  data: {
    affiliation?: string
    expertise?: string[]
    anonymous_name?: string
    avatar_url?: string | null
    contact?: string | null
  }
): Promise<any> {
  const res = await apiClient.put(`/users/${userId}`, data)
  return res.data
}
```

### 6.8 修改 clear() 清除凭据

找到 `clear()` 函数（约第 170 行），确认包含：

```typescript
_pendingServerCreds = null
syncError.value = null
```

### 6.9 更新 store 返回值

找到 `return { ... }` 块（约第 276 行），确保导出：

```typescript
return {
  // ... 已有字段
  syncError,           // 新增
  trySyncServerAuth,   // 新增（之前已加过）
  syncProfileToServer, // 新增
}
```

---

## 7. 任务 T4：Composable — bookmark 等待同步

**优先级:** P1 | **文件:** `frontend/src/composables/useBookmarkToggle.ts` | **验证:** useBookmarkToggle 测试通过

### 7.1 修改 toggle() 函数

**文件:** `frontend/src/composables/useBookmarkToggle.ts`

找到 `toggle()` 函数中的 `try` 块。在 `if (isLocal)` 之前添加：

```typescript
// 如果服务器可达但没有 token，先尝试同步
if (!isLocal && !userStore.token?.value) {
  await userStore.trySyncServerAuth()
  // 同步成功后 token 已更新，重新计算 isLocal
  // 注意：isLocal 的值在函数创建时已确定，这里需要手动判断
  if (userStore.token?.value) {
    // 同步成功 → 使用 REST API
  } else {
    // 同步失败 → 使用 IPC fallback，调用 onError
    if (onError) {
      onError(userStore.syncError?.value || '书签功能需要服务器账号。请在 Auth 中注册服务器账号。')
    }
    article.is_bookmarked = previous  // 回滚乐观更新
    return
  }
}
```

完整的 toggle() 逻辑：

```typescript
async function toggle(articleId: string, currentlyBookmarked: boolean) {
  if (!userStore.viewer) return
  const article = articles.value.find(a => a.id === articleId)
  if (!article) return

  // 静默忽略自收藏
  if (article.is_own_article) return

  const previous = article.is_bookmarked
  article.is_bookmarked = !currentlyBookmarked   // 乐观更新

  // 如果服务器可达但无 token → 先同步再操作
  const needsSync = (userStore.isTauriMode || userStore.isBrowserLocal)
    && isOnline.value
    && !userStore.token?.value

  if (needsSync) {
    const synced = await userStore.trySyncServerAuth()
    if (!synced || !userStore.token?.value) {
      article.is_bookmarked = previous  // 回滚
      if (onError) {
        onError(userStore.syncError?.value || '书签功能需要服务器账号')
      }
      return
    }
  }

  try {
    if (isLocal) {
      if (currentlyBookmarked) {
        await tauri.removeBookmark({ user_id: userStore.viewer.id, article_id: articleId })
      } else {
        await tauri.addBookmark({ user_id: userStore.viewer.id, article_id: articleId })
      }
    } else {
      if (currentlyBookmarked) {
        await removeBookmark(articleId)
      } else {
        await addBookmark(articleId)
      }
    }
  } catch (e: any) {
    article.is_bookmarked = previous  // 回滚乐观更新
    if (onError) {
      onError(e.userMessage || 'Failed to update bookmark')
    }
  }
}
```

---

## 8. 任务 T4b：ArticlePage — DRY 修复，改用 useBookmarkToggle

**优先级:** P1 | **文件:** `frontend/src/pages/ArticlePage.vue` | **验证:** ArticlePage 测试通过

### 8.1 问题

ArticlePage.vue 第 325-346 行有一个手写的 `toggleBookmark` 函数，逻辑与 `useBookmarkToggle` 几乎相同，但**缺少 `userStore.token?.value` 检查**。当前 plan 修了 `useBookmarkToggle`，但 ArticlePage 不走那个 composable，所以修不到。

### 8.2 改动

删除手写的 `toggleBookmark`，改为调用 `useBookmarkToggle`：

```typescript
// 删除（第 322-346 行）:
// import { useNetworkStatus } from '../composables/useNetworkStatus'
// async function toggleBookmark(articleId: string, currentlyBookmarked: boolean) { ... }

// 改为:
import { useBookmarkToggle } from '../composables/useBookmarkToggle'

// 在 setup 中:
const { toggle: handleToggleBookmark } = useBookmarkToggle(
  article,  // Ref<ArticleSummary[]> — 注意 ArticlePage 的数据结构
  (msg: string) => { /* toast error */ }
)
```

注意事项：
- ArticlePage 的 article 数据结构可能与 composable 期望的 `Ref<ArticleSummary[]>` 不完全匹配，需要检查转换
- 确认 `onError` 回调正确接入现有的 toast/错误提示机制

### 8.3 验证

```bash
cd frontend && npx vitest run src/pages/__tests__/ArticlePage.test.ts
```

---

## 9. 任务 T4c：UserPage — follow 操作加 sync

**优先级:** P1 | **文件:** `frontend/src/pages/UserPage.vue` | **验证:** UserPage 测试通过

### 9.1 问题

UserPage.vue 第 90-110 行的 `handleFollow` 函数只按 `isLocal` 分支，不检查 `isOnline` 和 `userStore.token`。在 Tauri 模式下服务器可达但无 token 时，直接走 else 分支调 REST API（`followUser` / `unfollowUser`），导致 401。

### 9.2 改动

```typescript
// 改前（约第 90-110 行）:
async function handleFollow() {
  if (!user.value) return
  const isCurrentlyFollowing = user.value.is_following
  user.value.is_following = !isCurrentlyFollowing  // 乐观更新

  try {
    if (isLocal.value) {
      if (isCurrentlyFollowing) {
        await tauri.unfollowUser(user.value.id)
      } else {
        await tauri.followUser(user.value.id)
      }
    } else {
      if (isCurrentlyFollowing) {
        await unfollowUser(user.value.id)
      } else {
        await followUser(user.value.id)
      }
    }
  } catch (e: any) {
    user.value.is_following = isCurrentlyFollowing  // 回滚
    // error handling
  }
}

// 改为:
async function handleFollow() {
  if (!user.value) return

  // 如果服务器可达但无 token → 先同步
  const needsSync = (userStore.isTauriMode || userStore.isBrowserLocal)
    && isOnline.value
    && !userStore.token?.value

  if (needsSync) {
    const synced = await userStore.trySyncServerAuth()
    if (!synced || !userStore.token?.value) {
      // 同步失败 → 提示用户
      showError(userStore.syncError?.value || '关注功能需要服务器账号')
      return
    }
  }

  const isCurrentlyFollowing = user.value.is_following
  user.value.is_following = !isCurrentlyFollowing

  try {
    if (isLocal.value) {
      if (isCurrentlyFollowing) {
        await tauri.unfollowUser(user.value.id)
      } else {
        await tauri.followUser(user.value.id)
      }
    } else {
      if (isCurrentlyFollowing) {
        await unfollowUser(user.value.id)
      } else {
        await followUser(user.value.id)
      }
    }
  } catch (e: any) {
    user.value.is_following = isCurrentlyFollowing
    showError(e.userMessage || '关注操作失败')
  }
}
```

### 9.3 验证

```bash
cd frontend && npx vitest run src/pages/__tests__/UserPage.test.ts
```

---

## 10. 任务 T5：单元测试

**优先级:** P1 | **文件:** 5 个测试文件 | **验证:** `npx vitest run` + `cargo test`

新增 10 个测试，分布在 4 个文件中：

**文件:** `frontend/src/stores/__tests__/useUserStore.test.ts`

在 `SPEC-AUTH server token sync` describe 块中添加：

#### SPEC-AUTH-6: loginLocal captures email/name from Rust

```typescript
it('SPEC-AUTH-6: loginLocal captures email and name from Tauri login result', async () => {
  // Server unreachable — apiLogin rejects
  authMocks.login.mockRejectedValueOnce(new Error('Network Error'))

  // Tauri login returns email/name
  const tauriMod = await import('../../composables/useTauri')
  const tauriMock = (tauriMod as any).useTauri()
  // 用 vi.mocked 设置返回值
  tauriMocks.login.mockResolvedValue({
    id: 'local-1',
    username: 'alice',
    token: 'session-token',
    email: 'alice@test.com',
    name: 'Alice Test',
  })

  const { useUserStore } = await import('../useUserStore')
  const store = useUserStore()
  await store.login('alice', '666666')

  // 验证凭据包含 email/name
  expect(store.viewer).not.toBeNull()
  expect(store.token).toBeNull()  // 服务器没开

  // 调用 trySyncServerAuth — 应使用 email/name 调用 apiRegister
  authMocks.register.mockResolvedValueOnce({
    user: { id: 's1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
    token: 'synced-jwt',
  })
  const result = await store.trySyncServerAuth()
  expect(result).toBe(true)
  expect(store.token).toBe('synced-jwt')
  expect(authMocks.register).toHaveBeenCalledWith({
    username: 'alice',
    password: '666666',
    email: 'alice@test.com',
    name: 'Alice Test',
  })
})
```

#### SPEC-AUTH-7: apiLogin → apiRegister fallback

```typescript
it('SPEC-AUTH-7: falls back to apiRegister when apiLogin fails', async () => {
  // Login with server unreachable
  authMocks.login.mockRejectedValueOnce(new Error('Network Error'))

  const { useUserStore } = await import('../useUserStore')
  const store = useUserStore()
  await store.login('alice', '666666')

  // apiLogin fails (user not found)
  authMocks.login.mockRejectedValueOnce({
    response: { status: 401, data: { detail: 'Invalid credentials' } },
  })
  // apiRegister succeeds
  authMocks.register.mockResolvedValueOnce({
    user: { id: 's1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
    token: 'registered-jwt',
  })

  const result = await store.trySyncServerAuth()
  expect(result).toBe(true)
  expect(store.token).toBe('registered-jwt')
  // apiLogin 被调用过，然后 apiRegister 也被调用过
  expect(authMocks.login).toHaveBeenCalled()
  expect(authMocks.register).toHaveBeenCalled()
})
```

#### SPEC-AUTH-8: Username conflict → syncError

```typescript
it('SPEC-AUTH-8: sets syncError on username conflict', async () => {
  authMocks.login.mockRejectedValueOnce(new Error('Network Error'))

  const { useUserStore } = await import('../useUserStore')
  const store = useUserStore()
  await store.login('alice', '666666')

  // apiLogin fails
  authMocks.login.mockRejectedValueOnce({ response: { status: 401 } })
  // apiRegister fails with "already exists"
  authMocks.register.mockRejectedValueOnce({
    response: { status: 409, data: { detail: 'Username already exists' } },
  })

  const result = await store.trySyncServerAuth()
  expect(result).toBe(false)
  expect(store.syncError).toBeTruthy()
  expect(store.syncError).toContain('alice')
  // 凭据保留（不清除）
  expect(store.token).toBeNull()
})
```

#### SPEC-AUTH-9: Failed sync keeps credentials

```typescript
it('SPEC-AUTH-9: keeps credentials after failed sync for retry', async () => {
  authMocks.login.mockRejectedValueOnce(new Error('Network Error'))

  const { useUserStore } = await import('../useUserStore')
  const store = useUserStore()
  await store.login('alice', '666666')

  // 第一次 trySyncServerAuth 失败
  authMocks.login.mockRejectedValueOnce(new Error('Network Error'))
  authMocks.register.mockRejectedValueOnce(new Error('Server error'))

  await store.trySyncServerAuth()
  expect(store.token).toBeNull()

  // 第二次 trySyncServerAuth 应该还能尝试（凭据未清）
  authMocks.login.mockResolvedValueOnce({
    user: { id: 's1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
    token: 'delayed-jwt',
  })
  const result = await store.trySyncServerAuth()
  expect(result).toBe(true)
  expect(store.token).toBe('delayed-jwt')
})
```

### 10.2 useBookmarkToggle.test.ts — 更新 mock + 新增 2 个测试

**文件:** `frontend/src/composables/__tests__/useBookmarkToggle.test.ts`

更新 `useUserStore` mock，加入 `token`、`trySyncServerAuth`、`syncError`：

```typescript
// 确认 mock 包含:
vi.mock('../../stores/useUserStore', () => ({
  useUserStore: vi.fn(() => ({
    viewer: mockViewer,
    isTauriMode: mockIsTauriMode,
    isBrowserLocal: false,
    token: mockToken,                                // 已有
    syncError: ref(null),                            // 新增
    trySyncServerAuth: vi.fn().mockResolvedValue(false),  // 新增
  })),
}))
```

新增 SPEC-AUTH-BM-2 测试：

```typescript
describe('SPEC-AUTH-BM-2: Bookmark awaits sync when no token', () => {
  beforeEach(() => {
    mockIsTauri.value = true
    mockIsTauriMode.value = true
    mockIsOnline.value = true       // Server reachable
    mockToken.value = null          // No token — need sync
  })

  it('calls trySyncServerAuth before making REST call', async () => {
    const mod = await import('../../stores/useUserStore')
    const mockTrySync = vi.fn().mockResolvedValue(true)
    // 模拟 sync 成功后 token 出现
    const mockStore = (mod as any).useUserStore()
    mockStore.trySyncServerAuth = mockTrySync

    const { toggle } = useBookmarkToggle(articles)
    await toggle('a1', false)

    expect(mockTrySync).toHaveBeenCalled()
  })
})
```

### 10.3 Rust 测试 — 更新 test_login_correct_password

已在任务 T1 中完成（4.6 节）。

### 10.4 ArticlePage.test.ts — 新增 2 个测试

验证 ArticlePage 使用 useBookmarkToggle（而非手写逻辑），且 bookmark 无 token 时触发 sync。

### 10.5 UserPage.test.ts — 新增 2 个测试

验证 UserPage handleFollow：无 token 时调 trySyncServerAuth，失败时显示错误。

---

## 11. 任务 T6：A11y — aria-live + aria-label

**优先级:** P2 | **文件:** `NavBar.vue` + bookmark 图标组件 | **验证:** 手动 VoiceOver 检查

### 11.1 Toast 通知加 aria-live

**文件:** `frontend/src/components/NavBar.vue`（或包含 toast 的组件）

找到 toast 通知的 HTML 元素，添加：

```html
<div role="alert" aria-live="polite" class="toast-notification">
  {{ toastMessage }}
</div>
```

关键属性：
- `role="alert"` — 屏幕阅读器自动朗读
- `aria-live="polite"` — 不打断当前朗读

### 11.2 Bookmark 图标 spinner 期间加 aria-label

找到 bookmark 图标的按钮/span 元素。spinner 期间：

```html
<!-- 正常状态 -->
<button aria-label="Bookmark this article" @click="toggle">
  <BookmarkIcon />
</button>

<!-- Spinner 状态（trySyncServerAuth 中） -->
<button aria-label="Syncing with server…" disabled>
  <SpinnerIcon class="animate-spin" />
</button>

<!-- 错误状态 -->
<button aria-label="Bookmark failed — tap to retry" @click="toggle">
  <BookmarkIcon class="opacity-50" />
</button>
```

### 11.3 App.vue 检查 watch isOnline

**文件:** `frontend/src/App.vue`

确认以下代码存在（前次改动已添加，此处仅确认）：

```typescript
const { startPing, stopPing, isOnline } = useNetworkStatus()

watch(isOnline, (online, wasOffline) => {
  if (online && !wasOffline) {
    userStore.trySyncServerAuth()
  }
})
```

---

## 12. 任务 T7：大闭环测试 — SPEC-SYNC-E2E

**优先级:** P1 | **文件:** `backend/tests/test_spec_user_sync.py` | **验证:** pytest

### 12.1 测试文件已创建

文件位于 `backend/tests/test_spec_user_sync.py`，包含 13 个测试，覆盖 3 个 spec：

- **TestSpecSyncE2E** (5 tests): 注册 → 登录 → Pool → Bookmark → 验证 → 取消
- **TestSpecSyncProfile** (3 tests): affiliation 更新、跨用户编辑拒绝、expertise 更新
- **TestSpecSyncConflict** (5 tests): 重复用户名拒绝、密码错误 401、正确登录 200、不存在用户、JWT 访问受保护端点

### 12.2 运行测试

```bash
cd backend
.venv/bin/python -m pytest backend/tests/test_spec_user_sync.py -v
```

### 12.3 测试失败排查

如果 `test_full_bookmark_lifecycle_after_registration` 失败（Pool 为空）：

```bash
# 检查 seed 数据中是否有 published/sedimentation 状态的文章
.venv/bin/python -c "
from peerpedia_core.storage.db.engine import get_engine, get_session
eng = get_engine('sqlite:///peerpedia.db')
s = get_session(eng)
from peerpedia_core.storage.db.article import Article
articles = s.query(Article).filter(Article.status.in_(['published', 'sedimentation'])).all()
print(f'Found {len(articles)} pool-eligible articles')
for a in articles[:3]:
    print(f'  {a.id[:8]}... status={a.status}')
"
```

如果 `test_new_user_appears_in_users_list` 失败（KeyError: 'username'）：

```bash
# 检查 GET /users 响应格式
curl -s http://localhost:8080/api/v1/users | python3 -m json.tool | head -20
```

根据实际响应结构修正测试中的字段名（`'username'` 可能为 `'name'` 或其他 key）。

---

## 13. 全局验证

### 运行全部测试

```bash
# 1. Rust 测试
cd frontend/src-tauri && cargo test

# 2. 前端测试
cd frontend && npx vitest run

# 3. 后端测试
cd backend && .venv/bin/python -m pytest backend/tests/ core/tests/ -q

# 4. TypeScript 类型检查
cd frontend && npx vue-tsc --noEmit
```

**通过标准:**
- Rust: 全部测试通过（含 email/name 断言）
- 前端: 485+ 测试通过，0 失败
- 后端: 379+ 测试通过（366 + 13 新测试）
- 类型检查: 0 errors

---

## 14. 手动端到端测试

### 测试场景 1：新用户自动同步

```
1. 确保后端运行在 8080
2. 启动 Tauri (npm run tauri dev)
3. 在 Tauri 中注册新账号:
   - username: "testuser_manual"
   - password: "test123"
   - email: "test@example.com"
   - name: "Test User"
4. 观察: 登录后 NavBar WiFi 图标变绿
5. 浏览 Pool → 点击书签图标
6. 预期: 书签图标短暂 spinner → 变实心 → 无报错
7. 验证: curl http://localhost:8080/api/v1/users | grep testuser_manual
   预期: 用户出现在服务器用户列表中
```

### 测试场景 2：已存在种子用户同步

```
1. 确保后端运行在 8080
2. 在 Tauri 中注册本地账号:
   - username: "einstein"
   - password: "666666"
3. 浏览 Pool → 点击书签
4. 预期: 直接成功（apiLogin 成功，无需 apiRegister）
```

### 测试场景 3：用户名冲突

```
1. 确保后端运行在 8080
2. 在 Tauri 中注册本地账号:
   - username: "einstein"
   - password: "wrongpassword"
3. 浏览 Pool → 点击书签
4. 预期: 弹出 AuthModal，提示"服务器已有同名用户 einstein"
5. 输入服务器密码 "666666" → 登录成功
6. 再次点击书签 → 成功
```

---

## 15. NOT in Scope（不在本 PR 范围）

| 内容 | 原因 | 目标 |
|------|------|------|
| L4: 文章/书签/关注数据同步 | 独立子系统，15+ 文件。多设备通过服务器互相同步（设备A → 服务器 ← 设备B），这**不是** P2P，服务器就是中介。 | Phase 2.2 Week 2 |
| P2P 内容寻址存储 | Phase 3 特性 — peerpedia://hash 协议，去中心化分发。与通过服务器的多设备同步是两回事。 | 未来 |
| 密码修改同步 | 本地密码修改流程尚不存在 | 待定 |
| 多本地账号 → 单服务器账号 | 设计决定：1:1 映射，不支持共享。多设备允许（同用户名密码 → 同服务器账号） | N/A |

---

## 16. 设计决策速查表

| 决策 | 选择 | 理由 |
|------|------|------|
| Bookmark loading | Spinner + toast | 操作 > 300ms 需反馈（UX guideline: Loading States） |
| 用户名冲突 | AuthModal + 上下文文案 | 提供恢复路径，不是静默失败（UX guideline: Error Recovery） |
| Profile sync | 静默后台同步 | 无用户影响，无需通知 |
| 失败凭据处理 | 保留不清除 | 支持重试（用户可能在服务器上线前多次点击 bookmark） |
| Sync 逻辑 | apiLogin → apiRegister fallback | 统一处理新用户和已有种子的用户 |
| 本地↔服务器账号 | 1:1 映射 | 一个本地账号对应一个服务器账号，不支持多账号共享。多设备通过同用户名密码登录同一服务器账号 |

---

*最后更新: 2026-06-10 · 审查: ENG + DESIGN CLEARED · 9 个任务（T1-T7 + T4b/T4c）· 3 层同步 · 17 个 xspec 测试（4 composable + 13 backend）*
