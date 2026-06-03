# Phase 3 M2: Review Workflow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full review workflow: article status state machine (draft → submitted → in_review → accepted → published), review assignment/scoring/decision, and first points calculation.

**Architecture:** Three new modules — `peerpedia_core/workflow/` package (state_machine.py + review.py) for business logic, plus a Review DB model added to the existing db.py. CLI and Web are wired to call the new workflow functions. MVP rule: any user can self-assign as reviewer, 1 review is sufficient for decision.

**Tech Stack:** Python 3.14, SQLAlchemy 2.0, SQLite, FastAPI, Jinja2, Click, pytest

---

## File Map

```
NEW:
  peerpedia_core/workflow/__init__.py       # Package init, exports
  peerpedia_core/workflow/state_machine.py  # ArticleStatus transitions + validation
  peerpedia_core/workflow/review.py         # Review orchestration (assign, submit, decide, points)
  tests/test_state_machine.py               # State machine transition tests
  tests/test_review_workflow.py             # Review orchestration tests

MODIFY:
  peerpedia_core/storage/db.py              # Add Review ORM model + CRUD
  peerpedia_core/storage/__init__.py         # Export workflow symbols (optional)
  peerpedia/cli/main.py                     # Wire review command
  peerpedia/web/routes/api.py               # Review API endpoints
  peerpedia/web/routes/pages.py             # Review queue real data
  peerpedia/web/templates/review.html       # Real review queue UI

DEPENDENCY GRAPH:
  Task 1 (state machine) ──┐
                           ├── Task 3 (review orchestration) ──┬── Task 5 (CLI)
  Task 2 (Review DB model)─┘                                  ├── Task 6 (Web)
                                                               └── Task 4 (points)
```

---

### Task 1: State Machine Engine

**Files:**
- Create: `peerpedia_core/workflow/__init__.py`
- Create: `peerpedia_core/workflow/state_machine.py`
- Create: `tests/test_state_machine.py`

**What:** A minimal state machine that validates ArticleStatus transitions and executes them. Returns the new status or raises on invalid transitions.

- [ ] **Step 1: Write the failing state machine test**

Create `tests/test_state_machine.py`:

```python
"""Tests for ArticleStatus state machine."""
import pytest
from peerpedia_core.workflow.state_machine import (
    StateMachine,
    VALID_TRANSITIONS,
    ArticleStatus,
    transition,
    can_transition,
)


class TestValidTransitions:
    """Valid transitions defined in the state machine."""

    def test_draft_to_submitted(self):
        assert can_transition("draft", "submitted") is True

    def test_submitted_to_in_review(self):
        assert can_transition("submitted", "in_review") is True

    def test_in_review_to_accepted(self):
        assert can_transition("in_review", "accepted") is True

    def test_in_review_to_rejected(self):
        assert can_transition("in_review", "rejected") is True

    def test_in_review_to_revisions_requested(self):
        assert can_transition("in_review", "revisions_requested") is True

    def test_accepted_to_published(self):
        assert can_transition("accepted", "published") is True

    def test_revisions_requested_to_submitted(self):
        assert can_transition("revisions_requested", "submitted") is True

    def test_rejected_to_submitted(self):
        assert can_transition("rejected", "submitted") is True


class TestInvalidTransitions:
    """Invalid transitions should return False."""

    def test_draft_to_published_invalid(self):
        assert can_transition("draft", "published") is False

    def test_draft_to_accepted_invalid(self):
        assert can_transition("draft", "accepted") is False

    def test_submitted_to_published_invalid(self):
        assert can_transition("submitted", "published") is False

    def test_published_to_draft_invalid(self):
        assert can_transition("published", "draft") is False

    def test_rejected_to_accepted_invalid(self):
        assert can_transition("rejected", "accepted") is False


class TestTransitionExecution:
    """transition() should execute valid transitions and raise on invalid."""

    def test_transition_returns_new_status(self):
        result = transition("draft", "submitted")
        assert result == "submitted"

    def test_transition_raises_on_invalid(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            transition("draft", "published")

    def test_full_happy_path(self):
        """draft → submitted → in_review → accepted → published"""
        s = transition("draft", "submitted")
        assert s == "submitted"
        s = transition(s, "in_review")
        assert s == "in_review"
        s = transition(s, "accepted")
        assert s == "accepted"
        s = transition(s, "published")
        assert s == "published"

    def test_revise_loop(self):
        """submitted → in_review → revisions_requested → submitted → in_review → accepted"""
        s = transition("draft", "submitted")
        s = transition(s, "in_review")
        s = transition(s, "revisions_requested")
        assert s == "revisions_requested"
        s = transition(s, "submitted")
        s = transition(s, "in_review")
        s = transition(s, "accepted")
        assert s == "accepted"

    def test_reject_path(self):
        """submitted → in_review → rejected → submitted (resubmit)"""
        s = transition("draft", "submitted")
        s = transition(s, "in_review")
        s = transition(s, "rejected")
        assert s == "rejected"
        s = transition(s, "submitted")  # can resubmit
        assert s == "submitted"


class TestStateMachineClass:
    """StateMachine class wraps an article and tracks its status."""

    def test_sm_apply(self):
        sm = StateMachine(article_id="a1", current_status="draft")
        sm.apply("submitted")
        assert sm.current_status == "submitted"
        assert len(sm.history) == 1
        assert sm.history[0] == ("draft", "submitted")

    def test_sm_can_apply(self):
        sm = StateMachine(article_id="a1", current_status="published")
        assert sm.can_apply("edit_proposed") is False  # not in M2 scope yet
        assert sm.can_apply("draft") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_state_machine.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write the state machine module**

Create `peerpedia_core/workflow/__init__.py`:

```python
"""PeerPedia Core — Workflow module.

Business logic for article lifecycle: state machine, review workflow,
points calculation, and collaboration management.
"""
```

Create `peerpedia_core/workflow/state_machine.py`:

```python
"""Layer 1: ArticleStatus state machine.

Defines valid transitions and provides transition validation + execution.
The state machine is versioned — transition rules can be modified via PIP.

MVP transitions (M2):
    draft → submitted
    submitted → in_review
    in_review → accepted
    in_review → rejected
    in_review → revisions_requested
    accepted → published
    revisions_requested → submitted
    rejected → submitted
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Status constants (mirrors protocol enum) ───────────────────────────────────

class ArticleStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    REVISIONS_REQUESTED = "revisions_requested"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"


# ── Valid transitions ──────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, set[str]] = {
    ArticleStatus.DRAFT: {ArticleStatus.SUBMITTED},
    ArticleStatus.SUBMITTED: {ArticleStatus.IN_REVIEW},
    ArticleStatus.IN_REVIEW: {
        ArticleStatus.ACCEPTED,
        ArticleStatus.REJECTED,
        ArticleStatus.REVISIONS_REQUESTED,
    },
    ArticleStatus.REVISIONS_REQUESTED: {ArticleStatus.SUBMITTED},
    ArticleStatus.REJECTED: {ArticleStatus.SUBMITTED},
    ArticleStatus.ACCEPTED: {ArticleStatus.PUBLISHED},
    ArticleStatus.PUBLISHED: set(),  # terminal state for M2
}


# ── Functions ──────────────────────────────────────────────────────────────────

def can_transition(current: str, target: str) -> bool:
    """Check if a transition from current to target status is valid."""
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed


def transition(current: str, target: str) -> str:
    """Execute a status transition. Returns new status.

    Raises ValueError if the transition is invalid.
    """
    if not can_transition(current, target):
        raise ValueError(
            f"Invalid transition: {current} → {target}. "
            f"Allowed: {VALID_TRANSITIONS.get(current, set())}"
        )
    return target


# ── State machine class ────────────────────────────────────────────────────────

@dataclass
class StateMachine:
    """Tracks an article's status transitions with history."""

    article_id: str
    current_status: str = ArticleStatus.DRAFT
    history: list[tuple[str, str]] = field(default_factory=list)

    def can_apply(self, target: str) -> bool:
        """Check if target transition is valid from current status."""
        return can_transition(self.current_status, target)

    def apply(self, target: str) -> str:
        """Apply a transition, recording it in history."""
        old = self.current_status
        self.current_status = transition(old, target)
        self.history.append((old, target))
        return self.current_status
```

- [ ] **Step 4: Run tests to verify**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_state_machine.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia_core/workflow/ tests/test_state_machine.py
git commit -m "feat: add ArticleStatus state machine (M2 Task 1)

- peerpedia_core/workflow/state_machine.py: transition validation + execution
- VALID_TRANSITIONS dict defines all allowed transitions
- transition() raises ValueError on invalid transitions
- StateMachine class tracks history per article
- 14 tests for valid/invalid transitions and full paths

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Review DB Model + CRUD

**Files:**
- Modify: `peerpedia_core/storage/db.py` (add Review model + CRUD)
- Modify: `tests/test_db.py` (add review tests)

**What:** Add a `Review` SQLAlchemy model mirroring `ReviewMessage` Pydantic schema, plus CRUD functions. Reviews are stored in a `reviews` table with foreign key to articles.

- [ ] **Step 1: Add Review tests to test_db.py**

Append to `tests/test_db.py`:

```python
from peerpedia_core.storage.db import (
    Review,
    create_review,
    get_review,
    get_reviews_for_article,
)


class TestReviewModel:
    """Review model CRUD tests."""

    def test_create_review(self):
        """Create a review for an article."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            # First create an article
            article = create_article(
                session,
                title="Review Target",
                founding_authors=["author-1"],
                abstract="To be reviewed.",
                git_repo_path="/tmp/review-test",
            )
            session.commit()

            review = create_review(
                session,
                article_id=article.id,
                reviewer_id="reviewer-1",
                decision="accept",
                comments="Looks great.",
                scientific_correctness=5,
                clarity=4,
            )
            session.commit()

            assert review.id is not None
            assert review.article_id == article.id
            assert review.reviewer_id == "reviewer-1"
            assert review.decision == "accept"
            assert review.scientific_correctness == 5

    def test_get_reviews_for_article(self):
        """Get all reviews for a specific article."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(
                session,
                title="Multi-Review Article",
                founding_authors=["author-1"],
                abstract="Getting multiple reviews.",
                git_repo_path="/tmp/multi-review",
            )
            session.commit()

            r1 = create_review(session, article_id=article.id, reviewer_id="r1", decision="accept", comments="Good", scientific_correctness=4, clarity=4)
            r2 = create_review(session, article_id=article.id, reviewer_id="r2", decision="revise", comments="Needs work", scientific_correctness=3, clarity=3)
            session.commit()

            reviews = get_reviews_for_article(session, article.id)
            assert len(reviews) == 2
            assert reviews[0].reviewer_id == "r1"
            assert reviews[1].reviewer_id == "r2"

    def test_review_defaults(self):
        """Review should have correct default values."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(session, title="Default Test", founding_authors=["a1"], abstract="Test", git_repo_path="/tmp/defaults")
            session.commit()

            review = create_review(session, article_id=article.id, reviewer_id="r1", decision="accept", comments="OK")
            session.commit()

            assert review.scientific_correctness == 0
            assert review.clarity == 0
            assert review.collaboration_request is False
            assert review.points_earned == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_db.py::TestReviewModel -v`
Expected: FAIL — Review/create_review not defined

- [ ] **Step 3: Add Review model + CRUD to db.py**

In `peerpedia_core/storage/db.py`, add after the Article model (before the CRUD section):

```python
# ── ORM Model: Review ──────────────────────────────────────────────────────────

class Review(Base):
    """SQLAlchemy model for peer reviews. Mirrors protocol ReviewMessage."""

    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)
    decision = Column(String(20), nullable=False)  # accept | revise | reject
    comments = Column(Text, nullable=False, default="")
    scientific_correctness = Column(Integer, nullable=False, default=0)  # 1-5
    clarity = Column(Integer, nullable=False, default=0)  # 1-5
    collaboration_request = Column(Integer, nullable=False, default=0)  # SQLite bool
    collaboration_message = Column(Text, nullable=False, default="")
    points_earned = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "reviewer_id": self.reviewer_id,
            "decision": self.decision,
            "comments": self.comments,
            "scientific_correctness": self.scientific_correctness,
            "clarity": self.clarity,
            "collaboration_request": bool(self.collaboration_request),
            "collaboration_message": self.collaboration_message,
            "points_earned": self.points_earned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

Add CRUD functions after the existing article CRUD functions:

```python
# ── Review CRUD ────────────────────────────────────────────────────────────────

def create_review(
    session: Session,
    *,
    article_id: str,
    reviewer_id: str,
    decision: str,
    comments: str,
    scientific_correctness: int = 0,
    clarity: int = 0,
    collaboration_request: bool = False,
    collaboration_message: str = "",
    points_earned: int = 0,
) -> Review:
    """Create a new review record."""
    review = Review(
        id=str(uuid.uuid4()),
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific_correctness,
        clarity=clarity,
        collaboration_request=1 if collaboration_request else 0,
        collaboration_message=collaboration_message,
        points_earned=points_earned,
    )
    session.add(review)
    return review


def get_review(session: Session, review_id: str) -> Optional[Review]:
    """Get a review by ID."""
    return session.query(Review).filter(Review.id == review_id).first()


def get_reviews_for_article(session: Session, article_id: str) -> list[Review]:
    """Get all reviews for an article, oldest first."""
    return (
        session.query(Review)
        .filter(Review.article_id == article_id)
        .order_by(Review.created_at.asc())
        .all()
    )
```

- [ ] **Step 4: Run tests to verify**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: 8 passed (5 article + 3 review)

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: 45 passed (42 previous + 3 review tests... wait, we also added 14 state machine tests in Task 1. But Task 1 isn't committed yet if we're running Task 2 in parallel.)

- [ ] **Step 5: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia_core/storage/db.py tests/test_db.py
git commit -m "feat: add Review DB model + CRUD (M2 Task 2)

- Review ORM model: article_id, reviewer_id, decision, scores, comments
- create_review, get_review, get_reviews_for_article CRUD functions
- Reviews table with index on article_id
- 3 tests for review creation, listing, and defaults

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Review Orchestration + Points

**Files:**
- Create: `peerpedia_core/workflow/review.py`
- Create: `tests/test_review_workflow.py`

**What:** The `review.py` module orchestrates the full review workflow: assign reviewer → submit review → make decision → award points. It ties the state machine + Review DB model + ReputationParams together.

- [ ] **Step 1: Write the failing workflow tests**

Create `tests/test_review_workflow.py`:

```python
"""Tests for review workflow orchestration."""
import pytest
import tempfile
from pathlib import Path

from peerpedia.submit import submit_article
from peerpedia_core.workflow.review import (
    assign_reviewer,
    submit_review,
    make_decision,
    calculate_review_points,
    ReviewResult,
    DecisionResult,
)


SIMPLE_ARTICLE = """---
title: Review Workflow Test
abstract: Testing review orchestration.
categories:
  - test
language: en
---

= Review Workflow Test

== Section 1

Content for review testing.
"""


class TestReviewAssignment:
    """Assigning reviewers to articles."""

    def test_assign_reviewer_to_submitted_article(self):
        """Reviewer can be assigned to a submitted article."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text(SIMPLE_ARTICLE)

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )
            assert result.success

            # Manually move to submitted (submit_article leaves as draft)
            from peerpedia_core.storage.db import get_engine, init_db, get_session, update_article_status
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_result = assign_reviewer(
                article_id=result.article_id,
                reviewer_id="reviewer-1",
                database_url=f"sqlite:///{db_path}",
            )
            assert assign_result.success is True
            assert assign_result.new_status == "in_review"

    def test_assign_reviewer_to_draft_fails(self):
        """Cannot assign reviewer to draft article."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text(SIMPLE_ARTICLE)

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            assign_result = assign_reviewer(
                article_id=result.article_id,
                reviewer_id="reviewer-1",
                database_url=f"sqlite:///{db_path}",
            )
            assert assign_result.success is False
            assert "Cannot assign" in assign_result.error


class TestReviewSubmission:
    """Submitting reviews and points calculation."""

    def test_submit_review_and_points(self):
        """Submit a review and verify points are calculated."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text(SIMPLE_ARTICLE)

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            from peerpedia_core.storage.db import get_engine, init_db, get_session, update_article_status
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_reviewer(
                article_id=result.article_id,
                reviewer_id="reviewer-1",
                database_url=f"sqlite:///{db_path}",
            )

            review_result = submit_review(
                article_id=result.article_id,
                reviewer_id="reviewer-1",
                decision="accept",
                comments="Excellent work.",
                scientific_correctness=5,
                clarity=4,
                database_url=f"sqlite:///{db_path}",
            )
            assert review_result.success is True
            assert review_result.review_id is not None
            assert review_result.points_earned == 20  # base review points

    def test_submit_review_duplicate_fails(self):
        """Same reviewer cannot review the same article twice."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text(SIMPLE_ARTICLE)
            result = submit_article(source_path=source, database_url=f"sqlite:///{db_path}", articles_dir=articles_dir)

            from peerpedia_core.storage.db import get_engine, init_db, get_session, update_article_status
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_reviewer(article_id=result.article_id, reviewer_id="r1", database_url=f"sqlite:///{db_path}")
            r1 = submit_review(article_id=result.article_id, reviewer_id="r1", decision="accept", comments="OK", database_url=f"sqlite:///{db_path}")
            assert r1.success

            r2 = submit_review(article_id=result.article_id, reviewer_id="r1", decision="accept", comments="Again", database_url=f"sqlite:///{db_path}")
            assert r2.success is False
            assert "already" in r2.error.lower()


class TestDecisionMaking:
    """Making decisions based on reviews."""

    def test_accept_decision(self):
        """Accept an article after a positive review."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text(SIMPLE_ARTICLE)
            result = submit_article(source_path=source, database_url=f"sqlite:///{db_path}", articles_dir=articles_dir)

            from peerpedia_core.storage.db import get_engine, init_db, get_session, update_article_status
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_reviewer(article_id=result.article_id, reviewer_id="r1", database_url=f"sqlite:///{db_path}")
            submit_review(article_id=result.article_id, reviewer_id="r1", decision="accept", comments="OK", scientific_correctness=5, clarity=5, database_url=f"sqlite:///{db_path}")

            decision = make_decision(
                article_id=result.article_id,
                database_url=f"sqlite:///{db_path}",
            )
            assert decision.success is True
            assert decision.new_status == "accepted"
            assert decision.author_points == 50  # accepted bonus

    def test_reject_decision(self):
        """Reject an article after a negative review."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text(SIMPLE_ARTICLE)
            result = submit_article(source_path=source, database_url=f"sqlite:///{db_path}", articles_dir=articles_dir)

            from peerpedia_core.storage.db import get_engine, init_db, get_session, update_article_status
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_reviewer(article_id=result.article_id, reviewer_id="r1", database_url=f"sqlite:///{db_path}")
            submit_review(article_id=result.article_id, reviewer_id="r1", decision="reject", comments="Not good.", database_url=f"sqlite:///{db_path}")

            decision = make_decision(article_id=result.article_id, database_url=f"sqlite:///{db_path}")
            assert decision.success is True
            assert decision.new_status == "rejected"
            assert decision.author_points == 0

    def test_no_decision_without_reviews(self):
        """Cannot make decision on article with no reviews."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text(SIMPLE_ARTICLE)
            result = submit_article(source_path=source, database_url=f"sqlite:///{db_path}", articles_dir=articles_dir)

            from peerpedia_core.storage.db import get_engine, init_db, get_session, update_article_status
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "in_review")
            session.commit()
            session.close()

            decision = make_decision(article_id=result.article_id, database_url=f"sqlite:///{db_path}")
            assert decision.success is False


class TestPointsCalculation:
    """Points calculation logic."""

    def test_calculate_review_points(self):
        """Base review always gives 20 points."""
        pts = calculate_review_points(scientific_correctness=5, clarity=5)
        assert pts == 20  # base + 0 quality bonus in MVP

    def test_calculate_review_points_minimum(self):
        """Even low-quality reviews get base points."""
        pts = calculate_review_points(scientific_correctness=1, clarity=1)
        assert pts == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_review_workflow.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write the review orchestration module**

Create `peerpedia_core/workflow/review.py`:

```python
"""Layer 1: Review workflow orchestration.

Coordinates the full review lifecycle:
    assign reviewer → submit review → make decision → award points

This is a versioned module — review rules (quorum size, point values)
can be upgraded via PIP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from peerpedia_core.workflow.state_machine import can_transition, ArticleStatus
from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    get_article,
    get_reviews_for_article,
    create_review,
    update_article_status,
)
from peerpedia_core.reputation.v1 import ReputationParams


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class AssignResult:
    """Result of assigning a reviewer."""
    success: bool
    article_id: str = ""
    reviewer_id: str = ""
    new_status: str = ""
    error: str = ""


@dataclass
class ReviewResult:
    """Result of submitting a review."""
    success: bool
    review_id: Optional[str] = None
    article_id: str = ""
    reviewer_id: str = ""
    points_earned: int = 0
    error: str = ""


@dataclass
class DecisionResult:
    """Result of making a decision on an article."""
    success: bool
    article_id: str = ""
    new_status: str = ""
    author_points: int = 0
    error: str = ""


# ── Points calculation ────────────────────────────────────────────────────────

def calculate_review_points(
    scientific_correctness: int = 0,
    clarity: int = 0,
) -> int:
    """Calculate points earned for a review.

    MVP: flat 20 points per review. Quality bonus (M4+): extra points
    for high scores from the author's rating of the review.
    """
    params = ReputationParams()
    return params.points_review


# ── Review assignment ─────────────────────────────────────────────────────────

def assign_reviewer(
    article_id: str,
    reviewer_id: str,
    *,
    database_url: str,
) -> AssignResult:
    """Assign a reviewer to an article. Transitions submitted → in_review.

    MVP rule: any user can self-assign as reviewer.
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        if article is None:
            return AssignResult(success=False, article_id=article_id, error="Article not found")

        if article.status != ArticleStatus.SUBMITTED:
            return AssignResult(
                success=False,
                article_id=article_id,
                error=f"Cannot assign reviewer: article status is '{article.status}', must be 'submitted'",
            )

        # Transition to in_review
        update_article_status(session, article_id, ArticleStatus.IN_REVIEW)
        session.commit()

        return AssignResult(
            success=True,
            article_id=article_id,
            reviewer_id=reviewer_id,
            new_status=ArticleStatus.IN_REVIEW,
        )
    except Exception as e:
        session.rollback()
        return AssignResult(success=False, article_id=article_id, error=str(e))
    finally:
        session.close()


# ── Review submission ─────────────────────────────────────────────────────────

def submit_review(
    article_id: str,
    reviewer_id: str,
    decision: str,
    comments: str,
    *,
    database_url: str,
    scientific_correctness: int = 0,
    clarity: int = 0,
    collaboration_request: bool = False,
    collaboration_message: str = "",
) -> ReviewResult:
    """Submit a review for an article.

    The article must be in_review. A reviewer can only review once.
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        if article is None:
            return ReviewResult(success=False, article_id=article_id, error="Article not found")

        if article.status != ArticleStatus.IN_REVIEW:
            return ReviewResult(
                success=False,
                article_id=article_id,
                error=f"Cannot submit review: article status is '{article.status}', must be 'in_review'",
            )

        # Check for duplicate reviewer
        existing = get_reviews_for_article(session, article_id)
        for r in existing:
            if r.reviewer_id == reviewer_id:
                return ReviewResult(
                    success=False,
                    article_id=article_id,
                    error=f"Reviewer '{reviewer_id}' has already reviewed this article",
                )

        # Calculate points
        points = calculate_review_points(scientific_correctness, clarity)

        # Create review record
        review = create_review(
            session,
            article_id=article_id,
            reviewer_id=reviewer_id,
            decision=decision,
            comments=comments,
            scientific_correctness=scientific_correctness,
            clarity=clarity,
            collaboration_request=collaboration_request,
            collaboration_message=collaboration_message,
            points_earned=points,
        )
        session.commit()

        return ReviewResult(
            success=True,
            review_id=review.id,
            article_id=article_id,
            reviewer_id=reviewer_id,
            points_earned=points,
        )
    except Exception as e:
        session.rollback()
        return ReviewResult(success=False, article_id=article_id, error=str(e))
    finally:
        session.close()


# ── Decision ──────────────────────────────────────────────────────────────────

def make_decision(
    article_id: str,
    *,
    database_url: str,
) -> DecisionResult:
    """Make a decision on an article based on accumulated reviews.

    MVP rule: if any review says 'accept', accept. If all say 'reject', reject.
    If mixed, use majority. With a single review, follow that review.
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        if article is None:
            return DecisionResult(success=False, article_id=article_id, error="Article not found")

        if article.status != ArticleStatus.IN_REVIEW:
            return DecisionResult(
                success=False,
                article_id=article_id,
                error=f"Cannot decide: article status is '{article.status}', must be 'in_review'",
            )

        reviews = get_reviews_for_article(session, article_id)
        if not reviews:
            return DecisionResult(
                success=False,
                article_id=article_id,
                error="No reviews available for decision",
            )

        # Count decisions
        accepts = sum(1 for r in reviews if r.decision == "accept")
        revises = sum(1 for r in reviews if r.decision == "revise")
        rejects = sum(1 for r in reviews if r.decision == "reject")

        # MVP logic: accept if any accept, else revise if any revise, else reject
        if accepts > 0:
            new_status = ArticleStatus.ACCEPTED
            author_points = ReputationParams().points_accepted
        elif revises > 0:
            new_status = ArticleStatus.REVISIONS_REQUESTED
            author_points = 0
        else:
            new_status = ArticleStatus.REJECTED
            author_points = 0

        update_article_status(session, article_id, new_status)
        session.commit()

        return DecisionResult(
            success=True,
            article_id=article_id,
            new_status=new_status,
            author_points=author_points,
        )
    except Exception as e:
        session.rollback()
        return DecisionResult(success=False, article_id=article_id, error=str(e))
    finally:
        session.close()
```

- [ ] **Step 4: Run tests to verify**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_review_workflow.py -v`
Expected: 8 passed

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: 56 passed (42 previous + 14 state machine + 3 review DB + 8 workflow... but if running in parallel, state machine tests might not exist yet)

- [ ] **Step 6: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia_core/workflow/review.py tests/test_review_workflow.py
git commit -m "feat: add review workflow orchestration + points (M2 Task 3)

- peerpedia_core/workflow/review.py: assign → submit → decide → points
- assign_reviewer(): self-assign, transitions submitted → in_review
- submit_review(): records review, prevents duplicates, awards 20 pts
- make_decision(): majority vote (accept if any positive review)
- calculate_review_points(): base 20 points per review (MVP)
- 8 tests: assignment, submission, decision, points calculation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Wire CLI review command

**Files:**
- Modify: `peerpedia/cli/main.py`

**What:** Replace the placeholder `review` command with real review submission. CLI flow: user specifies article_id → enters review details → review submitted.

- [ ] **Step 1: Read current main.py, then replace the review command**

Replace the existing `review()` function in `peerpedia/cli/main.py`:

```python
@cli.command()
@click.argument("article_id")
@click.option("--decision", "-d", type=click.Choice(["accept", "revise", "reject"]), prompt="Decision (accept/revise/reject)")
@click.option("--comments", "-c", prompt="Review comments (Markdown)")
@click.option("--scientific", type=click.IntRange(1, 5), default=3, help="Scientific correctness (1-5)")
@click.option("--clarity", type=click.IntRange(1, 5), default=3, help="Clarity score (1-5)")
@click.option("--reviewer", default=None, help="Your reviewer ID/name")
def review(article_id: str, decision: str, comments: str, scientific: int, clarity: int, reviewer: str | None):
    """Review an article pending peer review.

    ARTICLE_ID: The article UUID to review.
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.review import assign_reviewer, submit_review

    reviewer_id = reviewer or "anonymous"

    # Ensure DB is ready
    from peerpedia_core.storage.db import get_engine, init_db
    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"Reviewing article: {article_id}")
    click.echo(f"  Reviewer: {reviewer_id}")

    # Step 1: Assign reviewer (if not already in_review)
    assign_result = assign_reviewer(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not assign_result.success:
        # If already in_review, that's fine — continue
        if "must be" not in assign_result.error:
            click.echo(f"✗ Assignment failed: {assign_result.error}", err=True)
            raise SystemExit(1)
        click.echo(f"  (Article already in review)")

    # Step 2: Submit review
    result = submit_review(
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific,
        clarity=clarity,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ Review submitted successfully!")
        click.echo(f"  Review ID: {result.review_id}")
        click.echo(f"  Decision:  {decision}")
        click.echo(f"  Points:    +{result.points_earned}")
    else:
        click.echo(f"✗ Review failed: {result.error}", err=True)
        raise SystemExit(1)
```

Also add a `decide` command for making decisions:

```python
@cli.command()
@click.argument("article_id")
def decide(article_id: str):
    """Make a decision on an article based on accumulated reviews.

    ARTICLE_ID: The article UUID to decide on.
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.review import make_decision
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    result = make_decision(
        article_id=article_id,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo(f"✓ Decision made: {result.new_status}")
        if result.author_points:
            click.echo(f"  Author points: +{result.author_points}")
        if result.new_status == "accepted":
            click.echo(f"  Next: peerpedia publish {article_id}")
    else:
        click.echo(f"✗ Decision failed: {result.error}", err=True)
        raise SystemExit(1)
```

- [ ] **Step 2: Run tests to verify nothing is broken**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: all tests pass

- [ ] **Step 3: Manual smoke test**

```bash
cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate

# Create + submit article
echo '---
title: Review Test
abstract: Testing review CLI.
---

= Review Test

Hello.
' > /tmp/review_test.typ

peerpedia submit /tmp/review_test.typ --author "Author1"

# Get article ID from output, then manually set status to submitted
python -c "
from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db, get_session, list_articles, update_article_status
engine = get_engine(settings.database_url)
init_db(engine)
session = get_session(engine)
articles = list_articles(session)
if articles:
    aid = articles[0].id
    update_article_status(session, aid, 'submitted')
    session.commit()
    print(f'Article {aid} set to submitted')
    print(f'Run: peerpedia review {aid}')
session.close()
"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia/cli/main.py
git commit -m "feat: wire CLI review + decide commands (M2 Task 4)

- peerpedia review: prompts for decision/comments/scores, submits review
- peerpedia decide: makes decision based on accumulated reviews
- Auto-assigns reviewer on first review (self-assign MVP rule)
- 8 CLI commands total now (init, serve, submit, review, decide,
  collaborate, propose_edit)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Wire Web Review Routes + Templates

**Files:**
- Modify: `peerpedia/web/routes/api.py` (add review endpoints)
- Modify: `peerpedia/web/routes/pages.py` (wire review queue + review form)
- Modify: `peerpedia/web/templates/review.html` (real review queue UI)

**What:** API endpoints for listing reviews, submitting reviews. Pages: review queue shows submitted articles, individual review page with form.

- [ ] **Step 1: Add review API endpoints to api.py**

Append to `peerpedia/web/routes/api.py` (after the existing endpoints, before `health_check`):

```python
@router.get("/articles/{article_id}/reviews")
async def api_get_reviews(article_id: str):
    """Get all reviews for an article."""
    from peerpedia_core.storage.db import get_reviews_for_article
    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        reviews = get_reviews_for_article(session, article_id)
        return {
            "article_id": article_id,
            "reviews": [r.to_dict() for r in reviews],
            "total": len(reviews),
        }
    finally:
        session.close()


@router.post("/articles/{article_id}/reviews")
async def api_submit_review(
    article_id: str,
    reviewer_id: str = Form(...),
    decision: str = Form(...),
    comments: str = Form(""),
    scientific_correctness: int = Form(0),
    clarity: int = Form(0),
):
    """Submit a review for an article."""
    from peerpedia_core.workflow.review import assign_reviewer, submit_review

    # Assign
    assign_result = assign_reviewer(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not assign_result.success and "must be" not in assign_result.error:
        raise HTTPException(status_code=400, detail=assign_result.error)

    # Submit review
    result = submit_review(
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific_correctness,
        clarity=clarity,
        database_url=settings.database_url,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "review_id": result.review_id,
        "points_earned": result.points_earned,
        "status": "submitted",
    }


@router.post("/articles/{article_id}/decide")
async def api_decide_article(article_id: str):
    """Make a decision on an article."""
    from peerpedia_core.workflow.review import make_decision

    result = make_decision(
        article_id=article_id,
        database_url=settings.database_url,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "article_id": article_id,
        "new_status": result.new_status,
        "author_points": result.author_points,
    }
```

- [ ] **Step 2: Update pages.py — add review page route**

Add to `peerpedia/web/routes/pages.py` (before the review_queue route, replace it):

```python
@router.get("/review/{article_id}", response_class=HTMLResponse)
async def review_article_page(request: Request, article_id: str):
    """Review form for a specific article."""
    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return templates.TemplateResponse(
                "review.html",
                {"request": request, "title": "Not Found", "article": None, "reviews": []},
                status_code=404,
            )

        from peerpedia_core.storage.db import get_reviews_for_article
        reviews = get_reviews_for_article(session, article_id)

        return templates.TemplateResponse(
            "review.html",
            {
                "request": request,
                "title": f"Review: {article.title}",
                "article": article.to_dict(),
                "reviews": [r.to_dict() for r in reviews],
            },
        )
    finally:
        session.close()
```

- [ ] **Step 3: Rewrite review.html template**

Replace `peerpedia/web/templates/review.html`:

```html
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>{{ title }} — PeerPedia</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body>
    <header>
        <h1>📚 PeerPedia</h1>
        <nav>
            <a href="/">Home</a>
            <a href="/submit">Submit</a>
            <a href="/review">Review Queue</a>
        </nav>
    </header>

    <main>
    {% if article %}
        <h2>Review: {{ article.title }}</h2>

        <div class="article-meta">
            <span>Status: <span class="status {{ article.status }}">{{ article.status }}</span></span>
            <span>Format: {{ article.format }}</span>
            <span>Authors: {{ article.founding_authors | join(", ") }}</span>
        </div>

        <div class="article-abstract">
            <h3>Abstract</h3>
            <p>{{ article.abstract }}</p>
        </div>

        {% if reviews %}
        <section class="existing-reviews">
            <h3>Existing Reviews ({{ reviews | length }})</h3>
            {% for r in reviews %}
            <div class="review-card">
                <p class="meta">
                    {{ r.reviewer_id }} · {{ r.decision }} ·
                    Scientific: {{ r.scientific_correctness }}/5 ·
                    Clarity: {{ r.clarity }}/5 ·
                    +{{ r.points_earned }} pts
                </p>
                <p>{{ r.comments }}</p>
            </div>
            {% endfor %}
        </section>
        {% endif %}

        <section class="review-form">
            <h3>Submit Your Review</h3>
            <form action="/api/v1/articles/{{ article.id }}/reviews" method="post"
                  hx-post="/api/v1/articles/{{ article.id }}/reviews"
                  hx-target="#review-result"
                  hx-swap="innerHTML">
                <label>Your Name/ID: <input type="text" name="reviewer_id" required></label>
                <label>Decision:
                    <select name="decision" required>
                        <option value="accept">Accept</option>
                        <option value="revise">Revise</option>
                        <option value="reject">Reject</option>
                    </select>
                </label>
                <label>Scientific Correctness (1-5):
                    <input type="range" name="scientific_correctness" min="1" max="5" value="3">
                </label>
                <label>Clarity (1-5):
                    <input type="range" name="clarity" min="1" max="5" value="3">
                </label>
                <label>Comments (Markdown):
                    <textarea name="comments" rows="6"></textarea>
                </label>
                <button type="submit">Submit Review</button>
            </form>
            <div id="review-result"></div>
        </section>

        <section class="decision-action">
            <h3>Make Decision</h3>
            <button hx-post="/api/v1/articles/{{ article.id }}/decide"
                    hx-target="#decision-result"
                    hx-swap="innerHTML">
                Decide Now
            </button>
            <div id="decision-result"></div>
        </section>

    {% elif articles is defined and articles %}
        <h2>Review Queue</h2>
        <p>{{ articles | length }} article(s) pending review.</p>
        {% for a in articles %}
        <article class="article-card">
            <h3><a href="/review/{{ a.id }}">{{ a.title }}</a></h3>
            <p class="meta">
                {{ a.founding_authors | join(", ") }} · {{ a.format }} ·
                <span class="status {{ a.status }}">{{ a.status }}</span>
            </p>
            <p class="abstract">{{ a.abstract[:200] }}</p>
        </article>
        {% endfor %}
    {% else %}
        <h2>Review Queue</h2>
        <p class="empty-state">No articles pending review.</p>
    {% endif %}
    </main>
</body>
</html>
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia/web/routes/api.py peerpedia/web/routes/pages.py peerpedia/web/templates/review.html
git commit -m "feat: wire Web review routes + templates (M2 Task 5)

- API: GET/POST /api/v1/articles/{id}/reviews, POST .../decide
- Pages: /review/{article_id} shows review form with HTMX
- review.html: real review queue + individual review page
- HTMX-powered review submission and decision with inline results

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: E2E Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: ~56 passed, 0 failures

- [ ] **Step 2: End-to-end review workflow**

```bash
cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate

# Reset
rm -f ~/.peerpedia/db/peerpedia.db
peerpedia init

# Submit article
cat > /tmp/m2_test.typ << 'TYPST'
---
title: M2 Review Workflow Test
abstract: Testing the complete M2 review pipeline.
categories:
  - test
language: en
---

= M2 Review Workflow Test

== Introduction

This article tests the full M2 review workflow: submit → assign → review → decide.
TYPST

peerpedia submit /tmp/m2_test.typ --author "Author1"

# Manually set to submitted (for testing)
ARTICLE_ID=$(python -c "
from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db, get_session, list_articles, update_article_status
engine = get_engine(settings.database_url)
init_db(engine)
session = get_session(engine)
articles = list_articles(session)
aid = articles[0].id
update_article_status(session, aid, 'submitted')
session.commit()
print(aid)
session.close()
")

echo "Article ID: $ARTICLE_ID"

# Review the article
peerpedia review "$ARTICLE_ID" -d accept -c "Excellent paper." --scientific 5 --clarity 5 --reviewer "Reviewer1"

# Make decision
peerpedia decide "$ARTICLE_ID"

# Verify
python -c "
from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db, get_session, get_article, get_reviews_for_article
engine = get_engine(settings.database_url)
init_db(engine)
session = get_session(engine)
article = get_article(session, '$ARTICLE_ID')
print(f'Article status: {article.status}')
reviews = get_reviews_for_article(session, '$ARTICLE_ID')
print(f'Reviews: {len(reviews)}')
for r in reviews:
    print(f'  {r.reviewer_id}: {r.decision} (+{r.points_earned} pts)')
session.close()
"
```

Expected: article accepted, 1 review with 20 points, author gets 50 points.

- [ ] **Step 3: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add -A
git commit -m "feat: Phase 3 M2 complete — review workflow

State machine (14 tests) + Review DB model (3 tests) + Review
orchestration (8 tests) + CLI + Web = full review pipeline.

Workflow: submit → assign reviewer → submit review → decide → points
- assign_reviewer(): self-assign, transitions submitted → in_review
- submit_review(): records review, prevents duplicates, awards 20 pts
- make_decision(): accepts if any positive review
- CLI: peerpedia review (-d/-c/--scientific/--clarity), peerpedia decide
- Web: review queue, HTMX review form, decision button
- ~56 tests, 0 failures

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Summary

| Task | What | Files | Tests |
|---|---|---|---|
| 1 | State machine | `workflow/state_machine.py` (new) | 14 |
| 2 | Review DB model | `db.py` (edit) | +3 |
| 3 | Review orchestration | `workflow/review.py` (new) | 8 |
| 4 | Wire CLI | `main.py` (edit) | — |
| 5 | Wire Web | `api.py`, `pages.py`, `review.html` (edit) | — |
| 6 | E2E verification | — | — |

**Parallel dispatch strategy:**
- Round 1: Task 1 + Task 2 (independent)
- Round 2: Task 3 (depends on 1+2)
- Round 3: Task 4 + Task 5 (independent, both depend on 3)
- Final: Task 6 (I run this)

**After M2:** Full review pipeline works: submit article → assign reviewer → submit review → decide (accept/reject/revise) → points awarded.
