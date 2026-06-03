"""PeerPedia CLI — Reference client command-line interface."""

from __future__ import annotations

import click

from peerpedia_core import __version__


@click.group()
@click.version_option(__version__)
def cli():
    """PeerPedia — 去中心化学术出版系统。

    用 Typst 写作，同行审核，P2P 发布。
    """
    pass


@cli.command()
def init():
    """Initialize PeerPedia in the current directory.

    Creates ~/.peerpedia/ with default configuration, empty database,
    and required directory structure.
    """
    from pathlib import Path
    from peerpedia_core.storage import DEFAULT_ARTICLES_DIR
    from peerpedia_core.storage.db import get_engine, init_db
    from peerpedia.config.settings import settings

    base = Path.home() / ".peerpedia"
    dirs = [
        base,
        DEFAULT_ARTICLES_DIR,
        base / "profiles",
        base / "db",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Initialize database tables
    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"PeerPedia 初始化完成: {base}")
    click.echo(f"  文章仓库目录: {DEFAULT_ARTICLES_DIR}")
    click.echo(f"  数据库: {settings.db_path}")
    click.echo(f"  下一步: peerpedia serve")


@cli.command()
@click.option("--lan", is_flag=True, help="Enable LAN mode for multi-user collaboration")
@click.option("--port", default=8080, help="Port to listen on")
def serve(lan: bool, port: int):
    """Start the PeerPedia web interface.

    In default mode, runs as single-user local server.
    With --lan, discovers other PeerPedia nodes on the local network.
    """
    import uvicorn

    mode = "局域网" if lan else "本地"
    click.echo(f"PeerPedia 启动中 ({mode}模式，端口 {port})...")
    click.echo(f"浏览器打开 http://localhost:{port}")

    uvicorn.run(
        "peerpedia.web.app:app",
        host="0.0.0.0" if lan else "127.0.0.1",
        port=port,
        reload=True,
    )


@cli.command()
@click.argument("article_path", type=click.Path(exists=True))
@click.option("--author", default=None, help="你的名字（用于 git commit）")
@click.option("--email", default=None, help="你的邮箱（用于 git commit）")
def submit(article_path: str, author: str | None, email: str | None):
    """Submit a Typst or Markdown article for peer review.

    ARTICLE_PATH: Path to the main .typ or .md file.
    """
    from pathlib import Path
    from peerpedia.config.settings import settings
    from peerpedia.submit import submit_article

    path = Path(article_path).resolve()

    author_name = author or "peerpedia"
    author_email = email or "peerpedia@localhost"

    click.echo(f"提交文章: {path.name}")
    click.echo(f"  格式: {'Typst' if path.suffix in ('.typ', '.typst') else 'Markdown'}")

    # Ensure database is initialized
    from peerpedia_core.storage.db import get_engine, init_db
    engine = get_engine(settings.database_url)
    init_db(engine)

    settings.ensure_dirs()

    result = submit_article(
        source_path=path,
        database_url=settings.database_url,
        articles_dir=settings.articles_dir,
        author_name=author_name,
        author_email=author_email,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 文章提交成功！")
        click.echo(f"  ID:     {result.article_id}")
        click.echo(f"  标题:   {result.title}")
        click.echo(f"  提交:   {result.git_commit_hash[:8]}")
        if result.cid:
            click.echo(f"  CID:    {result.cid[:16]}...")
        if result.compile_output:
            click.echo(f"  输出:   {result.compile_output}")
        click.echo()
        click.echo(f"  查看: peerpedia serve → http://localhost:{settings.port}")
    else:
        click.echo(f"✗ 提交失败: {result.error}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("article_id")
@click.option("--decision", "-d", type=click.Choice(["accept", "revise", "reject"]), prompt="决定 (accept/revise/reject)")
@click.option("--comments", "-c", prompt="审稿意见 (Markdown)")
@click.option("--scientific", type=click.IntRange(1, 5), default=3, help="科学正确性 (1-5)")
@click.option("--clarity", type=click.IntRange(1, 5), default=3, help="表述清晰度 (1-5)")
@click.option("--reviewer", default=None, help="你的审稿人 ID/名字")
def review(article_id: str, decision: str, comments: str, scientific: int, clarity: int, reviewer: str | None):
    """Review an article pending peer review.

    ARTICLE_ID: The article UUID to review.
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.review import assign_reviewer, submit_review
    from peerpedia_core.storage.db import get_engine, init_db

    reviewer_id = reviewer or "anonymous"

    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"审稿文章: {article_id}")
    click.echo(f"  审稿人: {reviewer_id}")

    # Step 1: Assign reviewer (if not already in_review)
    assign_result = assign_reviewer(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not assign_result.success:
        if "must be" not in assign_result.error:
            click.echo(f"✗ 分配审稿人失败: {assign_result.error}", err=True)
            raise SystemExit(1)
        click.echo(f"  (文章已在审稿中)")

    # Step 2: Submit review
    result = submit_review(
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific,
        clarity=clarity,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 审稿提交成功！")
        click.echo(f"  审稿 ID: {result.review_id}")
        click.echo(f"  决定:    {decision}")
        click.echo(f"  积分:    +{result.points_earned}")
    else:
        click.echo(f"✗ 审稿失败: {result.error}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("article_id")
def decide(article_id: str):
    """Make a decision on an article based on accumulated reviews.

    ARTICLE_ID: The article UUID to decide on.
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.review import make_decision
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    result = make_decision(
        article_id=article_id,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo(f"✓ 决定已做出: {result.new_status}")
        if result.author_points:
            click.echo(f"  作者积分: +{result.author_points}")
        if result.new_status == "accepted":
            click.echo(f"  下一步: peerpedia publish {article_id}")
    else:
        click.echo(f"✗ 决定失败: {result.error}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("arxiv_id")
@click.option("--user", "-u", default="anonymous", help="你的用户 ID")
def mirror(arxiv_id: str, user: str):
    """从 arXiv 搬运一篇文章到 PeerPedia。

    ARXIV_ID: arXiv 文章 ID，例如 2301.00001
    """
    from pathlib import Path
    from peerpedia.config.settings import settings
    from peerpedia.mirror import mirror_arxiv
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)
    settings.ensure_dirs()

    click.echo(f"正在从 arXiv 搬运: {arxiv_id}")
    click.echo(f"  搬运者: {user}")

    result = mirror_arxiv(
        arxiv_id=arxiv_id,
        mirror_user_id=user,
        database_url=settings.database_url,
        articles_dir=settings.articles_dir,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 搬运成功！")
        click.echo(f"  arXiv:  {result.arxiv_id}")
        click.echo(f"  标题:   {result.title}")
        click.echo(f"  作者:   {', '.join(result.authors)}")
        click.echo(f"  搬运积分: +{result.mirror_points}")
    else:
        click.echo(f"✗ 搬运失败: {result.error}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("article_id")
def collaborate(article_id: str):
    """Request to collaborate on an article as a reviewer.

    ARTICLE_ID: The article UUID to collaborate on.
    """
    click.echo(f"Requesting collaboration on: {article_id}")
    click.echo("(Not yet implemented — coming in Phase 3)")


@cli.command()
@click.argument("article_id")
def propose_edit(article_id: str):
    """Propose an edit to a published article (post-publication editing).

    ARTICLE_ID: The article UUID to edit.
    """
    click.echo(f"Creating edit proposal for: {article_id}")
    click.echo("(Not yet implemented — coming in Phase 3)")


if __name__ == "__main__":
    cli()
