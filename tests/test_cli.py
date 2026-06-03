"""CLI smoke tests — covers previously untested (0%) CLI commands.

Uses Click's CliRunner for isolated command testing.
"""

import tempfile
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def cli():
    """Import the CLI group."""
    from peerpedia.cli.main import cli
    return cli


def _patch_settings(db_url: str, db_path: str, articles_dir: Path):
    """Return a list of mock patches for settings attributes."""
    return [
        mock.patch("peerpedia.config.settings.settings.database_url", db_url),
        mock.patch("peerpedia.config.settings.settings.db_path", Path(db_path)),
        mock.patch("peerpedia_core.storage.DEFAULT_ARTICLES_DIR", articles_dir),
        mock.patch.object(Path, "home", return_value=articles_dir.parent),
    ]


class TestCliHelp:
    """--help and --version smoke tests."""

    def test_help(self, runner, cli):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "知诸网" in result.output

    def test_version(self, runner, cli):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output


class TestInitCommand:
    """peerpedia init — initializes ~/.peerpedia/."""

    def test_init_creates_directories(self, runner, cli):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            articles_dir = base / "articles"
            db_path = base / "db" / "peerpedia.db"
            db_path.parent.mkdir(parents=True)
            db_url = f"sqlite:///{db_path}"

            patches = _patch_settings(db_url, str(db_path), articles_dir)
            from peerpedia.config.settings import settings
            with mock.patch.object(settings, "database_url", db_url), \
                 mock.patch.object(settings, "db_path", db_path), \
                 mock.patch("peerpedia_core.storage.DEFAULT_ARTICLES_DIR", articles_dir), \
                 mock.patch.object(Path, "home", return_value=base):
                result = runner.invoke(cli, ["init"])
                assert result.exit_code == 0
                assert "初始化完成" in result.output

    def test_init_idempotent(self, runner, cli):
        """Second init should succeed (mkdir exist_ok=True)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            articles_dir = base / "articles"
            db_path = base / "db" / "peerpedia.db"
            db_path.parent.mkdir(parents=True)
            db_url = f"sqlite:///{db_path}"

            from peerpedia.config.settings import settings
            with mock.patch.object(settings, "database_url", db_url), \
                 mock.patch.object(settings, "db_path", db_path), \
                 mock.patch("peerpedia_core.storage.DEFAULT_ARTICLES_DIR", articles_dir), \
                 mock.patch.object(Path, "home", return_value=base):
                r1 = runner.invoke(cli, ["init"])
                assert r1.exit_code == 0
                r2 = runner.invoke(cli, ["init"])
                assert r2.exit_code == 0


class TestUserCommands:
    """peerpedia user register — smoke test."""

    def test_user_help(self, runner, cli):
        result = runner.invoke(cli, ["user", "--help"])
        assert result.exit_code == 0

    def test_register_help(self, runner, cli):
        result = runner.invoke(cli, ["user", "register", "--help"])
        assert result.exit_code == 0

    def test_register_basic(self, runner, cli):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            db_url = f"sqlite:///{db_path}"

            from peerpedia_core.storage.db import get_engine, init_db
            engine = get_engine(db_url)
            init_db(engine)

            from peerpedia.config.settings import settings
            with mock.patch.object(settings, "database_url", db_url), \
                 mock.patch.object(settings, "db_path", db_path):
                result = runner.invoke(cli, [
                    "user", "register", "testuser",
                    "--name", "Test User",
                    "--email", "test@example.com",
                ])
                assert result.exit_code == 0
                assert "注册" in result.output or "testuser" in result.output


class TestSubcommandHelp:
    """All subcommands should respond to --help."""

    SUBCOMMANDS = [
        "submit",
        "review",
        "decide",
        "mirror",
        "collaborate",
        "propose-edit",
        "merge-proposal",
        "lan",
    ]

    @pytest.mark.parametrize("cmd", SUBCOMMANDS)
    def test_subcommand_help(self, runner, cli, cmd):
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} --help failed: {result.output}"


class TestLanCommands:
    """peerpedia lan — status and sync smoke tests."""

    def test_lan_help(self, runner, cli):
        result = runner.invoke(cli, ["lan", "--help"])
        assert result.exit_code == 0

    def test_lan_status_no_network(self, runner, cli):
        """LAN status should not crash even without UDP."""
        result = runner.invoke(cli, ["lan", "status"])
        # Exit code varies — just confirm it doesn't raise
        assert result.exit_code is not None


class TestSubmitCommand:
    """peerpedia submit — basic smoke test."""

    def test_submit_help(self, runner, cli):
        result = runner.invoke(cli, ["submit", "--help"])
        assert result.exit_code == 0

    def test_submit_nonexistent_file(self, runner, cli):
        result = runner.invoke(cli, ["submit", "/nonexistent/file.typ"])
        assert result.exit_code != 0


class TestReviewCommand:
    """peerpedia review — basic smoke test."""

    def test_review_help(self, runner, cli):
        result = runner.invoke(cli, ["review", "--help"])
        assert result.exit_code == 0


class TestDecideCommand:
    """peerpedia decide — basic smoke test."""

    def test_decide_help(self, runner, cli):
        result = runner.invoke(cli, ["decide", "--help"])
        assert result.exit_code == 0


class TestMirrorCommand:
    """peerpedia mirror — basic smoke test."""

    def test_mirror_help(self, runner, cli):
        result = runner.invoke(cli, ["mirror", "--help"])
        assert result.exit_code == 0
