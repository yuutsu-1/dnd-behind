import uuid

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, inspect
from sqlalchemy.orm import configure_mappers

from app.db.models.compendium import (
    BackgroundDefinition,
    BackgroundInitialEquipment,
    ClassDefinition,
    ClassInitialEquipment,
    FeatDefinition,
    ItemDefinition,
    ProficiencyGrant,
    SpeciesDefinition,
    background_ability_scores,
    background_proficiency_grants,
    class_primary_abilities,
    class_proficiency_grants,
    class_skills,
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
        (background_ability_scores, "ability_code", "ability_scores.code"),
        (class_skills, "skill_code", "skills.code"),
    ])
    def test_column_is_restrict_fk_to_reference_table(self, table, column, target):
        assert column in table.c
        fk = _single_fk(table.c[column])
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"

    @pytest.mark.parametrize("table,old_column", [
        (class_primary_abilities, "ability_score"),
        (background_ability_scores, "ability_score"),
        (class_skills, "skill_id"),
    ])
    def test_old_column_is_gone(self, table, old_column):
        assert old_column not in table.c


REMOVED_PHASE2_TABLES = [
    "tool_proficiency_options",
    "class_saving_throws", "class_armor_proficiencies", "class_weapon_proficiencies", "class_tool_proficiencies",
    "background_skills", "background_tool_proficiencies",
]

# (column, target)
GRANT_TARGETS = [
    ("weapon_category_code", "weapon_categories.code"),
    ("required_weapon_property_code", "weapon_properties.code"),
    ("armor_category_code", "armor_categories.code"),
    ("tool_type_code", "tool_types.code"),
    ("tool_category_code", "tool_categories.code"),
    ("skill_code", "skills.code"),
    ("saving_throw_ability_code", "ability_scores.code"),
    ("language_code", "languages.code"),
]


def _metadata_table(name):
    from app.db.base import Base
    return Base.metadata.tables[name]


class TestProficiencyGrantsTable:
    @pytest.mark.parametrize("name", REMOVED_PHASE2_TABLES)
    def test_old_tables_are_gone(self, name):
        import app.db.models.compendium as compendium
        from app.db.base import Base

        assert name not in Base.metadata.tables
        assert not hasattr(compendium, name)

    def test_columns(self):
        table = _metadata_table("proficiency_grants")
        assert set(table.c.keys()) == {"id"} | {column for column, _ in GRANT_TARGETS}
        assert [c.name for c in table.primary_key.columns] == ["id"]
        assert "weapon_item_id" not in table.c
        assert "kind" not in table.c

    @pytest.mark.parametrize("column,target", GRANT_TARGETS)
    def test_target_columns_are_nullable_restrict_fks(self, column, target):
        table = _metadata_table("proficiency_grants")
        fk = _single_fk(table.c[column])
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"
        assert table.c[column].nullable is True

    def test_single_target_check(self):
        table = _metadata_table("proficiency_grants")
        checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
        single = checks["ck_proficiency_grants_single_target"]
        for column, _ in GRANT_TARGETS:
            if column == "required_weapon_property_code":
                assert column not in single
            else:
                assert column in single
        required = checks["ck_proficiency_grants_required_property"]
        assert "required_weapon_property_code IS NULL" in required
        assert "weapon_category_code IS NOT NULL" in required

    def test_unique_nulls_not_distinct_over_every_target(self):
        table = _metadata_table("proficiency_grants")
        uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        assert len(uniques) == 1
        unique = uniques[0]
        assert unique.name == "uq_proficiency_grants_target"
        assert {c.name for c in unique.columns} == {column for column, _ in GRANT_TARGETS}
        assert unique.dialect_options["postgresql"]["nulls_not_distinct"] is True

    @pytest.mark.parametrize("table,owner_column,owner_target", [
        (class_proficiency_grants, "class_id", "class_definitions.id"),
        (background_proficiency_grants, "background_id", "background_definitions.id"),
    ])
    def test_link_tables(self, table, owner_column, owner_target):
        assert {c.name for c in table.primary_key.columns} == {owner_column, "grant_id"}
        owner = _single_fk(table.c[owner_column])
        assert (owner.target_fullname, owner.ondelete) == (owner_target, "CASCADE")
        grant = _single_fk(table.c.grant_id)
        assert (grant.target_fullname, grant.ondelete) == ("proficiency_grants.id", "RESTRICT")


class TestProficiencyGrantKind:
    @pytest.mark.parametrize("values,kind", [
        ({"weapon_category_code": "martial"}, "weapon_category"),
        ({"weapon_category_code": "martial", "required_weapon_property_code": "light"}, "weapon_category"),
        ({"armor_category_code": "shield"}, "armor_category"),
        ({"tool_type_code": "thieves_tools"}, "tool"),
        ({"tool_category_code": "gaming_set"}, "tool_category"),
        ({"skill_code": "stealth"}, "skill"),
        ({"saving_throw_ability_code": "dex"}, "saving_throw"),
        ({"language_code": "elvish"}, "language"),
    ])
    def test_kind_is_derived_from_the_filled_target(self, values, kind):
        assert ProficiencyGrant(**values).kind == kind

    def test_target_name_and_required_property_name(self):
        from app.db.models.reference import WeaponCategory, WeaponProperty

        grant = ProficiencyGrant(
            weapon_category_code="martial", required_weapon_property_code="light",
            weapon_category=WeaponCategory(code="martial", name="Martial"),
            required_weapon_property=WeaponProperty(code="light", name="Light"),
        )
        assert grant.target_name == "Martial"
        assert grant.required_weapon_property_name == "Light"
        skill = ProficiencyGrant(skill_code="stealth", skill=Skill(code="stealth", name="Stealth", ability_code="dex"))
        assert skill.target_name == "Stealth"
        assert skill.required_weapon_property_name is None


class TestOwnersExposeGrants:
    def test_class_has_grants_and_no_old_relationships(self):
        relationships = _relationship_names(ClassDefinition)
        assert "proficiency_grants" in relationships
        for old in ("saving_throw_proficiencies", "armor_proficiencies", "weapon_proficiencies", "tool_proficiencies"):
            assert old not in relationships
        assert ClassDefinition.proficiency_grants.property.lazy == "selectin"

    def test_class_saving_throws_are_derived_and_sorted_by_code(self):
        grants = [
            ProficiencyGrant(saving_throw_ability_code="str"),
            ProficiencyGrant(weapon_category_code="simple"),
            ProficiencyGrant(saving_throw_ability_code="con"),
        ]
        klass = ClassDefinition(name="Fighter", hit_die=10, proficiency_grants=grants)
        assert klass.saving_throw_proficiencies == ["con", "str"]

    def test_background_has_grants_and_derived_skills_sorted_by_name(self):
        relationships = _relationship_names(BackgroundDefinition)
        assert "proficiency_grants" in relationships
        assert "tool_proficiencies" not in relationships
        assert BackgroundDefinition.proficiency_grants.property.lazy == "selectin"
        stealth = Skill(code="stealth", name="Stealth", ability_code="dex")
        athletics = Skill(code="athletics", name="Athletics", ability_code="str")
        background = BackgroundDefinition(name="Soldier", proficiency_grants=[
            ProficiencyGrant(skill_code="stealth", skill=stealth),
            ProficiencyGrant(tool_category_code="gaming_set"),
            ProficiencyGrant(skill_code="athletics", skill=athletics),
        ])
        assert background.skills == [athletics, stealth]

    def test_grant_targets_load_eagerly_with_the_grant(self):
        for name in ("weapon_category", "required_weapon_property", "armor_category", "tool_type",
                     "tool_category", "skill", "saving_throw_ability", "language"):
            assert getattr(ProficiencyGrant, name).property.lazy == "joined"


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
        item = ItemDefinition(id=uuid.uuid4(), name="Longsword", item_type_code="weapon")
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
        assert {"ability_scores", "feat", "proficiency_grants", "initial_equipment"} <= relationships

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
        item = ItemDefinition(id=uuid.uuid4(), name="Fine Clothes", item_type_code="adventuring_gear")
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
