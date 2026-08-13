import uuid

import pytest
from fastapi import HTTPException

from app.schemas.character import CharacterClassCreate, CharacterClassUpdate, HitDiceUsedUpdate
from app.services.character import (
    add_character_class,
    remove_character_class,
    update_character_class,
    update_hit_dice_used,
)
from tests.conftest import make_character, make_character_class, make_class, make_result, make_subclass


class TestAddCharacterClass:
    async def test_adds_entry_when_class_exists_and_no_duplicate(self, fake_db):
        klass = make_class(name="Fighter", hit_die=10)
        character = make_character(classes=[])
        fake_db.execute.return_value = make_result(scalar=klass)

        entry = await add_character_class(
            fake_db, character, CharacterClassCreate(class_id=klass.id, level=3)
        )

        assert entry.class_id == klass.id
        assert entry.level == 3
        assert entry.hit_dice_used == 0
        fake_db.commit.assert_awaited_once()

    async def test_class_not_found_raises_404(self, fake_db):
        character = make_character(classes=[])
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(fake_db, character, CharacterClassCreate(class_id=uuid.uuid4(), level=1))
        assert exc_info.value.status_code == 404

    async def test_duplicate_class_rejected_with_validation_error_not_raw_integrity_error(self, fake_db):
        klass = make_class(name="Fighter")
        existing_entry = make_character_class(class_id=klass.id, class_=klass, level=2)
        character = make_character(classes=[existing_entry])
        fake_db.execute.return_value = make_result(scalar=klass)

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(fake_db, character, CharacterClassCreate(class_id=klass.id, level=1))
        assert exc_info.value.status_code == 400
        fake_db.commit.assert_not_awaited()

    async def test_sum_of_levels_exceeding_20_is_rejected(self, fake_db):
        klass_a = make_class(name="Fighter")
        klass_b = make_class(name="Wizard")
        existing_entry = make_character_class(class_id=klass_a.id, class_=klass_a, level=18)
        character = make_character(classes=[existing_entry])
        fake_db.execute.return_value = make_result(scalar=klass_b)

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(fake_db, character, CharacterClassCreate(class_id=klass_b.id, level=3))
        assert exc_info.value.status_code == 400
        fake_db.commit.assert_not_awaited()

    async def test_sum_of_levels_exactly_20_is_allowed(self, fake_db):
        klass_a = make_class(name="Fighter")
        klass_b = make_class(name="Wizard")
        existing_entry = make_character_class(class_id=klass_a.id, class_=klass_a, level=18)
        character = make_character(classes=[existing_entry])
        fake_db.execute.return_value = make_result(scalar=klass_b)

        entry = await add_character_class(fake_db, character, CharacterClassCreate(class_id=klass_b.id, level=2))
        assert entry.level == 2

    async def test_subclass_below_required_level_is_rejected(self, fake_db):
        klass = make_class(name="Wizard", subclass_level=3)
        subclass = make_subclass(name="Evocation", class_id=klass.id)
        character = make_character(classes=[])
        fake_db.execute.side_effect = [make_result(scalar=klass), make_result(scalar=subclass)]

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(
                fake_db, character,
                CharacterClassCreate(class_id=klass.id, level=2, subclass_id=subclass.id),
            )
        assert exc_info.value.status_code == 400
        fake_db.commit.assert_not_awaited()

    async def test_subclass_from_a_different_class_is_rejected(self, fake_db):
        klass = make_class(name="Wizard", subclass_level=3)
        other_klass_id = uuid.uuid4()
        subclass = make_subclass(name="Champion", class_id=other_klass_id)
        character = make_character(classes=[])
        fake_db.execute.side_effect = [make_result(scalar=klass), make_result(scalar=subclass)]

        with pytest.raises(HTTPException) as exc_info:
            await add_character_class(
                fake_db, character,
                CharacterClassCreate(class_id=klass.id, level=5, subclass_id=subclass.id),
            )
        assert exc_info.value.status_code == 400

    async def test_subclass_meeting_requirements_is_accepted(self, fake_db):
        klass = make_class(name="Wizard", subclass_level=3)
        subclass = make_subclass(name="Evocation", class_id=klass.id)
        character = make_character(classes=[])
        fake_db.execute.side_effect = [make_result(scalar=klass), make_result(scalar=subclass)]

        entry = await add_character_class(
            fake_db, character,
            CharacterClassCreate(class_id=klass.id, level=3, subclass_id=subclass.id),
        )
        assert entry.subclass_id == subclass.id


class TestUpdateCharacterClass:
    async def test_updates_level_within_bounds(self, fake_db):
        klass = make_class(name="Fighter")
        entry = make_character_class(class_id=klass.id, class_=klass, level=2, subclass_id=None, subclass=None)
        character = make_character(classes=[entry])

        result = await update_character_class(fake_db, character, entry.id, CharacterClassUpdate(level=5))
        assert result.level == 5
        fake_db.commit.assert_awaited_once()

    async def test_entry_not_found_raises_404(self, fake_db):
        character = make_character(classes=[])
        with pytest.raises(HTTPException) as exc_info:
            await update_character_class(fake_db, character, uuid.uuid4(), CharacterClassUpdate(level=2))
        assert exc_info.value.status_code == 404

    async def test_total_level_sum_exceeding_20_is_rejected(self, fake_db):
        klass_a = make_class(name="Fighter")
        klass_b = make_class(name="Wizard")
        entry_a = make_character_class(class_id=klass_a.id, class_=klass_a, level=15)
        entry_b = make_character_class(class_id=klass_b.id, class_=klass_b, level=3)
        character = make_character(classes=[entry_a, entry_b])

        with pytest.raises(HTTPException) as exc_info:
            await update_character_class(fake_db, character, entry_b.id, CharacterClassUpdate(level=10))
        assert exc_info.value.status_code == 400
        fake_db.commit.assert_not_awaited()

    async def test_reducing_level_below_subclass_level_with_subclass_assigned_is_blocked(self, fake_db):
        klass = make_class(name="Wizard", subclass_level=3)
        subclass = make_subclass(name="Evocation", class_id=klass.id)
        entry = make_character_class(
            class_id=klass.id, class_=klass, level=5, subclass_id=subclass.id, subclass=subclass,
        )
        character = make_character(classes=[entry])

        with pytest.raises(HTTPException) as exc_info:
            await update_character_class(fake_db, character, entry.id, CharacterClassUpdate(level=2))
        assert exc_info.value.status_code == 400
        # Subclass must NOT be silently cleared.
        assert entry.subclass_id == subclass.id
        fake_db.commit.assert_not_awaited()

    async def test_reducing_level_while_explicitly_clearing_subclass_is_allowed(self, fake_db):
        klass = make_class(name="Wizard", subclass_level=3)
        subclass = make_subclass(name="Evocation", class_id=klass.id)
        entry = make_character_class(
            class_id=klass.id, class_=klass, level=5, subclass_id=subclass.id, subclass=subclass,
        )
        character = make_character(classes=[entry])

        result = await update_character_class(
            fake_db, character, entry.id, CharacterClassUpdate(level=2, subclass_id=None)
        )
        assert result.level == 2
        assert result.subclass_id is None


class TestRemoveCharacterClass:
    async def test_deletes_entry(self, fake_db):
        entry = make_character_class()
        character = make_character(classes=[entry])

        await remove_character_class(fake_db, character, entry.id)

        fake_db.delete.assert_awaited_once_with(entry)
        fake_db.commit.assert_awaited_once()

    async def test_entry_not_found_raises_404(self, fake_db):
        character = make_character(classes=[])
        with pytest.raises(HTTPException) as exc_info:
            await remove_character_class(fake_db, character, uuid.uuid4())
        assert exc_info.value.status_code == 404
        fake_db.delete.assert_not_awaited()


class TestUpdateHitDiceUsed:
    async def test_updates_within_bounds(self, fake_db):
        entry = make_character_class(level=5, hit_dice_used=0)
        character = make_character(classes=[entry])

        result = await update_hit_dice_used(fake_db, character, entry.id, HitDiceUsedUpdate(hit_dice_used=3))
        assert result.hit_dice_used == 3

    async def test_exceeding_level_is_rejected(self, fake_db):
        entry = make_character_class(level=3, hit_dice_used=0)
        character = make_character(classes=[entry])

        with pytest.raises(HTTPException) as exc_info:
            await update_hit_dice_used(fake_db, character, entry.id, HitDiceUsedUpdate(hit_dice_used=4))
        assert exc_info.value.status_code == 400
        fake_db.commit.assert_not_awaited()

    async def test_negative_value_rejected_by_schema(self):
        with pytest.raises(ValueError):
            HitDiceUsedUpdate(hit_dice_used=-1)
