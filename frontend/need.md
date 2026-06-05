# PeerPedia 前端需求文档

> 最后更新：2026-06-05

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
| 后端 Routes | `backend/peerpedia_api/routes/` | 10 个路由模块，REST 端点 |
| 前端 Types | `frontend/src/api/types.ts` | TypeScript 接口，消费者镜像 |
| 前端 API | `frontend/src/api/*.ts` | 7 个 API 模块，axios 调用封装 |
| 核心逻辑 | `core/peerpedia_core/` | 业务层 + 存储层 + 工作流 |

### 2.2 当前 API 端点清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/articles` | 文章列表（`?status=`） |
| GET | `/articles/{id}` | 文章详情 |
| POST | `/articles` | 创建文章 |
| PUT | `/articles/{id}` | 编辑文章 |
| PUT | `/articles/{id}/sink-extension` | 延期出池 |
| GET | `/articles/{id}/history` | 提交历史 |
| GET | `/articles/{id}/diff/{h1}/{h2}` | 两提交 diff |
| POST | `/articles/{id}/fork` | 派生文章 |
| POST | `/articles/{id}/rollback/{hash}` | 回滚到历史版本 |
| GET | `/articles/{id}/reviews` | 评审列表 |
| POST | `/articles/{id}/reviews` | 提交评审 |
| POST | `/articles/{id}/reviews/{rid}/messages` | 评审线程消息 |
| GET | `/articles/{id}/citations` | 引用关系 |
| POST | `/articles/{id}/merge-proposals` | 创建汇合提案 |
| GET | `/articles/{id}/merge-proposals` | 汇合提案列表 |
| POST | `/articles/{id}/merge-proposals/{pid}/accept` | 接受汇合 |
| POST | `/articles/{id}/merge-proposals/{pid}/reject` | 拒绝汇合 |
| GET | `/users` | 用户列表 |
| POST | `/users` | 创建用户 |
| GET | `/users/{id}` | 用户详情 |
| GET | `/users/{id}/followers` | 粉丝列表 |
| GET | `/users/{id}/following` | 关注列表 |
| POST | `/users/{id}/follow` | 关注用户 |
| DELETE | `/users/{id}/follow` | 取关用户 |
| GET | `/pool` | 沉淀池文章 |
| GET | `/bookmarks` | 收藏列表 |
| POST | `/bookmarks` | 添加收藏 |
| DELETE | `/bookmarks/{id}` | 取消收藏 |
| GET | `/feed` | 关注动态 |
| GET | `/search?q=` | 搜索文章 |
| POST | `/compile-preview` | 编译预览 |
| POST | `/citations/click` | 记录引用点击 |

### 2.3 核心数据形状

**文章（Article）：**
- ID：UUID 字符串
- 每个文章是一个独立的 git 仓库（`~/.peerpedia/articles/{id}/`）
- 每次编辑 = 一次 git commit
- 每次 commit 有独立的评审和评分（per-commit independent scoring）
- Article 级别的 `score` 缓存最新 commit 的评分
- 自评（self-review）与 commit 绑定，权重 0.15；社区评审权重 0.85

**评审（Review）：**
- 唯一约束：`(article_id, reviewer_id, scope, commit_hash)` — 每人每 commit 每 scope 一条
- scope：`"pool"`（池内匿名）或 `"published"`（实名）
- 包含 5 维评分 + 评论线程 + 自评标记
- ⚠️ 需要新增 `contributions` 字段（见 §4.4）

**用户（User）：**
- 4 维声誉（professionalism, objectivity, collaboration, pedagogy）
- 匿名名（池内显示）+ 实名（已发表后显示）
- ⚠️ 需要新增 `avatar_url`、`contact` 字段

---

## 3. 页面需求

### 3.1 首页

**工具栏**（所有页面固定）：
- PeerPedia logo → 回主页
- 搜索框
- 我的收藏（书签图标）
- 我的主页（头像图标）
- 新建文章（+图标）
- 沉淀池入口

**正文**：
- 我关注的人的最新文章，以 Article Bar 列表展示
- 分页加载，使用页码（所有分页页面统一）

**API 需求：**
- `GET /feed?page=1&size=20`（需新增分页参数）
- 每篇文章需返回完整 Article Bar 所需字段（见 §4.1）
- 需传入当前用户 ID 以判断 `is_bookmarked` 和 `is_own_article`

---

### 3.2 编辑页

参照 Overleaf 布局。

**主编辑区**：
- 左侧代码编辑器（Monaco），右侧实时预览
- 中间分隔条可拖拽调整比例
- 编辑器与预览同步滚动
- 文章标题在编辑器上方，**仅初次提交时可编辑**，之后显示为固定文本
- 编辑器上方小滑块：Markdown ↔ Typst 切换
- 预览框上方小按钮：编译、下载源码、下载 PDF
- **暂存按钮**：将草稿保存到浏览器 localStorage

**发布流程**：
1. 点击右上角"发布"按钮
2. 进入自评栏（弹窗或侧面板）：
   - 5 维自评分数（originality, rigor, completeness, pedagogy, impact）
   - 关键词标签
   - 领域/分类
   - 摘要
   - （多作者时）各作者贡献比例 — 5 维，每维全员总和 = 1.0
   - "发布到沉淀池"按钮

**发布后**：新 commit → 自动进沉淀池 → 自评作为该 commit 的评审

**API 需求：**
- `POST /articles`（新建）
- `PUT /articles/{id}`（编辑，新 commit）
- `POST /compile-preview`（实时编译预览）
- `GET /articles/{id}/source`（🆕 加载已有文章内容到编辑器）
- `GET /articles/{id}/download/source`（🆕 下载源码）
- `GET /articles/{id}/download/pdf`（🆕 下载 PDF）

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
| 编辑按钮 | 仅文章作者可见，点击 → 跳转编辑页 |
| 延期按钮 | 仅文章作者 + 处于沉淀中时显示，点击 → 延期 7 天 |

**下方**（双选项卡切换）：
- **正文选项卡**：文章编译预览，横向撑满屏幕。编译后的 Typst SVG / Markdown HTML 渲染。
- **评论选项卡**：评论列表（含每条评论的 5 维评分 + 评论线程），可在此发布新评论。页面顶部窄栏的评论入口（带评论数）点击后切换到此选项卡。

**API 需求：**
- `GET /articles/{id}`（详情 + 分数 + 编译输出）
- `GET /articles/{id}/source`（🆕 获取原始源码用于展示）
- `GET /articles/{id}/reviews`（评论列表，含贡献数据）
- `GET /articles/{id}/citations`（引用图）
- `GET /articles/{id}/has-forked?user_id=X`（🆕 判断是否已派生）
- `PUT /articles/{id}/sink-extension`（延期，已有）
- `POST /articles/{id}/fork`（派生，已有）
- `POST /bookmarks` / `DELETE /bookmarks/{id}`（收藏，已有）

---

### 3.4 用户页

**上方**：
- 用户头像
- 用户名 + 匿名名（仅本人可见自己的匿名名）
- 4 维声誉雷达图（professionalism, objectivity, collaboration, pedagogy）
- 粉丝数 / 关注数（数字），点击展开粉丝列表和关注列表
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
| 作者 | `ArticleSummary.authors` → 需解析为 `AuthorInfo[]` | 🟡 |
| 内容预览（~200 字） | 🆕 `ArticleSummary.content_preview` | 🔴 |
| commit 短哈希 | 🆕 `ArticleSummary.commit_hash` | 🔴 |
| 5 维评分 | `ArticleSummary.score` | ✅ |
| 状态（published/sedimentation） | `ArticleSummary.status` | ✅ |
| 出池剩余天数 | 🆕 `ArticleSummary.days_remaining` | 🔴 |
| 出池总天数（进度条分母） | 🆕 `ArticleSummary.sink_duration_days` | 🔴 |
| fork 数 | 🆕 `ArticleSummary.fork_count` | 🔴 |
| 是否来自 fork | 🆕 `ArticleSummary.forked_from`（非 null = fork） | 🔴 |
| 是否收藏 | 🆕 `ArticleSummary.is_bookmarked` | 🔴 |
| 是否自己的文章 | 🆕 `ArticleSummary.is_own_article` | 🔴 |
| 是更新还是初次 | 🆕 `ArticleSummary.commit_count`（>1 = 编辑过） | 🔴 |
| 历史按钮 | 前端跳转 `/articles/{id}/history` | ✅ |
| 编辑按钮 | 条件：`is_own_article` | 🔴 |
| 派生按钮 | 前端调用 `POST /articles/{id}/fork` | ✅ |
| 融合按钮 | 条件：用户已派生过此文 | 🔴 |

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

### 🔴 阻塞（9 项）— 不改前端无法工作

| # | 缺口 | 涉及端点 |
|---|------|---------|
| 1 | ID 类型：后端 `string` vs 前端 `number` | `types.ts` 全量修改 |
| 2 | 作者对象化：返回 `AuthorInfo[]` 而非 `list[str]` | `GET /articles`, `/articles/{id}`, `/pool`, `/feed`, `/search` |
| 3 | 源内容端点 | 🆕 `GET /articles/{id}/source` |
| 4 | `ArticleSummary` 扩展字段 | `GET /articles`, `/pool`, `/feed`, `/search`, `/bookmarks` |
| 5 | 收藏状态 `is_bookmarked` | `GET /articles`, `/articles/{id}` + `?user_id=` |
| 6 | 用户上下文 `is_own_article` | 同上 |
| 7 | 沉淀池关注过滤 + 排序方向 | `GET /pool?user_id=X` |
| 8 | 按作者查文章 | `GET /articles?author_id=X` |
| 9 | 分页 | `GET /articles`, `/feed`, `/pool`, `/search` + `?page=&size=` |

### 🟡 重要（6 项）— 特定功能缺失

| # | 缺口 | 涉及端点 |
|---|------|---------|
| 10 | 下载端点 | 🆕 `GET /articles/{id}/download/source`, `GET /articles/{id}/download/pdf` |
| 11 | 用户资料扩展字段 | `User` 模型 + `avatar_url`, `contact` |
| 12 | 用户编辑资料 | 🆕 `PUT /users/{id}`（name 不可改） |
| 13 | 响应形状匹配 | compile（`content`→`output`）、citations、merge（`target_article_id`→`article_id`）、feed |
| 14 | 自评 `contributions` 字段 | `ReviewCreate` + `ReviewOut` + `Review` 模型 |
| 15 | Commit history `parents` 字段 | `get_commit_history` 返回格式扩展 |

### 🟢 延后（5 项）

| # | 缺口 |
|---|------|
| 16 | 搜索扩展至摘要、关键词 |
| 17 | "是否派生过"查询端点 |
| 18 | 显式 `POST /articles/{id}/publish` |
| 19 | AI 集成（辅助编辑 + 审核） |
| 20 | P2P 分布式存储 |

---

## 6. 数据模型变更

### 6.1 User 模型新增列

```python
# core/peerpedia_core/storage/db/models.py
class User(Base):
    ...
    avatar_url = Column(String, nullable=True)   # 头像 URL
    contact = Column(String, nullable=True)       # 联系方式（自由文本或 JSON）
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

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | 关注动态 + 文章列表 |
| `/editor` | 编辑页（新建） | 无 articleId → 新建模式 |
| `/editor/{id}` | 编辑页（编辑） | 有 articleId → 编辑模式 |
| `/articles/{id}` | 文章页 | Google Scholar 风格，正文/评论双选项卡 |
| `/articles/{id}/history` | 文章历史页 | GitHub 风格 commit 图 |
| `/articles/{id}/citations` | 引用页 | 独立页面 |
| `/users/{id}` | 用户页 | 用户资料 + 文章列表 |
| `/pool` | 沉淀池 | 关注圈文章池 |
| `/search?q=` | 搜索结果 | 文章列表 |
| `/bookmarks` | 收藏夹 | 文章列表 |

---

## 8. 已确认的交互细节

1. **分页策略**：所有需要分页的页面统一使用**页码**（非无限滚动、非"加载更多"）
2. **贡献比例协商 UI**：自评栏中，每个维度一个滑块组，每个作者一个滑块，同维度所有作者总和锁定为 1.0
3. **评论展示**：评论不独立成页。文章页下方使用双选项卡切换：**正文** / **评论**。页面顶栏的评论入口点击后自动切换到评论选项卡
4. **下载按钮**：不在文章 Bar 中。用户需要先进入文章页才能下载（至少看了摘要）
5. **暂存按钮**：编辑页的暂存功能使用浏览器 localStorage，不涉及后端 API
6. **编辑 + 发布逻辑**：每次编辑产生新 commit，自动重新进入沉淀池，覆盖旧的出池时间
7. **延期**：作者在沉淀中可延期，每次 +7 天，通过已有的 `PUT /articles/{id}/sink-extension` 端点
8. **用户编辑资料**：用户名不可修改；匿名名可修改；头像、联系方式、机构、专业领域可修改
9. **匿名名展示**：仅用户本人可见自己的匿名名（在用户页）
10. **沉淀池排序**：出池时间降序（剩余天数多的在上面，视觉上"慢慢沉下去"）
