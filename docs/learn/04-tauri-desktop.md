# Tauri Desktop 模块

> Rust 层。Tauri 桌面壳——本地 SQLite、本地 Git、IPC 桥接。

## 一句话职责

**给 PeerPedia 一个桌面版本。** 不连接服务器时，所有操作在本地完成——本地账号、本地草稿、本地 Git。网络恢复后通过 bundle sync 推送。

## C3: Tauri 组件依赖

```
   ┌──────────────────────────────────────┐
   │           前端 JS 层                  │  ← Vue 组件 + composables
   │  invoke("git_commit", {...})         │     通过 invoke() 调 IPC
   └────────────────┬─────────────────────┘
                    │ 依赖（invoke）
                    ▼
   ┌──────────────────────────────────────┐
   │            main.rs                   │  ← 入口：打开 SQLite、注册 62 个命令
   │  AppState { db: Mutex<Connection> }  │
   └────────────────┬─────────────────────┘
                    │ 注册所有 IPC handler
                    ▼
   ┌──────────────────────────────────────┐
   │           commands.rs                │  ← 62 个 IPC 命令入口
   └────┬──────┬──────┬──────┬──────┬─────┘
        │      │      │      │      │
        │ 依赖 │ 依赖 │ 依赖 │ 依赖 │ 依赖
        ▼      ▼      ▼      ▼      ▼
   ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
   │local_  ││local_  ││local_  ││  db.rs ││ error  │
   │auth.rs ││store.rs││git.rs  ││ 迁移 v10││ .rs    │
   │bcrypt  ││SQLite  ││git CLI ││        ││AppError│
   │会话管理 ││CRUD    ││封装    ││        ││5 变体  │
   └────────┘└────────┘└────────┘└────────┘└────────┘
        ▲         ▲         ▲
        └─────────┴─────────┘
        模块之间互不依赖，只通过 commands.rs 被调用
```

箭头约定：`A ──► B` = A 依赖 B（A import B、A 调 B）。

- **前端 JS 依赖 main.rs**：通过 Tauri IPC bridge
- **main.rs 依赖 commands.rs**：注册 62 个 handler
- **commands.rs 依赖 5 个模块**：每个命令委托给对应的模块
- **5 个模块互不依赖**：local_auth 不调 local_store，local_git 不调 db

## 模块地图

```
frontend/src-tauri/
├── Cargo.toml             # Rust 依赖
├── tauri.conf.json         # Tauri 窗口配置、CSP
├── src/
│   ├── main.rs             # 二进制入口：打开 SQLite、注册 62 个 IPC 命令
│   ├── lib.rs              # crate 根：导出 AppState
│   ├── commands.rs         # 62 个 IPC 命令处理器（~750 行）
│   ├── local_auth.rs       # 本地 bcrypt 认证 + 会话管理
│   ├── local_store.rs      # SQLite CRUD：草稿、缓存、历史（~1000 行）
│   ├── local_git.rs        # Git CLI 封装（~1100 行）
│   ├── db.rs               # SQLite 迁移（当前版本 10，~620 行）
│   └── error.rs            # 统一 AppError 枚举
├── tests/
│   └── test_commands.rs    # 集成测试
└── icons/
    └── icon.png
```

## Rust 依赖

| crate | 用途 |
|-------|------|
| `tauri 2` | 桌面框架 |
| `rusqlite 0.31` (bundled) | 本地 SQLite |
| `bcrypt 0.15` | 密码哈希 |
| `uuid 1` (v4) | 账号/草稿 ID 生成 |
| `serde` / `serde_json` | 序列化 |
| `base64 0.22` | bundle/导出编码 |
| `tokio 1` | 异步互斥锁 + 运行时 |

**没有网络栈。** 所有网络操作走前端的 JavaScript 层。

## IPC 命令分类（62 个）

### 认证（4）
`create_account`, `login`, `logout`, `list_accounts`

本地 bcrypt 认证，与服务器认证独立。会话令牌是 UUID v4，存在本地 `sessions` 表。

### 草稿（7）
`save_draft`, `list_drafts`, `get_draft`, `delete_draft`, `delete_article`, `search_drafts`, `get_pending_ops`

FTS5 全文搜索。按 `account_id` 隔离。`pending_push`/`pending_delete` 标志追踪离线队列。

### 文章缓存（4）
`cache_article`, `get_cached_article`, `get_cached_article_ids`, `cache_article_full`

离线阅读快照。已发布文章最多缓存 10MB，书签文章最多 20MB。

### 浏览历史（2）
`record_visit`, `get_history`

按账户隔离，支持分页。

### Git 操作（10）
`git_init`, `git_commit`, `git_history`, `git_show`, `git_diff`, `git_rollback`, `git_reset_hard`, `git_bundle_create`, `git_bundle_apply`, `git_update_meta`

所有 Git 操作通过 `spawn_blocking` 运行（GitPython 是同步的）。不操作数据库，直接操作文件系统。

### 同步（4）
`git_bundle_create`, `git_bundle_apply`, `clear_pending`, `set_pending_delete`, `set_pending_push`

### 编译 + 导出（3）
`compile_typst`, `compile_typst_pdf`, `export_article`

调用 `typst` CLI 子进程。`export_article` 创建 base64 编码的 tar.gz。

## 本地 Git 存储

```
~/.peerpedia/articles/{article_id}/
├── .git/                  # 完整 Git 仓库
├── article.md             # Markdown 格式的文章内容
├── article.typ            # Typst 格式的文章内容
└── article.json           # 元数据（标题、摘要、关键词、状态）
```

**每次保存草稿都是一次 git commit。** 作者的 email 格式为 `{uuid}@peerpedia`。

回滚不是 `git reset`，而是在历史之上创建一个新的 revert commit。

## SQLite 迁移（版本 10）

`db.rs` 通过手写迁移管理 schema 版本：

| 版本 | 内容 |
|------|------|
| 0-3 | local_accounts, drafts, article_cache, browsing_history |
| 4-8 | sessions, FTS 触发器, schema_version 表 |
| 9 | 重写 drafts 表：添加 pending_push/delete/offline_since，删除 server_article_id/commit_hash |
| 10 | 修复 v9 重写时丢失的 FTS 触发器 |

## 与 core 的关系

Tauri 层**不是** core 的替代。它是 core 的本地执行环境：

```
Tauri 桌面端                      服务器
────────────                      ──────
local_auth.rs  ← 独立实现      →  deps.py（服务器 JWT）
local_store.rs ← 独立实现      →  crud_*.py（服务器 SQLAlchemy）
local_git.rs   ← 与 core/git_backend.py 平行
db.rs          ← 独立的 schema，不共享
```

## 已知问题

1. **两套认证系统**。Tauri 用本地 bcrypt + UUID session，服务器用 JWT。同一个用户的 local UUID 和 server UUID 不同——这是 follow button 调试 12 轮的根因（debug-follow-button-retrospective）。
2. **没有共享 schema**。Tauri 的 SQLite schema 和 core 的 SQLAlchemy models 各自定义，各自迁移。
3. **Git CLI 依赖**。必须安装 `git` 命令行工具。不能用 libgit2。
4. **commands.rs 750 行**。62 个命令在一个文件里。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 加新 IPC 命令 | `commands.rs` + `main.rs` 的 `invoke_handler` |
| 改本地认证 | `local_auth.rs` |
| 改草稿存储 | `local_store.rs` |
| 改 Git 操作 | `local_git.rs` |
| 加 schema 迁移 | `db.rs` 加新版本号 |
