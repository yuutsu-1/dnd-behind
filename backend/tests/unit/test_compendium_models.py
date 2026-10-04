import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from app.db.models.compendium import (
    BackgroundDefinition,
    BackgroundInitialEquipment,
    ClassDefinition,
    ClassInitialEquipment,
    FeatDefinition,
    ItemDefinition,
    SpeciesDefinition,
    background_ability_scores,
    background_skills,
    background_tool_proficiencies,
    class_armor_proficiencies,
    class_primary_abilities,
    class_saving_throws,
    class_skills,
    class_tool_proficiencies,
    class_weapon_proficiencies,
)
from app.db.models.reference import Skill


def _relationship_names(model) -> set[str]:
    return {rel.key for rel in inspect(model).relationships}


def _column_names(model) -> set[str]:
    return {col.name for col in inspect(model).columns}


class TestMapperConfiguration:
    def test_configure_mappers_does_not_raise(self):
        configure_mappers()


class TestSkill:
    def test_has_expected_columns(self):
        columns = _column_names(Skill)
        assert {"code", "name", "ability_code"} <= columns
        assert "id" not in columns

    def test_assignable(self):
        skill = Skill(code="athletics", name="Athletics", ability_code="str")
        assert skill.name == "Athletics"
        assert skill.ability_code == "str"


def _single_fk(column):
    assert len(column.foreign_keys) == 1
    return next(iter(column.foreign_keys))


class TestAssociationTablesUseCodes:
    @pytest.mark.parametrize("table,column,target", [
        (class_primary_abilities, "ability_code", "ability_scores.code"),
        (class_saving_throws, "ability_code", "ability_scores.code"),
        (background_ability_scores, "ability_code", "ability_scores.code"),
        (class_armor_proficiencies, "armor_category_code", "armor_categories.code"),
        (class_weapon_proficiencies, "weapon_category_code", "weapon_categories.code"),
        (class_tool_proficiencies, "tool_proficiency_code", "tool_proficiency_options.code"),
        (background_tool_proficiencies, "tool_proficiency_code", "tool_proficiency_options.code"),
        (class_skills, "skill_code", "skills.code"),
        (background_skills, "skill_code", "skills.code"),
    ])
    def test_column_is_restrict_fk_to_reference_table(self, table, column, target):
        assert column in table.c
        fk = _single_fk(table.c[column])
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"

    @pytest.mark.parametrize("table,old_column", [
        (class_primary_abilities, "ability_score"),
        (class_saving_throws, "ability_score"),
        (background_ability_scores, "ability_score"),
        (class_armor_proficiencies, "armor_proficiency"),
        (class_weapon_proficiencies, "weapon_proficiency"),
        (class_tool_proficiencies, "tool_proficiency"),
        (background_tool_proficiencies, "tool_proficiency"),
        (class_skills, "skill_id"),
        (background_skills, "skill_id"),
    ])
    def test_old_column_is_gone(self, table, old_column):
        assert old_column not in table.c


class TestClassSkillsJunctionTable:
    def test_class_definition_no_longer_has_skill_pool_column(self):
        assert "skill_pool" not in _column_names(ClassDefinition)

    def test_class_definition_has_skills_relationship(self):
        assert "skills" in _relationship_names(ClassDefinition)


class TestClassDefinitionSpellAbilityForeignKey:
    def test_spell_ability_column_has_a_real_foreign_key(self):
        fk = _single_fk(ClassDefinition.__table__.c.spell_ability)
        assert fk.target_fullname == "ability_scores.code"
        assert fk.ondelete == "RESTRICT"


class TestSpeciesSizeCode:
    def test_size_code_is_fk_to_sizes_with_medium_default(self):
        table = SpeciesDefinition.__table__
        assert "size" not in table.c
        fk = _single_fk(table.c.size_code)
        assert fk.target_fullname == "sizes.code"
        assert fk.ondelete == "RESTRICT"
        assert table.c.size_code.nullable is False
        assert table.c.size_code.default.arg == "medium"

    def test_no_creaturesize_enum_in_metadata(self):
        from sqlalchemy import Enum

        from app.db.base import Base
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, Enum):
                    assert column.type.name != "creaturesize"


class TestLegacyLookupsRemoved:
    @pytest.mark.parametrize("name", [
        "ability_score_options", "skill_definitions", "armor_proficiency_options", "weapon_proficiency_options",
    ])
    def test_table_not_registered(self, name):
        from app.db.base import Base
        assert name not in Base.metadata.tables

    @pytest.mark.parametrize("symbol", [
        "AbilityScoreOption", "ArmorProficiencyOption", "WeaponProficiencyOption", "SkillDefinition",
    ])
    def test_model_not_exported(self, symbol):
        import app.db.models as models
        import app.db.models.compendium as compendium
        assert not hasattr(compendium, symbol)
        assert not hasattr(models, symbol)

    def test_enums_module_no_longer_exports_ability_score_or_creature_size(self):
        try:
            import app.enums as enums
        except ImportError:
            return
        assert not hasattr(enums, "AbilityScore")
        assert not hasattr(enums, "CreatureSize")


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


class TestBackgroundDefinition:
    def test_has_expected_columns(self):
        columns = _column_names(BackgroundDefinition)
        assert {"id", "name", "feat_id"} <= columns
        assert "tool_proficiency" not in columns

    def test_feat_id_column_has_foreign_key_to_feat_definitions(self):
        column = BackgroundDefinition.__table__.c.feat_id
        assert not column.nullable
        assert len(column.foreign_keys) == 1
        fk = next(iter(column.foreign_keys))
        assert fk.target_fullname == "feat_definitions.id"

    def test_has_expected_relationships(self):
        relationships = _relationship_names(BackgroundDefinition)
        assert {"ability_scores", "skills", "feat", "tool_proficiencies", "initial_equipment"} <= relationships

    def test_feat_name_property(self):
        feat = FeatDefinition(id=uuid.uuid4(), name="Alert", category="origin")
        background = BackgroundDefinition(
            id=uuid.uuid4(),
            name="Noble",
            feat_id=feat.id,
            feat=feat,
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
