# System Map

> C4 模型：C1 系统上下文 → C2 容器 → C3 组件。每个模块的 C3 图见 01-08。

## C1: 系统上下文

```
                    ┌──────────────────────┐
                    │      读者/作者        │
                    │    (学术用户)         │
                    └────┬────────────┬────┘
                         │ 浏览、搜索、   │ 写作、提交评审
                         │ 评审、fork     │
                         ▼               ▼
     ┌──────────────────────────────────────────────┐
     │              PeerPedia                       │
     │                                              │
     │  同行评审即基础设施。Git 存储 + 沉淀池评审。     │
     └──────────┬───────────────────────┬───────────┘
                │                       │
                │ 编译文章               │ 同步文章
                ▼                       ▼
     ┌──────────────┐        ┌──────────────────┐
     │  Typst CLI   │        │  远程服务器        │
     │  (外部工具)   │        │  (bundle sync)    │
     └──────────────┘        └──────────────────┘
```

- **用户**：学术作者和读者。通过浏览器或 Tauri 桌面端使用。
- **Typst CLI**：外部编译工具。PeerPedia 调用它把 .typ 源码编译为 SVG/PDF。
- **远程服务器**：同一个 PeerPedia 的另一实例。通过 git bundle sync 交换文章。

## C2: 容器

```
  ┌──────────────────────────────────────────────────────────┐
  │                     用户设备                             │
  │                                                          │
  │  ┌──────────────────────┐    ┌──────────────────────┐   │
  │  │    Web 浏览器         │    │   Tauri 桌面          │   │
  │  │  (Vue 3 SPA)         │    │  (Rust + WebView)     │   │
  │  │                      │    │                       │   │
  │  │  • 文章浏览/搜索       │    │  • 离线编辑            │   │
  │  │  • 编辑器             │    │  • 本地 Git            │   │
  │  │  • 评审/评分           │    │  • 本地 SQLite         │   │
  │  │  • 调用服务器 API      │    │  • 网络恢复后同步       │   │
  │  └──────────┬───────────┘    └───────────┬───────────┘   │
  │             │ HTTP                        │ IPC + fs      │
  └─────────────┼─────────────────────────────┼──────────────┘
                │                             │
                ▼                             ▼
  ┌──────────────────────┐    ┌──────────────────────────────┐
  │   FastAPI 服务器      │    │    本地文件系统                │
  │                      │    │                              │
  │  • REST API (40+)    │    │  ~/.peerpedia/articles/{id}/  │
  │  • JWT 认证           │    │    ├── .git/                 │
  │  • Bundle sync        │    │    ├── article.md/.typ       │
  │  • 自动发布            │    │    ├── article.json          │
  └──────────┬───────────┘    │    └── reviews/               │
             │                │        ├── scores.json        │
             ▼                │        └── thread.md          │
  ┌──────────────────────┐    └──────────────────────────────┘
  │   SQLite 数据库       │
  │                      │
  │  • 用户/关注/书签     │
  │  • 文章元数据缓存      │
  │  • 评审缓存           │
  └──────────────────────┘
```

核心关系：
- **浏览器 → FastAPI**：HTTP REST，JWT 认证
- **Tauri → 本地文件系统**：直接读写 Git repo + SQLite
- **Tauri → FastAPI**：HTTP bundle sync（网络可用时）
- **FastAPI → SQLite**：SQLAlchemy，缓存读、DB-only 实体的读写
- **FastAPI → Typst CLI**：子进程调用，编译 .typ 文件

## C3: 组件

每个容器的内部组件图见对应文件：

| 容器 | C3 图 | 关键组件 |
|------|-------|----------|
| FastAPI 服务器 | [02-backend.md](02-backend.md) | main.py → 11 routes → deps.py → core |
| 浏览器 SPA | [03-frontend.md](03-frontend.md) | App.vue → pages → stores + composables → api |
| Tauri 桌面 | [04-tauri-desktop.md](04-tauri-desktop.md) | main.rs → commands.rs → 5 模块 |
| Core 业务层 | [01-core.md](01-core.md) | workflow → storage/db + storage/git + storage/compiler |
| SQLite 数据库 | [05-database.md](05-database.md) | 7 实体 ER 图 |
| 编译管线 | [06-compiler.md](06-compiler.md) | detect → extract → Typst/Markdown → CompileResult |
| 同步协议 | [07-sync-network.md](07-sync-network.md) | networkStatus → offline → autoSync → bundle |
| 认证系统 | [08-auth-identity.md](08-auth-identity.md) | 本地 bcrypt / 服务器 JWT / useUserStore 桥接 |

## 架构原则

- **Git 是事实来源，DB 是索引**
- 文章内容、元数据、评审、分数的权威版本永远在 Git
- DB 里的 articles、reviews、article_authors 是缓存，可从 Git 重建
- 只有 users/follows/bookmarks/citations/merge_proposals 是纯 DB 数据
- 每篇文章一个独立 Git repo——可以 fork、merge、bundle sync

## 已知高风险边界

1. SQLite article_authors 和 Git history 可能不一致
2. policies 在 backend 层（HTTPException），issue #88 要搬进 core
3. repo_bundle 不可信——apply_bundle 做了 verify 但没有内容审查
4. v-html 渲染用户内容——phase-4-xss 的 PR 已关闭
5. Review.thread 和 MergeProposal.thread 是 JSON 列——不能查询
6. Article.compiled_* 字段是缓存混入主数据——issue #81
