# Learn

> 用自己的语言理解 PeerPedia。每个模块一个文件。

## 目录

| 文件 | 内容 |
|------|------|
| [00-system-map.md](00-system-map.md) | 系统全景图——模块、数据流、高风险边界 |
| [01-core.md](01-core.md) | Python 核心层——DB 模型、CRUD、workflow、Git 存储、编译管线 |
| [02-backend.md](02-backend.md) | FastAPI 层——40+ 端点、JWT 认证、bundle sync |
| [03-frontend.md](03-frontend.md) | Vue/TS 层——4 Pinia stores、16 composables、离线架构 |
| [04-tauri-desktop.md](04-tauri-desktop.md) | Tauri/Rust 层——62 IPC 命令、本地 SQLite、本地 Git |
| [05-database.md](05-database.md) | SQLite schema——7 实体 ER 图、JSON 列债务、迁移机制 |
| [06-compiler.md](06-compiler.md) | Typst/Markdown 编译管线——公式保护顺序、双后端 |
| [07-sync-network.md](07-sync-network.md) | 同步与网络模型——bundle sync 协议、离线队列、冲突策略 |
| [08-auth-identity.md](08-auth-identity.md) | 认证与身份——双 ID 问题、JWT vs 本地 auth、桥接层 |
| [decisions.md](decisions.md) | → 链接到 [../decisions/decisions.md](../decisions/decisions.md) |

## 不是文档

这些文件不是给别人看的，是给我自己看的。每写完一个模块，我对这个模块的理解就不再依赖"我记得好像是..."。
