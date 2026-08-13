import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.characters import (
    add_character_class,
    remove_character_class,
    update_character_class,
    update_character_class_hit_dice,
)
from app.schemas.character import CharacterClassCreate, CharacterClassUpdate, CharacterOut, HitDiceUsedUpdate
from app.services.character import get_character_or_404
from tests.integration.conftest import (
    seed_character,
    seed_character_class,
    seed_class,
    seed_subclass,
    seed_user,
)


class TestCharacterWithoutClasses:
    async def test_total_level_is_zero_and_classes_empty(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id

        db_session.expire_all()
        fetched = await get_character_or_404(db_session, character_id)
        out = CharacterOut.model_validate(fetched, from_attributes=True)

        assert out.total_level == 0
        assert out.classes == []


class TestAddCharacterClassEndpoint:
    async def test_adds_class_via_api(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session, name="Fighter", hit_die=10)

        entry = await add_character_class(
            character.id, CharacterClassCreate(class_id=klass.id, level=3), current_user=owner, db=db_session
        )

        assert entry.level == 3
        assert entry.hit_die == 10
        assert entry.hit_dice_total == 3
        assert entry.hit_dice_remaining == 3

    async def test_duplicate_class_rejected_as_400_not_raw_integrity_error(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id
        klass = await seed_class(db_session, name="Fighter")
        await add_character_class(
            character_id, CharacterClassCreate(class_id=klass.id, level=1), current_user=owner, db=db_session
        )

        # Re-fetch the character (as the route handler would on a fresh request)
        # so the in-memory `classes` collection reflects what was just persisted.
        db_session.expire_all()
        character = await get_character_or_404(db_session, character_id)

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(
                character_id, CharacterClassCreate(class_id=klass.id, level=1), current_user=owner, db=db_session
            )
        assert exc_info.value.status_code == 400

    async def test_sum_of_levels_over_20_rejected(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id
        klass_a = await seed_class(db_session, name="Fighter")
        klass_b = await seed_class(db_session, name="Wizard")
        klass_a_id, klass_b_id = klass_a.id, klass_b.id
        await add_character_class(
            character_id, CharacterClassCreate(class_id=klass_a_id, level=18), current_user=owner, db=db_session
        )
        db_session.expire_all()

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(
                character_id, CharacterClassCreate(class_id=klass_b_id, level=3), current_user=owner, db=db_session
            )
        assert exc_info.value.status_code == 400

    async def test_multiclass_total_level_and_hit_dice_pool_per_class(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id
        fighter = await seed_class(db_session, name="Fighter", hit_die=10)
        wizard = await seed_class(db_session, name="Wizard", hit_die=6)
        fighter_id, wizard_id = fighter.id, wizard.id

        await add_character_class(
            character_id, CharacterClassCreate(class_id=fighter_id, level=3), current_user=owner, db=db_session
        )
        db_session.expire_all()
        await add_character_class(
            character_id, CharacterClassCreate(class_id=wizard_id, level=2), current_user=owner, db=db_session
        )

        db_session.expire_all()
        fetched = await get_character_or_404(db_session, character_id)
        out = CharacterOut.model_validate(fetched, from_attributes=True)

        assert out.total_level == 5
        pool_by_class = {c.class_name: c for c in out.classes}
        assert pool_by_class["Fighter"].hit_die == 10
        assert pool_by_class["Fighter"].hit_dice_total == 3
        assert pool_by_class["Wizard"].hit_die == 6
        assert pool_by_class["Wizard"].hit_dice_total == 2
        # Hit dice must never be collapsed into a single combined value.
        assert len(out.classes) == 2

    async def test_subclass_requires_level_and_matching_class(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session, name="Wizard", subclass_level=3)
        subclass = await seed_subclass(db_session, klass, name="Evocation")

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(
                character.id,
                CharacterClassCreate(class_id=klass.id, level=2, subclass_id=subclass.id),
                current_user=owner,
                db=db_session,
            )
        assert exc_info.value.status_code == 400

    async def test_subclass_accepted_when_level_requirement_met(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session, name="Wizard", subclass_level=3)
        subclass = await seed_subclass(db_session, klass, name="Evocation")

        entry = await add_character_class(
            character.id,
            CharacterClassCreate(class_id=klass.id, level=3, subclass_id=subclass.id),
            current_user=owner,
            db=db_session,
        )
        assert entry.subclass_id == subclass.id
        assert entry.subclass_name == "Evocation"


class TestUpdateCharacterClassEndpoint:
    async def test_reducing_level_below_subclass_level_with_subclass_assigned_is_blocked(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id
        klass = await seed_class(db_session, name="Wizard", subclass_level=3)
        subclass = await seed_subclass(db_session, klass, name="Evocation")
        entry = await seed_character_class(db_session, character, klass, level=5, subclass_id=subclass.id)
        entry_id = entry.id

        db_session.expire_all()
        with pytest.raises(HTTPException) as exc_info:
            await update_character_class(
                character_id, entry_id, CharacterClassUpdate(level=2), current_user=owner, db=db_session
            )
        assert exc_info.value.status_code == 400

        # Subclass must not have been silently cleared.
        db_session.expire_all()
        refetched = await get_character_or_404(db_session, character_id)
        refetched_entry = next(c for c in refetched.classes if c.id == entry_id)
        assert refetched_entry.subclass_id == subclass.id

    async def test_hit_dice_used_cannot_exceed_level(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id
        klass = await seed_class(db_session, name="Fighter")
        entry = await seed_character_class(db_session, character, klass, level=3)
        entry_id = entry.id

        db_session.expire_all()
        with pytest.raises(HTTPException) as exc_info:
            await update_character_class_hit_dice(
                character_id, entry_id, HitDiceUsedUpdate(hit_dice_used=4), current_user=owner, db=db_session
            )
        assert exc_info.value.status_code == 400

    async def test_hit_dice_used_updates_within_bounds(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id
        klass = await seed_class(db_session, name="Fighter")
        entry = await seed_character_class(db_session, character, klass, level=5)
        entry_id = entry.id

        db_session.expire_all()
        updated = await update_character_class_hit_dice(
            character_id, entry_id, HitDiceUsedUpdate(hit_dice_used=2), current_user=owner, db=db_session
        )
        assert updated.hit_dice_used == 2
        assert updated.hit_dice_remaining == 3


class TestRemoveCharacterClassEndpoint:
    async def test_removes_entry(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        character_id = character.id
        klass = await seed_class(db_session, name="Fighter")
        entry = await seed_character_class(db_session, character, klass, level=2)
        entry_id = entry.id

        db_session.expire_all()
        await remove_character_class(character_id, entry_id, current_user=owner, db=db_session)

        db_session.expire_all()
        refetched = await get_character_or_404(db_session, character_id)
        assert refetched.classes == []
        assert refetched.total_level == 0


class TestRestrictDeleteOfReferencedDefinitions:
    async def test_deleting_class_definition_in_use_is_blocked_by_fk(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session, name="Fighter")
        await seed_character_class(db_session, character, klass, level=2)

        await db_session.delete(klass)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_deleting_subclass_definition_in_use_is_blocked_by_fk(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session, name="Wizard", subclass_level=1)
        subclass = await seed_subclass(db_session, klass, name="Evocation")
        await seed_character_class(db_session, character, klass, level=2, subclass_id=subclass.id)

        await db_session.delete(subclass)
        with pytest.raises(IntegrityError):
            await db_session.flush()
