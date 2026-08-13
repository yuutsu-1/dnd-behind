import uuid

from sqlalchemy import inspect

from app.db.models.campaign import Campaign
from app.db.models.character import Character, CharacterAbilityScore, CharacterClass, CharacterInventory
from app.db.models.compendium import (
    BackgroundDefinition,
    ClassDefinition,
    SpeciesDefinition,
    SubclassDefinition,
)
from app.db.models.user import User


def _relationship_names(model) -> set[str]:
    return {rel.key for rel in inspect(model).relationships}


def _column_names(model) -> set[str]:
    return {col.name for col in inspect(model).columns}


class TestCharacterRelationships:
    def test_has_species_relationship(self):
        assert "species" in _relationship_names(Character)

    def test_has_background_relationship(self):
        assert "background" in _relationship_names(Character)

    def test_has_classes_relationship(self):
        assert "classes" in _relationship_names(Character)

    def test_no_longer_has_legacy_class_fields(self):
        columns = _column_names(Character)
        assert "class_id" not in columns
        assert "subclass_id" not in columns
        assert "level" not in columns
        assert "hit_dice_remaining" not in columns

    def test_no_longer_has_ability_scores_jsonb_column(self):
        assert "ability_scores" not in _column_names(Character)

    def test_has_ability_scores_relationship(self):
        assert "ability_scores" in _relationship_names(Character)

    def test_relationships_are_assignable_and_target_expected_classes(self):
        species = SpeciesDefinition(id=uuid.uuid4(), name="Elf", creature_type="humanoid")
        background = BackgroundDefinition(id=uuid.uuid4(), name="Soldier")
        klass = ClassDefinition(id=uuid.uuid4(), name="Fighter", hit_die=10)
        subclass = SubclassDefinition(id=uuid.uuid4(), class_id=klass.id, name="Champion")
        entry = CharacterClass(
            id=uuid.uuid4(),
            class_id=klass.id,
            level=3,
            class_=klass,
            subclass_id=subclass.id,
            subclass=subclass,
        )

        character = Character(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Test",
            species=species,
            background=background,
            classes=[entry],
        )

        assert character.species is species
        assert character.background is background
        assert character.classes == [entry]
        assert entry.class_ is klass
        assert entry.subclass is subclass

    def test_total_level_is_zero_with_no_classes(self):
        character = Character(id=uuid.uuid4(), user_id=uuid.uuid4(), name="Test")
        assert character.total_level == 0

    def test_total_level_sums_entries(self):
        klass_a = ClassDefinition(id=uuid.uuid4(), name="Fighter", hit_die=10)
        klass_b = ClassDefinition(id=uuid.uuid4(), name="Wizard", hit_die=6)
        entry_a = CharacterClass(id=uuid.uuid4(), class_id=klass_a.id, level=3, class_=klass_a)
        entry_b = CharacterClass(id=uuid.uuid4(), class_id=klass_b.id, level=2, class_=klass_b)

        character = Character(
            id=uuid.uuid4(), user_id=uuid.uuid4(), name="Test", classes=[entry_a, entry_b]
        )

        assert character.total_level == 5


class TestCharacterAbilityScoreRelationship:
    def test_assignable_and_reachable_from_character(self):
        entry = CharacterAbilityScore(id=uuid.uuid4(), ability_score="STR", value=16)
        character = Character(
            id=uuid.uuid4(), user_id=uuid.uuid4(), name="Test", ability_scores=[entry]
        )
        assert character.ability_scores == [entry]
        assert entry.character is character

    def test_unique_constraint_on_character_id_and_ability_score(self):
        constraint_columns = [
            tuple(c.name for c in constraint.columns)
            for constraint in CharacterAbilityScore.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]
        assert ("character_id", "ability_score") in constraint_columns


class TestCharacterClassHitDice:
    def test_hit_dice_derived_from_class_hit_die_and_level(self):
        klass = ClassDefinition(id=uuid.uuid4(), name="Fighter", hit_die=10)
        entry = CharacterClass(id=uuid.uuid4(), class_id=klass.id, level=5, hit_dice_used=2, class_=klass)

        assert entry.hit_die == 10
        assert entry.hit_dice_total == 5
        assert entry.hit_dice_used == 2
        assert entry.hit_dice_remaining == 3


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
