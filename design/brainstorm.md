# PeerPedia — Brainstorming Document

> 日期: 2026-06-03
> 状态: Phase 3 M1+M2+M2.5+M2.6+M3 完成（126 tests, 0 failures）
> 英文名: **PeerPedia**（peer review + encyclopedia）
> 中文名: **知著网**（知 = 求知，著 = 著述，网 = 网络）

---

## 1. Vision（愿景）

**PeerPedia** 的终极目标是**取代 arXiv 和大部分学术出版系统**。

```
作者用 Typst 写文章 → 提交同行审核 → 审稿人评议 → 审核通过 → 发布到 P2P 网络
                                                      ↑
                                        审稿人可申请加入协作
                                        出版后任何人可持续改进
                                        贡献时间线永续记录
```

### 1.1 为什么 arXiv 和现有学术出版可以被取代

| 现有系统 | 问题 | PeerPedia 的答案 |
|---|---|---|
| **arXiv** | 中心化服务器，单一控制点，无审核 | P2P 分布式存储，社区治理 |
| **期刊** | 出版锁定、审稿无偿、收费墙、慢 | 开放编辑、积分激励、免费、快 |
| **同行审核** | 匿名、无激励、审稿人没有功劳 | 署名审核 + 积分 + 信誉雷达图 |
| **版本管理** | arXiv 只能追加版本号，无法 diff | git 原生：diff、blame、branch、merge |
| **贡献归属** | 只有作者列表，无贡献度细分 | git blame 驱动的贡献时间线 |
| **引用系统** | 静态参考文献，无法点击跳转 | 引用图 + CID 永久链接 + 可点击导航 |
| **出版模式** | 出版即锁定，纠错靠 errata | 持续演化，修改提案 + 审核，永远可以改进 |
| **守门人** | 期刊编辑、机构政治 | 社区投票 + 信誉加权，算法透明 |
| **收费** | APC（文章处理费）、订阅费 | 免费，积分驱动 |

### 1.2 定位：从百科全书到学术出版的全部

PeerPedia 的最终目标不是和 Wikipedia 竞争——而是让 Wikipedia 的开放协作精神 + arXiv 的预印本规模 + 期刊的同行审核质量，三者合一。

```
Wikipedia ─────── arXiv ─────── 传统期刊
    │                 │               │
    │  开放协作        │  快速发布      │  同行审核
    │  版本可追溯      │  免费          │  学术声誉
    │                 │               │
    └─────────┬───────┴───────┬───────┘
              │               │
              ▼               ▼
           PeerPedia
     ┌──────┴──────┐
     │  三者合一    │
     │  + git 原生  │
     │  + P2P 存储  │
     │  + 积分激励  │
     │  + 贡献追踪  │
     └─────────────┘
```

### 1.3 MVP 阶段的范围（务实）

取代 arXiv 是十年目标。MVP 阶段从物理/数学领域开始，覆盖所有学术内容类型：

**支持的内容**（从种子阶段逐渐扩展）：
- 完整研究论文（和 arXiv 同等定位）
- 综述/review 文章
- 学位论文
- 课程笔记/讲义
- 百科知识条目

**不区分"适合"和"不适合"**——如果 arXiv 可以发，PeerPedia 就可以发。质量由审核和信誉系统保证，不由内容类型限制。

### 1.4 内容许可

默认 **CC BY-SA 4.0**（署名-相同方式共享），和 Wikipedia 一致：
- 提交文章即同意此许可
- 贡献者保留署名权，放弃排他性
- 衍生作品必须同样开放
- 作者可申请例外许可（如商业使用限制）——需社区投票通过
- 符合 P2P 开放精神，也是学术界最可接受的开放许可

### 与 Wikipedia 的关键区别

| Wikipedia | PeerPedia |
|---|---|
| 先发布、后审核 | **先审核、后出版** |
| 匿名编辑、人人可改 | 署名作者 + 审稿人，变更可追溯 |
| 单一版本流 | Git 完整版本历史 |
| 中心化服务器 | P2P 分布式存储 (IPFS) |
| 无激励机制 | **积分制** + 多维信誉系统 |
| 编辑是独立的 | **一键协作**：审稿人 → 合作者 |
| 引用靠搜索 | **引用图可点击跳转** |

---

## 2. User Flow（用户流程）

### 2.1 作者视角

```
1. 安装 PeerPedia（CLI + 本地 Web 界面）
2. 用自己喜欢的 Typst 样式写文章（无强制模板）
3. 本地编译预览（$ typst compile main.typ）
4. git commit 保存版本
5. 提交审核：指定学科分类、关键词、摘要
6. 等待审稿意见
7. 根据意见修改 → 重新提交（可邀请审稿人协作）
8. 审核通过 → 文章获得 IPFS CID → 发布
9. 收获积分（基于文章质量评分和被引次数）
```

### 2.2 审稿人视角

```
1. 浏览待审文章列表（按学科/语言筛选）
2. 认领审稿任务 → 获得积分预承诺
3. 下载 Typst 源码 + 自动编译的 PDF
4. 填写审稿意见：
   - 科学性/正确性（1-5 星）
   - 表述清晰度（1-5 星）
   - 建议：接受 / 修改后接受 / 拒绝
5. 可选：点击 "申请协作" → 作者同意后成为合作者
6. 审稿完成后获得积分
7. 审稿记录公开（贡献于信誉系统）
```

### 2.3 读者视角

```
1. 浏览百科目录（按学科/关键词/时间/语言）
2. 全文搜索（Typst 源码 + 元数据）
3. 阅读文章（在线渲染 HTML 或下载 PDF）
4. 点击文中引用 → 直接跳转到被引文章 ⬅ 核心特性
5. 查看文章版本历史（git log + diff）
6. 查看审稿记录（谁审的、什么意见）
7. 查看作者信誉分和协作贡献度
8. Pin 文章到本地（IPFS 固定，帮助做种）
9. 引用文章：复制 CID 永久链接
```

### 2.4 引用跳转流程（核心交互）

```
阅读文章 A
  │
  ├─ 文中出现 @citation-key 或 \cite{...}
  │     ↓
  │  渲染为可点击链接（蓝色下划线）
  │     ↓
  │  点击 → 系统查找被引文章的 CID
  │     ↓
  │  如果本地有缓存 → 直接打开文章 B
  │  如果本地没有 → 从 IPFS 下载 → 然后打开
  │     ↓
  │  文章 B 渲染，引用图更新
  │     ↓
  │  读者可以沿着引用链一直跳转下去
  │    （类似 Wikipedia 的蓝色链接体验，但层级是学术引用关系）
```

---

## 3. Collaboration: 持续协作 + 开放编辑

PeerPedia 的协作不限于审稿阶段。文章出版后仍然**持续演化**——任何人都可以提交修改，所有贡献被 git 完整记录。

### 3.1 两种协作模式

```
模式 A: 审稿期协作（审稿人 → 合作者）
  审稿人审稿 → 申请协作 → 作者同意 → 修改 → 共同发表

模式 B: 出版后开放编辑（任何人 → 贡献者）
  文章已发布 → 任何人 fork/edit → 提交修改 → 作者/社区审查 → merge → 贡献历史更新
```

### 3.2 审稿期协作（模式 A）

```
审稿人审稿
  │
  ├─ 发现文章有改进空间
  │     │
  │     ▼
  │  点击 "申请协作" 按钮
  │     │
  │     ├─ 填写：我想改进的部分
  │     │
  │     ▼
  │  作者收到协作申请
  │     │
  │     ├─ 同意 → 审稿人在 git 分支上修改 → 提交 PR → merge
  │     │         └─ 审稿人变为 合作者，贡献记录写入 git log
  │     │
  │     └─ 拒绝 → 审稿意见保留
```

### 3.3 出版后开放编辑（模式 B）⭐ 核心创新

```
文章已发布（status = published）
  │
  │  任何用户都可以：
  │
  ├─ Fork 文章到自己的分支
  │     │
  │     ▼
  │   编辑 .typ 文件，改进内容
  │     │
  │     ▼
  │   提交 Edit Proposal（修改提案）
  │     │
  │     ├─ 微小修改（错字、格式）  → 自动通过（1 天公示期）
  │     ├─ 中等修改（段落/公式）   → 原作者 review
  │     └─ 重大修改（新增章节）    → 社区 review（消耗积分发起）
  │
  ▼
修改 merge → 贡献历史追加新条目 → 积分分配更新
```

### 3.4 功劳记录：从静态百分比到贡献时间线

**旧模型（静态）**：
```
作者: 张三 (70%), 李四 (30%)  ← 一次性的、出版时确定
```

**新模型（动态贡献时间线）**：
```
Article "Quantum Error Correction" 贡献时间线：
───────────────────────────────────────────────────────────▶
2025-03  v1.0  张三      初始版本（500 行）        70%
2025-04  v1.1  李四      新增 §3 表面码（+200 行）  25%
2025-06  v1.2  王五      修正定理 2.1 证明（±15 行） 3%
2025-09  v2.0  赵六      重构 §2 框架（+300/-100）   15%
2026-01  v2.1  张三      更新引用 + 排版（+10 行）   2%
         ...持续演化中...

当前快照（git blame on HEAD）：
  张三: 55%  李四: 20%  赵六: 15%  王五: 5%  其他: 5%
```

### 3.5 贡献度计算规则

```python
# 每个 commit 自动记录元数据
class ContributionRecord:
    user_id: str
    timestamp: datetime
    commit_hash: str
    lines_added: int
    lines_deleted: int
    files_changed: int
    contribution_weight: float     # 该 commit 的贡献权重
    # 权重 = f(lines_changed, complexity, time_factor)
    # 复杂度因子：公式修改 > 证明修改 > 文字修改 > 格式修改

# 当前贡献比例 = 各贡献者权重 / 总权重（时间衰减加权）
# 越近的贡献权重越大 → 持续维护者获得持续认可
```

| 修改类型 | 权重系数 | 示例 |
|---|---|---|
| 新增定理/证明 | 5.0× | 添加完整的数学证明 |
| 修改核心逻辑 | 4.0× | 修正定理或算法 |
| 新增段落/解释 | 2.0× | 补充背景或例子 |
| 文字润色 | 1.0× | 改善表述 |
| 格式/引用修正 | 0.3× | 排版调整、更新引用 |

### 3.6 开放编辑的治理

```
微小修改（自动通过）：
  ├─ 错别字修正、格式调整
  ├─ 引用更新（添加新文献）
  ├─ 公式排版优化
  └─ 门槛：diff < 20 行 && 不改变语义

中等修改（原作者 review）：
  ├─ 段落重写、补充解释
  ├─ 定理证明的修正
  ├─ 新增子章节（< 100 行）
  └─ 流程：提交 → 通知原作者 → 7 天内 review → merge/reject

重大修改（社区 review）：
  ├─ 新增完整章节
  ├─ 改变文章核心论点
  ├─ 重构文章结构
  └─ 流程：提交 → 消耗积分发起 review → 社区投票 → 原作者有否决权
```

### 3.7 原作者的权利保护

- **署名永存**：初始作者永远是 "Founding Author"，显示在文章顶部
- **否决权**：原作者可以拒绝任何修改（但需要给出理由）
- **转让机制**：原作者长期不活跃（>1 年），否决权降级为普通投票权
- **通知系统**：任何修改提案都会通知原作者（邮件/应用内）

---

## 4. Incentive System: 积分制

### 4.1 积分获取途径

| 行为 | 积分 | 说明 |
|---|---|---|
| **提交文章** | +10 | 提交并通过初审进入审核队列 |
| **文章被接受** | +50 | 审核通过，正式发表 |
| **完成审稿** | +20 | 提交有效的审稿意见（非敷衍） |
| **高质量审稿** | +5~30 | 作者/系统对审稿质量打分 |
| **协作贡献** | 按贡献权重 | 审稿期协作或出版后编辑，积分按贡献权重分配 |
| **出版后编辑** | 按贡献权重 × 时间衰减 | 持续维护者获得持续积分，但权重随时间下降 |
| **文章被引用** | +2/次 | 每被引用一次获得积分 |
| **Pin 内容** | +1/天 | IPFS 做种帮助分发（P2P 阶段） |
| **举报垃圾** | +5 | 有效举报恶意内容 |

### 4.2 积分用途

| 用途 | 花费 |
|---|---|
| 提交文章（防止垃圾） | -5（押金，接受后退还） |
| 提升文章可见度 | 消耗积分置顶/推荐 |
| 创建学科分类 | -20（防止分类爆炸） |
| 发起社区投票 | -10 |

---

## 5. Multi-dimensional Reputation System（多维信誉系统）

用户信誉不是一个数字，而是一个**雷达图**（radar chart），展示多维能力画像。

### 5.1 信誉维度

```
          学术贡献
             /\
            /  \
           /    \
          /      \
   教学传播 ────── 审稿质量
          \      /
           \    /
            \  /
          协作精神
```

| 维度 | 计算方式 | 含义 |
|---|---|---|
| **学术贡献** | 发表文章数量 × 平均被引次数 | 学术产出力 |
| **审稿质量** | 审稿意见被作者/系统评为有用的比例 | 同行评议能力 |
| **协作精神** | 合作文章数 + 作者对合作者的评分 | 团队合作能力 |
| **教学传播** | 文章被读者 pin/收藏/分享的次数 | 知识传播影响力 |

### 5.2 信誉累计效应

- 高信誉用户提交的文章**优先进入审核队列**
- 高信誉审稿人的意见**权重更高**
- 信誉随时间和活跃度**自然衰减**（防止早期大 V 垄断）
- 所有评分可追溯、可质疑（git 记录一切）

---

## 6. Community Governance（社区治理）

### 6.1 垃圾/恶意内容治理

不依赖中心化管理员，而是社区机制：

```
层级 1: 自动过滤
  ├─ 内容相似度检测（检测重复/剽窃提交）
  ├─ 提交押金机制（-5 积分，防止滥发）
  └─ 新用户提交频率限制

层级 2: 审稿人拦截
  ├─ 审稿人可标记 "疑似垃圾/低质量"
  ├─ 累计 3 个审稿人标记 → 文章自动退回
  └─ 标记准确则审稿人获得积分奖励

层级 3: 社区举报
  ├─ 任何用户可举报已发表文章
  ├─ 举报需要消耗积分（防止滥用举报）
  ├─ 达到阈值 → 触发重新审核（re-review）
  └─ 举报成功 → 返还积分 + 奖励

层级 4: 信誉惩罚
  ├─ 被多次退回/举报 → 用户信誉下降
  ├─ 低于阈值 → 提交和审稿权限受限
  └─ 可以通过高质量贡献恢复信誉
```

### 6.2 争议解决

```
争议类型           解决方式
────────────────────────────────────
审稿意见分歧     → 作者可请求第三方仲裁（消耗积分）
贡献度计算争议   → git blame 为准，可人工申诉
分类归属争议     → 社区投票（积分加权）
学术不端指控     → 触发正式调查，信誉冻结
```

---

## 7. Data Model（数据模型）

### 7.1 Article（文章）

```python
class Article:
    id: str                      # uuid
    title: str
    founding_authors: list[str]  # 创始作者 user_id（永不变）
    abstract: str
    abstract_zh: str | None      # 中文摘要
    categories: list[str]        # 学科分类标签（中英文）
    keywords: list[str]
    language: str                # "zh" | "en" | "bilingual"
    status: ArticleStatus
    git_repo_path: Path
    typst_main: str              # 主 .typ 文件名
    references: list[Ref]         # 引用列表（含 CID 跳转链接）
    cited_by: list[str]           # 被哪些文章引用（反向链接）
    created_at: datetime
    updated_at: datetime
    version: str                 # 语义版本，如 "v2.1"
    cid: str | None              # IPFS CID（发布后才有）
    pinned_by: int               # 被多少节点 pin
    edit_policy: EditPolicy      # 开放编辑策略（作者可设置）

class ContributionSnapshot:
    """每个版本发布时拍一张贡献度快照"""
    version: str                 # "v1.0", "v1.1", "v2.0"
    timestamp: datetime
    git_commit: str
    contributions: list[ContributorShare]
    total_lines: int

class ContributorShare:
    user_id: str
    percentage: float            # 该版本中的贡献占比
    lines_owned: int             # git blame 该用户的代码行数
    role: str                    # "founding" | "co-author" | "contributor" | "editor"
```

### 7.1b ContributionRecord（功劳记录）

```python
class ContributionRecord:
    """每次 commit 生成一条贡献记录，存储在 SQLite 中"""
    id: str
    article_id: str
    user_id: str
    timestamp: datetime
    commit_hash: str
    commit_message: str
    lines_added: int
    lines_deleted: int
    files_changed: list[str]
    change_type: ChangeType      # "new_theorem" | "proof_fix" | "content" | "prose" | "format"
    contribution_weight: float   # 自动计算
    edit_proposal_id: str | None # 关联的编辑提案（开放编辑时）

class ChangeType:
    NEW_THEOREM = "new_theorem"    # ×5.0 权重
    PROOF_FIX = "proof_fix"        # ×4.0 权重
    CONTENT = "content"             # ×2.0 权重
    PROSE = "prose"                 # ×1.0 权重
    FORMAT = "format"               # ×0.3 权重

class EditProposal:
    """开放编辑提案"""
    id: str
    article_id: str
    proposer_id: str
    proposal_type: EditType       # "minor" | "medium" | "major"
    description: str
    git_branch: str
    diff_stat: str                # 改动统计摘要
    status: ProposalStatus        # "pending" | "approved" | "rejected" | "auto_approved"
    reviewer_ids: list[str]       # 审阅者（原作者或社区成员）
    points_stake: int             # 发起提案消耗的积分（major 时）
    created_at: datetime
    resolved_at: datetime | None
```

### 7.2 ArticleStatus 状态机

```
                            ┌─ 开放编辑循环 ──────────────────────┐
                            │                                      │
                            ▼                                      │
draft ──submit──▶ submitted ──assign──▶ in_review                 │
                                            │                      │
                              ┌─ accept ────┤                      │
                              ▼             │                      │
                          accepted          │                      │
                              │             │                      │
                          publish           │                      │
                              ▼             │                      │
                          published ────────┼──▶ edit_proposed ──┤
                              │             │         │           │
                              │     revisions_requested  │        │
                              │             │         │           │
                              │    ┌───────┼───────┐ ▼           │
                              │    ▼       │       ▼ merge       │
                              │  revise     │   协作分支   ──────┘
                              │    │        │   (co-author  更新贡献
                              │    ▼        │    join)      历史)
                              │ submitted    │
                              │  (loop)      │
                              │           reject ──▶ rejected
                              │                        │
                              └── 重新提交 ─────────────┘
```

出版后状态循环：
```
published → 任何人提交 edit_proposal → 审核 → merge
                                               │
                                               ▼
                                        贡献历史更新
                                        版本号递增（v1.0 → v1.1）
                                        积分重新分配
                                               │
                                               ▼
                                        回到 published（等待下一次编辑）
```

### 7.3 Review

```python
class Review:
    id: str
    article_id: str
    reviewer_id: str
    decision: Decision             # accept | revise | reject
    comments: str                  # Markdown
    scientific_correctness: int    # 1-5
    clarity: int                   # 1-5
    collaboration_request: bool    # 是否申请协作
    collaboration_message: str     # 想改进的部分
    collaboration_accepted: bool   # 作者是否同意
    points_earned: int             # 本次审稿获得积分
    review_quality_score: float    # 作者的评分（影响审稿人信誉）
    created_at: datetime
    git_commit_hash: str
```

### 7.4 User（用户 Profile + 信誉 + 身份）

```python
class User:
    id: str
    name: str
    email: str
    affiliation: str | None
    expertise: list[str]           # 专长领域

    # 身份验证（可多选绑定，权重累加）
    identities: list[Identity]

    public_key: str                # PGP/SSH（用于签名）
    joined_at: datetime

class Identity:
    """身份验证源，不是自己造的，是接入已有信任根"""
    type: IdentityType
    value: str                    # ORCID ID / 机构邮箱 / arXiv ID / GitHub username
    verified: bool                # 是否已验证
    trust_weight: float           # 对信誉的贡献权重

class IdentityType:
    ORCID = "orcid"               # 学术界通用 ID，权重 1.0
    INST_EMAIL = "inst_email"     # 机构邮箱 @*.edu / @*.ac.cn，权重 0.8
    ARXIV = "arxiv"               # arXiv author ID，权重 0.6
    GITHUB = "github"             # GitHub 账号，权重 0.3
    GOOGLE_SCHOLAR = "scholar"    # Google Scholar profile，权重 0.5
    # 无验证 = 权重 0.1（可以做任何事，但信誉积累慢）

class Reputation:
    user_id: str
    academic_contribution: float   # 0-100 学术贡献
    review_quality: float          # 0-100 审稿质量
    collaboration_spirit: float    # 0-100 协作精神
    education_outreach: float      # 0-100 教学传播
    total_points: int              # 累计积分
    updated_at: datetime
    # 衰减规则：连续 90 天不活跃，各项每天衰减 0.1%
```

> **设计原则**：不自己造身份系统。接入 ORCID、机构邮箱、arXiv 等已有信任根。Sybil 攻击的成本 = 伪造这些已有身份的成本。

---

## 8. Cross-Reference System（引用跳转系统）

### 8.1 引用解析

```typst
// 在 Typst 文章中引用其他 PeerPedia 文章
#cite("peerpedia:<article-cid>")
#cite("peerpedia:<article-id>")
或使用 BibTeX 风格：
@peerpedia_article_key
```

系统在编译前**预处理** Typst 源码：
1. 扫描所有 `#cite("peerpedia:...")` 引用
2. 解析 CID/id → 查到目标文章元数据
3. 注入渲染为超链接（HTML）或 PDF 内部链接

### 8.2 引用图

```
Article A ──cites──▶ Article B
   │                     │
   └──cites──▶ Article C ──cites──▶ Article D
                     ▲
Article E ──cites───┘
```

- 每篇文章生成**引用关系图**（DAG）
- 用户可以沿引用链向上（谁引用了这篇）和向下（这篇引用了谁）浏览
- 类似 Wikipedia 的内部链接网络，但关系是**学术引用**而非词条关联

### 8.3 跳转体验

```
阅读页面右侧栏：
┌─────────────────────────┐
│ 📚 引用关系图            │
│                         │
│ 被引用 (cited by):      │
│ → Article E (2024)      │
│ → Article X (2025)      │
│                         │
│ 引用 (cites):           │
│ → Article B (2023) ⬅ 可点击
│ → Article C (2022) ⬅ 可点击
│ → Article D (2020) ⬅ 可点击
└─────────────────────────┘
```

---

## 9. Architecture（MVP 架构）

### 9.1 部署模式

```
Mode 1: 单机模式（本地）
  │  $ peerpedia serve
  │  一个人写文章、编译、管理，用于个人写作阶段
  │
Mode 2: LAN 模式（局域网）⭐ MVP 新增
  │  $ peerpedia serve --lan
  │  同 WiFi 下的两个用户可以互相提交/审稿/协作
  │  用 HTTP API + SQLite 同步
  │  比单机多不了多少工作量，但能真正验证协作流程
  │
Mode 3: P2P 模式（IPFS，Phase 2）
  │  全局分布式网络
```

### 9.2 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI (click)                               │
│  $ peerpedia init                                            │
│  $ peerpedia serve [--lan]    ← 启动 Web（可选 LAN 模式）    │
│  $ peerpedia submit article.typ                              │
│  $ peerpedia review <id>                                     │
│  $ peerpedia collaborate <id>                                │
│  $ peerpedia propose-edit <id>   ← 出版后提交修改提案         │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│             Web UI (FastAPI + Jinja2 + HTMX)                 │
│  - 文章列表 / 浏览 / 搜索（中英双语）                          │
│  - 提交页面（Typst / Markdown+KaTeX 两种入口）                │
│  - 审稿后台                                                 │
│  - 引用图可视化（D3.js 交互浏览）                              │
│  - 信誉雷达图（Chart.js 用户主页）                             │
│  - 一键协作按钮                                              │
│  - 开放编辑提案面板                                          │
│  - LAN 节点发现面板                                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                Core Engine (Python)                           │
│  - 文章状态机（draft → published → edit_proposed → ...）     │
│  - 审稿工作流 + 积分计算                                      │
│  - 协作管理 + 开放编辑提案                                    │
│  - 引用解析引擎（scan → resolve → hyperlink）                │
│  - 信誉计算引擎（多维度 + 衰减 + 身份权重）                    │
│  - Git 集成（GitPython）                                     │
│  - 编译器层（可插拔）                                         │
│    ├─ Typst 编译（subprocess typst CLI）                     │
│    └─ Markdown + KaTeX 转换器（Python 实现，轻量入口）        │
│  - LAN 同步（简单的 HTTP + SQLite pull/push）                 │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                  Storage Layer                                │
│  - ~/.peerpedia/articles/  (git repos)                       │
│  - ~/.peerpedia/profiles/  (用户数据)                         │
│  - SQLite: 元数据、信誉、积分、引用图、贡献历史               │
│  - 未来: IPFS blockstore                                     │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 可插拔编译器设计

```python
class CompilerBackend(ABC):
    """编译器后端抽象接口"""
    @abstractmethod
    def compile(self, source: str, output_dir: Path) -> CompileResult: ...
    @abstractmethod
    def extract_references(self, source: str) -> list[Ref]: ...
    @abstractmethod
    def extract_metadata(self, source: str) -> ArticleMeta: ...
    @property
    @abstractmethod
    def format_name(self) -> str: ...

class TypstBackend(CompilerBackend):
    format_name = "typst"
    # 调用本地 typst CLI
    # 完整支持 Typst 语法

class MarkdownBackend(CompilerBackend):
    format_name = "markdown"
    # Python 实现，Markdown + KaTeX 数学公式
    # 转为 HTML 渲染，轻量入口
    # 不支持复杂排版，但降低新用户的尝试成本
```

| 输入格式 | 目标用户 | MVP 包含？ |
|---|---|---|
| **Typst** | 学术核心用户（数学/物理/CS） | ✅ 主力支持 |
| **Markdown + KaTeX** | 轻量入门、快速笔记、跨学科用户 | ✅ MVP 包含 |

### 9.4 技术选型

| 层 | 技术 | 理由 |
|---|---|---|
| CLI | Python `click` | 简单、类型提示好 |
| Web | FastAPI + Jinja2 + HTMX | 轻量、服务端渲染为主、少写 JS |
| 数据库 | SQLite | 零配置、本地优先 |
| Git | GitPython | 原生 Python git 操作 |
| Typst | subprocess `typst` | Typst CLI 极快 |
| Markdown | Python `markdown-it-py` + KaTeX 服务端渲染 | 轻量入口 |
| 引用图 | NetworkX | Python 图算法库（DAG 遍历、PageRank 等） |
| LAN 同步 | HTTP API + SQLite diff/patch | 简单可靠 |
| 可视化 | D3.js（引用图）、Chart.js（雷达图） | 成熟、轻量 |

---

## 10. Protocol Design（协议设计）

PeerPedia 不仅是一个应用，更是一个**协议**。任何人可以基于协议写自己的客户端。

### 10.1 协议分层

```
Layer 0: Core Protocol（不可变 — 改了就是新协议）
  │  消息格式、签名方案、CID 寻址、git 对象结构
  │  类比：IP 数据包格式、HTTP 请求行
  │  互操作性依赖此层的稳定性
  │
Layer 1: Versioned Modules（版本化 — PIP 流程升级）
  │  信誉算法 / 积分计算 / 贡献度公式 / 审核权重
  │  通过 PeerPedia Improvement Proposal (PIP) 提案
  │  新旧版本共存过渡期，节点逐步升级
  │
Layer 2: Configurable Parameters（可配置 — 社区投票调整）
  │  衰减率、权重系数、投票阈值、乘数因子
  │  不同社区可设不同参数，不影响互操作
```

### 10.2 协议演进机制：PIP（PeerPedia Improvement Proposal）

```
任何人 → 提交 PIP 草案
  │
  ▼
社区讨论（公开，git tracked）
  │
  ▼
投票（积分 + 信誉加权）
  │
  ├─ 通过 → 纳入协议规范 → 参考实现更新
  │
  └─ 驳回 → 草案存档，可修改后重新提交
```

类比：Python 的 PEP、Bitcoin 的 BIP、IETF 的 RFC。

### 10.3 代码架构：协议 vs 客户端分离

```
peerpedia-core/          ← 协议库（Python package）
  ├─ protocol/
  │   ├─ messages.py     ← 消息格式定义（submit, review, edit_proposal, ...）
  │   ├─ signing.py      ← 签名和验证
  │   ├─ addressing.py   ← CID 寻址
  │   └─ schemas.py      ← JSON schemas（严格定义，不可变）
  ├─ reputation/
  │   ├─ v1.py           ← 信誉算法 v1
  │   ├─ v2.py           ← 信誉算法 v2（未来）
  │   └─ base.py         ← 抽象接口
  ├─ governance/
  │   └─ pip.py          ← PIP 提案流程
  └─ storage/
      ├─ git_backend.py  ← Git 对象存储
      └─ ipfs_backend.py ← IPFS 存储（Phase 2）

peerpedia/               ← 官方参考客户端（CLI + Web）
  ├─ cli/                ← click 命令
  ├─ web/                ← FastAPI + Jinja2 + HTMX
  └─ config/             ← 用户配置和社区参数
```

### 10.4 什么能改、什么不能改

| 能改（Layer 2） | 能升级（Layer 1） | 不能改（Layer 0） |
|---|---|---|
| 衰减率 0.1%/天 → 0.05%/天 | 信誉算法 v1 → v2 | 消息 JSON schema |
| 新定理权重 5.0× → 4.0× | 积分计算公式改进 | 签名算法 |
| 微小修改阈值 20 行 → 15 行 | 贡献度计算升级 | CID 寻址格式 |
| 投票通过阈值 51% → 67% | 审核分配算法 | git 对象结构 |

> **核心原则**：凡是影响 "两个节点能不能互相理解" 的，冻住（Layer 0）。凡是影响 "谁的信誉更高" 的，可以改（Layer 1/2）。

### 10.5 多客户端生态（远期）

```
官方参考客户端：peerpedia CLI + Web

可能的第三方客户端：
  ├─ PeerPedia Desktop（Tauri 桌面 App）
  ├─ PeerPedia.el（Emacs 集成，学者最爱）
  ├─ PeerPedia Mobile（手机浏览和审稿）
  ├─ PeerPedia Institutional（大学机构节点，自动 pin + 验证）
  └─ 任何实现协议的应用
```

只要实现了 Layer 0 消息格式和签名，就可以和所有其他节点互通。

---

## 11. Roadmap（路线图）

```
Phase 1 (MVP)        Phase 2              Phase 3              Phase 4
─────────────────────────────────────────────────────────────────────────
单机版               + IPFS 存储           + 联邦搜索           + AI 辅助
本地 git             + CID 寻址            + 跨节点审稿         + 智能审稿
本地用户/信誉        + IPNS 发布           + 分布式信誉         + 自动翻译
SQLite               + libp2p 发现         + 代币激励(可选)     + 推荐系统
```

### Phase 4: AI 辅助（远期展望，MVP 不需要考虑）

可能的 AI 集成点（等核心流程跑通后再设计）：

| 功能 | 说明 | 优先级 |
|---|---|---|
| **智能审稿辅助** | AI 先跑一遍文章，标注潜在的逻辑漏洞、数学错误、引用缺失 | 低 |
| **中英互译** | 自动翻译文章/摘要，降低双语维护成本 | 低 |
| **推荐审稿人** | 基于语义匹配推荐最合适的审稿人 | 低 |
| **写作辅助** | Typst 编辑器内 AI 补全、参考文献自动格式化 | 低 |
| **抄袭检测** | 语义相似度检测，标记可疑提交 | 低 |

> **设计原则**：架构上预留扩展点（如 review pipeline 可插拔 hook），但 MVP 不实现任何 AI 功能。先把人工审核的完整闭环跑通。

---

## 12. Cold Start Strategy（冷启动策略）

PeerPedia 面临双边冷启动问题：没有作者就没有审稿人，没有审稿人就没有作者。

### 11.1 策略：从一个学科切入，不追求全学科

不试图第一天就取代 arXiv 的所有学科。先在一个小领域证明模式可行：

```
Phase 0: 种子社区
  ├─ 目标领域：数学物理 / 张量网络 / 量子信息（用户的现有圈子）
  ├─ 招募 5-10 个种子用户（GitHub 合作者、同学、同行）
  ├─ 每人写 1-2 篇文章（可以是已有笔记的 Typst 化）
  └─ 互相审稿，跑通流程

Phase 1: 领域内增长
  ├─ 在该领域产生 20-50 篇文章后
  ├─ 文章质量成为最好的广告
  └─ 自然吸引该领域的其他人

Phase 2: 跨学科扩张
  └─ 当模式被验证后，其他学科自然复制
```

### 11.2 种子阶段不需要完美

| 暂时不需要的 | 为什么 |
|---|---|
| P2P 分布式存储 | 5 个人用 LAN 就够了 |
| 复杂信誉算法 | 互相认识的人不需要算法防作弊 |
| 垃圾治理 | 种子用户不会发垃圾 |
| AI 辅助 | 人比 AI 审得好 |

种子阶段只需要：**提交 → 审稿 → 协作 → 出版 → 贡献记录**。其他都是以后的事。

### 11.3 最小可发布版本

```
五个人能在 LAN 下：
  1. 用 Typst/Markdown 写文章
  2. 提交到共同的文章池
  3. 互相分配审稿
  4. 填写审稿意见、打分、决策
  5. 接受 → 文章出版，获得积分
  6. 出版后提交修改提案 → 原作者同意 → 合并 → 贡献记录更新
  7. 查看文章时点击引用跳转
```

这就是 PeerPedia 的 "Hello World"。

---

## 13. Decisions Made（已确定）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 项目名 | **PeerPedia** |
| 2 | 审稿激励 | **积分制**（提交/审稿/协作/被引 均获积分） |
| 3 | 信誉系统 | **多维雷达图**（学术/审稿/协作/传播四个维度 + 时间衰减） |
| 4 | 垃圾治理 | **社区多层级机制**（自动过滤 → 审稿拦截 → 举报 → 信誉惩罚） |
| 5 | Typst 模板 | **无强制模板**，用户自选排版风格 |
| 6 | 数学公式 | Typst 原生支持，**零配置** |
| 7 | 语言 | **中文 + 英文**双语言支持 |
| 8 | 协作 | **一键合作 + 开放编辑**：审稿期协作（模式 A）+ 出版后任何人可提交修改（模式 B） |
| 9 | 功劳机制 | **贡献时间线**：git log 即功劳历史，动态计算占比，不锁死在出版时刻 |
| 10 | 引用跳转 | **可点击引用图**：文中 @cite 渲染为超链接，侧栏显示引用关系 DAG |
| 11 | 应用形态 | CLI + 本地 Web（先单机 MVP，后 P2P） |
| 12 | P2P 协议 | IPFS（内容寻址 + CID 永久引用） |
| 13 | AI 辅助 | **MVP 不做**，架构预留扩展点，Phase 4 再加 |
| 14 | 内容许可 | **CC BY-SA 4.0**，和 Wikipedia 一致 |
| 15 | 身份系统 | **不自造**，接入 ORCID / 机构邮箱 / arXiv / GitHub 等已有信任根 |
| 16 | 输入格式 | **Typst 主力 + Markdown+KaTeX 轻量入口**，编译器可插拔 |
| 17 | 部署模式 | **单机 + LAN**，MVP 加局域网模式验证真协作 |
| 18 | 冷启动 | **从数学物理/张量网络圈子开始**，5-10 个种子用户，不追求全学科 |
| 19 | 定位 | **取代 arXiv + 学术出版**——Wikipedia 的开放 + arXiv 的规模 + 期刊的审核质量，三者合一 |
| 20 | 终极目标 | **arXiv 和大部分学术出版系统的替代品**（十年目标） |
| 21 | 协议设计 | **三层协议架构**：Layer 0 核心（不可变）→ Layer 1 版本化模块（PIP 升级）→ Layer 2 可配置参数（社区投票） |
| 22 | 代码架构 | `peerpedia-core`（协议库）+ `peerpedia`（参考客户端），分离为两个 Python 包 |
| 23 | 协议演进 | **PIP**（PeerPedia Improvement Proposal），类比 Python PEP / Bitcoin BIP |
| 24 | 历史参考 | **石渠阁**：Agent 硬件层解耦架构可继承，其他（浏览器 git、过早 P2P/AI）不再采用 |
| 25 | 中文原生支持 | **UI 层中文化**：CLI + Web 全中文界面，Frontmatter 支持中文字段别名（标题→title 等）。协议层保持英文不变 |
| 26 | ArXiv 搬运 | **peerpedia mirror**：调用 arXiv API 搬运文章。原作者成为悬空 founder（arxiv:slug 占位账户），搬运者 +5 积分。文章直接 published |
| 27 | 悬空 Founder | **arxiv:lastname-firstname** 占位账户，原作者以后可 claim。搬运文章 founding_authors 使用悬空 ID |
| 28 | 用户足迹 | **个人 arXiv**：/user/{user_id} 显示原创文章、搬运文章、审稿记录、积分统计、活动时间线 |
| 29 | PDF 策略 | **不存 PDF**：Typst 按需编译（毫秒级），git 仓库只存纯文本源码。阅读时 GET /compile?fmt=html|pdf |
| 30 | 编译时机 | **阅读时编译**：submit 时不做编译，文章页面通过 HTMX hx-trigger="load" 请求 /compile 端点 |

---

## 14. Progress（实际进度）

| Phase | 内容 | 状态 | 测试 |
|---|---|---|---|
| Phase 1 | Brainstorming（25 项决策） | ✅ | — |
| Phase 2 | 项目骨架（协议 + CLI + Web） | ✅ | 19 tests |
| Phase 3 M1 | 文章提交闭环（submit + DB + 编译器） | ✅ | 42 tests |
| Phase 3 M2 | 审稿工作流（状态机 + 审稿 + 决定 + 积分） | ✅ | 76 tests |
| Phase 3 M2.5 | 中文 UI + ArXiv 搬运 | ✅ | 84 tests |
| Phase 3 M2.6 | 用户足迹 + 按需编译 | ✅ | **87 tests** |
| Phase 3 M3 | 协作+开放编辑 | ✅ | **126 tests** |
| Phase 3 M4 | 信誉+LAN | ⏸ 待开始 | — |
| Phase 3 M5 | 引用跳转 | ⏸ 待开始 | — |
| Phase 4 | IPFS 集成 | ⏸ 远期 | — |
| Phase 5 | 种子社区测试 | ⏸ 远期 | — |
| Phase 6 | AI 辅助 | ⏸ 远期 | — |

### 当前可用的命令

```bash
peerpedia init                              # 初始化
peerpedia serve                             # 启动 Web（17 条路由）
peerpedia submit article.typ --author 张三    # 提交文章
peerpedia review <id> -d accept -c "很好"     # 审稿
peerpedia decide <id>                        # 决定
peerpedia mirror 2301.00001 -u 张三          # 搬运 arXiv
peerpedia collaborate <id> -r 审稿人         # 接受协作申请
peerpedia propose-edit <id> -t minor -d "修改" # 提交修改提案
peerpedia merge-proposal <pid> <aid>          # 合并提案
```

### 系统架构（实际）

```
peerpedia_core/
  protocol/        # Layer 0: 消息格式 + 签名 + CID
  reputation/      # Layer 1: 四维信誉算法 v1
  governance/      # Layer 1: PIP 提案流程
  workflow/        # Layer 1: 状态机 + 审稿编排 + 协作 + 编辑提案 + 贡献追踪
  storage/         # Layer 0: git backend + SQLite DB + compiler backends

peerpedia/
  cli/             # 7 个 CLI 命令（init, serve, submit, review, decide, mirror, collaborate, propose_edit）
  web/             # FastAPI + Jinja2 + HTMX（17 routes, 4 templates）
  submit.py        # 提交编排器
  mirror.py        # ArXiv 搬运编排器
  config/          # 设置

tests/             # 87 tests, 0 failures
```

---

> 本文档随实现进展持续更新。最新决策见 Section 13（#25-#30）。

> 本文档遵循 Superpowers 方法论：先 brainstorm，充分讨论后再进入 coding。
> 所有设计决策在进入 Phase 2 之前都可以修改。
