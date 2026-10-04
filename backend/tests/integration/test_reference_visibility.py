"""Visibility and campaign sharing of homebrew reference rows (app/services/reference.py)."""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.db.models.campaign import Campaign, CampaignMember
from app.db.models.reference import CampaignHomebrewRule, CharacterLevel, DamageType, Skill
from app.services import reference as ref_service
from tests.integration.conftest import (
    seed_campaign,
    seed_campaign_member,
    seed_reference,
    seed_user,
)


async def _visible_codes(db, model, user) -> set[str]:
    rows = await db.execute(select(model.code).where(ref_service.visible_filter(model, user)))
    return set(rows.scalars())


async def _share_count(db, table: str, key: str) -> int:
    return (await db.execute(
        select(func.count()).select_from(CampaignHomebrewRule).where(
            CampaignHomebrewRule.resource_table == table,
            CampaignHomebrewRule.resource_key == key,
        )
    )).scalar_one()


@pytest.fixture
async def scenario(db_session):
    """A (author, DM of C), P (player of C), B (outsider) and campaign C."""
    a = await seed_user(db_session)
    p = await seed_user(db_session)
    b = await seed_user(db_session)
    c = await seed_campaign(db_session, creator=a)
    await seed_campaign_member(db_session, c, a, role="dm")
    p_member = await seed_campaign_member(db_session, c, p, role="player")
    return dict(a=a, p=p, b=b, c=c, p_member=p_member)


class TestVisibleFilter:
    async def test_anonymous_sees_only_srd(self, db_session, scenario):
        hb = await seed_reference(db_session, DamageType, author=scenario["a"], code="psionic")
        codes = await _visible_codes(db_session, DamageType, None)
        assert "fire" in codes
        assert hb.code not in codes

    async def test_unshared_homebrew_visible_only_to_author(self, db_session, scenario):
        await seed_reference(db_session, DamageType, author=scenario["a"], code="psionic")
        assert "psionic" in await _visible_codes(db_session, DamageType, scenario["a"])
        assert "psionic" not in await _visible_codes(db_session, DamageType, scenario["b"])
        assert "psionic" not in await _visible_codes(db_session, DamageType, scenario["p"])
        assert "fire" in await _visible_codes(db_session, DamageType, scenario["b"])

    async def test_shared_homebrew_visible_to_campaign_members_until_they_leave(self, db_session, scenario):
        await seed_reference(
            db_session, DamageType, author=scenario["a"], code="psionic", campaigns=[scenario["c"]]
        )
        assert "psionic" in await _visible_codes(db_session, DamageType, scenario["p"])
        assert "psionic" not in await _visible_codes(db_session, DamageType, scenario["b"])

        await db_session.delete(scenario["p_member"])
        await db_session.flush()
        assert "psionic" not in await _visible_codes(db_session, DamageType, scenario["p"])

    async def test_numeric_key_tables_are_shared_by_stringified_key(self, db_session, scenario):
        await seed_reference(
            db_session, CharacterLevel, author=scenario["a"], level=21, min_xp=400000,
            proficiency_bonus=7, campaigns=[scenario["c"]],
        )
        rows = await db_session.execute(
            select(CharacterLevel.level).where(ref_service.visible_filter(CharacterLevel, scenario["p"]))
        )
        assert 21 in set(rows.scalars())
        rows = await db_session.execute(
            select(CharacterLevel.level).where(ref_service.visible_filter(CharacterLevel, scenario["b"]))
        )
        assert 21 not in set(rows.scalars())

    async def test_deleting_campaign_cascades_shares(self, db_session, scenario):
        await seed_reference(
            db_session, DamageType, author=scenario["a"], code="psionic", campaigns=[scenario["c"]]
        )
        assert await _share_count(db_session, "damage_types", "psionic") == 1
        await db_session.execute(delete(Campaign).where(Campaign.id == scenario["c"].id))
        assert await _share_count(db_session, "damage_types", "psionic") == 0


class TestValidateCampaignIds:
    async def test_dm_campaign_is_accepted(self, db_session, scenario):
        await ref_service.validate_campaign_ids(db_session, scenario["a"], [scenario["c"].id])

    async def test_empty_list_is_accepted(self, db_session, scenario):
        await ref_service.validate_campaign_ids(db_session, scenario["a"], [])

    async def test_unknown_campaign_is_400(self, db_session, scenario):
        with pytest.raises(HTTPException) as exc:
            await ref_service.validate_campaign_ids(db_session, scenario["a"], [uuid.uuid4()])
        assert exc.value.status_code == 400

    async def test_player_campaign_is_403(self, db_session, scenario):
        with pytest.raises(HTTPException) as exc:
            await ref_service.validate_campaign_ids(db_session, scenario["p"], [scenario["c"].id])
        assert exc.value.status_code == 403

    async def test_non_member_campaign_is_403(self, db_session, scenario):
        with pytest.raises(HTTPException) as exc:
            await ref_service.validate_campaign_ids(db_session, scenario["b"], [scenario["c"].id])
        assert exc.value.status_code == 403


class TestShares:
    async def test_replace_shares_replaces_whole_set(self, db_session, scenario):
        other = await seed_campaign(db_session, creator=scenario["a"])
        entry = await seed_reference(
            db_session, DamageType, author=scenario["a"], code="psionic", campaigns=[scenario["c"]]
        )
        await ref_service.replace_shares(db_session, DamageType, entry.code, [other.id])
        await db_session.flush()
        assert await ref_service.campaign_ids_for(db_session, DamageType, entry, scenario["a"]) == [other.id]

        await ref_service.replace_shares(db_session, DamageType, entry.code, [])
        await db_session.flush()
        assert await ref_service.campaign_ids_for(db_session, DamageType, entry, scenario["a"]) == []

    async def test_delete_shares_removes_all_shares_of_the_entry(self, db_session, scenario):
        await seed_reference(
            db_session, DamageType, author=scenario["a"], code="psionic", campaigns=[scenario["c"]]
        )
        await ref_service.delete_shares(db_session, DamageType, "psionic")
        await db_session.flush()
        assert await _share_count(db_session, "damage_types", "psionic") == 0

    async def test_campaign_ids_only_for_author(self, db_session, scenario):
        entry = await seed_reference(
            db_session, DamageType, author=scenario["a"], code="psionic", campaigns=[scenario["c"]]
        )
        assert await ref_service.campaign_ids_for(db_session, DamageType, entry, scenario["a"]) == [scenario["c"].id]
        assert await ref_service.campaign_ids_for(db_session, DamageType, entry, scenario["p"]) is None
        assert await ref_service.campaign_ids_for(db_session, DamageType, entry, None) is None
        srd = await db_session.get(DamageType, "fire")
        assert await ref_service.campaign_ids_for(db_session, DamageType, srd, scenario["a"]) is None


class TestResolveCodes:
    async def test_returns_visible_rows_in_request_order(self, db_session, scenario):
        rows = await ref_service.resolve_codes(db_session, Skill, ["stealth", "arcana"], scenario["b"], label="skill")
        assert [r.code for r in rows] == ["stealth", "arcana"]

    async def test_unknown_and_invisible_codes_give_the_same_400(self, db_session, scenario):
        await seed_reference(db_session, DamageType, author=scenario["a"], code="psionic")

        with pytest.raises(HTTPException) as unknown:
            await ref_service.resolve_codes(db_session, DamageType, ["nope"], scenario["b"], label="damage type")
        with pytest.raises(HTTPException) as invisible:
            await ref_service.resolve_codes(db_session, DamageType, ["psionic"], scenario["b"], label="damage type")

        assert unknown.value.status_code == invisible.value.status_code == 400
        assert unknown.value.detail.replace("nope", "X") == invisible.value.detail.replace("psionic", "X")

    async def test_author_resolves_own_homebrew(self, db_session, scenario):
        await seed_reference(db_session, DamageType, author=scenario["a"], code="psionic")
        rows = await ref_service.resolve_codes(db_session, DamageType, ["psionic"], scenario["a"], label="damage type")
        assert [r.code for r in rows] == ["psionic"]

    async def test_get_visible_returns_none_when_not_visible(self, db_session, scenario):
        await seed_reference(db_session, DamageType, author=scenario["a"], code="psionic")
        assert await ref_service.get_visible(db_session, DamageType, "psionic", scenario["b"]) is None
        assert (await ref_service.get_visible(db_session, DamageType, "psionic", scenario["a"])).code == "psionic"
        assert await ref_service.get_visible(db_session, DamageType, "nope", scenario["a"]) is None
