"""Hardening of the reference endpoints (minor findings of the phase 1 QA):
int32 overflow, LIKE wildcards in ?search=, concurrent-insert races and negative CR."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api import reference as reference_api
from tests.integration.conftest import auth_headers, seed_user

INT32_MAX = 2_147_483_647


class TestInt32Overflow:
    @pytest.mark.parametrize("slug", ["character-levels", "point-buy-costs"])
    async def test_public_get_with_huge_numeric_key_is_422(self, api_client, slug):
        response = await api_client.get(f"/api/compendium/{slug}/{2**40}")
        assert response.status_code == 422

    async def test_public_get_with_max_int32_key_is_404(self, api_client):
        response = await api_client.get(f"/api/compendium/character-levels/{INT32_MAX}")
        assert response.status_code == 404

    async def test_post_with_huge_level_is_422(self, api_client, db_session):
        user = await seed_user(db_session)
        await db_session.commit()
        response = await api_client.post(
            "/api/compendium/character-levels",
            json={"level": 2**40, "min_xp": 0, "proficiency_bonus": 2},
            headers=auth_headers(user),
        )
        assert response.status_code == 422


class TestSearchWildcards:
    @pytest.mark.parametrize("term", ["_", "%", "\\"])
    async def test_like_wildcards_are_literal(self, api_client, term):
        response = await api_client.get("/api/compendium/damage-types", params={"search": term})
        assert response.status_code == 200
        assert response.json() == []

    async def test_underscore_matches_literally(self, api_client, db_session):
        user = await seed_user(db_session)
        await db_session.commit()
        headers = auth_headers(user)
        created = await api_client.post(
            "/api/compendium/damage-types",
            json={"code": "under_score", "name": "Under_Score"},
            headers=headers,
        )
        assert created.status_code == 201
        response = await api_client.get(
            "/api/compendium/damage-types", params={"search": "r_s"}, headers=headers
        )
        assert [row["code"] for row in response.json()] == ["under_score"]

    async def test_plain_search_still_case_insensitive(self, api_client):
        response = await api_client.get("/api/compendium/damage-types", params={"search": "FIR"})
        assert [row["code"] for row in response.json()] == ["fire"]


class TestConcurrentInsertRace:
    """The pre-insert uniqueness checks can lose a race; the commit then raises
    IntegrityError, which must surface as 409 (not 500) and leave nothing behind."""

    async def test_post_race_on_primary_key_is_409(self, api_client, db_session, monkeypatch):
        user = await seed_user(db_session)
        await db_session.commit()

        async def _never_exists(*args, **kwargs):
            return False

        monkeypatch.setattr(reference_api, "_key_exists", _never_exists)
        response = await api_client.post(
            "/api/compendium/damage-types",
            json={"code": "fire", "name": "Second Fire"},
            headers=auth_headers(user),
        )
        assert response.status_code == 409
        count = await db_session.scalar(text("SELECT count(*) FROM damage_types WHERE code = 'fire'"))
        assert count == 1

    async def test_patch_race_on_unique_column_is_409(self, api_client, db_session, monkeypatch):
        user = await seed_user(db_session)
        await db_session.commit()
        headers = auth_headers(user)
        created = await api_client.post(
            "/api/compendium/sizes",
            json={"code": "titanic", "name": "Titanic", "hit_die": 20, "carry_multiplier": 240, "sort_order": 7},
            headers=headers,
        )
        assert created.status_code == 201

        async def _no_unique_check(*args, **kwargs):
            return None

        monkeypatch.setattr(reference_api, "_check_unique_columns", _no_unique_check)
        response = await api_client.patch(
            "/api/compendium/sizes/titanic", json={"sort_order": 6}, headers=headers
        )
        assert response.status_code == 409
        sort_order = await db_session.scalar(text("SELECT sort_order FROM sizes WHERE code = 'titanic'"))
        assert sort_order == 7


class TestNegativeChallengeRating:
    async def test_post_negative_numeric_value_is_422(self, api_client, db_session):
        user = await seed_user(db_session)
        await db_session.commit()
        response = await api_client.post(
            "/api/compendium/challenge-ratings",
            json={"code": "minus_1", "name": "-1", "numeric_value": -1, "proficiency_bonus": 2},
            headers=auth_headers(user),
        )
        assert response.status_code == 422

    async def test_db_check_rejects_negative_numeric_value(self, db_session):
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await db_session.execute(text(
                    "INSERT INTO challenge_ratings (code, name, numeric_value, proficiency_bonus, source, is_homebrew) "
                    "VALUES ('minus_1', '-1', -1, 2, 'homebrew', true)"
                ))
