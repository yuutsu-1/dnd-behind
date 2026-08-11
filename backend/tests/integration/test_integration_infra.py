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