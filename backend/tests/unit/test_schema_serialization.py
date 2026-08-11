import uuid

from app.schemas.campaign import CampaignOut, MemberOut
from app.schemas.character import CharacterOut, InventoryItemOut
from app.schemas.compendium import SubclassOut
from tests.conftest import (
    make_background,
    make_campaign,
    make_campaign_member,
    make_character,
    make_class,
    make_inventory_entry,
    make_item,
    make_species,
    make_subclass,
    make_user,
)


class TestCharacterOutUserName:
    def test_populated_from_owner(self):
        owner = make_user(username="gandalf")
        character = make_character(user_id=owner.id, owner=owner)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.user_name == "gandalf"


class TestCharacterOutCampaignName:
    def test_populated_when_campaign_loaded(self):
        campaign = make_campaign(name="Curse of Strahd")
        character = make_character(campaign_id=campaign.id, campaign=campaign)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.campaign_name == "Curse of Strahd"

    def test_none_when_campaign_id_none(self):
        character = make_character(campaign_id=None, campaign=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.campaign_id is None
        assert out.campaign_name is None

    def test_none_when_campaign_id_set_but_relationship_none(self):
        orphan_campaign_id = uuid.uuid4()
        character = make_character(campaign_id=orphan_campaign_id, campaign=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.campaign_id == orphan_campaign_id
        assert out.campaign_name is None


class TestCharacterOutSpeciesName:
    def test_populated_when_species_loaded(self):
        species = make_species(name="Elf")
        character = make_character(species_id=species.id, species=species)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.species_name == "Elf"

    def test_none_when_species_id_none(self):
        character = make_character(species_id=None, species=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.species_id is None
        assert out.species_name is None

    def test_none_when_species_id_set_but_relationship_none(self):
        orphan_id = uuid.uuid4()
        character = make_character(species_id=orphan_id, species=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.species_id == orphan_id
        assert out.species_name is None


class TestCharacterOutBackgroundName:
    def test_populated_when_background_loaded(self):
        background = make_background(name="Soldier")
        character = make_character(background_id=background.id, background=background)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.background_name == "Soldier"

    def test_none_when_background_id_none(self):
        character = make_character(background_id=None, background=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.background_id is None
        assert out.background_name is None

    def test_none_when_background_id_set_but_relationship_none(self):
        orphan_id = uuid.uuid4()
        character = make_character(background_id=orphan_id, background=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.background_id == orphan_id
        assert out.background_name is None


class TestCharacterOutClassName:
    def test_populated_when_class_loaded(self):
        klass = make_class(name="Wizard")
        character = make_character(class_id=klass.id, character_class=klass)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.class_name == "Wizard"

    def test_none_when_class_id_none(self):
        character = make_character(class_id=None, character_class=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.class_id is None
        assert out.class_name is None

    def test_none_when_class_id_set_but_relationship_none(self):
        orphan_id = uuid.uuid4()
        character = make_character(class_id=orphan_id, character_class=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.class_id == orphan_id
        assert out.class_name is None


class TestCharacterOutSubclassName:
    def test_populated_when_subclass_loaded(self):
        subclass = make_subclass(name="Evocation")
        character = make_character(subclass_id=subclass.id, subclass=subclass)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.subclass_name == "Evocation"

    def test_none_when_subclass_id_none(self):
        character = make_character(subclass_id=None, subclass=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.subclass_id is None
        assert out.subclass_name is None

    def test_none_when_subclass_id_set_but_relationship_none(self):
        orphan_id = uuid.uuid4()
        character = make_character(subclass_id=orphan_id, subclass=None)

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.subclass_id == orphan_id
        assert out.subclass_name is None


class TestInventoryItemOutItemName:
    def test_populated_from_item(self):
        item = make_item(name="Longsword")
        entry = make_inventory_entry(item_id=item.id, item=item)

        out = InventoryItemOut.model_validate(entry, from_attributes=True)

        assert out.item_name == "Longsword"


class TestInventoryItemOutAddedByName:
    def test_populated_when_added_by_user_loaded(self):
        user = make_user(username="dm_bob")
        entry = make_inventory_entry(added_by=user.id, added_by_user=user)

        out = InventoryItemOut.model_validate(entry, from_attributes=True)

        assert out.added_by_name == "dm_bob"

    def test_none_when_added_by_none(self):
        entry = make_inventory_entry(added_by=None, added_by_user=None)

        out = InventoryItemOut.model_validate(entry, from_attributes=True)

        assert out.added_by is None
        assert out.added_by_name is None

    def test_none_when_added_by_set_but_relationship_none(self):
        orphan_id = uuid.uuid4()
        entry = make_inventory_entry(added_by=orphan_id, added_by_user=None)

        out = InventoryItemOut.model_validate(entry, from_attributes=True)

        assert out.added_by == orphan_id
        assert out.added_by_name is None


class TestCampaignOutCreatedByName:
    def test_populated_from_creator(self):
        creator = make_user(username="dm_alice")
        campaign = make_campaign(created_by=creator.id, creator=creator)

        out = CampaignOut.model_validate(campaign, from_attributes=True)

        assert out.created_by_name == "dm_alice"


class TestMemberOutNames:
    def test_populated_from_user_and_campaign(self):
        user = make_user(username="player1")
        campaign = make_campaign(name="Tomb of Annihilation")
        member = make_campaign_member(
            user_id=user.id, campaign_id=campaign.id, user=user, campaign=campaign
        )

        out = MemberOut.model_validate(member, from_attributes=True)

        assert out.user_name == "player1"
        assert out.campaign_name == "Tomb of Annihilation"


class TestSubclassOutClassName:
    def test_populated_from_class_def(self):
        klass = make_class(name="Cleric")
        subclass = make_subclass(class_id=klass.id, class_def=klass)

        out = SubclassOut.model_validate(subclass, from_attributes=True)

        assert out.class_name == "Cleric"
