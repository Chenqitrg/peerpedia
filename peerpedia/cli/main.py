"""PeerPedia CLI — Reference client command-line interface."""

from __future__ import annotations

import click

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
@click.option("--reviewer", "-r", required=True, help="审稿人 ID（申请协作的审稿人）")
def collaborate(article_id: str, reviewer: str):
    """接受审稿人的协作申请，将其添加为合作者。

    ARTICLE_ID: 文章 UUID。
    审稿人必须先提交带有协作申请的审稿意见。
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.collaboration import accept_collaboration
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"接受协作申请")
    click.echo(f"  文章:  {article_id}")
    click.echo(f"  审稿人: {reviewer}")

    result = accept_collaboration(
        article_id=article_id,
        reviewer_id=reviewer,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 协作已建立！")
        click.echo(f"  合作者: {', '.join(result.founding_authors)}")
    else:
        click.echo(f"✗ 协作失败: {result.error}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("article_id")
@click.option("--type", "-t", "proposal_type", type=click.Choice(["minor", "medium", "major"]),
              required=True, help="修改类型: minor（微小）/ medium（中等）/ major（重大）")
@click.option("--description", "-d", required=True, help="修改描述")
@click.option("--proposer", "-p", default="anonymous", help="提案人 ID")
def propose_edit(article_id: str, proposal_type: str, description: str, proposer: str):
    """对已出版的文章提交修改提案（出版后开放编辑）。

    ARTICLE_ID: 文章 UUID。

    \b
    修改类型：
      minor  — 微小修改（错字、格式），自动通过
      medium — 中等修改（段落/公式），需原作者审核
      major  — 重大修改（新章节），需社区审核
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.edit_proposal import create_proposal
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    auto_label = "（自动通过）" if proposal_type == "minor" else "（等待审核）"

    click.echo(f"提交修改提案")
    click.echo(f"  文章:  {article_id}")
    click.echo(f"  类型:  {proposal_type} {auto_label}")
    click.echo(f"  提案人: {proposer}")

    result = create_proposal(
        article_id=article_id,
        proposer_id=proposer,
        proposal_type=proposal_type,
        description=description,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 修改提案已提交！")
        click.echo(f"  提案 ID: {result.proposal_id}")
        if result.auto_approved:
            click.echo(f"  状态:    自动通过（微小修改）")
            click.echo(f"  下一步:  peerpedia merge-proposal {result.proposal_id} {article_id}")
        else:
            click.echo(f"  状态:    等待审核")
            click.echo(f"  下一步:  原作者审核后可合并")
    else:
        click.echo(f"✗ 提案失败: {result.error}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("proposal_id")
@click.argument("article_id")
@click.option("--proposer", "-p", default="anonymous", help="提案人 ID")
@click.option("--change-type", "-c", type=click.Choice(["new_theorem", "proof_fix", "content", "prose", "format"]),
              default="content", help="修改内容类型（影响贡献权重）")
def merge_proposal(proposal_id: str, article_id: str, proposer: str, change_type: str):
    """合并一个已通过的修改提案到文章中。

    PROPOSAL_ID: 提案 UUID。
    ARTICLE_ID: 文章 UUID。
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.edit_proposal import merge_proposal as do_merge
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"合并修改提案")
    click.echo(f"  提案: {proposal_id}")
    click.echo(f"  文章: {article_id}")

    result = do_merge(
        proposal_id=proposal_id,
        article_id=article_id,
        proposer_id=proposer,
        repository_url=str(settings.articles_dir / article_id),
        database_url=settings.database_url,
        change_type=change_type,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 提案已合并！")
        click.echo(f"  新版本:  {result.new_version}")
        click.echo(f"  贡献记录: {result.contribution_record_id}")
    else:
        click.echo(f"✗ 合并失败: {result.error}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
