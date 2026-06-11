# Follow 按钮 Debug 回顾

> 2026-06-11，分支 `feat/article-sync-l4`，commit `b0d349c`

## 用户原始报告

"在 school 里看到 feynman，follow 他，按钮变了，但刷新后回去，点个人主页显示 user not found。"

后续："按钮一闪又变成正常的"、"还是 follow 不了大佬"、"看不到大佬的关注列表"。

## Debug 过程：12 轮迭代

### 第 1 轮：最初的两个 Bug

**Bug 1 — SchoolsPage 不加载 follow 状态**：`following` ref 初始化为空 Set，从未从 server/Tauri 加载。刷新后全部显示 "Follow"。

**Bug 2 — UserPage 在 Tauri 模式下查不到 server 用户**：`loadUser` 在 `isLocal && !isSelf` 时只查 `tauri.listAccounts()`（本地账户），server 用户（如 seed 数据的 feynman）永远找不到。

→ 修复：加 `loadFollowState()`，UserPage 加 server API fallback。

### 第 2-4 轮：前端补丁

用户反馈 "还是不行"。我继续在前端打补丁：
- `useServerApi`：Tauri+在线时走 REST API（绕过不存在的 Rust 命令）
- `isOnline` watch：网络延迟时重新触发数据加载
- IPC `{ error }` 检测：Tauri `_invoke` 不抛异常，返回 `{ error }` 需要显式检查

→ 505 个前端测试全通过，browse 验证也通过。但用户说**还是不行**。

### 第 5 轮：架构层面的发现

用户说 "/brainstorming"，"我感觉可能不是一个 bug，而是一个重要的功能没写进去"。

检查 `commands.rs`：583 行，28 个命令（auth、draft、cache、git、compile、export）——**零 follow 命令**。

三层 follow 系统：
| 层 | 状态 |
|----|------|
| Server REST API | ✅ |
| Browser-local mock | ✅ |
| Tauri Rust backend | ❌ **不存在** |

→ 实现 Rust follow 命令（5 个命令 + follows 表 + migration v7）。

### 第 6-7 轮：实现细节

**命令名不匹配**：Rust 函数命名 `get_following_cmd`（避免和 `local_store::get_following` 冲突），但 Tauri 从函数名推导命令名。前端调 `invoke('get_following')`，Rust 命令注册为 `get_following_cmd` → 不匹配。

→ 加 `#[tauri::command(name = "get_following")]`。

### 第 8 轮：身份系统分裂（真正的根因）

**现象**：按钮变化（乐观更新），但 follow 不持久化。看起来像"一闪而过"。

**根因**：Tauri 有**两套身份系统**：

1. **本地身份**：Tauri Rust 本地 SQLite 账户（`local_accounts` 表）。`resolve_account(token)` 返回本地 UUID。
2. **服务器身份**：Python 后端账户。`apiLogin()` 返回服务器 UUID，**覆盖** `viewer.id`。

**执行路径**：
```
登录 → tauri.login() → 设 _sessionToken
     → apiLogin() 成功 → viewer.id = 服务器 UUID（覆盖本地 UUID）

点击 Follow → toggleFollow({ follower_id: viewer.id })
           → viewer.id = 服务器 UUID
           → _invoke 自动加 token
           → Rust resolve_account(token) = 本地 UUID
           → INSERT INTO follows (follower_id = 本地 UUID, followed_id = 服务器 UUID)

刷新页面 → loadFollowState({ user_id: viewer.id })
         → viewer.id = 服务器 UUID
         → SELECT FROM follows WHERE follower_id = 服务器 UUID
         → 空结果！（follow 存的是本地 UUID）
```

**修复**：`SchoolsPage.vue` 和 `UserPage.vue` 的 follow 操作换成 `userStore.localAccount.id`（本地 UUID），不用 `viewer.id`（服务器 UUID）。

## 为什么花了 12 轮？

### 1. 架构盲区：Tauri 有两套身份

这是我最大的盲区。`viewer.id` 在 `apiLogin` 成功后**被覆写为服务器 UUID**，但 Tauri 的 `resolve_account` 返回的是**本地 UUID**。两个 UUID 不是同一个值，follow 的存储和查询用的 ID 对不上。

我之前一直在前端层调试（API 调用、状态管理、乐观更新），没有深入理解 `loginLocal` → `apiLogin` → `viewer` 覆写 这条链路。

### 2. 分层调试的陷阱

每次用户反馈 "不行"，我都默认是前端状态管理问题，继续在前端加补丁。但实际上：
- 第 1 轮修复的两个 Bug 是真实存在的
- 第 2-4 轮的补丁是治标的（绕过不存在的 Rust 命令）
- 第 5 轮才发现真正的架构问题（Rust 没有命令）
- 第 8 轮才发现身份分裂（local UUID vs server UUID）

**如果一开始就从 Rust 层往下查，而不是从 Vue 层往上查，会快很多。**

### 3. 测试的假安全感

505 个前端测试 + 87 个 Rust 测试全通过。但：
- 前端测试 mock 了 `useUserStore`，`viewer.id` 是假的
- Rust 测试用 in-memory SQLite，没有真实 Tauri IPC 调用
- **没有一个测试覆盖了"Tauri 登录 → apiLogin → viewer 覆写 → follow → 查询"这条完整链路**

### 4. 我无法直接观察 Tauri 行为

browse 只能测浏览器版本。Tauri 桌面应用的 `window.__TAURI__` 在 headless Chrome 里不存在。每次改完只能让用户试，反馈循环长。

## 最终的修复总览

| 层 | 文件 | 改动 |
|----|------|------|
| Rust | `db.rs` | migration v7: follows 表 |
| Rust | `local_store.rs` | FollowEntry + 5 CRUD + 8 tests |
| Rust | `commands.rs` | 5 个 follow 命令（含 name attr） |
| Rust | `main.rs` | 注册命令 |
| 前端 | `SchoolsPage.vue` | `localAccount.id` 做 follow ops；`isOnline` watch；简洁架构 |
| 前端 | `UserPage.vue` | 同上；server articles 在 Tauri+online 时加载 |
| 测试 | `SchoolsPage.xspec.test.ts` | 11 个 regression tests |
| 测试 | `UserPage.xspec.test.ts` | 4 个 regression tests |

## 待解决

- **关注/粉丝列表**（UserListPage）：从 server REST API 获取，不包含本地 follows。需要加 Tauri IPC fallback 或 follow sync。
- **关注者/正在关注数量**：来自 server API 的 `followers_count`/`following_count`，不反映本地 follows。
- `useFollowSync.ts`：本地→服务器同步（本期未做）。
