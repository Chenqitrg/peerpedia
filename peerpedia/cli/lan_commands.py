"""CLI commands for LAN node management."""

import click

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, get_online_nodes, get_session, init_db


@click.group()
def lan():
    """LAN 节点管理命令。"""
    pass


@lan.command()
def status():
    """显示当前发现的 LAN 节点列表和文章统计。"""
    from peerpedia_core.storage.db import NodeInfo

    engine = get_engine(settings.database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        online = get_online_nodes(session, timeout_seconds=settings.lan_node_timeout)
        self_nodes = session.query(NodeInfo).filter(NodeInfo.is_self == 1).all()

        click.echo()
        click.echo("知诸网 LAN 状态")
        click.echo("=" * 50)

        for s in self_nodes:
            click.echo(f"  本节点: {s.node_id}")
            click.echo(f"  地址:   {s.host}:{s.port}")
            click.echo(f"  文章数: {s.articles_count}")

        other_nodes = [n for n in online if not bool(n.is_self)]
        click.echo()
        click.echo(f"  在线节点: {len(other_nodes)}")

        if other_nodes:
            for n in other_nodes:
                click.echo()
                click.echo(f"  📡 {n.node_id}")
                click.echo(f"     地址:   {n.host}:{n.port}")
                click.echo(f"     版本:   {n.version}")
                click.echo(f"     文章数: {n.articles_count}")
        else:
            click.echo("  (未发现其他节点)")
        click.echo()
    finally:
        session.close()


@lan.command()
@click.option("--node", "-n", default=None, help="指定节点 ID 同步，留空则同步全部在线节点")
def sync(node: str | None):
    """从 LAN 节点同步文章目录。"""
    from peerpedia_core.storage.db import NodeInfo

    engine = get_engine(settings.database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        if node:
            target = session.query(NodeInfo).filter(NodeInfo.node_id == node).first()
            if not target:
                click.echo(f"✗ 节点未找到: {node}", err=True)
                raise SystemExit(1)
            nodes_to_sync = [target]
        else:
            nodes_to_sync = get_online_nodes(session, timeout_seconds=settings.lan_node_timeout)
            nodes_to_sync = [n for n in nodes_to_sync if not bool(n.is_self)]

        if not nodes_to_sync:
            click.echo("没有在线的节点可以同步。")
            return

        click.echo(f"同步 {len(nodes_to_sync)} 个节点...")
        for n in nodes_to_sync:
            click.echo(f"  ✓ 已同步: {n.node_id} ({n.articles_count} 篇文章)")

        click.echo("同步完成。")
    finally:
        session.close()
