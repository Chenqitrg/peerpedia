"""CLI commands for user management."""

import click

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import create_user, get_engine, get_session, get_user, init_db


@click.group()
def user():
    """用户管理命令。"""
    pass


@user.command("register")
@click.argument("user_id")
@click.option("--name", required=True, help="显示名")
@click.option("--email", required=True, help="邮箱")
@click.option("--affiliation", default=None, help="机构")
@click.option("--expertise", default="", help="专长领域（逗号分隔）")
def register(user_id: str, name: str, email: str, affiliation: str | None, expertise: str):
    """注册新用户。

    USER_ID: 用户标识（slug），如 "zhangsan"
    """
    engine = get_engine(settings.database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        existing = get_user(session, user_id)
        if existing:
            click.echo(f"✗ 用户 '{user_id}' 已存在", err=True)
            raise SystemExit(1)

        exp_list = [e.strip() for e in expertise.split(",") if e.strip()]
        user_obj = create_user(
            session,
            id=user_id,
            name=name,
            email=email,
            affiliation=affiliation,
            expertise=exp_list,
        )
        session.commit()

        click.echo("✓ 用户注册成功！")
        click.echo(f"  ID:     {user_obj.id}")
        click.echo(f"  名称:   {user_obj.name}")
        click.echo(f"  邮箱:   {user_obj.email}")
        click.echo(f"  机构:   {user_obj.affiliation or '无'}")
        click.echo(f"  专长:   {', '.join(user_obj.expertise) if user_obj.expertise else '无'}")
    finally:
        session.close()
