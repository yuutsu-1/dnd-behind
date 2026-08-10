import uuid
from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestHashPassword:
    def test_hash_is_not_the_plain_password(self):
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"

    def test_hash_is_not_deterministic_between_calls(self):
        first = hash_password("same-password")
        second = hash_password("same-password")
        assert first != second


class TestVerifyPassword:
    def test_verify_password_correct(self):
        hashed = hash_password("my-secret-password")
        assert verify_password("my-secret-password", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("my-secret-password")
        assert verify_password("wrong-password", hashed) is False


class TestCreateAccessToken:
    def test_claims(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "jti" in payload

    def test_jti_is_unique_between_calls(self):
        user_id = uuid.uuid4()
        token_a = create_access_token(user_id)
        token_b = create_access_token(user_id)

        payload_a = jwt.decode(token_a, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        payload_b = jwt.decode(token_b, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        assert payload_a["jti"] != payload_b["jti"]


class TestCreateRefreshToken:
    def test_claims(self):
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "jti" in payload

    def test_access_and_refresh_types_differ(self):
        user_id = uuid.uuid4()
        access = jwt.decode(
            create_access_token(user_id), settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        refresh = jwt.decode(
            create_refresh_token(user_id), settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert access["type"] != refresh["type"]


class TestDecodeToken:
    def test_valid_token_returns_payload(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_malformed_token_returns_none(self):
        assert decode_token("not-a-jwt-token") is None

    def test_token_signed_with_other_key_returns_none(self):
        token = jwt.encode(
            {"sub": "someone", "type": "access"},
            "a-completely-different-secret-key",
            algorithm=settings.JWT_ALGORITHM,
        )
        assert decode_token(token) is None

    def test_expired_token_returns_none(self):
        from datetime import datetime, timezone

        token = jwt.encode(
            {
                "sub": "someone",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        assert decode_token(token) is None
