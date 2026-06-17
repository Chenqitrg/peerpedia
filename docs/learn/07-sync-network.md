# Sync & Network 模块

> 同步与网络模型。PeerPedia 最复杂的横切关注点——离线编辑、bundle sync、冲突策略。

## 一句话职责

**让用户在离线时正常编辑，在线时自动同步，冲突时安全降级。**

## C3: Sync 组件依赖

```
   ┌─────────────────────┐
   │  browser events     │  ← online / offline 事件
   │  GET /health        │  ← 服务器心跳（10s 超时）
   └──────────┬──────────┘
              │ 触发
              ▼
   ┌─────────────────────┐
   │  useNetworkStatus   │  ← 单例：唯一连接状态来源
   │  idle → connecting  │
   │       → synced      │
   └──────────┬──────────┘
              │ 读取 isSynced
     ┌────────┼────────┐
     ▼        ▼        ▼
   ┌──────┐┌──────┐┌──────────┐
   │useOff││useAut││SyncButton│
   │line  ││oSync ││.vue      │
   │      ││      ││          │
   │canR/W││flush ││WiFi 图标  │
   │能力  ││离线队 ││红色徽章  │
   │门控  ││列刷新 ││          │
   └──────┘└──┬───┘└──────────┘
              │ 调 pushRepo
              ▼
   ┌────────────────────────────────┐
   │  useArticleSync (per-article)  │
   │  比较 本地 HEAD vs 服务器 HEAD  │
   │  → synced | upload | conflict  │
   └────────────┬───────────────────┘
                │ 调 git bundle 操作
                ▼
   ┌────────────────────────────────────┐
   │  local_git.rs  ←─ HTTP ──►  git_backend.py  │
   │  git bundle create/apply     apply_bundle   │
   └────────────────────────────────────────────┘
```

箭头约定：`A ──► B` = A 依赖 B。

- **useNetworkStatus 被所有人依赖**——它是连接状态的唯一事实来源
- **useAutoSync 依赖 useNetworkStatus**——监听到 synced 后才刷新
- **useAutoSync 依赖 local_git + git_backend**——bundle 是唯一同步协议
- **useOffline 只读 isSynced，不自己做网络检测**

## 架构概述

```
┌──────────────────────────────────────────────────────┐
│                    useNetworkStatus                   │
│  ping /health → idle | connecting | synced          │
│  监听 browser online/offline 事件                     │
└────────────────────┬─────────────────────────────────┘
                     │ isSynced
        ┌────────────┼────────────┐
        ▼            ▼            ▼
  useOffline    useAutoSync   SyncButton.vue
  (能力门控)     (离线队列)     (UI 状态指示)
        │            │
        ▼            ▼
  canRead/WRITE   flush()
  按 feature 判断   pending ops → git bundle sync
```

## 三态同步按钮（SyncButton）

```
离线 (红色 WiFi Off)  →  同步中 (黄色旋转)  →  已同步 (绿色 WiFi)
```

- 已同步时点击 = 手动断开（变为 idle）
- 离线时点击 = 手动连接（ping /health）
- `pendingCount > 0` 时显示红色徽章

## 网络检测（useNetworkStatus）

模块级单例。所有组件共享同一个连接状态：

```typescript
const state = ref<'idle' | 'connecting' | 'synced'>('idle')

// 自动检测
window.addEventListener('online', () => connect())
window.addEventListener('offline', () => state.value = 'idle')

// 手动连接
async function connect() {
  state.value = 'connecting'
  const ok = await ping()  // fetch /health，10 秒超时
  state.value = ok ? 'synced' : 'idle'
}
```

## 离线能力门控（useOffline）

用特征矩阵控制离线时什么能用、什么不能用：

```typescript
type Feature = 
  | 'feed.online' | 'pool' | 'schools'      // 网络独占 → 离线阻止
  | 'search.network'                         // 网络搜索 → 离线阻止
  | 'article.fork' | 'article.publish'       // fork/发布 → 离线阻止
  | 'editor.publish_pool'                    // 提交评审 → 离线阻止

canRead(feature): boolean   // 能不能读
canWrite(feature): boolean  // 能不能写（full | readonly | blocked）
```

离线时**完全可用**的功能：编辑草稿、编译预览、书签、本地搜索。

## Git Bundle Sync（核心同步协议）

不使用 REST 传输文件内容。用 Git 原生的 bundle 机制：

```
┌──────────┐                    ┌──────────┐
│  Tauri   │                    │  服务器  │
│  (本地)  │                    │  (远程)  │
└────┬─────┘                    └────┬─────┘
     │                               │
     │  GET /articles/{id}/head      │  1. 获取服务器 HEAD
     │◄──────────────────────────────│
     │                               │
     │  git bundle create            │  2. 创建增量包
     │  since_hash..HEAD             │     (本地 commits - 服务器已知)
     │                               │
     │  POST /articles/{id}/sync     │  3. 上传 + 合并
     │  (multipart bundle)           │
     │──────────────────────────────►│
     │                               │  git bundle verify
     │                               │  git fetch FETCH_HEAD
     │                               │  git merge --ff-only
     │                               │
     │◄──────────────────────────────│  4. 返回新 HEAD
     │                         200   │
     │                               │
     │  如果 409（冲突）：            │
     │  拉取服务器 bundle →          │
     │  apply → 然后重新 push        │
```

### 为什么用 bundle 而不是 REST

| 方式 | 问题 |
|------|------|
| REST 传文件内容 | 丢失 Git 历史，覆盖他人修改 |
| git bundle | 保留完整 commit DAG，ff-only 保证不丢数据 |

### 冲突处理

```
case 1: 服务器没有新 commit
  → 本地 bundle 直接 fast-forward merge → 成功

case 2: 服务器有新 commit，但本地是 ff 兼容的
  → 先拉服务器 bundle → apply → 再 push → 成功

case 3: 历史分叉（两个人都改了同一篇文章）
  → 服务器返回 409
  → 客户端回滚到服务器 HEAD
  → 用户的本地修改保存为 draft，不会丢
```

## 离线队列（useAutoSync）

```
用户在离线时编辑
  → local_store.rs: pending_push = 1
  → useAutoSync.pendingOps.push({ type: 'push', articleId })

网络恢复
  → useNetworkStatus.isSynced → true
  → App.vue watch 触发 useAutoSync.flush()
  → 顺序处理所有 pending ops
    → pushRepo()：git bundle sync
    → deleteOne()：REST DELETE
  → 成功的清掉，失败的保留等下次
```

## 单文章同步状态（useArticleSync）

每篇文章追踪自己的同步状态：

```
本地 HEAD == 服务器 HEAD → synced (绿色)
本地没有 server_article_id → upload (需要首次推送)
本地 HEAD != 服务器 HEAD && !offline → conflict (冲突)
网络断开 → offline (灰色)
正在检测 → loading
```

## 两层认证的同步挑战

Tauri 用本地 UUID，服务器用 JWT。同一个用户的 ID 在两端不同：

```
本地: account.id = "a1b2c3..." (本地 SQLite UUID)
服务器: user.id = "x9y8z7..." (服务器 User UUID)
        user 关联的 token = JWT (24h 过期)
```

`useUserStore` 处理这个映射：登录时 `trySyncServerAuth()` 用本地凭据在服务器注册/登录，获得服务器 JWT 和 UUID，存到 localStorage。

## 已知问题

1. **双重身份系统**。本地 UUID 和服务器 UUID 是两套——debug-follow-button-retrospective 的根因。
2. **冲突策略是本地覆盖服务器**。`sync-auto-push-design.md` 决定：本地是事实来源，冲突时本地胜出。这在多设备场景下可能丢数据。
3. **pending ops 没有持久化到后端**。离线队列只在 Rust 的 SQLite 里。如果用户切换设备，队列不会同步。
4. **/health ping 可能被防火墙拦截**。Tauri 的 CSP 限制了 `unsafe-eval`——issue #82。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 改同步协议 | `core/peerpedia_core/storage/git_backend.py` + `local_git.rs` |
| 改网络检测 | `frontend/src/composables/useNetworkStatus.ts` |
| 改离线队列 | `frontend/src/composables/useAutoSync.ts` + `local_store.rs` |
| 改冲突策略 | `useAutoSync.ts` 的 pushRepo() 和 409 处理 |
