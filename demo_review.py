#!/usr/bin/env python3
"""Demo script: full review + collaboration + edit proposal workflow.

Runs against the existing PeerPedia database. Creates new articles, submits
reviews, makes decisions, and demonstrates the complete lifecycle.

Usage:
    source .venv/bin/activate
    python demo_review.py
"""

import sys
import tempfile
import uuid
from pathlib import Path

from peerpedia.config.settings import settings
from peerpedia.submit import submit_article
from peerpedia_core.storage.db import (
    get_engine,
    get_session,
    init_db,
    get_article,
    update_article_status,
    update_article_founding_authors,
    list_articles,
)
from peerpedia_core.workflow.review import assign_reviewer, submit_review, make_decision
from peerpedia_core.workflow.collaboration import accept_collaboration
from peerpedia_core.workflow.edit_proposal import create_proposal, review_proposal, merge_proposal

DB_URL = settings.database_url
ARTICLES_DIR = settings.articles_dir


def banner(text: str):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def step(n: int, text: str):
    print(f"\n--- Step {n}: {text} ---")


def get_latest_article_id():
    """Get the most recently created article ID."""
    engine = get_engine(DB_URL)
    init_db(engine)
    session = get_session(engine)
    try:
        articles = list_articles(session, limit=1)
        return articles[0].id if articles else None
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════════════════
# Scene 1: zhangliang submits a Typst article → liqun reviews → published
# ══════════════════════════════════════════════════════════════════════════════

banner("Scene 1: 完整审稿流程 — 张量提交 → 李群审稿 → 出版")

step(1, "张量 提交 Typst 文章「Gauge Theory and Fiber Bundles」")

SOURCE_1 = r"""---
title: Gauge Theory and Fiber Bundles
abstract: A pedagogical introduction to gauge theory from the fiber bundle perspective. We explain connections, curvature, and the Yang-Mills action in geometric language accessible to physics graduate students.
categories:
  - physics
  - geometry
keywords:
  - gauge theory
  - fiber bundles
  - yang-mills
language: en
---

= Gauge Theory and Fiber Bundles

== Introduction

Gauge theory is the mathematical framework underlying our description of fundamental forces. While physicists learn gauge theory through the Lagrangian formalism, the geometric formulation in terms of fiber bundles reveals deeper structure. This article aims to bridge that gap.

== Principal Bundles

A principal $G$-bundle is a fiber bundle $P \rightarrow M$ with structure group $G$ acting freely on the right. The base manifold $M$ is spacetime (or a Euclidean continuation thereof), and the fiber is the group $G$ itself.

$$P \times G \rightarrow P, \quad (p, g) \mapsto p \cdot g$$

== Connections as Gauge Fields

A connection on $P$ is a $G$-equivariant splitting of the tangent space:

$$TP = VP \oplus HP$$

where $VP \cong P \times \mathfrak{g}$ is the vertical subbundle (tangent to fibers) and $HP$ is the horizontal subbundle.

The connection 1-form $\omega \in \Omega^1(P, \mathfrak{g})$ satisfies:

$$R_g^*\omega = \operatorname{Ad}_{g^{-1}} \omega$$

In local coordinates, this gives the familiar gauge field $A_\mu$.

== Curvature

The curvature 2-form $\Omega$ is defined by the Cartan structure equation:

$$\Omega = d\omega + \frac{1}{2}[\omega, \omega]$$

This corresponds to the field strength $F_{\mu\nu}$ in physics notation.

== References

See peerpedia:c9743edc-b177-4c53-a4cb-5ecc80a060cf for the tensor network formulation.
"""

with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / "gauge_theory.typ"
    src.write_text(SOURCE_1)
    result = submit_article(
        source_path=src,
        database_url=DB_URL,
        articles_dir=ARTICLES_DIR,
        author_name="zhangliang",
        author_email="zhang@peerpedia.local",
        self_originality=4,  # 综述评论
        self_rigor=4,        # 严格证明
        self_completeness=3, # 核心完整
        self_pedagogy=4,     # 教学导向
        self_impact=3,       # 领域相关
    )

if not result.success:
    print(f"FAIL: {result.error}")
    sys.exit(1)

article1_id = result.article_id
print(f"  文章 ID: {article1_id[:8]}...")
print(f"  标题:    {result.title}")
print(f"  Commit:  {result.git_commit_hash[:8]}")

# Move to submitted so it appears in review queue
engine = get_engine(DB_URL)
init_db(engine)
session = get_session(engine)
update_article_status(session, article1_id, "submitted")
session.commit()
session.close()
print(f"  状态:    submitted → 审稿队列可见")


step(2, "李群 浏览审稿队列，认领审稿")

assign_result = assign_reviewer(
    article_id=article1_id,
    reviewer_id="liqun",
    database_url=DB_URL,
)
print(f"  分配审稿人: liqun → 文章状态: {assign_result.new_status}")


step(3, "李群 填写审稿意见 — accept")

review_result = submit_review(
    article_id=article1_id,
    reviewer_id="liqun",
    decision="accept",
    comments="""这篇规范场论的导引写得很好。从纤维丛的几何语言出发解释 Yang-Mills 理论，
对物理系研究生非常友好。建议补充一些关于瞬子（instantons）的内容。

数学上准确，表述清晰。建议接受。""",
    scientific_correctness=5,
    clarity=5,
    database_url=DB_URL,
)
print(f"  审稿完成: review_id={review_result.review_id[:8]}... +{review_result.points_earned} 积分")


step(4, "系统作出决定 — accept → published")

decision = make_decision(
    article_id=article1_id,
    database_url=DB_URL,
)
print(f"  决定: {decision.new_status}")

# Publish: accepted → published
session = get_session(engine)
update_article_status(session, article1_id, "published")
session.commit()
article1 = get_article(session, article1_id)
print(f"  张量获得: +{decision.author_points} 积分")
print(f"  最终状态: {article1.status} (版本 {article1.version})")
session.close()


# ══════════════════════════════════════════════════════════════════════════════
# Scene 2: zhaotongji submits, liqun requests revisions
# ══════════════════════════════════════════════════════════════════════════════

banner("Scene 2: 修改后接受 — 赵统计提交 → 李群建议修改 → 修改后接受")

step(5, "赵统计 提交 Markdown 文章「Bayesian Inference on Statistical Manifolds」")

SOURCE_2 = r"""---
title: Bayesian Inference on Statistical Manifolds
abstract: We explore the connection between Bayesian inference and information geometry, showing how the Fisher information metric defines a natural Riemannian structure on the space of probability distributions.
categories:
  - statistics
  - geometry
keywords:
  - bayesian
  - fisher information
  - information geometry
language: en
---

# Bayesian Inference on Statistical Manifolds

## Introduction

Bayesian inference updates beliefs: $P(\theta \mid D) \propto P(D \mid \theta) P(\theta)$. The prior $P(\theta)$ is a probability distribution over parameter space. When the parameter space has a natural Riemannian structure, Bayesian updating becomes geometric.

## Fisher Information as Metric

The Fisher information matrix:

$$g_{ij}(\theta) = \mathbb{E}\left[\frac{\partial \log p}{\partial \theta^i} \frac{\partial \log p}{\partial \theta^j}\right]$$

defines a Riemannian metric on the statistical manifold. The volume element $\sqrt{\det g} \, d\theta$ is the Jeffreys prior — the unique prior invariant under reparameterization.

## Natural Gradient Descent

The natural gradient uses the Fisher metric:

$$\theta_{t+1} = \theta_t - \eta \, g^{-1} \nabla L(\theta_t)$$

This descends the loss in the steepest *statistical* direction, not the steepest Euclidean direction.

See also: peerpedia:c9191d58-fb85-4dc7-a975-3a4bc5aefffc for the quantum information geometry formulation.
"""

with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / "bayesian_info_geom.md"
    src.write_text(SOURCE_2)
    result = submit_article(
        source_path=src,
        database_url=DB_URL,
        articles_dir=ARTICLES_DIR,
        author_name="zhaotongji",
        author_email="zhao@peerpedia.local",
        self_originality=5,  # 原创研究
        self_rigor=3,        # 标准推导
        self_completeness=2, # 部分覆盖
        self_pedagogy=3,     # 有基础可读
        self_impact=3,       # 领域相关
    )

article2_id = result.article_id
print(f"  文章 ID: {article2_id[:8]}...")
print(f"  标题:    {result.title}")

session = get_session(engine)
update_article_status(session, article2_id, "submitted")
session.commit()
session.close()

assign_reviewer(article_id=article2_id, reviewer_id="liqun", database_url=DB_URL)


step(6, "李群 审稿 — 建议修改 (revise)")

review2 = submit_review(
    article_id=article2_id,
    reviewer_id="liqun",
    decision="revise",
    comments="""方向很好，信息几何和贝叶斯的结合。但缺少一个关键例子——建议加一个
具体计算：二维高斯分布族的 Fisher 度规和自然梯度下降的例子。这会大大增加可读性。

补充这个例子后建议接受。""",
    scientific_correctness=4,
    clarity=3,
    collaboration_request=True,
    collaboration_message="我可以帮忙写二维高斯分布族的 Fisher 度规计算。",
    database_url=DB_URL,
)
print(f"  审稿意见: revise — 需要补充例子")


step(7, "赵统计 修改文章，重新提交 → 王守恒二审 accept")

# First review was "revise" by liqun → status is now revisions_requested
# Author revises → status back to submitted
session = get_session(engine)
update_article_status(session, article2_id, "submitted")
session.commit()
session.close()

# Wang takes second review (different reviewer since liqun already reviewed)
assign_reviewer(article_id=article2_id, reviewer_id="wangshouheng", database_url=DB_URL)

submit_review(
    article_id=article2_id,
    reviewer_id="wangshouheng",
    decision="accept",
    comments="补充了二维高斯例子后文章质量提升很多。Fisher 度规的计算很清楚。建议接受。",
    scientific_correctness=5,
    clarity=5,
    database_url=DB_URL,
)

decision2 = make_decision(article_id=article2_id, database_url=DB_URL)
print(f"  决定: {decision2.new_status}")

# Publish
session = get_session(engine)
update_article_status(session, article2_id, "published")
session.commit()
session.close()
print(f"  赵统计获得: +{decision2.author_points} 积分 → published")


# ══════════════════════════════════════════════════════════════════════════════
# Scene 3: Collaboration — 审稿人变合作者
# ══════════════════════════════════════════════════════════════════════════════

banner("Scene 3: 协作 — 李群申请协作 → 赵统计接受 → 李群成为合作者")

step(8, "赵统计 接受李群的协作申请")

# First, set liqun's review to have collaboration_request=True (already done above)
# Now accept the collaboration
collab_result = accept_collaboration(
    article_id=article2_id,
    reviewer_id="liqun",
    database_url=DB_URL,
)

session = get_session(engine)
article2 = get_article(session, article2_id)
authors = article2.founding_authors if article2 else []
session.close()

print(f"  合作者列表: {', '.join(authors)}")
print(f"  李群 (liqun) 已加入为合作者 ✓")


# ══════════════════════════════════════════════════════════════════════════════
# Scene 4: Post-publication edit proposal
# ══════════════════════════════════════════════════════════════════════════════

banner("Scene 4: 开放编辑 — 王守恒提交修改提案 → 作者审核 → merge")

# Use article 1 (Gauge Theory, already published)
step(9, "王守恒 对出版文章提交微小修改提案 (minor, 自动通过)")

proposal = create_proposal(
    article_id=article1_id,
    proposer_id="wangshouheng",
    proposal_type="minor",
    description="修复了两处笔误：将 'fiber bundle' 统一为 'fibre bundle'（英式拼写），修正了 Cartan 结构方程中的因子。",
    database_url=DB_URL,
)
print(f"  提案 ID: {proposal.proposal_id[:8]}...")
print(f"  类型:    {proposal.proposal_type}")
print(f"  状态:    {'auto_approved (微小修改自动通过)' if proposal.auto_approved else 'pending'}")


step(10, "王守恒 提交中等修改提案 (medium, 需要审核)")

proposal2 = create_proposal(
    article_id=article1_id,
    proposer_id="wangshouheng",
    proposal_type="medium",
    description="补充了瞬子（instantons）的章节。添加了 ADHM 构造的简介和与 Donaldson 理论的关系。约新增 50 行内容。",
    database_url=DB_URL,
)
print(f"  提案 ID: {proposal2.proposal_id[:8]}...")
print(f"  类型:    {proposal2.proposal_type}")
print(f"  状态:    pending (等待原作者审核)")


step(11, "原作者 张量 审核中等提案 — approve")

review_p = review_proposal(
    proposal_id=proposal2.proposal_id,
    reviewer_id="zhangliang",
    decision="approve",
    comment="瞬子章节写得很清晰，ADHM 构造的介绍恰到好处。同意合并。",
    database_url=DB_URL,
)
print(f"  审核结果: {review_p.new_status}")


step(12, "合并提案 → 版本号递增")

merge_result = merge_proposal(
    proposal_id=proposal2.proposal_id,
    article_id=article1_id,
    proposer_id="wangshouheng",
    repository_url=str(ARTICLES_DIR / article1_id),
    database_url=DB_URL,
    change_type="content",
)
print(f"  合并完成: 版本 {article1.version} → {merge_result.new_version}")
print(f"  王守恒获得贡献记录: {merge_result.contribution_record_id[:8]}...")


# ══════════════════════════════════════════════════════════════════════════════
# Scene 5: Mirror an arXiv article (if not already mirrored)
# ══════════════════════════════════════════════════════════════════════════════

banner("Scene 5: arXiv 搬运已有论文，建立讨论基础")

step(13, "检查 arXiv 搬运文章")

session = get_session(engine)
all_articles = list_articles(session, limit=100)
mirror_count = sum(1 for a in all_articles if a.mirror_by)
session.close()

if mirror_count == 0:
    print("  注意: 尚无 arXiv 搬运文章。可以运行:")
    print("    peerpedia mirror 2301.00001 -u wangshouheng")
    print("    peerpedia mirror 2301.00002 -u zhaotongji")
    print("  来搬运一些 arXiv 论文到系统中。")
else:
    print(f"  已有 {mirror_count} 篇 arXiv 搬运文章。")


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════

banner("Demo 完成 — 状态汇总")

session = get_session(engine)
articles = list_articles(session, limit=20)

print(f"\n  系统共有 {len(articles)} 篇文章:\n")
for a in articles:
    status_icon = {
        "draft": "📝",
        "submitted": "📤",
        "in_review": "🔍",
        "accepted": "✅",
        "published": "📖",
        "rejected": "❌",
        "revisions_requested": "🔄",
    }.get(a.status, "❓")

    authors_str = ", ".join(a.founding_authors[:3])
    if len(a.founding_authors) > 3:
        authors_str += f" +{len(a.founding_authors) - 3}"

    print(f"  {status_icon} [{a.status:20s}] {a.title[:55]:55s} | {authors_str} | {a.version}")

session.close()

print(f"\n  打开 http://localhost:8080 查看首页")
print(f"  打开 http://localhost:8080/review 查看审稿队列")
print(f"  打开 http://localhost:8080/article/{article1_id} 查看新增文章（含版本历史 tab）")
print()

# Also recreate a submitted article for the review queue
# (the Gauge Theory article is now published; create one more in submitted state)
step(14, "额外: 创建一篇 submitted 状态文章，让审稿队列不空")

SOURCE_3 = r"""---
title: Category Theory for Physicists: Monoidal Categories
abstract: A follow-up to the existing category theory article, focusing on monoidal categories and their applications in quantum mechanics and topological order.
categories:
  - math
  - physics
keywords:
  - monoidal categories
  - tensor categories
  - topological order
language: en
---

# Category Theory for Physicists: Monoidal Categories

## Introduction

Monoidal categories (also called tensor categories) are categories equipped with a tensor product structure. They are the natural mathematical framework for quantum mechanics, where the tensor product of Hilbert spaces describes composite systems.

## Definition

A monoidal category $(\mathcal{C}, \otimes, I)$ consists of:

- A category $\mathcal{C}$
- A bifunctor $\otimes: \mathcal{C} \times \mathcal{C} \rightarrow \mathcal{C}$
- A unit object $I$
- Natural isomorphisms for associativity and unit laws

## Applications

### Quantum Mechanics

The category of Hilbert spaces (Hilb) with the standard tensor product is the prototypical monoidal category for quantum theory.

### Topological Order

Modular tensor categories describe anyons in 2D topological phases. The fusion rules $N_{ab}^c$ encode the possible outcomes of fusing two anyons.
"""

with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / "monoidal_categories.md"
    src.write_text(SOURCE_3)
    result = submit_article(
        source_path=src,
        database_url=DB_URL,
        articles_dir=ARTICLES_DIR,
        author_name="liqun",
        author_email="li@peerpedia.local",
        self_originality=2,  # 学习笔记
        self_rigor=3,        # 标准推导
        self_completeness=3, # 核心完整
        self_pedagogy=5,     # 零基础入门
        self_impact=2,       # 小众专题
    )

article3_id = result.article_id
session = get_session(engine)
update_article_status(session, article3_id, "submitted")
session.commit()
session.close()

print(f"  文章 ID: {article3_id[:8]}... 状态: submitted")
print(f"  审稿队列: http://localhost:8080/review")
