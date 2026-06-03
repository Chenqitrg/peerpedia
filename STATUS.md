# PeerPedia — Project Status & Restart Guide

> 最后更新: 2026-06-03
> 当前状态: Phase 3 M1+M2+M2.5+M2.6+M3 完成
> 测试: 126 tests, 0 failures
> 中文名: 知著网（知 = 求知，著 = 著述，网 = 网络）

---

## 快速重启

```bash
cd ~/Projects/peerpedia
source .venv/bin/activate
peerpedia --help                          # 验证 CLI 可用
python -m pytest tests/ -v                # 跑测试（应 19 passed）
open design/brainstorm.md                 # 打开设计文档
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

### Phase 3: MVP 实现 ⏸ 待开始

**目标**: 按 TDD 节奏实现核心功能闭环。一个人能在本地提交文章、找人审稿、发布。

**子任务**:

| ID | 任务 | 描述 | 优先级 |
|---|---|---|---|
| M1 | 文章提交闭环 | ✅ CLI `peerpedia init` + `submit` 工作。Typst/Markdown 编译集成。git repo + commit。DB 存储。Web 文章列表可读。 | 🔴 最高 |
| M2 | 审稿工作流 | ArticleStatus 状态机完整实现。审稿分配 → 打分 → 决策。积分首次计算。 | 🔴 最高 |
| M3 | 协作+开放编辑 | ✅ 一键合作（审稿人→合作者）。EditProposal 提案流程（minor/medium/major）。git blame 贡献时间线。126 tests。 | 🟡 高 |
| M4 | 信誉+LAN | 雷达图可视化。身份权重计算。LAN 节点发现 + 文章池同步。 | 🟡 高 |
| M5 | 引用跳转 | Typst/Markdown 引用扫描。引用图（NetworkX DAG）。点击跳转。 | 🟢 中 |

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
| Web 模板 (首页/文章/提交/审稿) | ✅ |
| 126 个测试全部通过 | ✅ |

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

### 还是空壳的

| 功能 | 状态 |
|---|---|
| `peerpedia submit` | ✅ **已实现** — 调用 submit_article() 编排器 |
| `peerpedia review` | ✅ 审稿分配+提交+决策完整实现 |
| `peerpedia decide` | ✅ 基于评审投票自动决策 |
| `peerpedia serve` | ✅ FastAPI 启动，17 条路由，API 从数据库读取真实数据 |
| 数据库 (SQLite) | ✅ SQLAlchemy 6 表 (Article/Review/ContributionRecord/EditProposal) |
| Typst 编译 | ✅ TypstBackend: subprocess typst compile → PDF |
| Markdown/KaTeX | ✅ MarkdownBackend: markdown → HTML + KaTeX CDN |
| 状态机 | ✅ 8 状态 (draft→submitted→in_review→accepted→published→edit_proposed→...) |
| 审稿流程 | ✅ 分配→审稿→决策 完整闭环 |
| LAN 同步 | ❌ 无 |
| 引用图 | ❌ 无 |

---

## 技术栈速查

```bash
source .venv/bin/activate    # 激活虚拟环境
python -m pytest tests/ -v   # 跑测试
peerpedia --help             # CLI 帮助
```

| 组件 | 技术 | 文档 |
|---|---|---|
| CLI | Python click | `peerpedia/cli/main.py` |
| Web | FastAPI + Jinja2 + HTMX | `peerpedia/web/` |
| ORM | SQLAlchemy (6 张表) | `pyproject.toml` |
| Git | GitPython | `peerpedia_core/storage/git_backend.py` |
| 消息模型 | Pydantic v2 | `peerpedia_core/protocol/messages.py` |
| 测试 | pytest | `tests/` |

---

## 下一步（重新启动时）

1. 打开 `design/brainstorm.md` 回顾设计文档
2. 运行 `python -m pytest tests/ -v` 确认 19 tests pass
3. 从 Phase 3 M1 开始：让 `peerpedia submit` 真正工作
   - 先写测试
   - 集成 Typst 编译器（subprocess）
   - 创建 git repo + 首次 commit
   - 存入 SQLite 元数据
   - Web 文章列表从数据库读取真实数据

---

## 项目路径

```
~/Projects/peerpedia/
├── design/brainstorm.md     ← 完整设计文档（986 行）
├── STATUS.md                ← 本文件，重启指南
├── README.md                ← 项目简介
├── pyproject.toml           ← 构建配置 + 依赖
├── .venv/                   ← Python 虚拟环境
├── peerpedia_core/          ← 协议库
├── peerpedia/               ← 参考客户端
└── tests/                   ← 测试（19 passed）
```
