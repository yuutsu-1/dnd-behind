import uuid

from app.api.characters import add_item, create_character, my_characters, update_character, update_hp
from app.schemas.character import (
    AddItemRequest,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    CharacterWithInventory,
    HPUpdate,
    InventoryItemOut,
)
from app.services.character import get_character_or_404, list_characters_for_campaign
from tests.integration.conftest import (
    seed_background,
    seed_campaign,
    seed_character,
    seed_class,
    seed_item,
    seed_species,
    seed_subclass,
    seed_user,
)


class TestCharacterOutNameFieldsPopulated:
    async def test_all_reference_names_populated_from_seeded_data(self, db_session):
        owner = await seed_user(db_session, username="aragorn_player")
        campaign = await seed_campaign(db_session, creator=owner, name="Fellowship")
        species = await seed_species(db_session, name="Human")
        background = await seed_background(db_session, name="Ranger")
        klass = await seed_class(db_session, name="Ranger Class")
        subclass = await seed_subclass(db_session, klass, name="Hunter")
        character = await seed_character(
            db_session,
            owner=owner,
            campaign_id=campaign.id,
            species_id=species.id,
            background_id=background.id,
            class_id=klass.id,
            subclass_id=subclass.id,
        )

        fetched = await get_character_or_404(db_session, character.id)
        out = CharacterOut.model_validate(fetched, from_attributes=True)

        assert out.user_name == "aragorn_player"
        assert out.campaign_name == "Fellowship"
        assert out.species_name == "Human"
        assert out.background_name == "Ranger"
        assert out.class_name == "Ranger Class"
        assert out.subclass_name == "Hunter"

    async def test_nullable_reference_names_are_none_with_real_null_ids(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(
            db_session,
            owner=owner,
            campaign_id=None,
            species_id=None,
            background_id=None,
            class_id=None,
            subclass_id=None,
        )

        fetched = await get_character_or_404(db_session, character.id)
        out = CharacterOut.model_validate(fetched, from_attributes=True)

        assert out.campaign_id is None and out.campaign_name is None
        assert out.species_id is None and out.species_name is None
        assert out.background_id is None and out.background_name is None
        assert out.class_id is None and out.class_name is None
        assert out.subclass_id is None and out.subclass_name is None
        assert out.user_name == owner.username


class TestInventoryItemOutNameFields:
    async def test_item_and_added_by_names_populated(self, db_session):
        owner = await seed_user(db_session)
        adder = await seed_user(db_session, username="dm_giving_loot")
        character = await seed_character(db_session, owner=owner)
        item = await seed_item(db_session, name="Longsword +1")

        added_by = adder.id
        data = AddItemRequest(item_id=item.id, quantity=1)
        entry = await add_item(character.id, data, current_user=owner, db=db_session)

        out = InventoryItemOut.model_validate(entry, from_attributes=True)
        assert out.item_name == "Longsword +1"

        assert out.added_by == owner.id
        assert out.added_by_name == owner.username


class TestNoMissingGreenletOnWriteEndpoints:
    async def test_create_character_serializes_without_error(self, db_session):
        owner = await seed_user(db_session)
        species = await seed_species(db_session)
        data = CharacterCreate(name="Freshly Created", species_id=species.id)

        character = await create_character(data, current_user=owner, db=db_session)

        out = CharacterOut.model_validate(character, from_attributes=True)
        assert out.name == "Freshly Created"
        assert out.user_name == owner.username
        assert out.species_name == species.name
        assert out.campaign_name is None  # no campaign on this character

    async def test_update_character_serializes_without_error(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, name="Before")

        updated = await update_character(
            character.id, CharacterUpdate(name="After"), current_user=owner, db=db_session
        )

        out = CharacterOut.model_validate(updated, from_attributes=True)
        assert out.name == "After"
        assert out.user_name == owner.username

    async def test_apply_hp_update_serializes_without_error(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner, current_hp=5, max_hp=20)

        updated = await update_hp(
            character.id, HPUpdate(delta=3, is_temp=False), current_user=owner, db=db_session
        )

        out = CharacterOut.model_validate(updated, from_attributes=True)
        assert out.current_hp == 8
        assert out.user_name == owner.username

    async def test_add_item_serializes_without_error(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        item = await seed_item(db_session)

        entry = await add_item(
            character.id, AddItemRequest(item_id=item.id, quantity=2), current_user=owner, db=db_session
        )

        out = InventoryItemOut.model_validate(entry, from_attributes=True)
        assert out.quantity == 2
        assert out.item_name == item.name
        assert out.added_by_name == owner.username

    async def test_my_characters_list_serializes_without_error(self, db_session):
        owner = await seed_user(db_session)
        await seed_character(db_session, owner=owner, name="Char A")
        await seed_character(db_session, owner=owner, name="Char B")

        characters = await my_characters(current_user=owner, db=db_session)

        out = [CharacterOut.model_validate(c, from_attributes=True) for c in characters]
        assert {c.name for c in out} == {"Char A", "Char B"}
        assert all(c.user_name == owner.username for c in out)

    async def test_list_characters_for_campaign_serializes_without_error(self, db_session):
        owner = await seed_user(db_session)
        campaign = await seed_campaign(db_session, creator=owner)
        await seed_character(db_session, owner=owner, campaign_id=campaign.id, name="Party Member")

        characters = await list_characters_for_campaign(db_session, campaign.id)

        out = [CharacterWithInventory.model_validate(c, from_attributes=True) for c in characters]
        assert out[0].campaign_name == campaign.name