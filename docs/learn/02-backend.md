# Backend 模块

> FastAPI 层。把 core 的能力翻译成 HTTP API。

## 一句话职责

**HTTP 翻译层。** 不包含业务逻辑——验证输入、调 core、返回 JSON。所有真正的决策在 core。

## 模块地图

```
backend/peerpedia_api/
├── main.py              # FastAPI app 创建、CORS、lifespan、路由注册
├── deps.py              # 依赖注入：JWT、密码、DB 会话、get_current_user
├── helpers.py           # 跨路由共享的工具函数
├── routes/              # 11 个路由模块
│   ├── auth.py          # 注册、登录、me
│   ├── articles.py      # 文章 CRUD、Git 操作、bundle sync
│   ├── reviews.py       # 评审 CRUD、讨论串
│   ├── users.py         # 用户 CRUD、关注/取关
│   ├── pool.py          # 沉淀池动态
│   ├── bookmarks.py     # 书签 CRUD
│   ├── feed.py          # 关注者动态 + 轻量缓存
│   ├── search.py        # 全文搜索（SQL + 源文件回退）
│   ├── compile.py       # 编译预览 + 下载
│   ├── citations.py     # 引用图
│   └── merge.py         # 合并提议
└── schemas/             # Pydantic 请求/响应模型
    ├── auth.py          # RegisterRequest, LoginRequest, AuthResponse
    ├── article.py       # ArticleDetail, ArticleSummary, ArticleCreate
    ├── user.py          # UserProfile, UserSummary
    └── review.py        # ReviewCreate, ReviewOut, ThreadMessage
```

## 应用启动流程

```
main.py: lifespan()
  ├── 读 PEERPEDIA_DB 环境变量（默认 sqlite:///peerpedia.db）
  ├── init_db() → 建表
  ├── migrate_db() → 跑迁移
  └── 启动后台任务 _auto_publish_loop()
       └── 每 60 秒调一次 publish_ready_articles()
```

注意：**迁移是启动时自动跑的，没有单独的 migration 命令。** 这是已知风险——如果迁移出错，应用起不来。

## C3: Backend 组件依赖

```
                     ┌──────────────┐
                     │   main.py    │  ← 创建 app、注册路由、启动任务
                     └──────┬───────┘
                            │ include_router() 注册 11 个模块
          ┌─────┬─────┬─────┼─────┬─────┬─────┬─────┬─────┬─────┐
          ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼
        auth arti- revi- users pool book- feed search comp- cita- merge
             cles  ews              marks            ile   tions
          │     │     │     │     │     │     │     │     │     │
          └─────┴─────┴─────┴──┬──┴─────┴─────┴─────┴─────┴─────┘
                               │ 所有 route 都依赖
                               ▼
                    ┌──────────────────┐
                    │     deps.py      │  ← 依赖注入枢纽
                    │ get_current_user │
                    │ require_user     │
                    │ get_db           │
                    │ hash_password    │
                    └────────┬─────────┘
                             │ 依赖
                             ▼
                    ┌──────────────────┐
                    │      core/       │  ← 业务逻辑
                    └──────────────────┘
```

箭头约定：`A ──► B` = A 依赖 B。

- **main.py 依赖所有 route**：通过 `include_router` 注册
- **所有 route 依赖 deps.py**：通过 `Depends()` 注入 JWT、DB、密码
- **deps.py 依赖 core**：get_db 调 core 的 engine，密码验证调 core 的 crud_user
- **routes 之间互不依赖**：一个 route 需要其他功能时调 core，不调另一个 route

## 认证系统

### JWT

- 算法 HS256，24 小时过期
- 密钥从 `JWT_SECRET` 环境变量读取（开发默认为 `peerpedia-dev-secret`）
- `create_token(user_id)` → `{"sub": user_id, "iat": ..., "exp": ...}`
- `decode_token(token)` → `user_id` or `None`

### 两级认证

| 级别 | 函数 | 行为 |
|------|------|------|
| 可选 | `get_current_user` | 有 token 就解析，没有就返回 None |
| 必需 | `require_user` | 无 token → 401 |

可选认证的妙处：`GET /articles` 在未登录时返回公开数据，登录后额外返回"你是否收藏了这篇文章"。

### 密码

- bcrypt 哈希和验证
- 用户名规则：3-32 字符，`[a-zA-Z0-9_]`
- 密码最少 6 字符

## 端点全景

**40+ 个端点**，按功能分组：

```
/api/v1/
├── auth/              # 注册、登录、me（3 个）
├── articles/          # CRUD + Git + 发布 + 下载（15 个）
├── reviews/           # 评审 CRUD + 讨论串（3 个）
├── users/             # 用户 CRUD + 关注（8 个）
├── pool/              # 沉淀池（1 个）
├── bookmarks/         # 书签 CRUD（3 个）
├── feed/              # 动态 + 缓存（2 个）
├── search/            # 全文搜索（1 个）
├── compile-preview/   # 实时编译预览（1 个）
├── compile-download/  # 编译下载（1 个）
├── citations/         # 引用图 + 点击（2 个）
└── merge-proposals/   # 合并提议（4 个）
```

## Bundle Sync 流程（核心同步机制）

```
客户端（Tauri）                         服务器（FastAPI）
     │                                      │
     │  GET /articles/{id}/head             │  获取服务器 HEAD
     │◄─────────────────────────────────    │
     │                                      │
     │  git bundle create since..HEAD       │  创建增量包
     │                                      │
     │  POST /articles/{id}/sync            │  上传 bundle
     │  ─────────────────────────────────►  │
     │                                      │  git bundle verify
     │                                      │  git fetch + merge --ff-only
     │                                      │  409 如果冲突 → 客户端回滚
     │◄─────────────────────────────────    │
```

## 数据流：一次文章请求经过什么？

```
GET /api/v1/articles/{id}
  → deps.get_current_user()  ← 从 Header 解析 token（可选）
  → deps.get_db()            ← 创建 SQLAlchemy session
  → routes/articles.py:get_article()
    → crud_article.get_article(session, id)
    → crud_article.get_author_ids(session, id)
    → crud_review.get_reviews_for_article(session, id)
    → 如果已登录：crud_bookmark.is_bookmarked(session, user_id, id)
    → 组装成 ArticleDetail schema 返回
  ← JSON response
```

## 已知问题

1. **迁移自动跑**。没有 `alembic`，没有版本控制。`migrate_db()` 是手写的 Python 代码，直接 ALTER TABLE。
2. **路由文件太大**。`articles.py` 单个文件处理了 15 个端点，包含 Git 操作、同步、发布、下载。
3. **helpers.py 职责不明确**。跨路由共享的工具函数混在一起。
4. **CORS 硬编码**。`localhost:5173`、`localhost:5174`、`tauri://localhost` 写死在 main.py 里。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 加新端点 | `routes/` 下找对应文件，或新建 |
| 改认证逻辑 | `deps.py` |
| 改 JWT 配置 | `deps.py` 顶部常量 |
| 改 CORS | `main.py` 的 `CORSMiddleware` |
