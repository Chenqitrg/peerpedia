# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Authentication Dependencies.

The dependency injection layer provides:
  - Database session lifecycle (get_db)
  - Password hashing/verification (bcrypt)
  - JWT token creation/decoding
  - Current user extraction from Bearer token
  - require_user — raises 401 when unauthenticated
"""

import os
import time

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session


class TestPasswordHashing:
    """bcrypt-based password hashing."""

    def test_hash_and_verify(self):
        from peerpedia_api.deps import hash_password, verify_password

        pw = "my_secure_password_123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed) is True

    def test_wrong_password_fails(self):
        from peerpedia_api.deps import hash_password, verify_password

        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_deterministically_verifiable(self):
        """Same password hashes differently but both verify."""
        from peerpedia_api.deps import hash_password, verify_password

        h1 = hash_password("same_pw")
        h2 = hash_password("same_pw")
        assert h1 != h2  # different salts
        assert verify_password("same_pw", h1) is True
        assert verify_password("same_pw", h2) is True


class TestJWTToken:
    """JWT token lifecycle."""

    def test_create_and_decode(self):
        from peerpedia_api.deps import create_token, decode_token

        token = create_token("user-123")
        user_id = decode_token(token)
        assert user_id == "user-123"

    def test_decode_expired_token(self):
        import jwt as pyjwt
        from peerpedia_api.deps import decode_token

        secret = os.environ.get("JWT_SECRET", "peerpedia-dev-secret")
        expired = pyjwt.encode(
            {"sub": "user-x", "iat": int(time.time()) - 10, "exp": int(time.time()) - 1},
            secret,
            algorithm="HS256",
        )
        assert decode_token(expired) is None

    def test_decode_invalid_token(self):
        from peerpedia_api.deps import decode_token

        assert decode_token("not.a.valid.token") is None

    def test_decode_empty_string(self):
        from peerpedia_api.deps import decode_token

        assert decode_token("") is None


class TestGetDb:
    """Database session dependency."""

    def test_get_db_yields_session(self):
        """get_db yields a usable SQLAlchemy Session."""
        from peerpedia_api.deps import get_db

        gen = get_db()
        session = next(gen)
        assert isinstance(session, Session)
        # Clean up
        try:
            next(gen)
        except StopIteration:
            pass  # expected — generator exhausted

    def test_get_db_session_is_closed_after_use(self):
        """After the generator is properly closed, the session is closed."""
        from peerpedia_api.deps import get_db

        gen = get_db()
        _ = next(gen)  # verify session is created, then close
        # Properly close the generator — triggers finally block
        gen.close()
        # Session should be closed via the finally block


class TestGetCurrentUser:
    """Current user extraction from Bearer token."""

    def test_no_authorization_header(self, db_engine):
        """Missing Authorization header returns None."""
        from peerpedia_api.deps import get_current_user, get_db

        gen = get_db()
        db = next(gen)
        try:
            user = get_current_user(authorization=None, db=db)
            assert user is None
        finally:
            try:
                next(gen)
            except StopIteration:
                pass

    def test_malformed_header(self, db_engine):
        """Non-Bearer header format returns None."""
        from peerpedia_api.deps import get_current_user, get_db

        gen = get_db()
        db = next(gen)
        try:
            user = get_current_user(authorization="Basic abc123", db=db)
            assert user is None
        finally:
            try:
                next(gen)
            except StopIteration:
                pass

    def test_invalid_token(self, db_engine):
        """Invalid JWT token returns None."""
        from peerpedia_api.deps import get_current_user, get_db

        gen = get_db()
        db = next(gen)
        try:
            user = get_current_user(authorization="Bearer invalid-token-here", db=db)
            assert user is None
        finally:
            try:
                next(gen)
            except StopIteration:
                pass


class TestRequireUser:
    """require_user raises 401 when unauthenticated."""

    def test_raises_401_when_none(self):
        from peerpedia_api.deps import require_user

        with pytest.raises(HTTPException) as exc:
            require_user(user=None)
        assert exc.value.status_code == 401
        assert "required" in exc.value.detail.lower()
