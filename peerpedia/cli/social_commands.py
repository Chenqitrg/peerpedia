"""CLI commands for mirroring, collaboration, and edit proposals."""

import click

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db


def _ensure_db():
    """Initialize database if needed."""
    engine = get_engine(settings.database_url)
    init_db(engine)


@click.command()
@click.argument("arxiv_id")
@click.option("--user", "-u", default="anonymous", help="你的用户 ID")
def mirror(arxiv_id: str, user: str):
    """从 arXiv 搬运一篇文章到 PeerPedia。

    ARXIV_ID: arXiv 文章 ID，例如 2301.00001
    """
    from peerpedia.mirror import mirror_arxiv

    _ensure_db()
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
        click.echo("✓ 搬运成功！")
        click.echo(f"  arXiv:  {result.arxiv_id}")
        click.echo(f"  标题:   {result.title}")
        click.echo(f"  作者:   {', '.join(result.authors)}")
        click.echo(f"  搬运积分: +{result.mirror_points}")
    else:
        click.echo(f"✗ 搬运失败: {result.error}", err=True)
        raise SystemExit(1)


@click.command()
@click.argument("article_id")
@click.option("--reviewer", "-r", required=True, help="审稿人 ID（申请协作的审稿人）")
def collaborate(article_id: str, reviewer: str):
    """接受审稿人的协作申请，将其添加为合作者。

    ARTICLE_ID: 文章 UUID。
    审稿人必须先提交带有协作申请的审稿意见。
    """
    from peerpedia_core.workflow.collaboration import accept_collaboration

    _ensure_db()

    click.echo("接受协作申请")
    click.echo(f"  文章:  {article_id}")
    click.echo(f"  审稿人: {reviewer}")

    result = accept_collaboration(
        article_id=article_id,
        reviewer_id=reviewer,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo("✓ 协作已建立！")
        click.echo(f"  合作者: {', '.join(result.founding_authors)}")
    else:
        click.echo(f"✗ 协作失败: {result.error}", err=True)
        raise SystemExit(1)


@click.command()
@click.argument("article_id")
@click.option("--type", "-t", "proposal_type",
              type=click.Choice(["minor", "medium", "major"]),
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
    from peerpedia_core.workflow.edit_proposal import create_proposal

    _ensure_db()

    auto_label = "（自动通过）" if proposal_type == "minor" else "（等待审核）"

    click.echo("提交修改提案")
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
        click.echo("✓ 修改提案已提交！")
        click.echo(f"  提案 ID: {result.proposal_id}")
        if result.auto_approved:
            click.echo("  状态:    自动通过（微小修改）")
            click.echo(f"  下一步:  peerpedia merge-proposal {result.proposal_id} {article_id}")
        else:
            click.echo("  状态:    等待审核")
            click.echo("  下一步:  原作者审核后可合并")
    else:
        click.echo(f"✗ 提案失败: {result.error}", err=True)
        raise SystemExit(1)


@click.command()
@click.argument("proposal_id")
@click.argument("article_id")
@click.option("--proposer", "-p", default="anonymous", help="提案人 ID")
@click.option("--change-type", "-c",
              type=click.Choice(["new_theorem", "proof_fix", "content", "prose", "format"]),
              default="content", help="修改内容类型（影响贡献权重）")
def merge_proposal(proposal_id: str, article_id: str, proposer: str, change_type: str):
    """合并一个已通过的修改提案到文章中。

    PROPOSAL_ID: 提案 UUID。
    ARTICLE_ID: 文章 UUID。
    """
    from peerpedia_core.workflow.edit_proposal import merge_proposal as do_merge

    _ensure_db()

    click.echo("合并修改提案")
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
        click.echo("✓ 提案已合并！")
        click.echo(f"  新版本:  {result.new_version}")
        click.echo(f"  贡献记录: {result.contribution_record_id}")
    else:
        click.echo(f"✗ 合并失败: {result.error}", err=True)
        raise SystemExit(1)
