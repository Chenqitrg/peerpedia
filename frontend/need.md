# PeerPedia 前端需求文档

> 最后更新：2026-06-05（当日修订：评审系统、自评匿名保护、commit message 必填、池内/池外评审独立）

---

## 1. 设计哲学

- **色调**：暗色、严肃，GitHub 风格配色
- **工具栏**：窄长、高级感，苹果风格
- **字体**：数学风格（衬线数学 + 无衬线 UI）
- **原则**：不绚丽，突出内容
- **对标**：编辑页参考 Overleaf；文章页参考 Google Scholar；历史页参考 VS Code GitHub 插件 commit 图

---

## 2. 系统架构

```
frontend/ (Vue 3 + Vite, port 5173)  →  HTTP JSON  →  backend/ (FastAPI, port 8080)  →  core/ (peerpedia_core)
```

### 2.1 API 契约位置

| 层 | 路径 | 角色 |
|----|------|------|
| 后端 Schemas | `backend/peerpedia_api/schemas/` | Pydantic 模型，权威数据形状 |
| 后端 Routes | `backend/peerpedia_api/routes/` | 11 个路由模块，REST 端点 |
| 前端 Types | `frontend/src/api/types.ts` | TypeScript 接口，消费者镜像 |
| 前端 API | `frontend/src/api/*.ts` | 8 个 API 模块，axios 调用封装 |
| 核心逻辑 | `core/peerpedia_core/` | 业务层 + 存储层 + 工作流 |

### 2.2 当前 API 端点清单

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | ✅ 注册（username + password + email + name） |
| POST | `/auth/login` | ✅ 登录（username + password） → JWT token |
| GET | `/auth/me` | ✅ 当前用户（Bearer token 恢复会话） |
| GET | `/articles` | ✅ 文章列表（`?status=`, `?author_id=`, `?page=`, `?size=`） |
| GET | `/articles/{id}` | ✅ 文章详情 |
| POST | `/articles` | ✅ 创建文章 🔒 |
| PUT | `/articles/{id}` | ✅ 编辑文章 🔒 |
| PUT | `/articles/{id}/sink-extension` | ✅ 延期出池 |
| GET | `/articles/{id}/history` | ✅ 提交历史（含 parents + per-commit score） |
| GET | `/articles/{id}/diff/{h1}/{h2}` | ✅ 两提交 diff |
| POST | `/articles/{id}/fork` | ✅ 派生文章 |
| POST | `/articles/{id}/rollback/{hash}` | ✅ 回滚到历史版本 |
| GET | `/articles/{id}/reviews` | ✅ 评审列表（含 reviewer_name + author_name 解析） |
| POST | `/articles/{id}/reviews` | ✅ 提交评审 🔒（JWT，池内/池外独立记录，池内评审出池后冻结） |
| POST | `/articles/{id}/reviews/{rid}/messages` | ✅ 评审线程消息 🔒（JWT，作者 rebuttal） |
| GET | `/articles/{id}/citations` | ✅ 引用关系 |
| POST | `/articles/{id}/merge-proposals` | ✅ 创建汇合提案 |
| GET | `/articles/{id}/merge-proposals` | ✅ 汇合提案列表 |
| POST | `/articles/{id}/merge-proposals/{pid}/accept` | ✅ 接受汇合 |
| POST | `/articles/{id}/merge-proposals/{pid}/reject` | ✅ 拒绝汇合 |
| GET | `/articles/{id}/source` | ✅ 获取文章源码 |
| GET | `/articles/{id}/download/source` | ✅ 下载源码文件 |
| GET | `/articles/{id}/download/pdf` | ✅ 下载 PDF/HTML（Typst→PDF, Markdown→HTML） |
| POST | `/compile-download` | 🟡 编译当前编辑器内容并下载（新建文章时用） |
| GET | `/users` | ✅ 用户列表（含 article_count + reputation） |
| POST | `/users` | ✅ 创建用户 |
| GET | `/users/{id}` | ✅ 用户详情 |
| PUT | `/users/{id}` | ✅ 编辑资料 🔒（仅本人） |
| GET | `/users/{id}/followers` | ✅ 粉丝列表 |
| GET | `/users/{id}/following` | ✅ 关注列表 |
| POST | `/users/{id}/follow` | ✅ 关注用户 |
| DELETE | `/users/{id}/follow` | ✅ 取关用户 |
| GET | `/pool` | ✅ 沉淀池文章 |
| GET | `/bookmarks` | ✅ 收藏列表 🔒 |
| POST | `/bookmarks` | ✅ 添加收藏 🔒 |
| DELETE | `/bookmarks/{id}` | ✅ 取消收藏 🔒 |
| GET | `/feed` | ✅ 关注动态 |
| GET | `/search?q=` | ✅ 搜索文章 |
| POST | `/compile-preview` | ✅ 编译预览（Markdown→HTML, Typst→SVG） |
| POST | `/citations/click` | ✅ 记录引用点击 |

🔒 = 需要 Bearer Token 认证

### 2.3 核心数据形状

**文章（Article）：**
- ID：UUID 字符串
- 每个文章是一个独立的 git 仓库（`~/.peerpedia/articles/{id}/`）
- 每次编辑 = 一次 git commit
- 每次 commit 有独立的评审和评分（per-commit independent scoring）
- Article 级别的 `score` 缓存最新 commit 的评分
- 自评（self-review）与 commit 绑定，权重 0.15；社区评审权重 0.85
- 每次 commit 必须携带 commit_message（必填），映射为 git commit message

**评审（Review）：**
- 唯一约束：`(article_id, reviewer_id, scope, commit_hash)` — 每人每 commit 每 scope 一条
- scope：`"pool"`（池内匿名）或 `"published"`（实名）
- `reviewer_id` 由服务端从 JWT 提取，客户端不传 ✅
- 包含 5 维评分 + 评论线程 + 自评标记 ✅
- Thread 消息存储在 Review 的 `thread` 字段（JSON 数组），每条消息含 `author_id`、`content`、`created_at` ✅
- Thread 回复权限：文章作者 + 该评审的评审人可回复，旁观者只读 ✅

**ReviewOut 数据形状（前后端一致）：**
```typescript
{
  id: string
  article_id: string
  commit_hash: string
  reviewer_id: string        // 服务端从 JWT 设置
  scope: "pool" | "published"
  scores: { originality: number, rigor: number, completeness: number, pedagogy: number, impact: number }
  contributions?: { [authorId: string]: FiveDimScores } | null  // 仅自评
  thread: { author_id: string, author_name: string, content: string, created_at: string }[]
  reviewer_name: string      // 根据 scope 解析实名/匿名
  is_self_review: boolean
  created_at: string
  updated_at: string
}
```

**用户（User）：**
- `username`：唯一登录标识 ✅
- `password_hash`：bcrypt 密码哈希 ✅
- `email`：邮箱，注册时收集，格式验证 ✅
- 4 维声誉（professionalism, objectivity, collaboration, pedagogy）
- 匿名名（池内显示）+ 实名（已发表后显示）
- `avatar_url`、`contact` 字段 ✅

**UserSummary 数据形状（GET /users 返回）：**
```typescript
{
  id: string
  name: string
  anonymous_name: string
  affiliation?: string
  expertise: string[]
  avatar_url?: string | null
  article_count: number        // 文章数量（按作者列表匹配）
  reputation: {                // 4 维声誉分数，空对象表示无数据
    professionalism: number
    objectivity: number
    collaboration: number
    pedagogy: number
  }
}
```

---

## 3. 页面需求

### 3.1 首页

**未登录状态**：
- 纯欢迎页：品牌 Logo + 标语 + 简短平台介绍
- "Sign In" 和 "Create Account" 两个按钮，点击弹出认证弹窗
- **工具栏仅显示**：Logo + "Sign In" 按钮
- **不显示**：搜索、书签、沉淀池、新建文章

**已登录状态**：
- 当前 Feed 实现（关注人的文章列表）
- 工具栏完整显示：Logo + 搜索 + 书签 + 头像（点击弹出小弹窗：用户名 + Logout）+ 新建 + 沉淀池
- 分页加载，使用页码

**API 需求：**
- `GET /feed?page=1&size=20`（需新增分页参数）
- 每篇文章需返回完整 Article Bar 所需字段（见 §4.1）
- 需传入当前用户 ID 以判断 `is_bookmarked` 和 `is_own_article`

---

### 3.2 编辑页

参照 Overleaf 布局。🔒 需要登录后才能访问。

**布局**：
- 编辑器页面使用**全宽布局**（`max-w-full`，突破全局 `max-w-content` 限制），仅保留极窄边距
- 左侧代码编辑器（textarea），右侧实时预览
- 中间分隔条**可拖拽**调整左右比例（mousedown/mousemove/mouseup），范围 20%-80%

**工具栏**（编辑器上方）：
- MD / Typst 格式切换
- 编译按钮（调用 `/compile-preview`，Markdown→HTML, Typst→SVG）
- **左侧区域：下载源码按钮**（`FileDown` 图标）
  - 已保存文章：`GET /articles/{id}/download/source`
  - 新建文章：客户端 Blob 下载当前编辑器内容为 `.md` / `.typ` 文件
- **右侧区域：下载 PDF 按钮**（`FileText` 图标）
  - 已保存文章：`GET /articles/{id}/download/pdf`（Typst→PDF, Markdown→HTML 文件）
  - 新建文章：`POST /compile-download`（传入当前内容 + format，编译后返回文件）
- 暂存按钮（localStorage）
- 发布按钮

**发布流程**：
1. 点击右上角"发布"按钮
2. 进入自评栏（弹窗或侧面板）：
   - **Commit message**（必填，不写不给过 — 模拟 Git 提交信息）
   - 5 维自评分数（originality, rigor, completeness, pedagogy, impact）
   - 关键词标签
   - 领域/分类
   - 摘要
   - （多作者时）各作者贡献比例 — 5 维，每维全员总和 = 1.0
   - "发布到沉淀池"按钮

**发布后**：新 commit → 自动进沉淀池 → 自评作为该 commit 的评审

**编译与下载规格**：
| 操作 | Markdown 输出 | Typst 输出 |
|------|-------------|-----------|
| 预览（`/compile-preview`） | HTML | SVG |
| 下载源码（`/download/source`） | `.md` 原始文件 | `.typ` 原始文件 |
| 下载 PDF（`/download/pdf` 或 `/compile-download`） | 编译后的 HTML 文件 | 编译后的 PDF 文件 |

**API 需求：**
- `POST /articles`（新建）
- `PUT /articles/{id}`（编辑，新 commit）
- `POST /compile-preview`（实时编译预览，Markdown→HTML, Typst→SVG）
- `GET /articles/{id}/source`（🆕 加载已有文章内容到编辑器）
- `GET /articles/{id}/download/source`（🆕 下载源码文件）
- `GET /articles/{id}/download/pdf`（🆕 下载 PDF/HTML 编译文件）
- `POST /compile-download`（🆕 新建文章时编译并下载，body: `{content, format}`）

---

### 3.3 文章页

参照 Google Scholar 文章页。

**上方窄栏**（文章元数据）：
| 元素 | 行为 |
|------|------|
| 标题 | 纯文本展示 |
| 作者列表 | 每人可点击 → 跳转用户页；显示各人贡献比例（5 维雷达图，hover 展开） |
| 历史入口 | 点击 → 跳转文章历史页 |
| 5 维评分雷达图 | 点击 → 展开详细评分数据（含各维度各评审人的分） |
| 引用关系 | 点击 → 进入独立引用页面（本文引用的 + 引用本文的） |
| 派生按钮 | 点击 → 跳转编辑页，自动创建该文章的 fork |
| 汇合按钮 | 仅当用户已派生过此文章时显示，点击 → 发起汇合请求 |
| 状态标签 | "沉淀中"（可点击→沉淀池）或"已发表" |
| 收藏按钮 | 星形 toggle |
| **下载源码按钮** | 🆕 下载文章的 `.md` / `.typ` 源文件 |
| **下载 PDF 按钮** | 🆕 下载编译后的 PDF（Typst→PDF, Markdown→HTML） |
| 编辑按钮 | 仅文章作者可见，点击 → 跳转编辑页 |
| 延期按钮 | 仅文章作者 + 处于沉淀中时显示，点击 → 延期 7 天 |

**下方**（双选项卡切换）：
- **正文选项卡**：文章编译预览，横向撑满屏幕。编译后的 Typst SVG / Markdown HTML 渲染。
- **评论选项卡**：
  - 登录用户（非作者）未评审过：显示五维星星 + 评论文本框 + 提交按钮 ✅
  - 已评审过：显示五维分数数字（O:4 R:3 C:5），自己的评审 hover 分数可展开为可编辑星星，移开恢复数字 ✅
  - 自己的评审始终置顶（accent 色左边框 + "(you)" 标签）✅
  - 所有评审都带 Thread 下拉抽屉（Chevron 展开/折叠），iMessage 风格聊天气泡 ✅
  - Thread 回复权限：仅文章作者 + 该评审的评审人可回复；旁观者看到 "仅作者和评审人可参与" 提示 ✅
  - 自己评审无 Thread 时：显示输入框可发起对话 ✅
  - 作者自评置顶，左侧 accent 色边框，标签 "Author (self-review)"，始终实名 ✅
  - 池内评审显示匿名名，出池后匿名不变（防止交叉对比泄露身份）✅
  - 未登录用户看到 "Sign in to submit a review" 提示 ✅
  - 页面顶部窄栏的评论入口（带评论数）点击后切换到此选项卡 ✅

**API 需求：**
- `GET /articles/{id}`（详情 + 分数 + 编译输出）
- `GET /articles/{id}/source`（🆕 获取原始源码用于展示）
- `GET /articles/{id}/reviews`（评论列表，含贡献数据）
- `GET /articles/{id}/citations`（引用图）
- `GET /articles/{id}/has-forked?user_id=X`（🆕 判断是否已派生）
- `PUT /articles/{id}/sink-extension`（延期，已有）
- `POST /articles/{id}/fork`（派生，已有）
- `GET /articles/{id}/download/source`（🆕 下载源码，已有端点）
- `GET /articles/{id}/download/pdf`（🆕 下载 PDF/HTML，已有端点）
- `POST /bookmarks` / `DELETE /bookmarks/{id}`（收藏，已有）

---

### 3.4 用户页

**上方**：
- 用户头像
- 用户名 + 匿名名（仅本人可见自己的匿名名）
- 4 维声誉雷达图（professionalism, objectivity, collaboration, pedagogy）
- 粉丝数 / 关注数（数字），点击展开列表，列表中每人可点击跳转到用户页
- 联系方式（邮箱/网站等）
- 机构
- **编辑资料按钮**（仅本人可见）→ 可修改匿名名、头像、联系方式、机构、专业领域；用户名不可修改

**下方**：
- 该用户的所有文章，以 Article Bar 列表展示，横向撑满

**API 需求：**
- `GET /users/{id}`（用户详情）
- `GET /users/{id}/followers`（已有）
- `GET /users/{id}/following`（已有）
- `PUT /users/{id}`（🆕 编辑资料，name 不可改）
- `GET /articles?author_id={id}`（🆕 按作者查文章）

---

### 3.5 沉淀池

**目标**：筛选高质量文章。越靠近出池时间，文章越往下"沉"。

**排序**：按出池时间**降序**（剩余天数多的在上面，快出池的在下面——视觉上"沉下去"）。

**可见范围**：只显示"我关注的人"和"关注我的人"的文章。不是公开池。

**展示**：Article Bar 列表。

**API 需求：**
- `GET /pool?user_id=X&page=1&size=20`（🆕 加 user_id 过滤 + 分页）
- 后端过滤逻辑：取 user 的 following + followers 的 ID 集合，只返回这些作者的 sedimentation 文章
- 排序：`days_remaining` 降序

---

### 3.6 文章历史页

参照 VS Code GitHub 插件 commit 图。

**功能**：
- 显示文章 commit 图（含分支）
- 点击任意两个节点 → 下方显示 diff（横向撑满）
- 每个 commit 节点显示：短哈希、提交信息、作者、时间戳、该 commit 的评分
- 可以回滚到任意历史版本

**diff 预览**：使用 diff2html，side-by-side 模式。

**API 需求：**
- `GET /articles/{id}/history`（已有，🆕 需在 commit 对象中加 `parents` 字段以支持分支图）
- `GET /articles/{id}/diff/{hash1}/{hash2}`（已有）
- `POST /articles/{id}/rollback/{hash}`（已有）

---

### 3.7 认证与授权

**认证机制**：
- JWT token，24h 过期，前端存 `localStorage`
- 登录标识：`username`（唯一，与显示名 `name` 分离）
- 密码：bcrypt 加密存储
- 邮箱：注册时收集，格式验证（MVP 不发送验证邮件）

**认证弹窗**（`AuthModal.vue`）：
- 双选项卡：**Log In** / **Create Account**
- Login tab：username + password 输入框 + "Log In" 按钮
- Register tab：username + password + email + display name + "Create Account" 按钮
- 错误提示（用户名已存在、密码错误等）
- 点击弹窗外或关闭按钮可关闭

**NavBar 认证状态**：
```
未登录：[Logo]                                              [Sign In]
已登录：[Logo] [Search] [Pool] [Bookmark] [+]   [Avatar▼]
                                                       └─ Logout
```
- 点击头像 → 弹出小弹窗（popover），显示 username  + "Logout" 按钮
- 注销后清除 token 和 viewer，回到欢迎页

**路由守卫**：
- 以下路由需要登录：`/edit`、`/edit/:id`、`/bookmarks`、`/pool`
- 未登录访问上述路由 → 重定向到首页 → 弹出认证弹窗
- 登录成功后跳回原目标路由

**API 端点**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册。body: `{username, password, email, name}` → `{user, token}` |
| POST | `/auth/login` | 登录。body: `{username, password}` → `{user, token}` |
| GET | `/auth/me` | 获取当前用户（Bearer token 携带）→ `{user}` |

---

## 4. 文章 Bar 组件规范

Article Bar 是跨页面复用的文章缩略组件，出现在搜索、首页、用户页、沉淀池、收藏夹。

### 4.1 布局

```
┌──────────────────────────────────────────────────────────────┐
│ 📄 文章标题（粗体，大）                                       │
│ 👤 Alice, Bob                            [forked] [v3 编辑]  │
│ 📝 内容预览（前 200 字符）...                                 │
│ ┌─────────────────────────────────────────────────────┐      │
│ 进度条: ████████████░░░░░░░░  剩余 12 天                  │
│ └─────────────────────────────────────────────────────┘      │
│ O:3 R:4 C:3 P:5 I:4    abc1234   [历史] [★] [✏️] [⑂] [↗]  │
└──────────────────────────────────────────────────────────────┘
```

**主信息**（突出）：标题、作者名
**辅助信息**（标签/图标）：评分、commit hash、状态、操作按钮、进度条

### 4.2 字段清单

| 字段 | API 来源 | 状态 |
|------|---------|------|
| 标题 | `ArticleSummary.title` | ✅ |
| 作者 | `ArticleSummary.authors` → 解析为 `AuthorInfo[]` | ✅ |
| 内容预览（~200 字） | `ArticleSummary.content_preview` | ✅ |
| commit 短哈希 | `ArticleSummary.commit_hash` | ✅ |
| 5 维评分 | `ArticleSummary.score` | ✅ |
| 状态（published/sedimentation） | `ArticleSummary.status` | ✅ |
| 出池剩余天数 | `ArticleSummary.days_remaining` | ✅ |
| 出池总天数（进度条分母） | `ArticleSummary.sink_duration_days` | ✅ |
| fork 数 | `ArticleSummary.fork_count` | ✅ |
| 是否来自 fork | `ArticleSummary.forked_from`（非 null = fork） | ✅ |
| 是否收藏 | `ArticleSummary.is_bookmarked` | ✅ |
| 是否自己的文章 | `ArticleSummary.is_own_article` | ✅ |
| 是更新还是初次 | `ArticleSummary.commit_count`（>1 = 编辑过） | ✅ |
| 历史按钮 | 前端跳转 `/articles/{id}/history` | ✅ |
| 编辑按钮 | 条件：`is_own_article` | ✅ |
| 派生按钮 | 前端调用 `POST /articles/{id}/fork` | ✅ |
| 融合按钮 | 条件：用户已派生过此文 | 🟡 |

### 4.3 进度条

- 水平进度条，显示**已过天数 / 总天数**
- `progress = (sink_duration_days - days_remaining) / sink_duration_days`
- 仅在 `status === "sedimentation"` 时显示

---

## 4.4 作者贡献比例

每个 commit 的自评可以携带作者贡献比例：

```json
{
  "self_review": {
    "scores": { "originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 4 }
  },
  "contributions": {
    "alice_id": { "originality": 0.6, "rigor": 0.7, "completeness": 0.5, "pedagogy": 0.8, "impact": 0.6 },
    "bob_id":   { "originality": 0.4, "rigor": 0.3, "completeness": 0.5, "pedagogy": 0.2, "impact": 0.4 }
  }
}
```

**规则**：
- 贡献比例存在 `Review` 表（自评记录），新增 `contributions` JSON 字段
- 每维度所有作者比例总和 = 1.0
- 初次提交时协商，merge 时重新协商
- 贡献比例与文章评分无关，不影响整体评分计算
- 贡献比例用于文章页作者展示，历史 commit 的贡献比例可通过 review 记录查询
- 自评分数仍按 0.15 权重参与整体评分

---

## 5. API 缺口总表

### 🟡 待实现（本轮）

| # | 缺口 | 涉及位置 | 状态 |
|---|------|---------|------|
| 1 | commit message 必填（编辑器自评弹窗 + API schema） | `EditorPage.vue`, `schemas/article.py` | 🟡 |
| 2 | 池内评审出池后冻结（后端守卫） | `routes/reviews.py` | 🟡 |
| 3 | 历史页时间精确到秒 | `HistoryPage.vue` | 🟡 |
| 4 | StarRating click 修复（reactive→ref） | `ArticlePage.vue` | 🟡 |

### ✅ 已完成

| # | 缺口 | 涉及端点/文件 |
|---|------|---------|
| 1-20 | 原 20 项 API 缺口（ID 类型、作者对象化、ArticleSummary 扩展、下载端点、User 模型字段、contributions、parents 字段、分页等） | 见 §2.2 端点清单 |
| 21 | 前端认证 UI（AuthModal + NavBar + 路由守卫） | `AuthModal.vue`, `NavBar.vue`, `router/index.ts` |
| 22 | 首页未登录欢迎状态 | `HomePage.vue` |
| 23 | 编辑页全宽布局 | `App.vue` |
| 24 | 编辑页分隔条可拖拽 | `EditorPage.vue` |
| 25 | 编辑页下载按钮 | `EditorPage.vue` |
| 26 | `POST /compile-download` | `backend/routes/compile.py` |
| 27 | 种子数据更新 | `seed.py` |
| 28 | 评审提交 + thread 回复 UI | `ArticlePage.vue`, `FiveDimForm.vue` |
| 29 | 自评匿名保护（实名 + 置顶） | `reviews.py`, `ArticlePage.vue` |
| 30 | JWT 认证加固（user_id → Bearer token） | 多个 routes + 前端 API |
| 31 | 后端去重（helpers.py + compile 重构） | `helpers.py`, `compile.py` |
| 32 | 前端去重（composables） | `composables/` |

### 🟢 延后

| # | 缺口 |
|---|------|
| — | 搜索扩展至摘要、关键词 |
| — | "是否派生过"查询端点 |
| — | 显式 `POST /articles/{id}/publish` |
| — | AI 集成（辅助编辑 + 审核） |
| — | P2P 分布式存储 |

---

## 6. 数据模型变更（✅ 全部已实现）

### 6.1 User 模型新增列

```python
# core/peerpedia_core/storage/db/models.py
class User(Base):
    ...
    username = Column(String, unique=True, nullable=False)    # 🆕 唯一登录标识
    password_hash = Column(String, nullable=False)             # 🆕 bcrypt 哈希
    email = Column(String, nullable=True)                      # 🆕 邮箱（格式验证）
    avatar_url = Column(String, nullable=True)                 # 头像 URL
    contact = Column(String, nullable=True)                    # 联系方式（自由文本或 JSON）
```

### 6.2 Review 模型新增列

```python
class Review(Base):
    ...
    contributions = Column(JSONDict, nullable=True)
    # {author_id: {originality: 0.6, rigor: 0.5, ...}, ...}
    # 仅自评（is_self_review=True）时填充
```

### 6.3 ArticleSummary 新增字段

```python
class ArticleSummary(BaseModel):
    # 已有
    id: str; title: str; status: ArticleStatus; score: Optional[dict]
    # 🆕
    authors: list[AuthorInfo]        # 从 list[str] 改为对象列表
    content_preview: str = ""        # 前 200 字符
    commit_hash: str = ""            # HEAD commit 短哈希
    sink_eta: Optional[datetime]     # 出池时间
    days_remaining: Optional[int]    # 剩余天数
    sink_duration_days: Optional[int] # 总天数（进度条分母）
    fork_count: int = 0
    forked_from: Optional[str] = None
    commit_count: int = 1            # 总 commit 数（>1 = 编辑过）
    is_bookmarked: bool = False      # 需 user_id 上下文
    is_own_article: bool = False     # 需 user_id 上下文
```

### 6.4 Commit 对象新增字段

```python
# get_commit_history 返回的 dict 新增：
{
    "hash": "...",
    "parents": ["parent_hash_1", "parent_hash_2"],  # 🆕 支持分支图
    "message": "...",
    "author": "...",
    "timestamp": "...",
    "score": {...}  # 已有（per-commit scoring）
}
```

---

## 7. 前端路由

| 路径 | 页面 | 认证 | 说明 |
|------|------|------|------|
| `/` | 首页 | 无 | 未登录→欢迎页；已登录→Feed |
| `/edit` | 编辑页（新建） | 🔒 | 无 articleId → 新建模式 |
| `/edit/:id` | 编辑页（编辑） | 🔒 | 有 articleId → 编辑模式 |
| `/articles/:id` | 文章页 | 无 | Google Scholar 风格，正文/评论双选项卡 |
| `/articles/:id/history` | 文章历史页 | 无 | GitHub 风格 commit 图 |
| `/articles/:id/citations` | 引用页 | 无 | 独立页面 |
| `/users/:id` | 用户页 | 无 | 用户资料 + 文章列表 |
| `/schools` | 用户目录 | 无 | 所有用户列表（按文章数排序），新用户发现关注对象 |
| `/pool` | 沉淀池 | 🔒 | 关注圈文章池 |
| `/search?q=` | 搜索结果 | 无 | 文章列表 |
| `/bookmarks` | 收藏夹 | 🔒 | 文章列表 |

🔒 = 需要登录，未登录重定向到首页并弹出认证弹窗

---

## 8. 已确认的交互细节

1. **分页策略**：所有需要分页的页面统一使用**页码**（非无限滚动、非"加载更多"）
2. **贡献比例协商 UI**：自评栏中，每个维度一个滑块组，每个作者一个滑块，同维度所有作者总和锁定为 1.0
3. **评论展示**：评论不独立成页。文章页下方使用双选项卡切换：**正文** / **评论**。页面顶栏的评论入口点击后自动切换到评论选项卡
4. **下载按钮**：不在文章 Bar 中。文章页上方窄栏提供"Source"和"PDF"两个下载按钮；编辑页工具栏也提供下载按钮
5. **暂存按钮**：编辑页的暂存功能使用浏览器 localStorage，不涉及后端 API
6. **编辑 + 发布逻辑**：每次编辑产生新 commit，自动重新进入沉淀池，覆盖旧的出池时间
7. **延期**：作者在沉淀中可延期，每次 +7 天，通过已有的 `PUT /articles/{id}/sink-extension` 端点
8. **用户编辑资料**：用户名不可修改；匿名名可修改；头像、联系方式、机构、专业领域可修改
9. **匿名名展示**：仅用户本人可见自己的匿名名（在用户页）
10. **沉淀池排序**：出池时间降序（剩余天数多的在上面，视觉上"慢慢沉下去"）
11. **登录状态保持**：JWT token 存 localStorage，刷新页面不丢失。启动时自动调用 `GET /auth/me` 恢复会话
12. **登录标识**：username 为唯一登录名，与显示名 name 分离。邮箱格式验证但不发送验证邮件（MVP）
13. **演示用户**：种子数据中 8 个用户统一密码 `666666`，username 为姓名拼音（如 `einstein`、`curie`）
14. **编辑器宽度**：编辑页面突破全局 `max-w-content` 限制，使用 `max-w-full` 全宽布局 + 极窄边距
15. **编辑器分隔条**：中间分隔条可拖拽，范围 20%-80%。使用 mousedown/mousemove/mouseup 实现
16. **下载按钮位置**：编辑器工具栏左侧放源码下载（`FileDown`），右侧放 PDF 下载（`FileText`），新建文章时可通过 `POST /compile-download` 编译后下载
17. **编译预览不变**：`POST /compile-preview` 固定 Markdown→HTML, Typst→SVG，不增加其他输出格式
