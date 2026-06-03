# PeerPedia — Project Status & Restart Guide

> 最后更新: 2026-06-03
> 当前状态: Phase 3 全部完成 + 沉淀池 + 五维评分 + Fork/Merge
> 测试: 361 tests, 0 failures
> 中文名: 知诸网 — 谐音「诸多」「蜘蛛网」🕸️

---

## 快速重启

```bash
cd ~/Projects/peerpedia
source .venv/bin/activate
.venv/bin/python -m pytest tests/ -v          # 跑测试（应 361 passed）
peerpedia seed --force                        # 重建 demo 数据
peerpedia serve                               # 启动 Web
open design/brainstorm.md                     # 打开设计文档
```

---

## Phase 总览

### Phase 1: Brainstorming ✅ 已完成

**目标**: 充分讨论需求，产出设计文档，不做任何代码实现。

**产出**:
- `design/brainstorm.md` — 986 行设计文档，25 项决策
- 愿景：取代 arXiv 和学术出版系统
- 核心流程：Typst 写作 → 同行审核 → P2P 发布
- 协议三层架构：Layer 0 核心（不可变）→ Layer 1 算法（版本化）→ Layer 2 参数（可配置）

### Phase 2: 项目骨架 ✅ 已完成

**目标**: 搭建项目结构，定义协议消息格式，建立测试框架。

**产出**:
```
peerpedia_core/          # 协议库（任何人可引用）
  protocol/
    messages.py          # 15 种消息类型（Pydantic v2）
    signing.py           # 签名/验签/密钥对生成
    addressing.py        # CID 内容寻址
  reputation/v1.py       # 四维信誉算法（衰减 + 身份权重）
  governance/pip.py      # PIP 提案流程
  storage/git_backend.py # Git init/commit/blame

peerpedia/               # 参考客户端
  cli/main.py            # 7 个 CLI 命令（空壳）
  web/app.py             # FastAPI 入口
  web/routes/            # pages.py + api.py（空壳）
  web/templates/         # 4 个 Jinja2 页面

tests/                   # 19 tests, 0 failures
```

**关键决策**:
- 协议和客户端分离：`peerpedia_core` vs `peerpedia`
- 信誉/权重算法在 Layer 1，可通过 PIP 升级
- 使用 Python 3.14 + FastAPI + Jinja2 + HTMX + SQLite + GitPython

### Phase 3: MVP 实现 ✅ 已完成（M1-M5 全部功能）

**目标**: 按 TDD 节奏实现核心功能闭环。一个人能在本地提交文章、找人审稿、发布。

**子任务**:

| ID | 任务 | 描述 | 优先级 |
|---|---|---|---|
| M1 | 文章提交闭环 | ✅ CLI `peerpedia init` + `submit` 工作。Typst/Markdown 编译集成。git repo + commit。DB 存储。Web 文章列表可读。 | 🔴 最高 |
| M2 | 审稿工作流 | ArticleStatus 状态机完整实现。审稿分配 → 打分 → 决策。积分首次计算。 | 🔴 最高 |
| M3 | 协作+开放编辑 | ✅ 一键合作（审稿人→合作者）。EditProposal 提案流程（minor/medium/major）。git blame 贡献时间线。126 tests。 | 🟡 高 |
| M4 | 信誉+LAN | 雷达图可视化。身份权重计算。User/Identity 表。4 API 端点。user register CLI。Chart.js 集成。**LAN 节点发现 (UDP 广播)**。**Catalog.md 文章池同步**。 | 🟢 已完成 |
| M5 | 引用跳转 | ✅ 引用扫描（Typst/Markdown）。NetworkX 引用图。cites/cited_by 查询。编译时引用链接注入。文章侧栏点击跳转。 | 🟢 中 |

**Phase 3 完成后，系统可以**:
1. 用 CLI 提交 Typst/Markdown 文章
2. 在 Web 界面浏览文章列表
3. 分配审稿人，填写审稿意见，做出决策
4. 将文章状态从 draft 推到 published
5. 获得积分
6. 两人在同一 WiFi 下（LAN 模式）互相审稿
7. 审稿人申请协作 → 作者同意 → 审稿人变为合作者
8. 出版后提交修改提案（minor/medium/major）→ 审核 → 合并
9. git blame 驱动的贡献时间线追踪

### Phase 4: IPFS 集成 ⏸ 待开始

**目标**: 将单机系统升级为 P2P 分布式存储。

- 文章发布时自动 `ipfs add` → 获得 CID
- IPNS 做可变指针，指向最新版本
- libp2p 节点发现
- 内容 pin 机制

### Phase 5: 种子社区测试 ⏸ 待开始

**目标**: 找 5-10 个物理/数学圈子的用户实际使用，验证完整流程。

### Phase 6: AI 辅助 ⏸ 远期

**目标**: 智能审稿、中英互译、推荐审稿人、写作辅助。

---

## 当前代码状态

### 可工作的

| 功能 | 状态 |
|---|---|
| `peerpedia --help` CLI | ✅ |
| `peerpedia init` (创建目录) | ✅ |
| 协议消息模型 (Pydantic) | ✅ |
| 签名/验签 | ✅ |
| CID 计算 | ✅ |
| 信誉算法 v1 (衰减 + 身份权重) | ✅ |
| PIP 提案模型 | ✅ |
| Git backend (init/commit/blame) | ✅ |
| FastAPI 启动 | ✅ |
| Web 模板 (首页/文章/提交/审稿/用户) | ✅ 5 个模板，统一导航栏 + 用户选择器 |
| 242 个测试全部通过 | ✅ |
| LAN 节点发现 (UDP) | ✅ |
| 文章池同步 (catalog.md) | ✅ |
| 引用点击追踪 (跃迁概率) | ✅ |
| Cookie 身份持久化 | ✅ viewer cookie + 导航栏用户选择器 |
| 粉丝/关注列表 | ✅ HTMX 点击展开，format=html API |
| 作者链接 | ✅ 首页/文章页作者名可点击跳转 |
| 编译错误处理 | ✅ 返回 HTML 错误信息而非 JSON 异常 |
| **代码审查** (2026-06-03) | ✅ bug修复 + 模块拆分 + SMI 3.7→2.5 |

### M3 新增功能

| 功能 | 状态 |
|---|---|
| `peerpedia collaborate` | ✅ 接受审稿人协作申请，审稿人→合作者 |
| `peerpedia propose-edit` | ✅ 提交修改提案（minor/medium/major） |
| `peerpedia merge-proposal` | ✅ 合并已通过的修改提案 |
| 贡献追踪（git blame） | ✅ ContributionRecord + 贡献时间线 + 百分比 |
| 开放编辑提案（DB） | ✅ EditProposal ORM + CRUD + 生命周期 |
| 状态机 edit_proposed | ✅ published ↔ edit_proposed 转换 |
| Web API 扩展 | ✅ 7 个新端点（协作/提案/贡献） |

### M4 Reputation Cluster 新增功能

| 功能 | 状态 |
|---|---|
| User + Identity ORM | ✅ users 表 + identities 表 + CRUD |
| `peerpedia user register` | ✅ CLI 命令，注册用户到数据库 |
| ReputationV1.compute() | ✅ 四维信誉实时计算（文章+审稿+贡献+身份boost+衰减） |
| 用户/身份/信誉 API | ✅ 4 个新端点（GET/POST users, POST identities, GET reputation） |
| 信誉雷达图 | ✅ Chart.js 四维雷达图 + 分数表格，嵌入用户主页 |
| LAN 节点发现 | ✅ UDP 广播心跳 (port 3690) |
| 文章池同步 | ✅ catalog.md (YAML + Markdown) |
| 引用点击追踪 | ✅ ClickEvent + 跃迁概率 API |

### M5 Citation Jump 新增功能

| 功能 | 状态 |
|---|---|
| 引用扫描 | ✅ extract_references() 识别 Typst #cite + 内联 peerpedia:id 格式 |
| 引用图 | ✅ NetworkX DiGraph + get_citation_info() 查询 cites/cited_by |
| 引用自动填充 | ✅ submit 时自动扫描源文件，写入 Article.references |
| 编译时链接注入 | ✅ inject_citation_links() 替换 peerpedia:id → 可点击 HTML 链接 |
| 引用侧栏 | ✅ 文章页面右侧边栏，fetch API 加载引用关系，点击跳转 |

### M5+ Follow + UI Polish 新增功能

| 功能 | 状态 |
|---|---|
| Follow ORM + CRUD | ✅ 复合主键 (follower_id, followed_id)，7 个 CRUD 函数 |
| 关注/取关 API | ✅ POST/DELETE /users/{id}/follow，HTMX 按钮 swap |
| 粉丝/关注列表 | ✅ GET /users/{id}/followers|following?format=html，点击展开 |
| 关注动态 Feed | ✅ GET /following/feed，近 30 天 new_article + new_version |
| 首页 tab 切换 | ✅ 全部文章 / 关注动态，HTMX 懒加载 |
| Cookie 身份持久化 | ✅ viewer cookie + 导航栏下拉选择器，跨页面保持 |
| 导航栏"我的主页" | ✅ 所有 5 个模板统一导航，viewer 存在时显示 |
| 作者名链接 | ✅ 首页 + 文章页 founding_authors 渲染为 /user/{id} 链接 |
| 编译端点容错 | ✅ 目录/源文件缺失时返回 HTML 提示而非 JSON 异常 |
| 自关注防护 | ✅ POST /users/{id}/follow，follower_id == user_id → 400 |
| 回归测试 | ✅ +31 tests（15 Bug 修复 + 16 Follow/Cookie UI）|

### 2026-06-03 新增功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 知诸网改名 | 知著网 → 知诸网，谐音「诸多」「蜘蛛网」 | ✅ |
| 五维自评 | 提交时自评原创性/严格性/完整性/教学性/影响力（1-5星） | ✅ |
| 社区五维评分 | 审稿人用同样五维评分，文章页自评 vs 社区对比 | ✅ |
| 沉淀池 | 替代审稿队列。匿名评分+讨论，评分加权自动下沉发表 | ✅ |
| 作者舌战群儒 | 作者真名置顶回复，不能自评，评论独立更新 | ✅ |
| 评分记忆 | 评分表单预填上次内容（灰色蒙皮），点击激活编辑 | ✅ |
| 本地搜索 | 首页搜索框，HTMX 实时过滤标题/摘要/关键词 | ✅ |
| 派生 (Fork) | 文章可派生，forked_from 链 + fork_count | ✅ |
| 派生→合并 | 派生后可提议合并回原文，原作者审核，版本号+1 | ✅ |
| Git Diff 视图 | 版本历史 tab，diff2html 渲染，行级评论 | ✅ |
| seed 命令 | `peerpedia seed --force` 一键重建 4 用户 + 5 文章 | ✅ |
| Demo 数据 | 5 篇文章（4 Markdown + 1 Typst）+ 自评 + 交叉引用 | ✅ |

### 已知缺口

| 缺口 | 说明 | 优先级 |
|---|---|---|
| 合并积分算法 | 当前简单公式，需设计 f(diff, complexity, reviewer_score) | 🟡 |
| Fork→Merge UI 完善 | 合并提议列表靠 HTMX 加载，需 viewer cookie | 🟡 |
| 编辑提案 UI | API 完整，文章页有提交表单，无审核界面 | 🟡 |
| 协作按钮 | API 有 `/collaborate`，审稿页面无"申请协作"按钮 | 🟡 |
| 引用跃迁图表 | API 有 `/citations/transitions`，无可视化 | 🟢 |
| 身份绑定 UI | API 有 POST `/users/{id}/identities`，无表单 | 🟢 |
| 搜索界面 | 仅首页搜索框，无独立搜索页 | 🟢 |
| Typst HTML 输出 | 等上游 Typst 稳定 HTML export | ⏳ |

---

## 技术栈速查

```bash
source .venv/bin/activate            # 激活虚拟环境
.venv/bin/python -m pytest tests/ -v  # 跑测试
peerpedia --help                     # CLI 帮助
```

| 组件 | 技术 | 文档 |
|---|---|---|
| CLI | Python click | `peerpedia/cli/main.py` |
| Web | FastAPI + Jinja2 + HTMX | `peerpedia/web/` |
| ORM | SQLAlchemy (8 张表) | `pyproject.toml` |
| Git | GitPython | `peerpedia_core/storage/git_backend.py` |
| 消息模型 | Pydantic v2 | `peerpedia_core/protocol/messages.py` |
| 测试 | pytest | `tests/` |

---

## 下一步

1. 打开 `design/brainstorm.md` 回顾设计文档
2. 运行 `.venv/bin/python -m pytest tests/ -v` 确认 242 tests pass
3. Phase 3 全部完成 ✅ (M1-M5+, 242 tests)
4. 下一步: Phase 5 种子社区测试（5-10 人实际使用）

---

## 项目路径

```
~/Projects/peerpedia/
├── design/brainstorm.md     ← 完整设计文档（53项决策）
├── STATUS.md                ← 本文件，重启指南
├── README.md                ← 项目简介
├── pyproject.toml           ← 构建配置 + 依赖
├── docs/superpowers/        ← 设计规范 + 实现计划
├── .venv/                   ← Python 虚拟环境
├── peerpedia_core/          ← 协议库（5子包，16模块）
├── peerpedia/               ← 参考客户端（CLI + Web，12模块）
└── tests/                   ← 测试（242 passed, 0 failures, 20 test files）
```
