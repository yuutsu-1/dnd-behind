import uuid

from sqlalchemy import select

from app.db.models.character import Character
from tests.integration.conftest import seed_character, seed_user


class TestIntegrationInfra:
    async def test_round_trip_character_creation(self, db_session):
        user = await seed_user(db_session)
        character = await seed_character(db_session, owner=user, name="Smoke Test Hero")

        result = await db_session.execute(select(Character).where(Character.id == character.id))
        fetched = result.scalar_one()

        assert fetched.id == character.id
        assert fetched.name == "Smoke Test Hero"
        assert fetched.user_id == user.id

    async def test_transaction_is_rolled_back_between_tests(self, db_session):
        result = await db_session.execute(select(Character).where(Character.name == "Smoke Test Hero"))
        assert result.scalar_one_or_none() is None

class TestReferenceFactories:
    async def test_seed_skill_uses_valid_code_and_srd_ability(self, db_session):
        import re

        from tests.integration.conftest import seed_skill

        skill = await seed_skill(db_session)
        assert re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", skill.code)
        assert skill.ability_code == "str"

    async def test_seed_reference_creates_homebrew_with_shares(self, db_session):
        from app.db.models.reference import CampaignHomebrewRule, DamageType
        from tests.integration.conftest import seed_campaign, seed_reference

        author = await seed_user(db_session)
        campaign = await seed_campaign(db_session, creator=author)
        entry = await seed_reference(db_session, DamageType, author=author, campaigns=[campaign])

        assert entry.is_homebrew is True
        assert entry.source == "homebrew"
        assert entry.created_by == author.id
        shares = (await db_session.execute(
            select(CampaignHomebrewRule).where(CampaignHomebrewRule.resource_key == entry.code)
        )).scalars().all()
        assert [(s.resource_table, s.campaign_id) for s in shares] == [("damage_types", campaign.id)]
