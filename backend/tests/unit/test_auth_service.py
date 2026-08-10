import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.schemas.auth import RegisterRequest
from app.services.auth import _hash_token, login, refresh, register
from tests.conftest import make_result, make_refresh_token, make_user


class TestHashToken:
    def test_deterministic_same_input_same_output(self):
        assert _hash_token("some-raw-token") == _hash_token("some-raw-token")

    def test_different_inputs_different_outputs(self):
        assert _hash_token("token-a") != _hash_token("token-b")

    def test_matches_sha256_hexdigest_shape(self):
        result = _hash_token("some-raw-token")
        expected = hashlib.sha256("some-raw-token".encode()).hexdigest()
        assert result == expected
        assert len(result) == 64


class TestRegister:
    async def test_success_persists_user_with_hashed_password(self, fake_db):
        fake_db.execute.return_value = make_result(scalar=None)
        data = RegisterRequest(email="new@example.com", username="newuser", password="password123")

        user = await register(fake_db, data)

        assert fake_db.add.call_count == 1
        added_user = fake_db.add.call_args[0][0]
        assert added_user is user
        assert user.email == "new@example.com"
        assert user.username == "newuser"
        assert user.hashed_password != "password123"
        assert verify_password("password123", user.hashed_password)
        fake_db.commit.assert_awaited_once()
        fake_db.refresh.assert_awaited_once_with(user)

    async def test_duplicate_email_or_username_raises_409(self, fake_db):
        existing = make_user()
        fake_db.execute.return_value = make_result(scalar=existing)
        data = RegisterRequest(email="new@example.com", username="newuser", password="password123")

        with pytest.raises(HTTPException) as exc_info:
            await register(fake_db, data)
        assert exc_info.value.status_code == 409


class TestLogin:
    async def test_success_returns_token_response(self, fake_db):
        password = "correct-password"
        user = make_user(hashed_password=hash_password(password), is_active=True)
        fake_db.execute.return_value = make_result(scalar=user)

        token_response = await login(fake_db, user.email, password)

        assert token_response.access_token
        assert token_response.refresh_token

    async def test_nonexistent_email_raises_401(self, fake_db):
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await login(fake_db, "nobody@example.com", "whatever")
        assert exc_info.value.status_code == 401

    async def test_wrong_password_raises_401(self, fake_db):
        user = make_user(hashed_password=hash_password("correct-password"), is_active=True)
        fake_db.execute.return_value = make_result(scalar=user)

        with pytest.raises(HTTPException) as exc_info:
            await login(fake_db, user.email, "wrong-password")
        assert exc_info.value.status_code == 401

    async def test_nonexistent_email_and_wrong_password_have_identical_response(self, fake_db):
        # Nonexistent email case
        fake_db.execute.return_value = make_result(scalar=None)
        with pytest.raises(HTTPException) as exc_missing:
            await login(fake_db, "nobody@example.com", "whatever")

        # Wrong password case
        user = make_user(hashed_password=hash_password("correct-password"), is_active=True)
        fake_db.execute.return_value = make_result(scalar=user)
        with pytest.raises(HTTPException) as exc_wrong_password:
            await login(fake_db, user.email, "wrong-password")

        assert exc_missing.value.status_code == exc_wrong_password.value.status_code
        assert exc_missing.value.detail == exc_wrong_password.value.detail

    async def test_inactive_user_raises_403(self, fake_db):
        password = "correct-password"
        user = make_user(hashed_password=hash_password(password), is_active=False)
        fake_db.execute.return_value = make_result(scalar=user)

        with pytest.raises(HTTPException) as exc_info:
            await login(fake_db, user.email, password)
        assert exc_info.value.status_code == 403

    async def test_wrong_password_on_inactive_account_raises_401_not_403(self, fake_db):
        user = make_user(hashed_password=hash_password("correct-password"), is_active=False)
        fake_db.execute.return_value = make_result(scalar=user)

        with pytest.raises(HTTPException) as exc_info:
            await login(fake_db, user.email, "wrong-password")
        assert exc_info.value.status_code == 401


class TestRefresh:
    async def test_success_rotates_token(self, fake_db):
        user = make_user(is_active=True)
        raw_token = create_refresh_token(user.id)
        token_hash = _hash_token(raw_token)
        stored = make_refresh_token(
            user_id=user.id,
            token_hash=token_hash,
            revoked=False,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        fake_db.execute.side_effect = [
            make_result(scalar=stored),
            make_result(scalar=user),
        ]

        token_response = await refresh(fake_db, raw_token)

        assert stored.revoked is True
        assert token_response.access_token
        assert token_response.refresh_token
        assert token_response.refresh_token != raw_token

    async def test_malformed_token_raises_401(self, fake_db):
        with pytest.raises(HTTPException) as exc_info:
            await refresh(fake_db, "not-a-jwt")
        assert exc_info.value.status_code == 401

    async def test_access_token_type_raises_401(self, fake_db):
        user_id = uuid.uuid4()
        access_token = create_access_token(user_id)

        with pytest.raises(HTTPException) as exc_info:
            await refresh(fake_db, access_token)
        assert exc_info.value.status_code == 401

    async def test_hash_not_found_raises_401(self, fake_db):
        user_id = uuid.uuid4()
        raw_token = create_refresh_token(user_id)
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await refresh(fake_db, raw_token)
        assert exc_info.value.status_code == 401

    async def test_revoked_token_raises_401(self, fake_db):
        user_id = uuid.uuid4()
        raw_token = create_refresh_token(user_id)
        # revoked tokens are filtered out by the query itself (revoked == False),
        # so the DB double simulates "no row found" for a revoked token.
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await refresh(fake_db, raw_token)
        assert exc_info.value.status_code == 401

    async def test_expired_token_raises_401(self, fake_db):
        user_id = uuid.uuid4()
        raw_token = create_refresh_token(user_id)
        token_hash = _hash_token(raw_token)
        stored = make_refresh_token(
            user_id=user_id,
            token_hash=token_hash,
            revoked=False,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        fake_db.execute.return_value = make_result(scalar=stored)

        with pytest.raises(HTTPException) as exc_info:
            await refresh(fake_db, raw_token)
        assert exc_info.value.status_code == 401

    async def test_user_not_found_raises_401(self, fake_db):
        user_id = uuid.uuid4()
        raw_token = create_refresh_token(user_id)
        token_hash = _hash_token(raw_token)
        stored = make_refresh_token(
            user_id=user_id,
            token_hash=token_hash,
            revoked=False,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        fake_db.execute.side_effect = [
            make_result(scalar=stored),
            make_result(scalar=None),
        ]

        with pytest.raises(HTTPException) as exc_info:
            await refresh(fake_db, raw_token)
        assert exc_info.value.status_code == 401

    async def test_inactive_user_raises_401(self, fake_db):
        user = make_user(is_active=False)
        raw_token = create_refresh_token(user.id)
        token_hash = _hash_token(raw_token)
        stored = make_refresh_token(
            user_id=user.id,
            token_hash=token_hash,
            revoked=False,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        fake_db.execute.side_effect = [
            make_result(scalar=stored),
            make_result(scalar=user),
        ]

        with pytest.raises(HTTPException) as exc_info:
            await refresh(fake_db, raw_token)
        assert exc_info.value.status_code == 401
