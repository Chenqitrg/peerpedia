"""Tests for user follow system."""
import pytest
from sqlalchemy.exc import IntegrityError

from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    create_user,
    follow_user,
    unfollow_user,
    is_following,
    get_following,
    get_followers,
    get_following_count,
    get_follower_count,
)


@pytest.fixture
def db_url():
    return "sqlite:///:memory:"


@pytest.fixture
def engine(db_url):
    eng = get_engine(db_url)
    init_db(eng)
    return eng


@pytest.fixture
def users(engine):
    session = get_session(engine)
    create_user(session, id="alice", name="Alice", email="alice@test.com")
    create_user(session, id="bob", name="Bob", email="bob@test.com")
    create_user(session, id="charlie", name="Charlie", email="charlie@test.com")
    session.commit()
    session.close()


class TestFollowCRUD:

    def test_follow_user(self, engine, users):
        session = get_session(engine)
        follow = follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert follow.follower_id == "alice"
        assert follow.followed_id == "bob"
        session.close()

    def test_unfollow_user(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()

        result = unfollow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert result is True
        assert not is_following(session, "alice", "bob")
        session.close()

    def test_unfollow_nonexistent(self, engine, users):
        session = get_session(engine)
        result = unfollow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert result is False
        session.close()

    def test_duplicate_follow_raises(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        with pytest.raises(IntegrityError):
            follow_user(session, follower_id="alice", followed_id="bob")
            session.flush()
        session.rollback()
        session.close()

    def test_is_following(self, engine, users):
        session = get_session(engine)
        assert not is_following(session, "alice", "bob")
        follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert is_following(session, "alice", "bob")
        session.close()

    def test_get_following(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        follow_user(session, follower_id="alice", followed_id="charlie")
        session.commit()

        following = get_following(session, "alice")
        assert len(following) == 2
        followed_ids = {f.followed_id for f in following}
        assert followed_ids == {"bob", "charlie"}
        session.close()

    def test_get_followers(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="charlie")
        follow_user(session, follower_id="bob", followed_id="charlie")
        session.commit()

        followers = get_followers(session, "charlie")
        assert len(followers) == 2
        follower_ids = {f.follower_id for f in followers}
        assert follower_ids == {"alice", "bob"}
        session.close()

    def test_counts(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        follow_user(session, follower_id="alice", followed_id="charlie")
        follow_user(session, follower_id="bob", followed_id="alice")
        session.commit()

        assert get_following_count(session, "alice") == 2
        assert get_follower_count(session, "alice") == 1
        assert get_following_count(session, "charlie") == 0
        assert get_follower_count(session, "charlie") == 1
        session.close()
