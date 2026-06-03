"""Tests for User and Identity ORM models."""
import tempfile
from pathlib import Path

from peerpedia_core.storage.db import (
    create_identity,
    create_user,
    get_engine,
    get_identities_for_user,
    get_session,
    get_user,
    init_db,
)


class TestUserModel:

    def test_user_table_creation(self):
        """init_db should create the users table."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert "users" in tables

    def test_create_and_get_user(self):
        """Create a user and retrieve by ID."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            user = create_user(
                session,
                id="zhangsan",
                name="张三",
                email="zhangsan@example.com",
                affiliation="MIT",
                expertise=["quantum_info", "topology"],
                bio="A physicist.",
            )
            session.commit()

            fetched = get_user(session, "zhangsan")
            assert fetched is not None
            assert fetched.id == "zhangsan"
            assert fetched.name == "张三"
            assert fetched.email == "zhangsan@example.com"
            assert fetched.affiliation == "MIT"
            assert "quantum_info" in fetched.expertise
            assert fetched.bio == "A physicist."
            assert fetched.joined_at is not None

    def test_get_nonexistent_user(self):
        """get_user should return None for unknown ID."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            assert get_user(session, "nobody") is None

    def test_user_last_active_update(self):
        """update_user_last_active should set last_active to now."""
        from datetime import datetime, timezone

        from peerpedia_core.storage.db import update_user_last_active

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            create_user(session, id="alice", name="Alice", email="alice@test.com")
            session.commit()

            before = datetime.now(timezone.utc)
            result = update_user_last_active(session, "alice")
            session.commit()

            assert result is not None
            # last_active should be set (timestamp set, not None)
            assert result.last_active is not None


class TestIdentityModel:

    def test_identity_table_creation(self):
        """init_db should create the identities table."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert "identities" in tables

    def test_create_and_get_identities(self):
        """Create identities and retrieve for a user."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            create_user(session, id="lisi", name="李四", email="lisi@test.com")
            session.commit()

            id1 = create_identity(
                session,
                user_id="lisi",
                type="orcid",
                value="0000-0001-2345-6789",
                verified=True,
                trust_weight=100,
            )
            id2 = create_identity(
                session,
                user_id="lisi",
                type="github",
                value="lisi-dev",
                verified=True,
                trust_weight=30,
            )
            session.commit()

            identities = get_identities_for_user(session, "lisi")
            assert len(identities) == 2
            types = {i.type for i in identities}
            assert "orcid" in types
            assert "github" in types

    def test_get_identities_empty(self):
        """get_identities_for_user should return empty list for user with no identities."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            create_user(session, id="wangwu", name="王五", email="wangwu@test.com")
            session.commit()

            identities = get_identities_for_user(session, "wangwu")
            assert identities == []
