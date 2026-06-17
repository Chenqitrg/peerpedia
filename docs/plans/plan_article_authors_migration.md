# Pre-Online Tech Debt — JSON → Join Tables

## Context

Before deploying PeerPedia for multi-user testing, migrate `Article.authors` from
JSON column to proper `article_authors` join table. This is a P0 blocker for Phase 2:
- `Article.authors.contains(user_id)` is a full-table scan in SQLite
- "Find articles by author" is the app's most frequent query
- Multi-user testing will surface this immediately

## Scope

### P0 — `Article.authors` → `article_authors` (must do now)
- Create `article_authors` model + table
- Create migration script
- Update CRUD: `create_article`, `list_articles`, `get_article`, `delete_article`
- Update all call sites (~15 files): routes, helpers, workflow, tests

### P1 — `Review.thread` → `review_messages` (can defer)
- Thread messages don't paginate or search yet, JSON works for now

### P3 — `MergeProposal.thread` (skip)
- Low-frequency operation, JSON is fine

## Implementation

### 1. New model
```python
# models.py
class ArticleAuthor(Base):
    __tablename__ = "article_authors"
    __table_args__ = (UniqueConstraint("article_id", "author_id"),)
    article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    author_id = Column(String, ForeignKey("users.id"), primary_key=True)
    position = Column(Integer, default=0)
```

### 2. Migration script
`scripts/migrate_article_authors.py` — one-shot script to create table +
migrate JSON data.

### 3. CRUD changes
`crud_article.py`:
- `create_article()` — insert into `article_authors` rows
- `list_articles()` — use `article_authors` join instead of `.contains()`
- `delete_article()` — cascade delete join rows

### 4. Update call sites
- `helpers.py`: `resolve_authors()` — query join table instead of reading JSON
- `routes/articles.py`: `build_article_detail()` — resolve from join
- `routes/reviews.py`: `_build_review_out()` — check authorship
- `routes/users.py`: article count query
- `workflow/reputation.py`: articles-by-author query
- `workflow/scoring.py`, `workflow/sedimentation.py`
- All test files

## Verification
```bash
python scripts/migrate_article_authors.py
.venv/bin/python -m pytest backend/tests/ core/tests/ -q
```

## NOT in Scope
- `Review.thread` → `review_messages` (deferred)
- `MergeProposal.thread` (deferred)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-ceo-review` | Pre-online tech debt | 1 | issues_open | 1 critical item |

- **VERDICT:** JSON→join table migration required before multi-user deployment
