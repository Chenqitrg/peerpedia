"""Tests for citation click tracking."""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    create_article,
    create_click_event,
    get_click_events_for_article,
    get_local_click_counts,
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
def articles(engine):
    session = get_session(engine)
    a1 = create_article(
        session,
        id="art-aaa",
        title="Article A",
        founding_authors=["alice"],
        abstract="First article.",
        git_repo_path="/tmp/a",
    )
    a2 = create_article(
        session,
        id="art-bbb",
        title="Article B",
        founding_authors=["bob"],
        abstract="Second article.",
        git_repo_path="/tmp/b",
    )
    a3 = create_article(
        session,
        id="art-ccc",
        title="Article C",
        founding_authors=["charlie"],
        abstract="Third article.",
        git_repo_path="/tmp/c",
    )
    a1_id = a1.id
    a2_id = a2.id
    a3_id = a3.id
    session.commit()
    session.close()
    return {"A": a1_id, "B": a2_id, "C": a3_id}


class TestClickEventCRUD:

    def test_create_click_event(self, engine, articles):
        """Create a click event record."""
        session = get_session(engine)
        event = create_click_event(
            session,
            from_article_id=articles["A"],
            to_article_id=articles["B"],
            node_id="node-01",
            user_id="alice",
        )
        session.commit()

        assert event.id is not None
        assert event.from_article_id == articles["A"]
        assert event.to_article_id == articles["B"]
        assert event.node_id == "node-01"
        assert event.user_id == "alice"
        assert event.timestamp is not None
        session.close()

    def test_create_click_event_without_user(self, engine, articles):
        """Click event without user_id is allowed (anonymous click)."""
        session = get_session(engine)
        event = create_click_event(
            session,
            from_article_id=articles["A"],
            to_article_id=articles["B"],
            node_id="node-01",
        )
        session.commit()
        assert event.user_id is None
        session.close()

    def test_get_click_events_for_article(self, engine, articles):
        """Retrieve click events for a specific source article."""
        session = get_session(engine)
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        create_click_event(session, from_article_id=articles["B"], to_article_id=articles["C"], node_id="n1")
        session.commit()

        events_a = get_click_events_for_article(session, articles["A"])
        assert len(events_a) == 2
        assert all(e.from_article_id == articles["A"] for e in events_a)
        session.close()

    def test_get_local_click_counts(self, engine, articles):
        """Click counts aggregate by target article."""
        session = get_session(engine)
        for _ in range(3):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        for _ in range(2):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        session.commit()

        counts = get_local_click_counts(session, articles["A"])
        assert counts == {articles["B"]: 3, articles["C"]: 2}
        session.close()

    def test_get_local_click_counts_empty(self, engine, articles):
        """No clicks returns empty dict."""
        session = get_session(engine)
        counts = get_local_click_counts(session, articles["A"])
        assert counts == {}
        session.close()
