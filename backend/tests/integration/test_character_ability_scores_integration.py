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

        assert out.ability_scores == {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

    async def test_custom_ability_scores_are_persisted(self, db_session):
        owner = await seed_user(db_session)
        data = CharacterCreate(
            name="Custom Hero",
            ability_scores={"str": 18, "dex": 14, "con": 16, "int": 8, "wis": 10, "cha": 12},
        )

        character = await create_character(data, current_user=owner, db=db_session)
        character_id = character.id

        db_session.expire_all()
        fetched = await get_character_or_404(db_session, character_id)
        out = CharacterOut.model_validate(fetched, from_attributes=True)

        assert out.ability_scores == {"str": 18, "dex": 14, "con": 16, "int": 8, "wis": 10, "cha": 12}


class TestUpdateCharacterAbilityScores:
    async def test_partial_update_only_changes_provided_ability(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(
            db_session, owner=owner,
            ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        )
        character_id = character.id

        db_session.expire_all()
        updated = await update_character(
            character_id, CharacterUpdate(ability_scores={"str": 18}), current_user=owner, db=db_session
        )
        out = CharacterOut.model_validate(updated, from_attributes=True)

        assert out.ability_scores == {"str": 18, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

    async def test_update_without_ability_scores_key_leaves_them_untouched(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={"str": 15})
        character_id = character.id

        db_session.expire_all()
        updated = await update_character(
            character_id, CharacterUpdate(name="Renamed"), current_user=owner, db=db_session
        )
        out = CharacterOut.model_validate(updated, from_attributes=True)

        assert out.ability_scores == {"str": 15}


class TestCharacterAbilityScoreConstraints:
    async def test_unique_constraint_on_character_id_and_ability_score(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={"str": 10})

        db_session.add(CharacterAbilityScore(id=uuid.uuid4(), character_id=character.id, ability_code="str", value=12))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_value_below_lower_bound_rejected(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={})

        with pytest.raises(IntegrityError):
            await seed_character_ability_score(db_session, character, ability_code="str", value=0)

    async def test_value_above_upper_bound_rejected(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={})

        with pytest.raises(IntegrityError):
            await seed_character_ability_score(db_session, character, ability_code="str", value=31)

    async def test_value_within_bounds_accepted(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={})

        row = await seed_character_ability_score(db_session, character, ability_code="str", value=30)
        assert row.value == 30


class TestAbilityCodesAreValidated:
    async def test_default_keys_are_the_six_lowercase_srd_codes(self):
        assert CharacterCreate(name="X").ability_scores == {
            "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10,
        }

    @pytest.mark.parametrize("scores", [{"STR": 10}, {"luck": 12}, {"str": 10, "Dex": 10}])
    async def test_create_with_unknown_code_is_400_and_writes_nothing(self, db_session, scores):
        from sqlalchemy import select

        from app.db.models.character import Character
        from fastapi import HTTPException

        owner = await seed_user(db_session)
        await db_session.commit()
        name = f"Bad-{uuid.uuid4().hex[:8]}"
        with pytest.raises(HTTPException) as exc:
            await create_character(CharacterCreate(name=name, ability_scores=scores), current_user=owner, db=db_session)
        assert exc.value.status_code == 400
        assert (await db_session.execute(select(Character).where(Character.name == name))).first() is None

    async def test_invisible_homebrew_ability_is_400_but_own_is_accepted(self, db_session):
        from fastapi import HTTPException

        from app.db.models.reference import Ability
        from tests.integration.conftest import seed_reference

        author, outsider = await seed_user(db_session), await seed_user(db_session)
        await seed_reference(db_session, Ability, author=author, code="luck", name="Luck")
        await db_session.commit()
        author_id = author.id

        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(name="Outsider", ability_scores={"luck": 12}), current_user=outsider, db=db_session
            )
        assert exc.value.status_code == 400

        author = await db_session.get(type(author), author_id)
        character = await create_character(
            CharacterCreate(name="Lucky", ability_scores={"str": 10, "luck": 14}), current_user=author, db=db_session
        )
        assert CharacterOut.model_validate(character).ability_scores == {"str": 10, "luck": 14}

    @pytest.mark.parametrize("scores", [{"STR": 18}, {"luck": 12}])
    async def test_update_with_unknown_code_is_400_and_changes_nothing(self, db_session, scores):
        from fastapi import HTTPException

        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, ability_scores={"str": 10})
        await db_session.commit()
        character_id = character.id

        with pytest.raises(HTTPException) as exc:
            await update_character(
                character_id, CharacterUpdate(name="Renamed", ability_scores=scores), current_user=owner, db=db_session
            )
        assert exc.value.status_code == 400

        db_session.expire_all()
        fetched = CharacterOut.model_validate(await get_character_or_404(db_session, character_id))
        assert fetched.ability_scores == {"str": 10}
        assert fetched.name != "Renamed"
