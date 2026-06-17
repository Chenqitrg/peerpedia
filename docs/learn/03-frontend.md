# Frontend 模块

> Vue 3 + TypeScript 层。PeerPedia 的 UI——编辑器、文章页、标签系统、离线支持。

## 一句话职责

**把 core 的数据变成用户能看、能写的界面。** 不存业务规则，不直接操作 DB。

## C3: Frontend 组件依赖

```
                     ┌──────────────────────┐
                     │      App.vue         │  ← 根组件
                     │  NavBar + TabDrawer  │
                     │  + AuthModal         │
                     └──────────┬───────────┘
                                │ <router-view> 渲染
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
     ┌──────────┐       ┌──────────┐         ┌──────────┐
     │ HomePage │       │EditorPage│         │ArticlePage│
     └──────────┘       └────┬─────┘         └──────────┘
                             │ 依赖
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────────┐  ┌──────────────┐
       │keep-alive│  │ composables: │  │ components:  │
       │TabStore  │  │ draft,commit │  │ CodeEditor   │
       └──────────┘  │ splitPane    │  │ DownloadBtn  │
                     └──────────────┘  └──────────────┘
                             │ 依赖
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────────┐  ┌──────────┐
       │  stores  │  │ composables: │  │  api/    │
       │ user     │  │ network     │  │ client   │
       │ article  │  │ autoSync    │  │ 13 模块  │
       │ tab      │  │ offline     │  └──────────┘
       │ review   │  │ tauri       │
       └──────────┘  └──────────────┘
```

箭头约定：`A ──► B` = A 依赖 B（A import B、A 调 B）。

- **App.vue 依赖 pages**：通过 `<router-view>` 渲染
- **pages 依赖 composables + components + stores**：EditorPage 和 ArticlePage 是最大的消费者
- **composables 依赖 stores + api**：useAutoSync 调 useArticleStore，所有数据请求走 api/
- **stores 之间互不依赖**——每个 store 独立
- **api/ 是 HTTP 边界**——上面所有层通过它和后端通信

## 模块地图

```
frontend/src/
├── App.vue              # 根组件：NavBar、TabDrawer、AuthModal、keep-alive
├── main.ts              # 入口：注册 Pinia、Vue Router、vue-i18n
├── pages/               # 11 个路由级页面
│   ├── HomePage.vue     # 首页（动态 feed）
│   ├── ArticlePage.vue  # 文章详情（最复杂的只读页面）
│   ├── EditorPage.vue   # 文章编辑器（最复杂的写页面）
│   ├── HistoryPage.vue  # 文章 Git 历史
│   ├── SearchPage.vue   # 全文搜索
│   ├── PoolPage.vue     # 沉淀池
│   ├── SchoolsPage.vue  # 学校/机构列表
│   ├── UserPage.vue     # 用户主页
│   ├── UserListPage.vue # 关注者/正在关注列表
│   ├── BookmarksPage.vue # 书签列表
│   └── CitationsPage.vue # 引用图
├── components/          # 20 个可复用组件
│   ├── NavBar.vue       # 顶部导航栏（含语言切换）
│   ├── AuthModal.vue    # 登录/注册弹窗
│   ├── TabDrawer.vue    # VSCode 风格标签抽屉
│   ├── ArticleCard.vue  # 文章卡片（列表项）
│   ├── CodeEditor.vue   # CodeMirror 6 Markdown 编辑器
│   ├── DiffView.vue     # Git diff 渲染
│   ├── StarRating.vue   # 五星评分组件
│   ├── ScoreBadges.vue  # 文章五维评分徽章
│   ├── ReviewPanel.vue  # 评审面板（含讨论串）
│   ├── FiveDimForm.vue  # 五维评分表单
│   ├── RadarChart.vue   # 雷达图可视化
│   ├── ReputationBadges.vue # 用户信誉徽章
│   ├── UserCard.vue     # 用户卡片
│   ├── SyncButton.vue   # 三态同步按钮
│   ├── DeleteButton.vue # 统一删除按钮
│   ├── DownloadButton.vue # 下载按钮
│   ├── Pagination.vue   # 分页组件
│   ├── SkeletonCard.vue # 加载占位符
│   ├── ErrorState.vue   # 错误状态展示
│   └── ThreadReplyInput.vue # 讨论回复输入
├── stores/              # 4 个 Pinia stores
│   ├── useArticleStore.ts  # 文章 CRUD 状态
│   ├── useUserStore.ts     # 用户认证（最复杂，双模式）
│   ├── useTabStore.ts      # IDE 风格标签管理
│   └── useReviewStore.ts   # 评审状态（含乐观更新）
├── composables/         # 16 个可组合函数
│   ├── useNetworkStatus.ts  # 网络连接检测（单例）
│   ├── useAutoSync.ts       # 离线队列自动刷新（单例）
│   ├── useArticleSync.ts    # 单文章同步状态机
│   ├── useOffline.ts        # 离线能力门控
│   ├── useTauri.ts          # Tauri 桌面桥接
│   ├── useDraftPersistence.ts # 草稿自动保存
│   ├── useCommitFlow.ts     # 提交/保存工作流
│   ├── useSplitPane.ts      # 分栏面板调整
│   ├── useTabIntegration.ts # 页面-标签绑定
│   ├── useBookmarkToggle.ts # 书签切换
│   ├── useFollowCache.ts    # 离线关注缓存
│   ├── useStatusMap.ts      # 文章状态映射
│   ├── useAsyncResource.ts  # 通用异步数据获取
│   ├── useLocalStorage.ts   # localStorage 封装
│   └── browserLocalBackend.ts # 浏览器本地后端（无 Tauri 时的开发 mock）
├── api/                 # 13 个 HTTP 客户端模块
│   ├── client.ts        # Axios 封装、base URL、拦截器
│   ├── types.ts         # 共享 TypeScript 类型
│   ├── constants.ts     # SCORE_DIMS 常量
│   ├── articles.ts      # 文章端点
│   ├── auth.ts          # 认证端点
│   ├── users.ts         # 用户端点
│   ├── reviews.ts       # 评审端点
│   ├── bookmarks.ts     # 书签端点
│   ├── feed.ts          # 动态端点
│   ├── pool.ts          # 沉淀池端点
│   ├── search.ts        # 搜索端点
│   ├── compile.ts       # 编译端点
│   └── citations.ts     # 引用端点
├── router/
│   └── index.ts         # Vue Router 配置（14 条路由）
├── locales/             # i18n
│   ├── zh-CN.json       # 中文（默认）
│   └── en-US.json       # 英文
└── utils/
    ├── markdown.ts      # Markdown 解析
    ├── typst.ts         # Typst SVG 清理
    └── math.ts          # KaTeX 渲染
```

## 两巨头：EditorPage 和 ArticlePage

### EditorPage（编辑器）
```
用户写文章
  → useDraftPersistence（自动存草稿到 localStorage）
  → CodeEditor.vue（CodeMirror 6 编辑器 + Typst 语法高亮）
  → 编译预览（compile-preview API）
  → useCommitFlow（保存 → git commit）
  → useAutoSync（网络恢复后自动推送）
```

### ArticlePage（文章详情）
```
加载文章
  → getArticle(id) → ArticleDetail
  → 渲染 title/authors/content/scores
  → DiffView（查看历史变更）
  → ReviewPanel（提交评审、查看评分）
  → DownloadButton（下载 PDF/源码）
  → 书签切换、fork、merge proposal
```

## 标签系统（useTabStore）

VSCode 风格的标签管理：

```typescript
interface Tab {
  id: string          // UUID
  routePath: string   // /edit/xxx 或 /article/xxx
  type: 'editor' | 'article'
  title: string
  dirty: boolean      // 未保存的更改
  icon?: string
}
```

- 最多同时打开多个文章/编辑器标签
- `keep-alive` 保持标签状态
- 关闭脏标签时弹出确认对话框
- 标签状态持久化到 localStorage（`peerpedia_tabs`）

## 用户认证的双模式

`useUserStore` 处理两种认证：

| 模式 | 何时 | 认证方式 |
|------|------|----------|
| 服务器模式 | Web 版本 | JWT token → `POST /auth/login` |
| 本地模式 | Tauri 桌面 / 浏览器本地 | 本地 bcrypt → `useTauri.login()` |

- 本地模式下注册成功后，凭证暂存到 localStorage
- 网络恢复时 `trySyncServerAuth()` 自动同步到服务器
- 登出时清除草稿数据防止跨用户泄漏

## 离线架构

```
useNetworkStatus（单例）
  → ping GET /health  ← 每 5 秒？
  → 状态：idle → connecting → synced
  ↓
useOffline（能力门控）
  → canRead(feature) / canWrite(feature)
  → 离线时阻止：feed、pool、schools、fork、publish
  → 离线时允许：编辑、编译、书签、搜索
  ↓
useAutoSync（离线队列）
  → 监听 isSynced 变化
  → 恢复时 flush() 所有 pending 操作
  → 用 git bundle 推送，409 冲突时回滚
```

## 已知问题

1. **EditorPage 太重了**。引用了 10+ 个 composable，800+ 行。是"上帝组件"——issue #89 要拆。
2. **useUserStore 也太大**。双模式认证 + localStorage 管理混在一起。
3. **Tauri/Web 模式分支散落各处**。`if (isTauri) { ... } else { ... }` 出现在 EditorPage、useUserStore、useAutoSync 等多个地方——issue #90 要统一。
4. **API client 没有错误重试**。网络抖动会直接报错。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 加新页面 | `pages/` 新建 + `router/index.ts` 加路由 |
| 改编辑器 | `pages/EditorPage.vue` + `components/CodeEditor.vue` |
| 改认证流程 | `stores/useUserStore.ts` |
| 改标签系统 | `stores/useTabStore.ts` + `components/TabDrawer.vue` |
