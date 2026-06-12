# PeerPedia · 知诸网

**同行评审即基础设施。知识如何被筛选，应该是一个开放协议，而不是一门生意。**

---

## 问题

学术出版运行在一个断裂的循环上：

```
学者写论文       →  无偿劳动
学者投稿给出版社  →  无偿转让版权
学者为出版社审稿  →  无偿劳动
大学买回期刊     →  每年数百万美元
学者读自己的论文  →  付费墙
```

学者写。学者审。学者买单。出版商只拥有那个信封。

arXiv 解决了**分发**问题。但它没有解决**筛选**问题——如何判断什么值得读。今天，筛选仍然是同行评审，而同行评审仍然掌握在那些对科学一无所知的出版商手中。他们只是运营了一个邮件列表。

**为什么同行评审本身不能成为基础设施？** 不是公司运营的服务，而是协议。像 TCP/IP 一样，但用于知识筛选。任何人都可以在上面构建。没有任何人拥有它。

这就是 PeerPedia 想要构建的东西。

---

> 🚧 **早期阶段，vibe-coded，寻找贡献者。** 由 Claude Code + DeepSeek V4 构建。很多东西能跑，很多东西粗糙，很多东西还根本没有。最难的问题不是代码——是冷启动用户群和网络效应。如果你关心开放知识，[加入我们](#contributing)。我们需要设计师、工程师、作者和思考者。

---

## 路线图：农村包围城市，武装夺取政权

我们不是在明天取代 Elsevier。这个策略——借用毛主席的思想——是**农村包围城市，武装夺取政权。** "城市"是精英期刊、名校机构和出版商垄断。"农村"是个体学者、小型实验室和被排斥在声望经济之外的全球大多数研究者。

**Phase 1 — 更好的笔记本。** 带 Git 历史的互联笔记。Fork 想法。Merge 改进。引用一切。通过对个体学者真正有用，而不是对机构有用，来建立用户群。*在农村建立根据地。*

**Phase 1 的载体是 Tauri 桌面版。** 离线 Markdown/Typst 写作 + Git 版本控制 + 本地 SQLite 存储。5MB 体积、30MB 内存。一个人用也爽——这是吸引冷启动用户的关键。Web 版保留给社区功能。

**Phase 2 — 给 arXiv 打分。** arXiv 上数百万预印本没有质量信号。一套社区驱动的评分层——任何人可以查询、审计或构建——给读者一个不属于任何出版商的筛选器。*包围城市。开始建立让旧系统明显不足的平行基础设施。*

**Phase 3 — 取代同行评审。** 一旦声誉和评分基础设施存在且人们信任它，期刊的最后一个功能就过时了。同行评审不再是服务。它是协议。*夺取筛选的手段。*

每个阶段独立有用。每个阶段为下一个建立网络。你不是通过攻击出版商来击败他们，而是通过在下面建立更好的东西让他们变得无关紧要。

---

## Why PeerPedia?

知识应该自由流动并相互构建。PeerPedia 让你：

- **连接**笔记和文章——通过引用、派生、合并
- **演化**想法——完整的 Git 历史，每次编辑可追踪、可对比、可回滚
- **评审**彼此的工作——沉淀池内匿名
- **建立声誉**——反映贡献质量，而不是机构声望

| 问题 | PeerPedia |
|---------|-----------|
| 孤立的笔记 | 引用图——每篇文章可引用、可被引用 |
| 无版本历史 | Git 原生：派生、编辑、合并、回滚 |
| 不透明的反馈 | 透明的五维评分（O/R/C/P/I） |
| 无作者激励 | 声誉系统（P/O/C/R）奖励高质量工作 |
| 仅英语 | 完整的中英双语界面（知诸网） |

---

## Architecture

```
Phase 1（冷启动 — Tauri Desktop）
┌──────────────────────────────────────────────────────────┐
│  Vue 3 → IPC → Rust commands → SQLite + Git（本地）       │
│  离线写作、本地编译、版本控制                               │
└──────────────────────────────────────────────────────────┘
                         ↕ 可选同步（Slice 2）

Phase 2+（社区 — Web）
┌──────────────────────────────────────────────────────────┐
│  Vue 3 SPA → REST → FastAPI → SQLite + Git（服务器）       │
│  沉淀池、社区评审、信誉系统、AI 交融                          │
└──────────────────────────────────────────────────────────┘
```

### 技术栈

| Layer | Technology |
|-------|-----------|
| 桌面壳 | Tauri 2.x (Rust) |
| 前端 | Vue 3, TypeScript, Vite, Tailwind CSS, Pinia, vue-i18n |
| 后端 (Web) | Python 3, FastAPI, SQLAlchemy, SQLite |
| 后端 (Desktop) | Rust, rusqlite, bcrypt, libgit2 |
| 存储 (Desktop) | SQLite + Git 仓库（本地） |
| 存储 (Web) | SQLite + Git 仓库（服务器） |
| Auth | JWT (Web) / bcrypt + SQLite (Desktop) |
| 编译 | Typst CLI, Python Markdown |
| 数学 | KaTeX |

---

## Quick Start

### 前置要求
- Python 3.12+
- Node.js 18+
- Rust（用于 Tauri 桌面版）
- [Typst](https://github.com/typst/typst) CLI（用于 PDF 编译）

### Web 后端

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 导入演示数据（23 位科学家，密码 666666）
python seed.py

# 启动服务器
uvicorn peerpedia_api.main:app --port 8080 --reload
```

### Web 前端

```bash
cd frontend
npm install
npm run dev    # → http://localhost:5173
```

### Tauri 桌面版（开发模式）

```bash
cd frontend
npm run tauri dev    # → 启动 Tauri 窗口
```

### 演示用户（23 位科学家，密码 666666）

| 姓名 | 用户名 | 密码 |
|------|----------|----------|
| Albert Einstein | `einstein` | `666666` |
| Marie Curie | `curie` | `666666` |
| Alan Turing | `turing` | `666666` |
| Ada Lovelace | `lovelace` | `666666` |
| Richard Feynman | `feynman` | `666666` |
| Emmy Noether | `noether` | `666666` |
| Claude Shannon | `shannon` | `666666` |
| Rosalind Franklin | `franklin` | `666666` |
| …还有 15 位 | `bohr`, `heisenberg`, `schrodinger`, `dirac`, `born`, `vonneumann`, `hopper`, `hodgkin`, `crick`, `cajal`, `goldmanrakic`, `popper`, `kuhn`, `putnam`, `chandra` | `666666` |

---

## 核心概念

### 文章即 Git 仓库

每篇文章是独立的 Git 仓库。写作、编辑、派生和合并都映射到 Git 操作：

- 完整的版本历史，永久保存
- 任意两个版本间的并行对比（diff2html）
- Fork → 修改 → Merge Proposal 工作流
- 不可篡改的审计记录

**保存即提交（Save = Commit）。** 编辑器中每次保存触发一次 Git 提交。下载文件名包含提交哈希（如 `My_Article-a1b2c3d.html`）。首次保存前下载按钮禁用，确保每次下载对应一个已提交的版本。

### 五维评分

所有评审使用五个维度：

| 维度 | 名称 | 衡量什么 |
|-----|------|-----------------|
| **O** | Originality | 贡献有多新颖？ |
| **R** | Rigor | 方法和论证是否可靠？ |
| **C** | Completeness | 工作是否详尽、自包含？ |
| **P** | Pedagogy | 写作是否清晰易懂？ |
| **I** | Impact | 对该领域有多重要？ |

### 沉淀池（Sedimentation Pool）

新文章进入**沉淀池**等待社区评审：

- 高分**缩短**评审期；低分**延长**评审期
- 池内评审匿名
- 作者可通过 Thread 回复逐条反驳
- 计时器到期后文章**发布**

池仅对关注网络（followers + following）可见。

### 声誉系统

作者和评审者在四个维度上积累声誉：

| 维度 | 名称 | 衡量什么 |
|-----|------|-----------------|
| **P** | Professionalism | 贡献的质量和诚信 |
| **O** | Objectivity | 评审的公平性和准确性 |
| **C** | Collaboration | 与同行的建设性互动 |
| **R** | Readability | 写作的清晰性和可访问性 |

声誉越高 → 沉池内投票权重越大。

---

## 功能

### 桌面版（Phase 1 — 冷启动）

- 离线 Markdown/Typst 编辑，实时预览
- 三态同步按钮（电话模型）：点击连接、绿色已同步、红色超时，用户手动控制，无后台轮询
- 本地 Git 版本控制（fork, history, diff）
- 基于 SQLite 的草稿和文章缓存
- 本地账号系统（bcrypt，无需服务器）
- Typst → PDF 编译，Markdown → HTML
- 安装 5MB，内存 30MB

### Web 版（Phase 2+ — 社区）

- 五维评分（O/R/C/P/I）带悬浮展开 ScoreBadges
- 沉淀池带可配置计时器
- 文章派生 + 合并提案
- 引用图（参考文献 + 被引，点击跳转）
- JWT 认证（注册、登录、会话恢复）
- 用户资料带紧凑 ReputationBadges（P/O/C/R）
- 关注/取关、动态 Feed、书签
- 全文搜索，带分类/排序筛选
- Thread 评审讨论（含多轮双作者对话）
- 中英双语界面（vue-i18n，80+ 键）
- LXGW WenKai 书法品牌字体 + Noto Serif SC 标题字体
- Waypoints 星座图标品牌标识

---

## 项目结构

```
peerpedia/
├── frontend/                  # Vue 3 SPA + Tauri
│   ├── src/
│   │   ├── api/               # Axios API 模块
│   │   ├── components/        # 可复用组件
│   │   ├── composables/       # 共享逻辑（含 useTauri）
│   │   ├── locales/           # i18n (zh-CN, en-US)
│   │   ├── pages/             # 路由页面（含 LoginPage）
│   │   ├── router/            # Vue Router + auth guards
│   │   └── stores/            # Pinia 状态
│   └── src-tauri/             # Tauri Rust backend
│       └── src/
│           ├── main.rs        # Tauri entry
│           ├── commands.rs    # IPC handlers
│           ├── local_auth.rs  # 本地账号 CRUD + bcrypt
│           └── local_store.rs # 草稿 + 文章缓存 SQLite
├── backend/                   # FastAPI server
│   └── peerpedia_api/
│       ├── routes/            # REST endpoints
│       ├── schemas/           # Pydantic models
│       └── tests/             # Integration tests
├── core/                      # Business logic
│   └── peerpedia_core/
│       ├── storage/           # Git backend + SQLAlchemy ORM
│       ├── workflow/          # Scoring, reputation, sedimentation
│       └── config/            # Parameters
├── docs/
│   ├── DESIGN.md              # 设计文档（中文）
│   ├── DESIGN.en.md           # 设计文档（英文）
│   └── api-contract.json      # OpenAPI 3.1 specification
└── seed.py                    # Demo data seeder（23 users）
```

---

## 测试

```bash
# 后端
source .venv/bin/activate
python -m pytest backend/ -q

# 前端
cd frontend
npm test -- --run
```

---

## 路线图

详细工程计划见 [`docs/plan_reshape.md`](docs/plan_reshape.md)。

| 阶段 | 重点 | 状态 |
|-------|-------|--------|
| **1 — 桌面 MVP** | 离线写作、本地 Git、会话认证、带草稿的个人主页 | ✅ 已完成 |
| **1.5 — 打磨与分发** | 删除文章、差异对比、Typst 编译、编辑器体验（VSCode 风格多标签页）、软件分发、草稿搜索 | ✅ 已完成 |
| **2 — arXiv 镜像** | arXiv 评分、分类标签、社区评审 | 🔜 进行中 |
| **3 — P2P 网络** | 索引服务器、内容寻址存储、点对点分发 | 🔮 未来 |

---

## 贡献

**我们需要你。** 说真的。这个项目的野心远超现有资源。

### 我们缺少什么

- **UI/UX 打磨** — 很多页面能用但体验还不够好
- **无障碍** — 键盘导航、屏幕阅读器、焦点管理
- **性能** — bundle 大小、懒加载、API 响应缓存
- **测试** — 覆盖度不错但远未全面
- **移动端** — 能用但不是为小屏幕设计的
- **错误处理** — 边缘情况很多，优雅降级不够
- **部署** — 没有 Docker，没有 CI/CD 管线，没有生产指南
- **安全审计** — JWT 能用但未被外部审查
- **国际化** — 中英文翻译需要优化

### 如何开始

1. 阅读 `docs/DESIGN.md` 了解设计理念
2. 查看 `CLAUDE.md` 了解开发规范
3. 选一个 issue 或提出你想做的事情
4. 遵循 TDD：先写失败测试 → 实现 → 重构

没有太小的贡献。改个错别字。翻译一个字符串。写一个测试。每一点都有帮助。

---

## 愿景

长期目标：**取代学术出版商，打破声望垄断。**

今天，少数出版商控制着什么算知识。他们向大学收取数百万美元，用于获取他们自己的教师产出的研究。他们通过期刊声望而非价值来把持职业命运。过去 300 年他们之所以能做到这一点，是因为没有替代的基础设施。

PeerPedia 就是那个替代方案。不是明年。不是五年后。但棋子已经在桌上：

- **Git 原生文章** 取代出版商版本控制
- **社区评分** 取代编辑把关
- **匿名评审** 消除声望偏见
- **声誉** 取代影响因子
- **免费开放** 取代付费墙

离目标还很远。现在我们需要帮助把基础打牢。但每一个 pull request 都在推动这件
事。

> 一个知识自由连接的世界——每个想法都可以关联、构建和精炼其他想法。质量从社区共识中涌现，而不是看门人。每个贡献者获得与其影响力相称的认可。没有人通过把知识锁在墙后面来获利。

*"走向更好的学术 — To a better academia."*

---

## 许可

MIT。通过 PeerPedia 发布的内容默认使用 CC BY-SA 4.0。

---

*"走向更好的学术 — To a better academia."*
