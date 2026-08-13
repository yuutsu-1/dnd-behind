import uuid

import pytest
from fastapi import HTTPException

from app.schemas.character import AddItemRequest, CharacterCreate, CharacterUpdate, HPUpdate
from app.services.character import (
    add_item,
    apply_hp_update,
    assert_owner_or_dm,
    create_character,
    get_character_or_404,
    list_characters_for_campaign,
    remove_item,
    update_character,
)
from tests.conftest import (
    make_campaign_member,
    make_character,
    make_character_ability_score,
    make_inventory_entry,
    make_result,
)


class TestGetCharacterOr404:
    async def test_found_returns_character(self, fake_db):
        character = make_character()
        fake_db.execute.return_value = make_result(scalar=character)

        result = await get_character_or_404(fake_db, character.id)
        assert result is character

    async def test_not_found_raises_404(self, fake_db):
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_character_or_404(fake_db, uuid.uuid4())
        assert exc_info.value.status_code == 404

    async def test_inactive_character_treated_as_not_found(self, fake_db):
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_character_or_404(fake_db, uuid.uuid4())
        assert exc_info.value.status_code == 404


class TestAssertOwnerOrDM:
    async def test_owner_is_authorised(self, fake_db):
        user_id = uuid.uuid4()
        character = make_character(user_id=user_id)

        await assert_owner_or_dm(fake_db, character, user_id)
        fake_db.execute.assert_not_awaited()

    async def test_dm_of_campaign_is_authorised(self, fake_db):
        owner_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        campaign_id = uuid.uuid4()
        character = make_character(user_id=owner_id, campaign_id=campaign_id)
        membership = make_campaign_member(
            campaign_id=campaign_id, user_id=requester_id, role="dm"
        )
        fake_db.execute.return_value = make_result(scalar=membership)

        await assert_owner_or_dm(fake_db, character, requester_id)

    async def test_non_owner_without_campaign_raises_403(self, fake_db):
        owner_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        character = make_character(user_id=owner_id, campaign_id=None)

        with pytest.raises(HTTPException) as exc_info:
            await assert_owner_or_dm(fake_db, character, requester_id)
        assert exc_info.value.status_code == 403

    async def test_non_owner_player_member_raises_403(self, fake_db):
        owner_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        campaign_id = uuid.uuid4()
        character = make_character(user_id=owner_id, campaign_id=campaign_id)
        # Requester is a player, not a dm; the query filters role == "dm",
        # so it is simulated as "no row found".
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await assert_owner_or_dm(fake_db, character, requester_id)
        assert exc_info.value.status_code == 403


class TestCreateCharacter:
    async def test_persists_character_with_propagated_fields(self, fake_db):
        user_id = uuid.uuid4()
        campaign_id = uuid.uuid4()
        data = CharacterCreate(
            name="Aragorn",
            species_id=uuid.uuid4(),
            background_id=uuid.uuid4(),
            ability_scores={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
            appearance={"hair": "dark"},
            notes="A ranger",
        )

        character = await create_character(fake_db, data, user_id=user_id, campaign_id=campaign_id)

        # `db.add` is also called once per missing `AbilityScoreOption` lookup
        # row (get-or-create, via `ensure_ability_score_options`); the
        # character itself must still be among the added objects.
        added_objects = [call.args[0] for call in fake_db.add.call_args_list]
        assert character in added_objects
        assert character.user_id == user_id
        assert character.campaign_id == campaign_id
        assert character.name == "Aragorn"
        assert character.species_id == data.species_id
        assert character.background_id == data.background_id
        assert {row.ability_score: row.value for row in character.ability_scores} == data.ability_scores
        assert character.appearance == data.appearance
        assert character.notes == "A ranger"
        fake_db.commit.assert_awaited_once()
        fake_db.refresh.assert_awaited_once_with(
            character,
            attribute_names=["owner", "campaign", "species", "background", "classes", "ability_scores"],
        )

    async def test_campaign_id_optional_defaults_to_none(self, fake_db):
        data = CharacterCreate(name="Solo Hero")
        character = await create_character(fake_db, data, user_id=uuid.uuid4())
        assert character.campaign_id is None

    async def test_uses_default_ability_scores_when_not_provided(self, fake_db):
        data = CharacterCreate(name="Solo Hero")
        character = await create_character(fake_db, data, user_id=uuid.uuid4())

        scores = {row.ability_score: row.value for row in character.ability_scores}
        assert scores == {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}


class TestUpdateCharacter:
    async def test_applies_only_non_none_fields(self, fake_db):
        character = make_character(name="Old Name", experience_points=0, notes="original notes")
        update = CharacterUpdate(name="New Name", experience_points=100)

        result = await update_character(fake_db, character, update)

        assert result.name == "New Name"
        assert result.experience_points == 100
        assert result.notes == "original notes"
        fake_db.commit.assert_awaited_once()
        fake_db.refresh.assert_awaited_once_with(character)

    async def test_no_fields_set_leaves_character_unchanged(self, fake_db):
        character = make_character(name="Unchanged", experience_points=3)
        update = CharacterUpdate()

        result = await update_character(fake_db, character, update)

        assert result.name == "Unchanged"
        assert result.experience_points == 3

    async def test_ability_scores_partial_update_upserts_only_provided_ability(self, fake_db):
        character = make_character(
            ability_scores={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        )
        update = CharacterUpdate(ability_scores={"STR": 18})

        result = await update_character(fake_db, character, update)

        scores = {row.ability_score: row.value for row in result.ability_scores}
        assert scores == {"STR": 18, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}

    async def test_ability_scores_update_creates_missing_ability_row(self, fake_db):
        character = make_character(
            ability_scores=[make_character_ability_score(ability_score="STR", value=10)]
        )
        update = CharacterUpdate(ability_scores={"DEX": 14})

        result = await update_character(fake_db, character, update)

        scores = {row.ability_score: row.value for row in result.ability_scores}
        assert scores == {"STR": 10, "DEX": 14}

    async def test_ability_scores_omitted_from_payload_leaves_existing_untouched(self, fake_db):
        character = make_character(ability_scores={"STR": 16})
        update = CharacterUpdate(name="Renamed")

        result = await update_character(fake_db, character, update)

        scores = {row.ability_score: row.value for row in result.ability_scores}
        assert scores == {"STR": 16}


class TestApplyHPUpdate:
    async def test_simple_heal_adds_to_current_hp(self, fake_db):
        character = make_character(current_hp=5, max_hp=20, temp_hp=0)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=3, is_temp=False))
        assert result.current_hp == 8
        assert result.temp_hp == 0

    async def test_heal_exceeding_max_hp_is_capped(self, fake_db):
        character = make_character(current_hp=18, max_hp=20, temp_hp=0)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=10, is_temp=False))
        assert result.current_hp == 20

    async def test_damage_fully_absorbed_by_temp_hp(self, fake_db):
        character = make_character(current_hp=15, max_hp=20, temp_hp=10)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=-6, is_temp=False))
        assert result.temp_hp == 4
        assert result.current_hp == 15

    async def test_damage_exceeding_temp_hp_spills_into_current_hp(self, fake_db):
        character = make_character(current_hp=15, max_hp=20, temp_hp=5)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=-8, is_temp=False))
        assert result.temp_hp == 0
        assert result.current_hp == 12

    async def test_damage_exceeding_temp_plus_current_floors_at_zero(self, fake_db):
        character = make_character(current_hp=5, max_hp=20, temp_hp=3)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=-100, is_temp=False))
        assert result.temp_hp == 0
        assert result.current_hp == 0

    async def test_zero_delta_damage_is_idempotent(self, fake_db):
        character = make_character(current_hp=10, max_hp=20, temp_hp=5)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=0, is_temp=False))
        assert result.current_hp == 10
        assert result.temp_hp == 5

    async def test_zero_delta_heal_is_idempotent(self, fake_db):
        character = make_character(current_hp=10, max_hp=20, temp_hp=5)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=0, is_temp=False))
        assert result.current_hp == 10
        assert result.temp_hp == 5

    async def test_is_temp_true_positive_delta_adds_to_temp_hp(self, fake_db):
        character = make_character(current_hp=10, max_hp=20, temp_hp=2)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=5, is_temp=True))
        assert result.temp_hp == 7
        assert result.current_hp == 10

    async def test_is_temp_true_negative_delta_floors_at_zero(self, fake_db):
        character = make_character(current_hp=10, max_hp=20, temp_hp=3)
        result = await apply_hp_update(fake_db, character, HPUpdate(delta=-10, is_temp=True))
        assert result.temp_hp == 0
        assert result.current_hp == 10

    async def test_commits_and_refreshes(self, fake_db):
        character = make_character(current_hp=10, max_hp=20, temp_hp=0)
        await apply_hp_update(fake_db, character, HPUpdate(delta=1, is_temp=False))
        fake_db.commit.assert_awaited_once()
        fake_db.refresh.assert_awaited_once_with(character)


class TestAddItem:
    async def test_creates_inventory_entry_with_propagated_fields(self, fake_db):
        character = make_character()
        item_id = uuid.uuid4()
        added_by = uuid.uuid4()
        data = AddItemRequest(item_id=item_id, quantity=3, custom_notes="shiny")

        entry = await add_item(fake_db, character, data, added_by=added_by)

        assert fake_db.add.call_count == 1
        assert fake_db.add.call_args[0][0] is entry
        assert entry.character_id == character.id
        assert entry.item_id == item_id
        assert entry.quantity == 3
        assert entry.custom_notes == "shiny"
        assert entry.added_by == added_by
        fake_db.commit.assert_awaited_once()

        fake_db.refresh.assert_awaited_once_with(entry, attribute_names=["item", "added_by_user"])


class TestRemoveItem:
    async def test_no_permission_raises_403_and_does_not_delete(self, fake_db):
        owner_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        character = make_character(user_id=owner_id, campaign_id=None)

        with pytest.raises(HTTPException) as exc_info:
            await remove_item(fake_db, character, uuid.uuid4(), requester_id)
        assert exc_info.value.status_code == 403
        fake_db.delete.assert_not_awaited()

    async def test_entry_not_found_raises_404(self, fake_db):
        owner_id = uuid.uuid4()
        character = make_character(user_id=owner_id)
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await remove_item(fake_db, character, uuid.uuid4(), owner_id)
        assert exc_info.value.status_code == 404
        fake_db.delete.assert_not_awaited()

    async def test_entry_from_other_character_treated_as_not_found(self, fake_db):
        owner_id = uuid.uuid4()
        character = make_character(user_id=owner_id)
        # Query filters by character_id == character.id; an entry belonging
        # to another character is simulated as "no row found".
        fake_db.execute.return_value = make_result(scalar=None)

        with pytest.raises(HTTPException) as exc_info:
            await remove_item(fake_db, character, uuid.uuid4(), owner_id)
        assert exc_info.value.status_code == 404

    async def test_success_deletes_entry(self, fake_db):
        owner_id = uuid.uuid4()
        character = make_character(user_id=owner_id)
        entry = make_inventory_entry(character_id=character.id)
        fake_db.execute.return_value = make_result(scalar=entry)

        await remove_item(fake_db, character, entry.id, owner_id)

        fake_db.delete.assert_awaited_once_with(entry)
        fake_db.commit.assert_awaited_once()


class TestListCharactersForCampaign:
    async def test_returns_empty_list(self, fake_db):
        fake_db.execute.return_value = make_result(scalars_list=[])
        result = await list_characters_for_campaign(fake_db, uuid.uuid4())
        assert result == []

    async def test_returns_characters_for_the_given_campaign(self, fake_db):
        campaign_id = uuid.uuid4()
        characters = [
            make_character(campaign_id=campaign_id),
            make_character(campaign_id=campaign_id),
        ]
        fake_db.execute.return_value = make_result(scalars_list=characters)

        result = await list_characters_for_campaign(fake_db, campaign_id)
        assert result == characters
