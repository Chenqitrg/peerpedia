# Community Five-Dimension Review — Implementation Plan

> **Goal:** Community reviewers rate articles using the same 5 dimensions as self-review (originality, rigor, completeness, pedagogy, impact). Article page shows self vs community comparison.

**Architecture:** Add 5 columns to Review model. Review form gets star-rating UI matching submit page. Article page computes average community scores and displays them alongside self-ratings.

---

### Task 1: Review Model — 5 New Columns

**File:** `peerpedia_core/storage/db/models.py`

- [ ] Add after `points_earned` in Review model:
```python
    review_originality = Column(Integer, nullable=False, default=0)
    review_rigor = Column(Integer, nullable=False, default=0)
    review_completeness = Column(Integer, nullable=False, default=0)
    review_pedagogy = Column(Integer, nullable=False, default=0)
    review_impact = Column(Integer, nullable=False, default=0)
```

- [ ] Add to `Review.to_dict()`

- [ ] Run `pytest tests/test_db.py -v` — all pass

- [ ] Commit

### Task 2: CRUD + submit_review — Pass Through Dimensions

**Files:** `peerpedia_core/storage/db/crud_article.py`, `peerpedia_core/workflow/review.py`

- [ ] `create_review()` — add 5 keyword params (all int=0)
- [ ] `submit_review()` — accept 5 params, pass to `create_review()`
- [ ] Run `pytest tests/test_review_workflow.py -v` — all pass
- [ ] Commit

### Task 3: API — Accept Review Dimensions

**File:** `peerpedia/web/routes/api_articles.py`

- [ ] `api_submit_review` — add 5 Form params, pass to `submit_review()`
- [ ] Run `pytest tests/test_api_routes.py -v` — all pass  
- [ ] Commit

### Task 4: Review Form — Star Rating UI

**File:** `peerpedia/web/templates/review.html`

- [ ] Add 5-dimension star-rating fieldset (copy+adapt from submit.html) between existing sliders and comments textarea
- [ ] Add same `DOMContentLoaded` star-rating JS
- [ ] Verify server renders page correctly
- [ ] Commit

### Task 5: Article Page — Self vs Community Comparison

**File:** `peerpedia/web/templates/article.html`, `peerpedia/web/routes/pages.py`

- [ ] In `pages.py`, compute community average scores from reviews
- [ ] In `article.html`, show comparison table when reviews exist:

```
         自评  社区(N条审稿)
原创性    4     4.2
严格性    4     3.8
...
```

- [ ] When no reviews: keep existing "作者未自评" display
- [ ] Run `pytest tests/test_web_pages.py -v` — all pass
- [ ] Commit

### Task 6: Tests

**File:** `tests/test_community_review.py` (new)

- [ ] Submit review with 5 dimensions → verify stored
- [ ] Submit review without dimensions → defaults to 0
- [ ] API accepts review dimensions
- [ ] Article page shows comparison when reviews exist
- [ ] Article page shows "社区审稿后此处显示评分对比" when no reviews
- [ ] Commit
