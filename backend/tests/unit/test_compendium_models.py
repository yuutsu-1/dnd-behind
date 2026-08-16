import uuid

from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from app.db.models.compendium import (
    BackgroundDefinition,
    BackgroundInitialEquipment,
    ClassDefinition,
    ClassInitialEquipment,
    FeatDefinition,
    ItemDefinition,
    SkillDefinition,
    background_ability_scores,
    background_skills,
    class_skills,
)


def _relationship_names(model) -> set[str]:
    return {rel.key for rel in inspect(model).relationships}


def _column_names(model) -> set[str]:
    return {col.name for col in inspect(model).columns}


class TestMapperConfiguration:
    def test_configure_mappers_does_not_raise(self):
        configure_mappers()


class TestSkillDefinition:
    def test_has_expected_columns(self):
        columns = _column_names(SkillDefinition)
        assert {"id", "name", "ability_score"} <= columns

    def test_assignable(self):
        skill = SkillDefinition(id=uuid.uuid4(), name="Athletics", ability_score="STR")
        assert skill.name == "Athletics"
        assert skill.ability_score == "STR"

    def test_unique_constraint_on_name_and_ability_score(self):
        constraint_columns = [
            tuple(c.name for c in constraint.columns)
            for constraint in SkillDefinition.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]
        assert ("name", "ability_score") in constraint_columns


class TestClassSkillsJunctionTable:
    def test_junction_table_has_class_id_and_skill_id_columns(self):
        assert "class_id" in class_skills.c
        assert "skill_id" in class_skills.c

    def test_class_definition_no_longer_has_skill_pool_column(self):
        assert "skill_pool" not in _column_names(ClassDefinition)

    def test_class_definition_has_skills_relationship(self):
        assert "skills" in _relationship_names(ClassDefinition)


class TestClassDefinitionSpellAbilityForeignKey:
    def test_spell_ability_column_has_a_real_foreign_key(self):
        column = ClassDefinition.__table__.c.spell_ability
        assert len(column.foreign_keys) == 1
        fk = next(iter(column.foreign_keys))
        assert fk.target_fullname == "ability_score_options.name"


class TestClassInitialEquipment:
    def test_has_expected_columns(self):
        columns = _column_names(ClassInitialEquipment)
        assert {"id", "class_id", "item_id", "option", "quantity"} <= columns

    def test_assignable(self):
        item = ItemDefinition(id=uuid.uuid4(), name="Longsword", item_type="weapon")
        entry = ClassInitialEquipment(
            id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            item_id=item.id,
            item=item,
            option="A",
            quantity=1,
        )
        assert entry.item is item
        assert entry.option == "A"
        assert entry.quantity == 1


class TestBackgroundAbilityScoresJunctionTable:
    def test_junction_table_has_background_id_and_ability_score_columns(self):
        assert "background_id" in background_ability_scores.c
        assert "ability_score" in background_ability_scores.c


class TestBackgroundSkillsJunctionTable:
    def test_junction_table_has_background_id_and_skill_id_columns(self):
        assert "background_id" in background_skills.c
        assert "skill_id" in background_skills.c


class TestBackgroundDefinition:
    def test_has_expected_columns(self):
        columns = _column_names(BackgroundDefinition)
        assert {"id", "name", "feat_id", "tool_proficiency"} <= columns

    def test_feat_id_column_has_foreign_key_to_feat_definitions(self):
        column = BackgroundDefinition.__table__.c.feat_id
        assert not column.nullable
        assert len(column.foreign_keys) == 1
        fk = next(iter(column.foreign_keys))
        assert fk.target_fullname == "feat_definitions.id"

    def test_tool_proficiency_column_has_foreign_key_to_tool_proficiency_options(self):
        column = BackgroundDefinition.__table__.c.tool_proficiency
        assert not column.nullable
        assert len(column.foreign_keys) == 1
        fk = next(iter(column.foreign_keys))
        assert fk.target_fullname == "tool_proficiency_options.name"

    def test_has_expected_relationships(self):
        relationships = _relationship_names(BackgroundDefinition)
        assert {"ability_scores", "skills", "feat", "initial_equipment"} <= relationships

    def test_feat_name_property(self):
        feat = FeatDefinition(id=uuid.uuid4(), name="Alert", category="origin")
        background = BackgroundDefinition(
            id=uuid.uuid4(),
            name="Noble",
            feat_id=feat.id,
            feat=feat,
            tool_proficiency="Gaming Set",
        )
        assert background.feat_name == "Alert"

    def test_feat_name_none_when_relationship_not_loaded(self):
        background = BackgroundDefinition(id=uuid.uuid4(), name="Noble")
        assert background.feat_name is None


class TestBackgroundInitialEquipment:
    def test_has_expected_columns(self):
        columns = _column_names(BackgroundInitialEquipment)
        assert {"id", "background_id", "item_id", "option", "quantity"} <= columns

    def test_assignable(self):
        item = ItemDefinition(id=uuid.uuid4(), name="Fine Clothes", item_type="gear")
        entry = BackgroundInitialEquipment(
            id=uuid.uuid4(),
            background_id=uuid.uuid4(),
            item_id=item.id,
            item=item,
            option="A",
            quantity=1,
        )
        assert entry.item is item
        assert entry.item_name == "Fine Clothes"
        assert entry.option == "A"
        assert entry.quantity == 1
