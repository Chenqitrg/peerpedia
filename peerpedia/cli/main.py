"""PeerPedia CLI — Reference client command-line interface."""

from __future__ import annotations

from pathlib import Path

import click

# Import subcommand modules
from peerpedia.cli.article_commands import decide, review, submit
from peerpedia.cli.lan_commands import lan
from peerpedia.cli.social_commands import collaborate, merge_proposal, mirror, propose_edit
from peerpedia.cli.user_commands import user
from peerpedia_core import __version__


@click.group()
@click.version_option(__version__)
def cli():
    """知著网 (PeerPedia) — 去中心化学术出版系统。

    用 Typst 写作，同行审核，P2P 发布。
    """
    pass


@cli.command()
def init():
    """Initialize PeerPedia in the current directory.

    Creates ~/.peerpedia/ with default configuration, empty database,
    and required directory structure.
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.storage import DEFAULT_ARTICLES_DIR
    from peerpedia_core.storage.db import get_engine, init_db

    base = Path.home() / ".peerpedia"
    dirs = [
        base,
        DEFAULT_ARTICLES_DIR,
        base / "profiles",
        base / "db",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"PeerPedia 初始化完成: {base}")
    click.echo(f"  文章仓库目录: {DEFAULT_ARTICLES_DIR}")
    click.echo(f"  数据库: {settings.db_path}")
    click.echo("  下一步: peerpedia seed")


@cli.command()
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def seed(force: bool):
    """Recreate demo data — 4 users + 8 articles with self-ratings.

    Destroys existing database and rebuilds from scratch.
    Safe to run any time to reset to a known demo state.
    """
    import shutil
    import sys
    import tempfile
    import uuid
    from datetime import datetime, timezone

    from peerpedia.config.settings import settings
    from peerpedia.submit import submit_article
    from peerpedia_core.storage import DEFAULT_ARTICLES_DIR
    from peerpedia_core.storage.db import (
        get_engine, init_db, get_session, create_article,
        update_article_status, ArticleStatus,
    )
    from peerpedia_core.storage.db.models import User
    from peerpedia_core.workflow.review import (
        assign_reviewer, submit_review, make_decision,
    )

    if not force:
        click.confirm("⚠️  这将删除所有现有数据并重建 demo。继续？", abort=True)

    # ── Destroy old DB ──────────────────────────────────────────────────
    db_path = settings.db_path
    if db_path.exists():
        db_path.unlink()
        click.echo("  旧数据库已删除")

    # ── Recreate DB tables ──────────────────────────────────────────────
    engine = get_engine(settings.database_url)
    init_db(engine)

    # ── Create users ────────────────────────────────────────────────────
    session = get_session(engine)
    users_data = [
        ("zhangliang", "张量"),
        ("liqun", "李群"),
        ("wangshouheng", "王守恒"),
        ("zhaotongji", "赵统计"),
    ]
    for uid, name in users_data:
        u = User(id=uid, name=name, email=f"{uid}@peerpedia.local")
        session.add(u)
    session.commit()
    session.close()
    click.echo(f"  + {len(users_data)} 用户")

    # ── Article definitions ─────────────────────────────────────────────
    articles_def = [
        {
            "source": r"""---
title: Tensor Network Renormalization with R-functors
abstract: We propose a new framework for tensor network renormalization based on R-functors, establishing a rigorous connection between TNR algorithms and category theory.
categories:
  - physics
  - category-theory
keywords:
  - tensor networks
  - r-functors
  - renormalization
language: en
---

# Tensor Network Renormalization with R-functors

## Introduction

Tensor network renormalization (TNR) is a powerful framework for studying strongly correlated quantum systems. The partition function is:

$$Z = \operatorname{Tr}\left[e^{-\beta H}\right]$$

## R-functors

An R-functor $F: \mathcal{C} \rightarrow \mathcal{D}$ between tensor categories preserves the monoidal structure up to a natural isomorphism. This provides the categorical foundation for TNR.

## References

See peerpedia:c9191d58-fb85-4dc7-a975-3a4bc5aefffc for quantum information geometry applications.
""",
            "fmt": "md", "author": "zhangliang",
            "status": "published",
            "self_originality": 5, "self_rigor": 5, "self_completeness": 4,
            "self_pedagogy": 2, "self_impact": 5,
        },
        {
            "source": r"""---
title: Quantum Information Geometry and Statistical Manifolds
abstract: We develop the geometric framework for quantum statistical inference, connecting Fisher information metric to quantum fidelity.
categories:
  - physics
  - information-geometry
keywords:
  - quantum fisher
  - statistical manifolds
  - fidelity
language: en
---

# Quantum Information Geometry

## Introduction

The manifold of quantum states: $$\mathcal{M} = \{\rho(\theta) \mid \theta \in \Theta \subset \mathbb{R}^n\}$$

## Quantum Fisher Information

The SLD quantum Fisher information defines a Riemannian metric on $\mathcal{M}$.

## References

See peerpedia:c9743edc-b177-4c53-a4cb-5ecc80a060cf for the tensor network connection.
""",
            "fmt": "md", "author": "zhaotongji",
            "status": "published",
            "self_originality": 5, "self_rigor": 4, "self_completeness": 3,
            "self_pedagogy": 3, "self_impact": 4,
        },
        {
            "source": r"""---
title: Category Theory for Physicists: A Practical Introduction
abstract: A pedagogical introduction to category theory aimed at physicists. Covers categories, functors, natural transformations, adjunctions, and monoidal categories with physics examples throughout.
categories:
  - math
  - physics
keywords:
  - category theory
  - monoidal categories
  - functors
language: en
---

# Category Theory for Physicists

## Why Categories?

A category $\mathcal{C}$ consists of objects and morphisms. For physicists, the natural setting is $\operatorname{Hom}_{\mathcal{C}}(A, B)$ — the set of morphisms from $A$ to $B$ with associative composition.

## Monoidal Categories

A monoidal category $(\mathcal{C}, \otimes, I)$ adds a tensor product to the categorical structure. This is the natural language for quantum mechanics.
""",
            "fmt": "md", "author": "liqun",
            "status": "published",
            "self_originality": 2, "self_rigor": 3, "self_completeness": 3,
            "self_pedagogy": 5, "self_impact": 2,
        },
        {
            "source": r"""---
title: Holographic Duality and Entanglement Entropy
abstract: We investigate the relation between holographic duality and entanglement entropy, including the Ryu-Takayanagi formula and its covariant generalization.
categories:
  - physics
  - holography
keywords:
  - ads/cft
  - entanglement
  - ryu-takayanagi
language: en
---

# Holographic Duality and Entanglement Entropy

## AdS/CFT Correspondence

The $(d+1)$-dimensional gravitational theory in anti-de Sitter space is dual to a $d$-dimensional conformal field theory.

## Entanglement Entropy

The Ryu-Takayanagi formula relates entanglement entropy to minimal surface area:

$$S_A = \frac{\operatorname{Area}(\gamma_A)}{4G_N}$$

where $\gamma_A$ is the minimal surface in the bulk homologous to the boundary region $A$.
""",
            "fmt": "md", "author": "wangshouheng",
            "status": "published",
            "self_originality": 4, "self_rigor": 4, "self_completeness": 3,
            "self_pedagogy": 3, "self_impact": 4,
        },
        {
            "source": r"""---
title: Quantum Error Correction with Surface Codes
abstract: A pedagogical introduction to surface code quantum error correction.
categories:
  - physics
  - quantum-information
keywords:
  - surface codes
  - error correction
  - topological order
language: en
---

= Quantum Error Correction with Surface Codes

== Introduction

Quantum error correction protects quantum information from decoherence. The surface code is the most promising architecture for fault-tolerant quantum computation.

== Stabilizer Formalism

The surface code is a stabilizer code defined on a 2D lattice of qubits.
""",
            "fmt": "typ", "author": "zhangliang",
            "status": "published",
            "self_originality": 4, "self_rigor": 4, "self_completeness": 3,
            "self_pedagogy": 4, "self_impact": 4,
        },
    ]

    # ── Submit articles ─────────────────────────────────────────────────
    settings.ensure_dirs()
    articles_dir = DEFAULT_ARTICLES_DIR

    click.echo(f"  提交 {len(articles_def)} 篇文章...")

    for i, ad in enumerate(articles_def):
        ext = ".md" if ad["fmt"] == "md" else ".typ"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(ad["source"])
            tmp_path = Path(tmp.name)

        result = submit_article(
            source_path=tmp_path,
            database_url=settings.database_url,
            articles_dir=articles_dir,
            author_name=ad["author"],
            self_originality=ad["self_originality"],
            self_rigor=ad["self_rigor"],
            self_completeness=ad["self_completeness"],
            self_pedagogy=ad["self_pedagogy"],
            self_impact=ad["self_impact"],
        )

        if not result.success:
            click.echo(f"    ✗ {ad['source'].split(chr(10))[1][7:40]}... 失败: {result.error}")
            continue

        # Set status
        session = get_session(engine)
        session.close()
        engine2 = get_engine(settings.database_url)
        session2 = get_session(engine2)
        update_article_status(session2, result.article_id, "submitted")
        session2.commit()

        if ad["status"] == "published":
            assign_reviewer(article_id=result.article_id, reviewer_id="liqun", database_url=settings.database_url)
            submit_review(
                article_id=result.article_id, reviewer_id="liqun",
                decision="accept", comments="Excellent work. Ready for publication.",
                scientific_correctness=5, clarity=5,
                database_url=settings.database_url,
            )
            make_decision(article_id=result.article_id, database_url=settings.database_url)
            update_article_status(session2, result.article_id, "published")
            session2.commit()

        session2.close()
        tmp_path.unlink()
        click.echo(f"    ✓ [{ad['status']}] {result.title[:55]}")

    # ── Add cross-references ────────────────────────────────────────────
    session = get_session(engine)
    from peerpedia_core.storage.db import get_article, list_articles
    all_arts = list_articles(session, limit=20)
    if len(all_arts) >= 2:
        # Tensor → Category + Holographic
        if len(all_arts) >= 3:
            tn = all_arts[0]
            qi = all_arts[1]
            tn_refs = [
                {"article_id": qi.id, "title": qi.title},
            ]
            if len(all_arts) >= 4:
                hd = all_arts[3]
                tn_refs.append({"article_id": hd.id, "title": hd.title})
            tn.references = tn_refs
            qi.references = [{"article_id": tn.id, "title": tn.title}]
            session.commit()
            click.echo("  + 交叉引用关系")
    session.close()

    # ── Summary ─────────────────────────────────────────────────────────
    session = get_session(engine)
    all_arts = list_articles(session, limit=20)
    published = sum(1 for a in all_arts if a.status == "published")
    click.echo(f"\n✅ Demo 数据就绪: {len(users_data)} 用户, {published} 篇 published")
    click.echo("   peerpedia serve → http://localhost:8080")
    session.close()


@cli.command()
@click.option("--lan", is_flag=True, help="Enable LAN mode for multi-user collaboration")
@click.option("--port", default=8080, help="Port to listen on")
def serve(lan: bool, port: int):
    """Start the PeerPedia web interface.

    In default mode, runs as single-user local server.
    With --lan, discovers other PeerPedia nodes on the local network.
    """
    import socket

    import uvicorn

    from peerpedia.config.settings import settings

    mode = "局域网" if lan else "本地"
    click.echo(f"PeerPedia 启动中 ({mode}模式，端口 {port})...")
    click.echo(f"浏览器打开 http://localhost:{port}")

    if lan:
        settings.lan_enabled = True
        hostname = socket.gethostname()
        node_id = f"node-{hostname}"

        from peerpedia_core.storage.db import get_engine, get_session, init_db, upsert_node
        engine = get_engine(settings.database_url)
        init_db(engine)
        session = get_session(engine)
        upsert_node(
            session,
            node_id=node_id,
            host="0.0.0.0",
            port=port,
            is_self=True,
        )
        session.commit()
        session.close()

        import threading

        from peerpedia_core.workflow.lan import start_udp_broadcaster, start_udp_listener
        stop = threading.Event()
        start_udp_broadcaster(
            node_id=node_id,
            host="0.0.0.0",
            port=port,
            database_url=settings.database_url,
            broadcast_port=settings.lan_broadcast_port,
            interval=settings.lan_broadcast_interval,
            stop_event=stop,
        )
        start_udp_listener(
            database_url=settings.database_url,
            listen_port=settings.lan_broadcast_port,
            stop_event=stop,
        )
        click.echo(f"  LAN 节点: {node_id}")
        click.echo(f"  UDP 广播: 端口 {settings.lan_broadcast_port}")

    uvicorn.run(
        "peerpedia.web.app:app",
        host="0.0.0.0" if lan else "127.0.0.1",
        port=port,
        reload=True,
    )


# Register subcommands
cli.add_command(submit)
cli.add_command(review)
cli.add_command(decide)
cli.add_command(mirror)
cli.add_command(collaborate)
cli.add_command(propose_edit)
cli.add_command(merge_proposal)
cli.add_command(user)
cli.add_command(lan)


if __name__ == "__main__":
    cli()
