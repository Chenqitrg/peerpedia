"""CLI commands for article submission, review, and decisions."""

from pathlib import Path

import click

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db


def _ensure_db():
    """Initialize database if needed."""
    engine = get_engine(settings.database_url)
    init_db(engine)


@click.command()
@click.argument("article_path", type=click.Path(exists=True))
@click.option("--author", default=None, help="你的名字（用于 git commit）")
@click.option("--email", default=None, help="你的邮箱（用于 git commit）")
def submit(article_path: str, author: str | None, email: str | None):
    """Submit a Typst or Markdown article for peer review.

    ARTICLE_PATH: Path to the main .typ or .md file.
    """
    from peerpedia.submit import submit_article

    path = Path(article_path).resolve()
    author_name = author or "peerpedia"
    author_email = email or "peerpedia@localhost"

    click.echo(f"提交文章: {path.name}")
    click.echo(f"  格式: {'Typst' if path.suffix in ('.typ', '.typst') else 'Markdown'}")

    _ensure_db()
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
        click.echo("✓ 文章提交成功！")
        click.echo(f"  ID:     {result.article_id}")
        click.echo(f"  标题:   {result.title}")
        commit_hash = result.git_commit_hash or ""
        click.echo(f"  提交:   {commit_hash[:8]}")
        if result.cid:
            click.echo(f"  CID:    {result.cid[:16]}...")
        click.echo()
        click.echo(f"  查看: peerpedia serve → http://localhost:{settings.port}")
    else:
        click.echo(f"✗ 提交失败: {result.error}", err=True)
        raise SystemExit(1)


@click.command()
@click.argument("article_id")
@click.option("--decision", "-d", type=click.Choice(["accept", "revise", "reject"]),
              prompt="决定 (accept/revise/reject)")
@click.option("--comments", "-c", prompt="审稿意见 (Markdown)")
@click.option("--scientific", type=click.IntRange(1, 5), default=3,
              help="科学正确性 (1-5)")
@click.option("--clarity", type=click.IntRange(1, 5), default=3,
              help="表述清晰度 (1-5)")
@click.option("--reviewer", default=None, help="你的审稿人 ID/名字")
def review(article_id: str, decision: str, comments: str, scientific: int,
           clarity: int, reviewer: str | None):
    """Review an article pending peer review.

    ARTICLE_ID: The article UUID to review.
    """
    from peerpedia_core.workflow.review import assign_reviewer, submit_review

    reviewer_id = reviewer or "anonymous"
    _ensure_db()

    click.echo(f"审稿文章: {article_id}")
    click.echo(f"  审稿人: {reviewer_id}")

    assign_result = assign_reviewer(
        article_id=article_id, reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not assign_result.success:
        if "must be" not in assign_result.error:
            click.echo(f"✗ 分配审稿人失败: {assign_result.error}", err=True)
            raise SystemExit(1)
        click.echo("  (文章已在审稿中)")

    result = submit_review(
        article_id=article_id, reviewer_id=reviewer_id,
        decision=decision, comments=comments,
        scientific_correctness=scientific, clarity=clarity,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo("✓ 审稿提交成功！")
        click.echo(f"  审稿 ID: {result.review_id}")
        click.echo(f"  决定:    {decision}")
        click.echo(f"  积分:    +{result.points_earned}")
    else:
        click.echo(f"✗ 审稿失败: {result.error}", err=True)
        raise SystemExit(1)


@click.command()
@click.argument("article_id")
def decide(article_id: str):
    """Make a decision on an article based on accumulated reviews.

    ARTICLE_ID: The article UUID to decide on.
    """
    from peerpedia_core.workflow.review import make_decision

    _ensure_db()

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
