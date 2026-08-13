import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.characters import create_character, update_character
from app.db.models.character import CharacterAbilityScore
from app.schemas.character import CharacterCreate, CharacterOut, CharacterUpdate
from app.services.character import get_character_or_404
from tests.integration.conftest import seed_character, seed_character_ability_score, seed_user


class TestCreateCharacterAbilityScores:
    async def test_default_ability_scores_are_all_ten(self, db_session):
        owner = await seed_user(db_session)
        data = CharacterCreate(name="Default Hero")

        character = await create_character(data, current_user=owner, db=db_session)
        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.ability_scores == {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}

    async def test_custom_ability_scores_are_persisted(self, db_session):
        owner = await seed_user(db_session)
        data = CharacterCreate(
            name="Custom Hero",
            ability_scores={"STR": 18, "DEX": 14, "CON": 16, "INT": 8, "WIS": 10, "CHA": 12},
        )

        character = await create_character(data, current_user=owner, db=db_session)
        character_id = character.id

        db_session.expire_all()
        fetched = await get_character_or_404(db_session, character_id)
        out = CharacterOut.model_validate(fetched, from_attributes=True)

        assert out.ability_scores == {"STR": 18, "DEX": 14, "CON": 16, "INT": 8, "WIS": 10, "CHA": 12}


class TestUpdateCharacterAbilityScores:
    async def test_partial_update_only_changes_provided_ability(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(
            db_session, owner=owner,
            ability_scores={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        )
        character_id = character.id

        db_session.expire_all()
        updated = await update_character(
            character_id, CharacterUpdate(ability_scores={"STR": 18}), current_user=owner, db=db_session
        )
        out = CharacterOut.model_validate(updated, from_attributes=True)

        assert out.ability_scores == {"STR": 18, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}

    async def test_update_without_ability_scores_key_leaves_them_untouched(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={"STR": 15})
        character_id = character.id

        db_session.expire_all()
        updated = await update_character(
            character_id, CharacterUpdate(name="Renamed"), current_user=owner, db=db_session
        )
        out = CharacterOut.model_validate(updated, from_attributes=True)

        assert out.ability_scores == {"STR": 15}


class TestCharacterAbilityScoreConstraints:
    async def test_unique_constraint_on_character_id_and_ability_score(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={"STR": 10})

        db_session.add(CharacterAbilityScore(id=uuid.uuid4(), character_id=character.id, ability_score="STR", value=12))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_value_below_lower_bound_rejected(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={})

        with pytest.raises(IntegrityError):
            await seed_character_ability_score(db_session, character, ability_score="STR", value=0)

    async def test_value_above_upper_bound_rejected(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={})

        with pytest.raises(IntegrityError):
            await seed_character_ability_score(db_session, character, ability_score="STR", value=31)

    async def test_value_within_bounds_accepted(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={})

        row = await seed_character_ability_score(db_session, character, ability_score="STR", value=30)
        assert row.value == 30
