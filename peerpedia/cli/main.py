"""PeerPedia CLI — Reference client command-line interface."""

from __future__ import annotations

from pathlib import Path

import click

from peerpedia_core import __version__

# Import subcommand modules
from peerpedia.cli.article_commands import submit, review, decide
from peerpedia.cli.social_commands import mirror, collaborate, propose_edit, merge_proposal
from peerpedia.cli.user_commands import user
from peerpedia.cli.lan_commands import lan


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
    import socket

    mode = "局域网" if lan else "本地"
    click.echo(f"PeerPedia 启动中 ({mode}模式，端口 {port})...")
    click.echo(f"浏览器打开 http://localhost:{port}")

    if lan:
        settings.lan_enabled = True
        hostname = socket.gethostname()
        node_id = f"node-{hostname}"

        from peerpedia_core.storage.db import get_engine, init_db, get_session, upsert_node
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

        from peerpedia_core.workflow.lan import start_udp_broadcaster, start_udp_listener
        import threading
        stop = threading.Event()
        start_udp_broadcaster(
            node_id=node_id,
            host="0.0.0.0",
            port=port,
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
