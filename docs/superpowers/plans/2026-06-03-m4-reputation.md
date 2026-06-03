# M4 Reputation Cluster — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add User/Identity tables, identity-weighted reputation computation, and Chart.js radar chart to user profile page.

**Architecture:** New `User` and `Identity` ORM models in `db.py` with CRUD operations. `ReputationV1.compute()` reads from these tables + existing Article/Review/ContributionRecord tables to produce a 4D reputation vector. New REST API endpoints serve user data and reputation. The user profile page renders a Chart.js radar chart from the reputation API.

**Tech Stack:** Python 3.14, SQLAlchemy, FastAPI, Jinja2, HTMX, Chart.js (CDN), pytest

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `peerpedia_core/storage/db.py` | User + Identity ORM models + CRUD | Modify |
| `peerpedia_core/reputation/v1.py` | `compute()` implementation aggregating DB data | Modify |
| `peerpedia/web/routes/api.py` | 4 new API endpoints (user CRUD + reputation) | Modify |
| `peerpedia/web/routes/pages.py` | User page fetches reputation data | Modify |
| `peerpedia/web/templates/user.html` | Radar chart canvas + Chart.js script | Modify |
| `peerpedia/cli/main.py` | `user register` command | Modify |
| `tests/test_user_db.py` | User + Identity CRUD tests | Create |
| `tests/test_reputation.py` | Extended reputation compute tests | Modify |
| `tests/test_user_api.py` | API endpoint tests | Create |

---

### Task 1: User + Identity ORM Models and CRUD

**Files:**
- Modify: `peerpedia_core/storage/db.py` (add ~120 lines after the edit_proposals section)
- Create: `tests/test_user_db.py`

- [ ] **Step 1: Write the failing tests for User and Identity CRUD**

Create `tests/test_user_db.py`:

```python
"""Tests for User and Identity ORM models."""
import pytest
import tempfile
from pathlib import Path

from peerpedia_core.storage.db import (
    Base,
    User,
    Identity,
    create_user,
    get_user,
    create_identity,
    get_identities_for_user,
    get_engine,
    get_session,
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
        from peerpedia_core.storage.db import update_user_last_active
        from datetime import datetime, timezone

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
            after = datetime.now(timezone.utc)

            assert result is not None
            assert result.last_active is not None
            assert before <= result.last_active <= after


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

    def test_identity_without_user(self):
        """create_identity should work even if user row doesn't exist (lax FK)."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            identity = create_identity(
                session,
                user_id="nonexistent",
                type="orcid",
                value="0000-0002-3456-7890",
                verified=False,
                trust_weight=100,
            )
            session.commit()
            assert identity.id is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_user_db.py -v`
Expected: FAIL — `User` and `create_user` etc. not defined in `peerpedia_core.storage.db`

- [ ] **Step 3: Add User + Identity ORM models to db.py**

Insert after the `EditProposal` ORM model (after line ~314 in db.py) and before the CRUD Operations section:

```python
# ── ORM Model: User ──────────────────────────────────────────────────────────────

class User(Base):
    """SQLAlchemy model for user profiles. Mirrors protocol UserProfile."""

    __tablename__ = "users"

    id = Column(String(100), primary_key=True)  # user-chosen slug
    name = Column(String(200), nullable=False)
    email = Column(String(300), nullable=False)
    affiliation = Column(String(500), nullable=True)
    expertise = Column(JSONList, nullable=False, default=list)
    bio = Column(Text, nullable=True)
    public_key = Column(Text, nullable=True)
    joined_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "affiliation": self.affiliation,
            "expertise": self.expertise,
            "bio": self.bio,
            "public_key": self.public_key,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
        }


# ── ORM Model: Identity ──────────────────────────────────────────────────────────

class Identity(Base):
    """SQLAlchemy model for verified identity bindings. Mirrors protocol Identity."""

    __tablename__ = "identities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False)
    # "orcid" | "inst_email" | "arxiv" | "github" | "scholar"
    value = Column(String(300), nullable=False)
    verified = Column(Integer, nullable=False, default=0)  # SQLite bool
    trust_weight = Column(Integer, nullable=False, default=10)
    # Scaled integer: weight × 100 (1.0 → 100, 0.3 → 30)

    __table_args__ = (
        Index("ix_identity_user_type", "user_id", "type"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "value": self.value,
            "verified": bool(self.verified),
            "trust_weight": self.trust_weight / 100.0,  # Convert back to float
        }
```

- [ ] **Step 4: Add User + Identity CRUD functions to db.py**

Insert after the `update_article_version` function (end of db.py):

```python
# ── User CRUD ────────────────────────────────────────────────────────────────────


def create_user(
    session: Session,
    *,
    id: str,
    name: str,
    email: str,
    affiliation: Optional[str] = None,
    expertise: Optional[list[str]] = None,
    bio: Optional[str] = None,
    public_key: Optional[str] = None,
) -> User:
    """Create a new user record."""
    user = User(
        id=id,
        name=name,
        email=email,
        affiliation=affiliation,
        expertise=expertise or [],
        bio=bio,
        public_key=public_key,
    )
    session.add(user)
    return user


def get_user(session: Session, user_id: str) -> Optional[User]:
    """Get a user by ID, or None."""
    return session.query(User).filter(User.id == user_id).first()


def update_user_last_active(
    session: Session, user_id: str
) -> Optional[User]:
    """Update a user's last_active timestamp to now."""
    user = get_user(session, user_id)
    if user:
        user.last_active = datetime.now(timezone.utc)
    return user


# ── Identity CRUD ───────────────────────────────────────────────────────────────


def create_identity(
    session: Session,
    *,
    user_id: str,
    type: str,
    value: str,
    verified: bool = False,
    trust_weight: int = 10,
) -> Identity:
    """Create an identity binding for a user.
    
    trust_weight is scaled ×100 (e.g., 100 for ORCID = 1.0 weight).
    """
    identity = Identity(
        id=str(uuid.uuid4()),
        user_id=user_id,
        type=type,
        value=value,
        verified=1 if verified else 0,
        trust_weight=trust_weight,
    )
    session.add(identity)
    return identity


def get_identities_for_user(session: Session, user_id: str) -> list[Identity]:
    """Get all identity bindings for a user."""
    return (
        session.query(Identity)
        .filter(Identity.user_id == user_id)
        .all()
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_user_db.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add peerpedia_core/storage/db.py tests/test_user_db.py
git commit -m "feat: add User and Identity ORM models with CRUD

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: ReputationV1.compute() Implementation

**Files:**
- Modify: `peerpedia_core/reputation/v1.py`
- Modify: `tests/test_reputation.py`

- [ ] **Step 7: Write extended tests for reputation compute**

Append to `tests/test_reputation.py`:

```python
class TestReputationComputeIntegration:
    """Integration tests for ReputationV1.compute() with real DB data."""

    def test_compute_from_articles_and_reviews(self):
        """compute() should aggregate articles, reviews, and contributions."""
        import tempfile
        from pathlib import Path
        from peerpedia_core.storage.db import (
            get_engine, get_session, init_db,
            create_user, create_article, create_review, create_contribution_record,
            create_identity, get_identities_for_user,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            # Create user
            create_user(session, id="alice", name="Alice", email="a@test.com",
                        affiliation="MIT", expertise=["physics"])
            session.commit()

            # Create 2 articles
            create_article(session, title="Article 1",
                           founding_authors=["alice"], abstract="...",
                           git_repo_path="/tmp/a1")
            create_article(session, title="Article 2",
                           founding_authors=["alice"], abstract="...",
                           git_repo_path="/tmp/a2")
            session.commit()

            # Create 3 reviews by alice
            for i in range(3):
                create_review(session, article_id="dummy-1", reviewer_id="alice",
                              decision="accept", comments="good",
                              scientific_correctness=4, clarity=4,
                              points_earned=20)
            session.commit()

            # Create contribution records for alice
            create_contribution_record(session, article_id="dummy-1",
                                       user_id="alice", commit_hash="abc123",
                                       change_type="content",
                                       contribution_weight=200)
            session.commit()

            algo = ReputationV1()
            vec = algo.compute("alice", session)

            # With 2 articles, 3 reviews, 200 contrib weight
            assert vec.academic_contribution > 0
            assert vec.review_quality > 0
            assert vec.total_points == 60  # 3 × 20

    def test_compute_with_identities(self):
        """Verified identities should boost reputation via multiplier."""
        import tempfile
        from pathlib import Path
        from peerpedia_core.storage.db import (
            get_engine, get_session, init_db,
            create_user, create_article, create_identity,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            # User with ORCID (trust_weight=100) and GitHub (trust_weight=30)
            create_user(session, id="bob", name="Bob", email="b@test.com")
            create_identity(session, user_id="bob", type="orcid",
                            value="0000-0001-2345-6789", verified=True,
                            trust_weight=100)
            create_identity(session, user_id="bob", type="github",
                            value="bob-dev", verified=True, trust_weight=30)
            session.commit()

            create_article(session, title="Bob's Paper",
                           founding_authors=["bob"], abstract="...",
                           git_repo_path="/tmp/b1")
            session.commit()

            algo = ReputationV1()
            vec = algo.compute("bob", session)

            # Should be higher than base due to identity multiplier
            # multiplier = 1.0 + (1.0 + 0.3) * 0.1 = 1.13
            assert vec.academic_contribution > 0
            assert vec.review_quality >= 0  # 0 reviews = 0 but not negative

    def test_compute_nonexistent_user(self):
        """compute() should return zero vector for unknown user."""
        import tempfile
        from pathlib import Path
        from peerpedia_core.storage.db import get_engine, get_session, init_db

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            algo = ReputationV1()
            vec = algo.compute("ghost", session)
            assert vec.academic_contribution == 0.0
            assert vec.review_quality == 0.0
            assert vec.collaboration_spirit == 0.0
            assert vec.education_outreach == 0.0
            assert vec.total_points == 0

    def test_last_active_tracking(self):
        """update_user_last_active should work correctly."""
        import tempfile
        from pathlib import Path
        from datetime import datetime, timezone
        from peerpedia_core.storage.db import (
            get_engine, get_session, init_db,
            create_user, update_user_last_active,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            create_user(session, id="eve", name="Eve", email="eve@test.com")
            session.commit()

            # Initially no last_active
            user = session.query(User).filter_by(id="eve").first()
            assert user.last_active is None

            # Update
            update_user_last_active(session, "eve")
            session.commit()

            user = session.query(User).filter_by(id="eve").first()
            assert user.last_active is not None
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `python -m pytest tests/test_reputation.py::TestReputationComputeIntegration -v`
Expected: FAIL — `compute()` is a placeholder that returns empty vector

- [ ] **Step 9: Implement ReputationV1.compute()**

Replace the `compute` method in `peerpedia_core/reputation/v1.py` (line 95-98):

```python
    def compute(self, user_id: str, session) -> ReputationVector:
        """Compute reputation from stored article, review, and identity records.

        Args:
            user_id: The user slug to compute for.
            session: SQLAlchemy Session for database access.

        Returns:
            ReputationVector with 4D scores (0-100) and total_points.
        """
        from peerpedia_core.storage.db import (
            Article, Review, ContributionRecord, Identity,
            get_user, get_identities_for_user,
        )
        from sqlalchemy import func

        # ── 1. Aggregate activity data ──
        # Count articles where user is a founding author
        article_count = session.query(func.count(Article.id)).filter(
            Article.founding_authors.contains(user_id)
        ).scalar() or 0

        # Count reviews by user
        review_count = session.query(func.count(Review.id)).filter(
            Review.reviewer_id == user_id
        ).scalar() or 0

        # Sum review points
        review_points = session.query(func.sum(Review.points_earned)).filter(
            Review.reviewer_id == user_id
        ).scalar() or 0

        # Sum contribution weights
        contrib_weight_total = session.query(
            func.sum(ContributionRecord.contribution_weight)
        ).filter(
            ContributionRecord.user_id == user_id
        ).scalar() or 0

        # Count collaborations (articles where user is co-author beyond founding)
        collab_count = 0
        articles = session.query(Article).filter(
            Article.founding_authors.contains(user_id)
        ).all()
        for a in articles:
            if len(a.founding_authors) > 1:
                collab_count += 1

        # Education outreach: pinned_by count on user's articles
        outreach_articles = session.query(Article).filter(
            Article.founding_authors.contains(user_id)
        ).all()
        outreach = sum(a.pinned_by for a in outreach_articles)

        # ── 2. Identity multiplier ──
        identities = get_identities_for_user(session, user_id)
        identity_multiplier = 1.0
        for ident in identities:
            if ident.verified:
                identity_multiplier += (ident.trust_weight / 100.0) * 0.1

        # ── 3. Time decay ──
        user = get_user(session, user_id)
        decay = 1.0
        if user is not None and user.last_active is not None:
            from datetime import datetime, timezone
            days_inactive = (datetime.now(timezone.utc) - user.last_active).days
            if days_inactive > self.params.decay_grace_days:
                decay_days = days_inactive - self.params.decay_grace_days
                decay = max(0.5, (1.0 - self.params.decay_rate_per_day) ** decay_days)

        # ── 4. Compute four dimensions ──
        academic = min(100.0, (article_count * 10.0 + contrib_weight_total / 100.0)
                       * identity_multiplier * decay)
        review = min(100.0, (review_count * 15.0 + review_points / 10.0)
                     * identity_multiplier * decay)
        collaboration = min(100.0, (collab_count * 20.0)
                            * identity_multiplier * decay)
        education = min(100.0, (outreach * 5.0)
                        * identity_multiplier * decay)

        return ReputationVector(
            user_id=user_id,
            academic_contribution=round(academic, 1),
            review_quality=round(review, 1),
            collaboration_spirit=round(collaboration, 1),
            education_outreach=round(education, 1),
            total_points=review_points,
        )
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `python -m pytest tests/test_reputation.py -v`
Expected: ALL tests pass (existing + new integration tests)

- [ ] **Step 11: Commit**

```bash
git add peerpedia_core/reputation/v1.py tests/test_reputation.py
git commit -m "feat: implement ReputationV1.compute() with identity boost and decay

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: User/Identity/Reputation API Endpoints

**Files:**
- Modify: `peerpedia/web/routes/api.py`
- Create: `tests/test_user_api.py`

- [ ] **Step 12: Write failing tests for new API endpoints**

Create `tests/test_user_api.py`:

```python
"""Tests for user, identity, and reputation API endpoints."""
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from peerpedia_core.storage.db import get_engine, get_session, init_db
from peerpedia.web.app import app


def _setup_test_app(db_path: Path):
    """Override the app's DB with a temp database for testing."""
    import peerpedia.web.routes.api as api_mod
    import peerpedia.web.routes.pages as pages_mod

    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)

    # Override session factory for tests
    original_get_session = api_mod._get_db_session
    original_pages_session = pages_mod._get_db_session

    def test_session():
        return get_session(engine)

    api_mod._get_db_session = test_session
    pages_mod._get_db_session = test_session

    yield engine

    api_mod._get_db_session = original_get_session
    pages_mod._get_db_session = original_pages_session


class TestUserAPI:

    def test_create_user(self):
        """POST /api/v1/users should create a user."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            for _ in _setup_test_app(db_path):
                pass

            client = TestClient(app)

            resp = client.post("/api/v1/users", json={
                "id": "testuser",
                "name": "Test User",
                "email": "test@example.com",
                "affiliation": "MIT",
                "expertise": ["physics", "math"],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "testuser"
            assert data["name"] == "Test User"

    def test_get_user(self):
        """GET /api/v1/users/{user_id} should return user info."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            for _ in _setup_test_app(db_path):
                pass

            client = TestClient(app)

            # Create user first
            client.post("/api/v1/users", json={
                "id": "alice", "name": "Alice", "email": "alice@test.com",
            })

            resp = client.get("/api/v1/users/alice")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "alice"
            assert data["name"] == "Alice"

    def test_get_user_not_found(self):
        """GET /api/v1/users/{user_id} should 404 for unknown user."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            for _ in _setup_test_app(db_path):
                pass

            client = TestClient(app)
            resp = client.get("/api/v1/users/nobody")
            assert resp.status_code == 404

    def test_create_identity(self):
        """POST /api/v1/users/{user_id}/identities should bind identity."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            for _ in _setup_test_app(db_path):
                pass

            client = TestClient(app)

            client.post("/api/v1/users", json={
                "id": "bob", "name": "Bob", "email": "bob@test.com",
            })

            resp = client.post("/api/v1/users/bob/identities", json={
                "type": "orcid",
                "value": "0000-0001-2345-6789",
                "verified": True,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["type"] == "orcid"
            assert data["verified"] is True

    def test_create_identity_user_not_found(self):
        """POST /api/v1/users/{user_id}/identities should 404 if user missing."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            for _ in _setup_test_app(db_path):
                pass

            client = TestClient(app)
            resp = client.post("/api/v1/users/ghost/identities", json={
                "type": "orcid",
                "value": "0000-0002-3456-7890",
            })
            assert resp.status_code == 404

    def test_get_reputation(self):
        """GET /api/v1/users/{user_id}/reputation should return ReputationVector."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            for _ in _setup_test_app(db_path):
                pass

            client = TestClient(app)

            client.post("/api/v1/users", json={
                "id": "charlie", "name": "Charlie", "email": "c@test.com",
            })

            resp = client.get("/api/v1/users/charlie/reputation")
            assert resp.status_code == 200
            data = resp.json()
            assert data["user_id"] == "charlie"
            assert "academic_contribution" in data
            assert "review_quality" in data
            assert "collaboration_spirit" in data
            assert "education_outreach" in data
            assert "total_points" in data

    def test_get_reputation_nonexistent_user(self):
        """GET /api/v1/users/{user_id}/reputation should return zeros for unknown user."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            for _ in _setup_test_app(db_path):
                pass

            client = TestClient(app)

            resp = client.get("/api/v1/users/nobody/reputation")
            assert resp.status_code == 200
            data = resp.json()
            assert data["user_id"] == "nobody"
            assert data["academic_contribution"] == 0.0
```


- [ ] **Step 13: Run tests to verify they fail**

Run: `python -m pytest tests/test_user_api.py -v`
Expected: FAIL — 404 on `/api/v1/users` etc. (endpoints not yet defined)

- [ ] **Step 14: Add API endpoints to api.py**

Add to `peerpedia/web/routes/api.py` after the existing imports and before the last endpoint (after line ~430, before health check):

```python
# ── User & Identity ──────────────────────────────────────────────────────────────

from pydantic import BaseModel as PydanticBaseModel, Field


class UserCreateRequest(PydanticBaseModel):
    id: str
    name: str
    email: str
    affiliation: str | None = None
    expertise: list[str] = Field(default_factory=list)
    bio: str | None = None


class IdentityCreateRequest(PydanticBaseModel):
    type: str
    value: str
    verified: bool = False


@router.get("/users/{user_id}")
async def api_get_user(user_id: str):
    """Get user profile with identities."""
    from peerpedia_core.storage.db import get_user, get_identities_for_user

    session = _get_db_session()
    try:
        user = get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        identities = get_identities_for_user(session, user_id)
        result = user.to_dict()
        result["identities"] = [i.to_dict() for i in identities]
        return result
    finally:
        session.close()


@router.post("/users")
async def api_create_user(req: UserCreateRequest):
    """Create (register) a new user."""
    from peerpedia_core.storage.db import create_user as db_create_user, get_user

    session = _get_db_session()
    try:
        existing = get_user(session, req.id)
        if existing:
            raise HTTPException(status_code=409, detail=f"User '{req.id}' already exists")

        user = db_create_user(
            session,
            id=req.id,
            name=req.name,
            email=req.email,
            affiliation=req.affiliation,
            expertise=req.expertise,
            bio=req.bio,
        )
        session.commit()
        return user.to_dict()
    finally:
        session.close()


@router.post("/users/{user_id}/identities")
async def api_create_identity(user_id: str, req: IdentityCreateRequest):
    """Bind a verified identity to a user."""
    from peerpedia_core.storage.db import (
        get_user, create_identity as db_create_identity,
    )

    session = _get_db_session()
    try:
        user = get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Determine trust_weight from identity type
        from peerpedia_core.reputation import ReputationParams
        params = ReputationParams()
        weight_map = {
            "orcid": params.identity_weights["orcid"],
            "inst_email": params.identity_weights["inst_email"],
            "arxiv": params.identity_weights["arxiv"],
            "scholar": params.identity_weights["scholar"],
            "github": params.identity_weights["github"],
        }
        trust_weight_float = weight_map.get(req.type, 0.1)
        trust_weight_scaled = int(trust_weight_float * 100)

        identity = db_create_identity(
            session,
            user_id=user_id,
            type=req.type,
            value=req.value,
            verified=req.verified,
            trust_weight=trust_weight_scaled,
        )
        session.commit()
        return identity.to_dict()
    finally:
        session.close()


@router.get("/users/{user_id}/reputation")
async def api_get_user_reputation(user_id: str):
    """Get the reputation vector for a user."""
    from peerpedia_core.reputation import ReputationV1

    session = _get_db_session()
    try:
        algo = ReputationV1()
        vec = algo.compute(user_id, session)
        return vec.model_dump()
    finally:
        session.close()
```

Note: In the imports we need to handle the `IdentityType` enum—the `ReputationParams.identity_weights` dict uses `IdentityType` enum keys but our DB stores string types. We need to fix the lookup. Change the weight_map logic to use string keys:

```python
        weight_map = {
            "orcid": 1.0,
            "inst_email": 0.8,
            "arxiv": 0.6,
            "scholar": 0.5,
            "github": 0.3,
        }
```

- [ ] **Step 15: Run tests to verify they pass**

Run: `python -m pytest tests/test_user_api.py -v`
Expected: 7 passed

- [ ] **Step 16: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL tests pass (126 + 7 + whatever new tests from Task 2 = all green)

- [ ] **Step 17: Commit**

```bash
git add peerpedia/web/routes/api.py tests/test_user_api.py
git commit -m "feat: add user/identity/reputation API endpoints

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: User Profile Page with Reputation Data

**Files:**
- Modify: `peerpedia/web/routes/pages.py`
- Modify: `peerpedia/web/templates/user.html`

- [ ] **Step 18: Update pages.py user_profile route to fetch reputation**

Modify the user_profile function in `peerpedia/web/routes/pages.py`. After the existing `total_points` calculation (line ~215), add:

```python
        # Fetch reputation vector
        from peerpedia_core.reputation import ReputationV1
        algo = ReputationV1()
        rep = algo.compute(user_id, session)

        reputation = rep.model_dump()
```

And add `reputation` to the template context. The complete updated return statement (~line 192-217) should include:

```python
        return templates.TemplateResponse(
            "user.html",
            {
                "request": request,
                "title": f"用户: {user_id}",
                "user_id": user_id,
                "authored": [a.to_dict() for a in authored],
                "mirrored": [m.to_dict() for m in mirrored],
                "reviews": [
                    {
                        "article_id": r.article_id,
                        "decision": r.decision,
                        "points_earned": r.points_earned,
                        "scientific_correctness": r.scientific_correctness,
                        "clarity": r.clarity,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in reviews
                ],
                "activities": activities[:30],
                "total_articles": len(authored),
                "total_mirrors": len(mirrored),
                "total_reviews": len(reviews),
                "total_points": sum(r.points_earned for r in reviews),
                "reputation": reputation,
            },
        )
```

- [ ] **Step 19: Update user.html template with radar chart**

In `peerpedia/web/templates/user.html`, add the reputation radar chart section after the user stats block (after the `</section>` on line ~40). Insert:

```html
        {% if reputation %}
        <section class="user-section">
            <h3>📊 信誉雷达图</h3>
            <div style="display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap;">
                <div style="width: 280px; height: 280px;">
                    <canvas id="reputationRadar"></canvas>
                </div>
                <div style="flex: 1; min-width: 200px;">
                    <table class="rep-table">
                        <tr>
                            <td>学术贡献</td>
                            <td><strong>{{ reputation.academic_contribution }}</strong>/100</td>
                        </tr>
                        <tr>
                            <td>审稿质量</td>
                            <td><strong>{{ reputation.review_quality }}</strong>/100</td>
                        </tr>
                        <tr>
                            <td>协作精神</td>
                            <td><strong>{{ reputation.collaboration_spirit }}</strong>/100</td>
                        </tr>
                        <tr>
                            <td>教学传播</td>
                            <td><strong>{{ reputation.education_outreach }}</strong>/100</td>
                        </tr>
                        <tr>
                            <td>总积分</td>
                            <td><strong>{{ reputation.total_points }}</strong></td>
                        </tr>
                    </table>
                </div>
            </div>
        </section>
        {% endif %}
```

And add the Chart.js CDN script + radar chart initialization right before `</body>` (before the footer, after line ~133):

```html
    </main>

    {% if reputation %}
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
    (function() {
        var ctx = document.getElementById('reputationRadar');
        if (!ctx) return;
        new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['学术贡献', '审稿质量', '协作精神', '教学传播'],
                datasets: [{
                    label: '{{ user_id }}',
                    data: [
                        {{ reputation.academic_contribution }},
                        {{ reputation.review_quality }},
                        {{ reputation.collaboration_spirit }},
                        {{ reputation.education_outreach }}
                    ],
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 2,
                    pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { stepSize: 20 }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    })();
    </script>
    {% endif %}

    <footer>
        <p>知著网 v0.1.0 — <a href="/api/v1/health">API</a></p>
    </footer>
```

- [ ] **Step 20: Run tests to verify existing tests still pass**

Run: `python -m pytest tests/ -v`
Expected: ALL tests pass

- [ ] **Step 21: Commit**

```bash
git add peerpedia/web/routes/pages.py peerpedia/web/templates/user.html
git commit -m "feat: add reputation radar chart to user profile page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: CLI `user register` Command

**Files:**
- Modify: `peerpedia/cli/main.py`

- [ ] **Step 22: Add `user register` CLI command**

Add after the `mirror` command in `peerpedia/cli/main.py` (after line ~250):

```python
@cli.group()
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
    from peerpedia.config.settings import settings
    from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user, get_user

    engine = get_engine(settings.database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        existing = get_user(session, user_id)
        if existing:
            click.echo(f"✗ 用户 '{user_id}' 已存在", err=True)
            raise SystemExit(1)

        exp_list = [e.strip() for e in expertise.split(",") if e.strip()]
        user = create_user(
            session,
            id=user_id,
            name=name,
            email=email,
            affiliation=affiliation,
            expertise=exp_list,
        )
        session.commit()

        click.echo(f"✓ 用户注册成功！")
        click.echo(f"  ID:     {user.id}")
        click.echo(f"  名称:   {user.name}")
        click.echo(f"  邮箱:   {user.email}")
        click.echo(f"  机构:   {user.affiliation or '无'}")
        click.echo(f"  专长:   {', '.join(user.expertise) if user.expertise else '无'}")
    finally:
        session.close()
```

- [ ] **Step 23: Test the CLI command**

Run: `python -m peerpedia.cli.main user register testuser --name "Test" --email "t@t.com"`
Expected: `✓ 用户注册成功！`

Run: `python -m peerpedia.cli.main user register testuser --name "Test" --email "t@t.com"` (duplicate)
Expected: `✗ 用户 'testuser' 已存在` with exit code 1

- [ ] **Step 24: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL tests pass

- [ ] **Step 25: Commit**

```bash
git add peerpedia/cli/main.py
git commit -m "feat: add 'peerpedia user register' CLI command

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Final Verification

- [ ] **Step 26: Run full test suite with coverage**

```bash
cd ~/Projects/peerpedia
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: ALL tests green, 0 failures.

- [ ] **Step 27: Verify manual flow**

```bash
# Register a user
python -m peerpedia.cli.main user register zhangsan --name "张三" --email "zhang@test.com" --affiliation "MIT" --expertise "quantum,topology"

# Submit an article as that user
python -m peerpedia.cli.main submit /path/to/test.typ --author zhangsan

# Review an article as that user (if article exists)
python -m peerpedia.cli.main review <article_id> -d accept -c "good" --reviewer zhangsan

# Check API
curl http://localhost:8080/api/v1/users/zhangsan
curl http://localhost:8080/api/v1/users/zhangsan/reputation

# Bind identity
curl -X POST http://localhost:8080/api/v1/users/zhangsan/identities \
  -H "Content-Type: application/json" \
  -d '{"type":"orcid","value":"0000-0001-2345-6789","verified":true}'
```

- [ ] **Step 28: Update STATUS.md**

```markdown
| Phase 3 M4 | 信誉+LAN（Reputation Cluster） | ✅ | N tests |
```

Update the test count in the header.

- [ ] **Step 29: Final commit**

```bash
git add STATUS.md
git commit -m "docs: update STATUS for M4 reputation cluster complete

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
