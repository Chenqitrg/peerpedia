# System Map

> PeerPedia 全景图——由哪些部分组成、数据怎么流、边界在哪。

## PeerPedia 由哪些部分组成？

| 部分 | 技术 | 负责什么 | 入口 |
|------|------|----------|------|
| core | Python | DB models、CRUD、workflow、Git 存储、编译 | `core/peerpedia_core/` |
| backend | FastAPI | HTTP API、auth、路由 | `backend/peerpedia_api/main.py` |
| frontend | Vue 3 + TS | Web UI、编辑器、文章页 | `frontend/src/` |
| desktop | Tauri + Rust | 桌面壳、本地 Git、本地 SQLite | `frontend/src-tauri/` |
| database | SQLite | users/articles/reviews/bookmarks 等 | `peerpedia.db` |
| article storage | Git repos | 文章源码、历史、作者 | `~/.peerpedia/articles/{id}/` |
| compiler | Typst CLI + Python markdown | 源码 → HTML/SVG/PDF | `core/.../compiler.py` |

## 架构原则

- **Git 是事实来源，DB 是索引**
- 文章内容、评审数据（scores.json）、分数的权威版本永远在 Git 里
- DB 里的 articles.score、reviews 表是缓存——可以从 Git 重建
- 用户、关注、书签等纯关系数据只在 DB
- 每篇文章一个独立 Git repo——可以 fork、可以 merge、可以 bundle sync

## 核心数据流

### 1. 文章详情加载

```
ArticlePage.vue
  → GET /api/v1/articles/{id}
    → backend 路由
      → core build_article_detail()
        → articles table + article_authors join + users table
        → 编译缓存（compiled_output）或重新编译
      ← ArticleDetail JSON
  ← 渲染 title/authors/content/scores
```

### 2. 文章创建与发布

```
EditorPage.vue（用户写文章）
  → POST /api/v1/articles（创建 draft）
    → core create_article()
      → DB: insert article + article_authors
      → Git: init_article_repo() + commit_article()
  → 用户点"提交评审"
    → set_sink_start() → status = "sedimentation"
  → 沉淀期结束
    → publish_ready_articles() → status = "published"
```

### 3. 评审与评分

```
ArticlePage.vue（读者打分）
  → POST /api/v1/articles/{id}/reviews
    → core: insert Review（scores + thread）
    → compute_article_score() → 更新 Article.score
    → compute_author_reputation() → 更新 User.reputation
```

### 4. 同步（Tauri 桌面端 ↔ 服务器）

```
本地编辑 → commit 到本地 Git repo
  → 网络恢复
    → create_bundle(since_hash) → HTTP 上传
    → 服务器 apply_bundle() → ff-only merge
    ← 服务器 create_bundle() → 下载
    → 本地 apply_bundle()
```

## 已知高风险边界

1. **SQLite article_authors 和 Git history 可能不一致**——rebuild_article_authors 从 git log 扫作者，但如果 email 前缀对不上 user_id，关联就断了
2. **draft/pool/public 权限要统一**——目前 policies 在 backend 层（HTTPException），issue #88 要搬进 core
3. **repo_bundle 不可信**——apply_bundle 做了 verify 但没有内容审查
4. **v-html 渲染用户内容**——issue #76（phase-4-xss）做了 DOMPurify，但那个 PR 现在是 CLOSED
5. **Review.thread 和 MergeProposal.thread 是 JSON 列**——gpt_review P0-1，不能查询
6. **Article.compiled_* 字段是缓存混入主数据**——issue #81

## 接下来要看

- [01-core.md](01-core.md) — 深入 core 模块
- [02-backend.md](02-backend.md) — FastAPI 层怎么把 core 暴露成 HTTP
- [03-frontend.md](03-frontend.md) — 前端组件和状态管理
