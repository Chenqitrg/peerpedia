# peerpedia_core/workflow/review_dimensions.py
"""Shared review dimension definitions.

Used by community review aggregation, sedimentation pool calculation,
and review submission — ensures the 5-dimension model has a single source of truth.
"""

REVIEW_DIMENSIONS = ["originality", "rigor", "completeness", "pedagogy", "impact"]
"""Ordered list of the 5 peer-review quality dimensions."""

REVIEW_DIM_COLUMN_PREFIX = "review_"
"""ORM column prefix for dimension fields on the Review model (e.g., review_originality)."""
