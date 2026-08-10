import uuid

import pytest
from fastapi import HTTPException

from app.core.deps import get_current_user, require_campaign_dm, require_campaign_member
from app.core.security import create_access_token, create_refresh_token
from tests.conftest import make_campaign, make_campaign_member, make_result, make_user


class TestGetCurrentUser:
    async def test_malformed_token_raises_401(self, fake_db):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="not-a-jwt", db=fake_db)
        assert exc_info.value.status_code == 401

    async def test_refresh_token_type_raises_401(self, fake_db):
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=fake_db)
        assert exc_info.value.status_code == 401

    async def test_missing_sub_raises_401(self, fake_db, monkeypatch):
        monkeypatch.setattr(
            "app.core.deps.decode_token", lambda token: {"type": "access"}
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="whatever", db=fake_db)
        assert exc_info.value.status_code == 401

    async def test_sub_not_a_valid_uuid_raises_401(self, fake_db, monkeypatch):
        monkeypatch.setattr(
            "app.core.deps.decode_token",
            lambda token: {"type": "access", "sub": "not-a-uuid"},
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="whatever", db=fake_db)
        assert exc_info.value.status_code == 401

    async def test_user_not_found_raises_401(self, fake_db):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=fake_db)
        assert exc_info.value.status_code == 401

    async def test_inactive_user_raises_401(self, fake_db):
        user = make_user(is_active=False)
        token = create_access_token(user.id)
        fake_db.execute.return_value = make_result(scalar=user)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=fake_db)
        assert exc_info.value.status_code == 401

    async def test_happy_path_returns_user(self, fake_db):
        user = make_user(is_active=True)
        token = create_access_token(user.id)
        fake_db.execute.return_value = make_result(scalar=user)

        result = await get_current_user(token=token, db=fake_db)
        assert result is user


class TestRequireCampaignDM:
    async def test_campaign_not_found_raises_404(self, fake_db):
        current_user = make_user()
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await require_campaign_dm(
                campaign_id=uuid.uuid4(), current_user=current_user, db=fake_db
            )
        assert exc_info.value.status_code == 404

    async def test_not_a_dm_no_membership_raises_403(self, fake_db):
        current_user = make_user()
        campaign = make_campaign()
        fake_db.execute.side_effect = [
            make_result(scalar=campaign),
            make_result(scalar=None),
        ]

        with pytest.raises(HTTPException) as exc_info:
            await require_campaign_dm(
                campaign_id=campaign.id, current_user=current_user, db=fake_db
            )
        assert exc_info.value.status_code == 403

    async def test_membership_with_different_role_raises_403(self, fake_db):
        current_user = make_user()
        campaign = make_campaign()
        # Query filters by role == "dm"; a player membership would not match,
        # simulated here as "no row found" for that filtered query.
        fake_db.execute.side_effect = [
            make_result(scalar=campaign),
            make_result(scalar=None),
        ]

        with pytest.raises(HTTPException) as exc_info:
            await require_campaign_dm(
                campaign_id=campaign.id, current_user=current_user, db=fake_db
            )
        assert exc_info.value.status_code == 403

    async def test_happy_path_returns_campaign(self, fake_db):
        current_user = make_user()
        campaign = make_campaign()
        membership = make_campaign_member(
            campaign_id=campaign.id, user_id=current_user.id, role="dm"
        )
        fake_db.execute.side_effect = [
            make_result(scalar=campaign),
            make_result(scalar=membership),
        ]

        result = await require_campaign_dm(
            campaign_id=campaign.id, current_user=current_user, db=fake_db
        )
        assert result is campaign


class TestRequireCampaignMember:
    async def test_no_membership_raises_403(self, fake_db):
        current_user = make_user()
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await require_campaign_member(
                campaign_id=uuid.uuid4(), current_user=current_user, db=fake_db
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.parametrize("role", ["player", "dm"])
    async def test_happy_path_returns_member_for_any_role(self, fake_db, role):
        current_user = make_user()
        campaign_id = uuid.uuid4()
        membership = make_campaign_member(
            campaign_id=campaign_id, user_id=current_user.id, role=role
        )
        fake_db.execute.return_value = make_result(scalar=membership)

        result = await require_campaign_member(
            campaign_id=campaign_id, current_user=current_user, db=fake_db
        )
        assert result is membership
