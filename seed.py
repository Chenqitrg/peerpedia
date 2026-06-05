#!/usr/bin/env python3
"""Seed the PeerPedia database with demo data for development and testing.

Usage:
    python3 seed.py [--db sqlite:///peerpedia.db] [--articles-dir ~/.peerpedia/articles]

Creates demo users, articles in various states, reviews, follows, bookmarks,
and git repos. Safe to run multiple times — it reuses existing data where
possible.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Add project paths ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "core"))
sys.path.insert(0, str(Path(__file__).parent / "backend"))


def seed(db_url: str, articles_dir: Path):
    """Main seed routine."""
    from peerpedia_core.storage.db.engine import get_engine, init_db
    from peerpedia_core.storage.db.models import (
        Article, User, Follow, Bookmark, Review,
    )
    from peerpedia_core.storage.db.crud_article import (
        create_article, set_sink_start, update_article_status,
    )
    from peerpedia_core.storage.db.crud_review import create_review, upsert_review
    from peerpedia_core.storage.db.crud_user import (
        create_user, list_users,
    )
    from peerpedia_core.storage.git_backend import (
        init_article_repo, commit_article,
    )

    engine = get_engine(db_url)
    init_db(engine)
    from peerpedia_core.storage.db.engine import get_session

    session = get_session(engine)

    print(f"Seeding database: {db_url}")
    print(f"Articles directory: {articles_dir}")

    # ── 1. Users ─────────────────────────────────────────────────────────────
    from peerpedia_api.deps import hash_password

    DEFAULT_PASSWORD = "666666"
    user_defs = [
        {"name": "Albert Einstein", "username": "einstein",
         "anonymous_name": "Physicist42",
         "affiliation": "Princeton", "expertise": ["physics", "relativity"]},
        {"name": "Marie Curie", "username": "curie",
         "anonymous_name": "RadiantOne",
         "affiliation": "Sorbonne", "expertise": ["chemistry", "radioactivity"]},
        {"name": "Alan Turing", "username": "turing",
         "anonymous_name": "CodeBreaker",
         "affiliation": "Manchester", "expertise": ["computer science", "cryptography"]},
        {"name": "Ada Lovelace", "username": "lovelace",
         "anonymous_name": "FirstProgrammer",
         "affiliation": "London", "expertise": ["mathematics", "computing"]},
        {"name": "Richard Feynman", "username": "feynman",
         "anonymous_name": "BongoPlayer",
         "affiliation": "Caltech", "expertise": ["physics", "quantum mechanics"]},
        {"name": "Emmy Noether", "username": "noether",
         "anonymous_name": "SymmetrySeeker",
         "affiliation": "Bryn Mawr", "expertise": ["mathematics", "abstract algebra"]},
        {"name": "Claude Shannon", "username": "shannon",
         "anonymous_name": "BitMaster",
         "affiliation": "MIT", "expertise": ["information theory", "electrical engineering"]},
        {"name": "Rosalind Franklin", "username": "franklin",
         "anonymous_name": "DoubleHelix",
         "affiliation": "King's College", "expertise": ["biology", "crystallography"]},
    ]

    pwd_hash = hash_password(DEFAULT_PASSWORD)
    users = {}
    for u in user_defs:
        existing = session.query(User).filter(User.username == u["username"]).first()
        if existing:
            users[u["name"]] = existing
            print(f"  User (existing): {u['name']} ({u['username']})")
        else:
            user = User(
                username=u["username"],
                password_hash=pwd_hash,
                email=f"{u['username']}@peerpedia.dev",
                name=u["name"],
                anonymous_name=u["anonymous_name"],
                affiliation=u["affiliation"],
                expertise=u["expertise"],
                reputation={"professionalism": 4.0, "objectivity": 4.0,
                            "collaboration": 4.0, "pedagogy": 4.0},
            )
            session.add(user)
            session.commit()
            users[u["name"]] = user
            print(f"  User (new): {u['name']} ({u['username']})")

    print(f"\n  Default password for all users: {DEFAULT_PASSWORD}")

    # ── 2. Follow relationships ──────────────────────────────────────────────
    follow_pairs = [
        ("Alan Turing", "Ada Lovelace"),
        ("Alan Turing", "Claude Shannon"),
        ("Ada Lovelace", "Alan Turing"),
        ("Albert Einstein", "Richard Feynman"),
        ("Richard Feynman", "Albert Einstein"),
        ("Marie Curie", "Rosalind Franklin"),
        ("Emmy Noether", "Albert Einstein"),
        ("Claude Shannon", "Alan Turing"),
        ("Rosalind Franklin", "Marie Curie"),
        ("Marie Curie", "Emmy Noether"),
    ]

    follow_count = 0
    for follower_name, followed_name in follow_pairs:
        f = session.query(Follow).filter(
            Follow.follower_id == users[follower_name].id,
            Follow.followed_id == users[followed_name].id,
        ).first()
        if not f:
            session.add(Follow(
                follower_id=users[follower_name].id,
                followed_id=users[followed_name].id,
            ))
            follow_count += 1
    session.commit()
    print(f"  Follows: {follow_count} new")

    # ── 3. Articles ──────────────────────────────────────────────────────────
    article_defs = [
        {
            "title": "On the Electrodynamics of Moving Bodies",
            "author": "Albert Einstein",
            "format": "markdown",
            "content": """# On the Electrodynamics of Moving Bodies

## Abstract

It is known that Maxwell's electrodynamics—as usually understood at the
present time—when applied to moving bodies, leads to asymmetries which do
not appear to be inherent in the phenomena.

## 1. Introduction

Take, for example, the reciprocal electrodynamic action of a magnet and a
conductor. The observable phenomenon here depends only on the relative
motion of the conductor and the magnet.

## 2. Kinematical Part

### §1. Definition of Simultaneity

Let us take a system of coordinates in which the equations of Newtonian
mechanics hold good. In order to render our presentation more precise and
to distinguish this system of coordinates verbally from others which will
be introduced hereafter, we call it the *stationary system*.

The theory to be developed is based—like all electrodynamics—on the
kinematics of the rigid body, since the assertions of any such theory
have to do with the relationships between rigid bodies (systems of
coordinates), clocks, and electromagnetic processes.

$$
E = mc^2
$$

This is the famous mass-energy equivalence formula that follows from
the special theory of relativity.
""",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 4.5, "completeness": 4.0,
                      "pedagogy": 3.5, "impact": 5.0},
        },
        {
            "title": "On Computable Numbers, with an Application to the Entscheidungsproblem",
            "author": "Alan Turing",
            "format": "markdown",
            "content": """# On Computable Numbers

## Abstract

The "computable" numbers may be described briefly as the real numbers
whose expressions as a decimal are calculable by finite means.

## 1. Computing Machines

We may compare a man in the process of computing a real number to a
machine which is only capable of a finite number of conditions.

The machine is supplied with a "tape" (the analogue of paper) running
through it, and divided into sections (called "squares") each capable
of bearing a "symbol".

$$
\\lambda = \\sum_{n=1}^{\\infty} \\frac{1}{2^n}
$$

This formulation captures the essence of the halting problem and
demonstrates that there exist well-defined problems that cannot be
solved by any mechanical procedure.
""",
            "status": "sedimentation",
            "sink_days": 5,
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5,
                      "pedagogy": 3.0, "impact": 5.0},
        },
        {
            "title": "The Space Distribution of the Photo-Electric Effect",
            "author": "Marie Curie",
            "format": "markdown",
            "content": """# The Space Distribution of the Photo-Electric Effect

## Introduction

The study of radioactive substances has revealed remarkable properties
concerning the emission of electrons under the influence of
electromagnetic radiation.

## Experimental Setup

The apparatus consisted of a vacuum chamber with two parallel plates
connected to a sensitive electrometer. The radioactive source was placed
at varying distances from the detecting plate.

$$
I = I_0 e^{-\\alpha x}
$$

Where $I$ is the measured intensity and $x$ is the distance from the source.

## Results

Our measurements show a clear exponential relationship, consistent with
the quantum theory of radiation. The absorption coefficient $\\alpha$
was found to be proportional to the atomic number of the absorbing material.
""",
            "status": "published",
            "score": {"originality": 4.5, "rigor": 5.0, "completeness": 4.5,
                      "pedagogy": 4.0, "impact": 4.5},
        },
        {
            "title": "Notes on Quantum Electrodynamics",
            "author": "Richard Feynman",
            "format": "markdown",
            "content": """# Notes on Quantum Electrodynamics

## Abstract

A new formulation of quantum electrodynamics using path integrals and
diagrams representing particle interactions.

## 1. The Path Integral Formulation

The probability amplitude for a particle to go from point A to point B
is given by the sum over all possible paths:

$$
K(b, a) = \\int \\mathcal{D}x(t)\\, e^{iS[x]/\\hbar}
$$

Where $S[x]$ is the classical action along the path $x(t)$.

## 2. Feynman Diagrams

Each diagram represents a term in the perturbation expansion. The rules
are:

1. Draw all connected diagrams with the required external lines
2. For each vertex, include a factor of $e\\gamma^\\mu$
3. For each internal line, include a propagator $\\frac{i}{\\not{p} - m}$

$$
\\mathcal{M} = \\bar{u}(p')\\gamma^\\mu u(p) \\cdot \\frac{-ig_{\\mu\\nu}}{q^2} \\cdot \\bar{u}(k')\\gamma^\\nu u(k)
$$
""",
            "status": "sedimentation",
            "sink_days": 3,
            "score": {"originality": 5.0, "rigor": 4.0, "completeness": 3.5,
                      "pedagogy": 5.0, "impact": 5.0},
        },
        {
            "title": "A Mathematical Theory of Communication",
            "author": "Claude Shannon",
            "format": "markdown",
            "content": """# A Mathematical Theory of Communication

## Abstract

The fundamental problem of communication is that of reproducing at one
point either exactly or approximately a message selected at another point.

## 1. Information Entropy

The quantity $H$ which we define as the measure of information produced
by a discrete information source is:

$$
H = -K \\sum_{i=1}^{n} p_i \\log p_i
$$

Where $p_i$ are the probabilities of the $n$ possible outcomes.

## 2. Channel Capacity

The capacity $C$ of a noisy channel is given by:

$$
C = \\max_{P(x)} I(X; Y)
$$

Where $I(X; Y)$ is the mutual information between input $X$ and output $Y$.
This fundamental result sets the theoretical maximum rate of reliable
communication over any channel.
""",
            "status": "draft",
            "score": None,
        },
        {
            "title": "The Structure of DNA: A Molecular Model",
            "author": "Rosalind Franklin",
            "format": "markdown",
            "content": """# The Structure of DNA

## Abstract

X-ray crystallography studies reveal the double-helical structure of
deoxyribonucleic acid (DNA). The sugar-phosphate backbone forms the
exterior with base pairs stacked in the interior.

## 1. X-Ray Diffraction Patterns

The characteristic X-shaped pattern in the diffraction image strongly
suggests a helical structure with a pitch of approximately 34 Å.

## 2. Base Pairing

The regular spacing of 3.4 Å between successive base pairs and the
requirement of Chargaff's rules lead to the conclusion that adenine
pairs with thymine, and guanine pairs with cytosine.

$$
\\text{A—T, G—C}
$$

These specific base pairings ensure the fidelity of genetic information
transfer during DNA replication.
""",
            "status": "sedimentation",
            "sink_days": 7,
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.0,
                      "pedagogy": 4.5, "impact": 5.0},
        },
    ]

    articles_created = 0
    for ad in article_defs:
        author = users[ad["author"]]
        # Check if article already exists with this title (by author)
        existing = session.query(Article).filter(
            Article.authors.contains([author.id])
        ).first()
        if existing:
            print(f"  Article (existing): {ad['title'][:50]}...")
            continue

        # Create article
        a = create_article(session, authors=[author.id], status="draft")

        # Initialize git repo
        try:
            rp = init_article_repo(a.id, base_dir=articles_dir)
            ext = ".typ" if ad["format"] == "typst" else ".md"
            (rp / f"article{ext}").write_text(ad["content"])
            commit_article(rp, "Initial submission", author.name,
                          f"{author.name.lower().replace(' ', '.')}@peerpedia",
                          allow_empty=True)
        except Exception as e:
            print(f"  Warning: git repo for {ad['title'][:40]} failed: {e}")

        # Set status and sink
        status = ad["status"]
        if status == "sedimentation":
            sink_days = ad.get("sink_days", 7)
            # Backdate sink_start so it reflects the remaining days
            elapsed = 7 - sink_days
            if elapsed > 0:
                st = datetime.now(timezone.utc) - timedelta(days=elapsed)
                a.status = "sedimentation"
                a.sink_start = st
                a.sink_duration_days = sink_days + elapsed
                session.commit()
            else:
                a = set_sink_start(session, a.id, sink_days)
        elif status == "published":
            a = update_article_status(session, a.id, "published")

        # Set score
        if ad["score"]:
            a.score = ad["score"]
            session.commit()

        # Create self-review
        if ad["score"]:
            scope = "pool" if status == "sedimentation" else "published"
            try:
                upsert_review(
                    session,
                    article_id=a.id,
                    commit_hash="0000000000000000000000000000000000000000",
                    reviewer_id=author.id,
                    scope=scope,
                    scores=ad["score"],
                )
            except Exception:
                pass  # Review upsert may fail without a real commit hash

        articles_created += 1
        print(f"  Article (new): {ad['title'][:50]}... [{status}]")

    # Add some community reviews
    review_pairs = [
        ("Albert Einstein", "Richard Feynman", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Richard Feynman", "Albert Einstein", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 3, "impact": 5}),
        ("Alan Turing", "Claude Shannon", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Marie Curie", "Rosalind Franklin", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Emmy Noether", "Albert Einstein", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 3, "impact": 5}),
        ("Ada Lovelace", "Alan Turing", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
    ]

    review_count = 0
    for reviewer_name, author_name, scores in review_pairs:
        reviewer = users[reviewer_name]
        author = users[author_name]
        # Find author's articles
        articles = session.query(Article).filter(
            Article.authors.contains([author.id])
        ).all()
        if not articles:
            continue
        a = articles[0]
        scope = "pool" if a.status == "sedimentation" else "published"
        existing = session.query(Review).filter(
            Review.article_id == a.id,
            Review.reviewer_id == reviewer.id,
            Review.scope == scope,
        ).first()
        if not existing:
            try:
                upsert_review(session, article_id=a.id,
                            commit_hash="0000000000000000000000000000000000000000",
                            reviewer_id=reviewer.id, scope=scope, scores=scores)
                review_count += 1
            except Exception:
                pass

    session.commit()
    print(f"  Reviews: {review_count} new")

    # ── 4. Bookmarks ─────────────────────────────────────────────────────────
    bookmark_pairs = [
        ("Alan Turing", "Albert Einstein"),
        ("Ada Lovelace", "Alan Turing"),
        ("Richard Feynman", "Marie Curie"),
        ("Claude Shannon", "Alan Turing"),
    ]

    bm_count = 0
    for user_name, author_name in bookmark_pairs:
        user = users[user_name]
        author = users[author_name]
        articles = session.query(Article).filter(
            Article.authors.contains([author.id])
        ).all()
        if not articles:
            continue
        a = articles[0]
        existing = session.query(Bookmark).filter(
            Bookmark.user_id == user.id,
            Bookmark.article_id == a.id,
        ).first()
        if not existing:
            session.add(Bookmark(user_id=user.id, article_id=a.id))
            bm_count += 1
    session.commit()
    print(f"  Bookmarks: {bm_count} new")

    session.close()
    engine.dispose()
    print("\n✅ Seed complete! Run the backend and frontend to explore.")


def main():
    parser = argparse.ArgumentParser(description="Seed PeerPedia database")
    parser.add_argument("--db", default="sqlite:///peerpedia.db",
                        help="Database URL (default: sqlite:///peerpedia.db)")
    parser.add_argument("--articles-dir", default=None,
                        help="Articles directory (default: ~/.peerpedia/articles)")
    args = parser.parse_args()

    articles_dir = Path(args.articles_dir).expanduser() if args.articles_dir \
        else Path.home() / ".peerpedia" / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    seed(args.db, articles_dir)


if __name__ == "__main__":
    main()
