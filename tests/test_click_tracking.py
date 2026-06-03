"""Tests for citation click tracking."""

import pytest

from peerpedia_core.storage.db import (
    create_article,
    create_click_event,
    get_click_events_for_article,
    get_engine,
    get_local_click_counts,
    get_session,
    init_db,
)
from peerpedia_core.workflow.citations import (
    compute_transition_probabilities,
    inject_citation_links,
    record_click,
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

    def test_to_dict(self, engine, articles):
        """ClickEvent.to_dict() returns correct fields."""
        session = get_session(engine)
        event = create_click_event(
            session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1", user_id="alice"
        )
        session.commit()
        d = event.to_dict()
        assert d["from_article_id"] == articles["A"]
        assert d["to_article_id"] == articles["B"]
        assert d["node_id"] == "n1"
        assert d["user_id"] == "alice"
        assert "timestamp" in d
        session.close()


class TestRecordClick:
    def test_record_click_returns_dict(self, engine, articles):
        session = get_session(engine)
        result = record_click(
            session,
            from_article_id=articles["A"],
            to_article_id=articles["B"],
            node_id="node-01",
            user_id="alice",
        )
        session.commit()
        assert result["from_article_id"] == articles["A"]
        assert result["to_article_id"] == articles["B"]
        assert result["node_id"] == "node-01"
        session.close()


class TestTransitionProbabilities:

    def test_empty_no_clicks(self, engine, articles):
        """No clicks returns empty transitions."""
        session = get_session(engine)
        result = compute_transition_probabilities(session, articles["A"])
        assert result["total_clicks"] == 0
        assert result["transitions"] == []
        session.close()

    def test_single_target(self, engine, articles):
        """Single click gives probability 1.0."""
        session = get_session(engine)
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        assert result["total_clicks"] == 1
        assert len(result["transitions"]) == 1
        assert result["transitions"][0]["probability"] == 1.0
        session.close()

    def test_probabilities_sum_to_one(self, engine, articles):
        """Probabilities always sum to 1.0."""
        session = get_session(engine)
        for _ in range(3):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        for _ in range(2):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        total_prob = sum(t["probability"] for t in result["transitions"])
        assert total_prob == pytest.approx(1.0)
        # B should have higher probability
        assert result["transitions"][0]["to_article_id"] == articles["B"]
        assert result["transitions"][0]["probability"] == pytest.approx(0.6)
        session.close()

    def test_sort_by_probability_desc(self, engine, articles):
        """Transitions sorted by probability descending."""
        session = get_session(engine)
        for _ in range(5):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        for _ in range(2):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        probs = [t["probability"] for t in result["transitions"]]
        assert probs == sorted(probs, reverse=True)
        session.close()

    def test_merge_other_nodes_clicks(self, engine, articles):
        """Merge local + other nodes click counts."""
        session = get_session(engine)
        # Local: 3 clicks A→B
        for _ in range(3):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        # Other nodes: A→B 8, A→C 2
        other = {articles["B"]: 8, articles["C"]: 2}
        result = compute_transition_probabilities(session, articles["A"], other_nodes_clicks=other)

        assert result["total_clicks"] == 13  # 3+8+2
        assert len(result["transitions"]) == 2
        b_trans = next(t for t in result["transitions"] if t["to_article_id"] == articles["B"])
        assert b_trans["clicks"] == 11
        assert b_trans["probability"] == pytest.approx(11 / 13, rel=0.01)
        session.close()

    def test_local_only_ignores_other(self, engine, articles):
        """Without other_nodes_clicks, returns only local data."""
        session = get_session(engine)
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        assert result["total_clicks"] == 1
        session.close()


class TestInjectCitationLinks:

    def test_injects_data_target_id(self):
        """inject_citation_links adds data-target-id attribute."""
        aid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        html = f"peerpedia:{aid}"
        result = inject_citation_links(html)
        assert f'data-target-id="{aid}"' in result
        assert 'class="citation-link"' in result

    def test_injects_href(self):
        """Citation link has correct href."""
        aid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        html = f"peerpedia:{aid}"
        result = inject_citation_links(html)
        assert f'href="/article/{aid}"' in result

    def test_multiple_citations(self):
        """Multiple citations all get data-target-id."""
        a1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        a2 = "11111111-2222-3333-4444-555555555555"
        html = f"peerpedia:{a1} and peerpedia:{a2}"
        result = inject_citation_links(html)
        assert f'data-target-id="{a1}"' in result
        assert f'data-target-id="{a2}"' in result
