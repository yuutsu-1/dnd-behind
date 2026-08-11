import uuid

from sqlalchemy import inspect

from app.db.models.campaign import Campaign
from app.db.models.character import Character, CharacterInventory
from app.db.models.compendium import (
    BackgroundDefinition,
    ClassDefinition,
    SpeciesDefinition,
    SubclassDefinition,
)
from app.db.models.user import User


def _relationship_names(model) -> set[str]:
    return {rel.key for rel in inspect(model).relationships}


class TestCharacterRelationships:
    def test_has_species_relationship(self):
        assert "species" in _relationship_names(Character)

    def test_has_background_relationship(self):
        assert "background" in _relationship_names(Character)

    def test_has_character_class_relationship(self):
        assert "character_class" in _relationship_names(Character)

    def test_has_subclass_relationship(self):
        assert "subclass" in _relationship_names(Character)

    def test_relationships_are_assignable_and_target_expected_classes(self):
        species = SpeciesDefinition(id=uuid.uuid4(), name="Elf", creature_type="humanoid")
        background = BackgroundDefinition(id=uuid.uuid4(), name="Soldier")
        klass = ClassDefinition(id=uuid.uuid4(), name="Fighter", hit_die=10)
        subclass = SubclassDefinition(id=uuid.uuid4(), class_id=klass.id, name="Champion")

        character = Character(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Test",
            species=species,
            background=background,
            character_class=klass,
            subclass=subclass,
        )

        assert character.species is species
        assert character.background is background
        assert character.character_class is klass
        assert character.subclass is subclass


class TestCharacterInventoryRelationships:
    def test_has_added_by_user_relationship(self):
        assert "added_by_user" in _relationship_names(CharacterInventory)

    def test_relationship_is_assignable(self):
        user = User(id=uuid.uuid4(), email="a@a.com", username="a", hashed_password="x")
        entry = CharacterInventory(
            id=uuid.uuid4(),
            character_id=uuid.uuid4(),
            item_id=uuid.uuid4(),
            added_by_user=user,
        )
        assert entry.added_by_user is user


class TestCampaignRelationships:
    def test_has_creator_relationship(self):
        assert "creator" in _relationship_names(Campaign)

    def test_relationship_is_assignable(self):
        user = User(id=uuid.uuid4(), email="b@b.com", username="b", hashed_password="x")
        campaign = Campaign(
            id=uuid.uuid4(),
            name="Test Campaign",
            created_by=user.id,
            invite_code="ABCDEF123456",
            creator=user,
        )
        assert campaign.creator is user
