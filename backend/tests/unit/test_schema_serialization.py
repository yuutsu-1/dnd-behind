import uuid

from app.schemas.campaign import CampaignOut, MemberOut
from app.schemas.character import CharacterOut, InventoryItemOut
from app.schemas.compendium import ClassOut, SubclassOut
from tests.conftest import (
    make_background,
    make_campaign,
    make_campaign_member,
    make_character,
    make_character_ability_score,
    make_character_class,
    make_class,
    make_class_initial_equipment,
    make_inventory_entry,
    make_item,
    make_skill,
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


class TestCharacterOutClasses:
    def test_no_classes_yields_empty_list_and_zero_total_level(self):
        character = make_character(classes=[])

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.classes == []
        assert out.total_level == 0

    def test_multiclass_entries_expose_names_and_hit_dice_pool_per_class(self):
        wizard = make_class(name="Wizard", hit_die=6)
        fighter = make_class(name="Fighter", hit_die=10)
        evocation = make_subclass(name="Evocation", class_id=wizard.id)
        entry_wizard = make_character_class(
            class_id=wizard.id, class_=wizard, level=3,
            subclass_id=evocation.id, subclass=evocation, hit_dice_used=1,
        )
        entry_fighter = make_character_class(class_id=fighter.id, class_=fighter, level=2, hit_dice_used=0)
        character = make_character(classes=[entry_wizard, entry_fighter])

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.total_level == 5
        by_name = {c.class_name: c for c in out.classes}
        assert by_name["Wizard"].level == 3
        assert by_name["Wizard"].subclass_name == "Evocation"
        assert by_name["Wizard"].hit_die == 6
        assert by_name["Wizard"].hit_dice_total == 3
        assert by_name["Wizard"].hit_dice_used == 1
        assert by_name["Wizard"].hit_dice_remaining == 2
        assert by_name["Fighter"].subclass_name is None
        assert by_name["Fighter"].hit_die == 10
        assert by_name["Fighter"].hit_dice_remaining == 2


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


class TestCharacterOutAbilityScores:
    def test_serializes_list_of_rows_as_name_to_value_dict(self):
        character = make_character(
            ability_scores=[
                make_character_ability_score(ability_score="STR", value=16),
                make_character_ability_score(ability_score="DEX", value=12),
            ]
        )

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.ability_scores == {"STR": 16, "DEX": 12}

    def test_empty_list_serializes_as_empty_dict(self):
        character = make_character(ability_scores=[])

        out = CharacterOut.model_validate(character, from_attributes=True)

        assert out.ability_scores == {}


class TestClassOutSkillsAndInitialEquipment:
    def test_no_longer_has_skill_pool_field(self):
        assert "skill_pool" not in ClassOut.model_fields

    def test_skills_and_initial_equipment_populated_from_relationships(self):
        athletics = make_skill(name="Athletics", ability_score="STR")
        arcana = make_skill(name="Arcana", ability_score="INT")
        item = make_item(name="Dagger")
        equipment_entry = make_class_initial_equipment(item=item, option="A", quantity=2)
        klass = make_class(name="Wizard", skills=[athletics, arcana], initial_equipment=[equipment_entry])

        out = ClassOut.model_validate(klass, from_attributes=True)

        assert {s.name for s in out.skills} == {"Athletics", "Arcana"}
        assert out.initial_equipment[0].item_name == "Dagger"
        assert out.initial_equipment[0].option == "A"
        assert out.initial_equipment[0].quantity == 2


class TestSubclassOutClassName:
    def test_populated_from_class_def(self):
        klass = make_class(name="Cleric")
        subclass = make_subclass(class_id=klass.id, class_def=klass)

        out = SubclassOut.model_validate(subclass, from_attributes=True)

        assert out.class_name == "Cleric"
