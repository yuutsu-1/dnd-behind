"""Metadata of the structured spell model (phase 3): `spell_definitions` with typed
columns, `spell_materials` and `spell_list_spells`; `spell_class_lists` is gone."""
import pytest
from sqlalchemy import CheckConstraint, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

import app.db.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base


def _table(name):
    assert name in Base.metadata.tables, f"table {name} not registered"
    return Base.metadata.tables[name]


def _fk(table_name, column_name):
    fks = list(_table(table_name).c[column_name].foreign_keys)
    assert len(fks) == 1, f"{table_name}.{column_name} should have exactly one FK"
    return fks[0]


def _checks(table_name) -> dict[str, str]:
    return {
        c.name: str(c.sqltext) for c in _table(table_name).constraints if isinstance(c, CheckConstraint)
    }


def _unique_column_sets(table_name) -> list[set[str]]:
    table = _table(table_name)
    sets = [{c.name for c in uc.columns} for uc in table.constraints if isinstance(uc, UniqueConstraint)]
    sets += [{c.name} for c in table.columns if c.unique]
    return sets


SPELL_COLUMNS = {
    "id", "name", "level", "school_code", "has_verbal", "has_somatic", "has_material",
    "casting_time_code", "ritual", "concentration", "range", "duration", "area", "area_shape_code",
    "description", "higher_levels", "cantrip_upgrade", "source", "is_homebrew", "created_by", "created_at",
}


class TestSpellDefinitions:
    def test_columns(self):
        assert set(_table("spell_definitions").c.keys()) == SPELL_COLUMNS

    @pytest.mark.parametrize("column", [
        "school", "casting_time", "components", "material_component", "casting_trigger",
        "casting_action_type_code", "casting_time_amount", "casting_time_unit_code",
        "range_type_code", "range_ft", "duration_type_code", "duration_amount", "duration_unit_code",
    ])
    def test_old_and_rejected_columns_are_absent(self, column):
        assert column not in _table("spell_definitions").c

    def test_no_jsonb(self):
        for name in ("spell_definitions", "spell_materials", "spell_list_spells"):
            for col in _table(name).columns:
                assert not isinstance(col.type, JSONB), f"{name}.{col.name} is JSONB"

    def test_name_is_not_unique(self):
        assert {"name"} not in _unique_column_sets("spell_definitions")

    @pytest.mark.parametrize("column", [
        "name", "level", "school_code", "has_verbal", "has_somatic", "has_material", "casting_time_code",
        "ritual", "concentration", "range", "duration", "description",
    ])
    def test_not_null_columns(self, column):
        assert _table("spell_definitions").c[column].nullable is False

    @pytest.mark.parametrize("column", ["area", "area_shape_code", "higher_levels", "cantrip_upgrade"])
    def test_nullable_columns(self, column):
        assert _table("spell_definitions").c[column].nullable is True

    @pytest.mark.parametrize("column", ["range", "duration", "area", "description"])
    def test_text_columns(self, column):
        assert isinstance(_table("spell_definitions").c[column].type, Text)

    @pytest.mark.parametrize("column,target", [
        ("school_code", "spell_schools.code"),
        ("casting_time_code", "casting_times.code"),
        ("area_shape_code", "area_shapes.code"),
    ])
    def test_reference_fks_are_restrict(self, column, target):
        fk = _fk("spell_definitions", column)
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"

    def test_checks(self):
        checks = _checks("spell_definitions")
        assert checks["ck_spell_definitions_level"] == "level BETWEEN 0 AND 9"
        assert checks["ck_spell_definitions_has_component"] == "has_verbal OR has_somatic OR has_material"
        assert checks["ck_spell_definitions_area_pair"] == "(area IS NULL) = (area_shape_code IS NULL)"
        assert checks["ck_spell_definitions_cantrip_upgrade"] == "cantrip_upgrade IS NULL OR level = 0"
        assert checks["ck_spell_definitions_higher_levels"] == "higher_levels IS NULL OR level >= 1"


class TestSpellMaterials:
    def test_columns(self):
        assert set(_table("spell_materials").c.keys()) == {
            "id", "spell_id", "sort_order", "description", "cost_gp", "consumed", "per_target", "quantity",
        }

    def test_types_and_nullability(self):
        table = _table("spell_materials")
        assert isinstance(table.c.cost_gp.type, Numeric)
        assert (table.c.cost_gp.type.precision, table.c.cost_gp.type.scale) == (12, 4)
        assert table.c.cost_gp.nullable is True
        for column in ("spell_id", "sort_order", "description", "consumed", "per_target", "quantity"):
            assert table.c[column].nullable is False, column
        assert table.c.quantity.default.arg == 1

    def test_spell_fk_cascades(self):
        fk = _fk("spell_materials", "spell_id")
        assert fk.target_fullname == "spell_definitions.id"
        assert fk.ondelete == "CASCADE"

    def test_checks_and_unique(self):
        checks = _checks("spell_materials")
        assert checks["ck_spell_materials_cost_gp"] == "cost_gp >= 0"
        assert checks["ck_spell_materials_quantity"] == "quantity >= 1"
        assert {"spell_id", "sort_order"} in _unique_column_sets("spell_materials")


class TestSpellListSpells:
    def test_primary_key(self):
        table = _table("spell_list_spells")
        assert set(table.c.keys()) == {"spell_list_code", "spell_id"}
        assert [c.name for c in table.primary_key.columns] == ["spell_list_code", "spell_id"]

    def test_fks(self):
        list_fk = _fk("spell_list_spells", "spell_list_code")
        assert list_fk.target_fullname == "spell_lists.code"
        assert list_fk.ondelete == "RESTRICT"
        spell_fk = _fk("spell_list_spells", "spell_id")
        assert spell_fk.target_fullname == "spell_definitions.id"
        assert spell_fk.ondelete == "CASCADE"


def test_spell_class_lists_is_gone():
    import app.db.models.compendium as compendium

    assert "spell_class_lists" not in Base.metadata.tables
    assert not hasattr(compendium, "spell_class_lists")


def test_character_spells_fk_still_blocks_spell_delete():
    """Unchanged structure: NO ACTION, so a referenced spell cannot be deleted (409)."""
    fk = _fk("character_spells", "spell_id")
    assert fk.target_fullname == "spell_definitions.id"
    assert fk.ondelete is None


def test_spell_definition_relationships():
    from app.db.models.compendium import SpellDefinition
    from app.db.models.spells import SpellMaterial

    assert "class_list" not in SpellDefinition.__mapper__.relationships
    materials = SpellDefinition.__mapper__.relationships["materials"]
    assert materials.mapper.class_ is SpellMaterial
    assert [c.name for c in materials.order_by] == ["sort_order"]
    lists = SpellDefinition.__mapper__.relationships["spell_lists"]
    assert lists.mapper.class_.__tablename__ == "spell_lists"


def test_spell_definition_reference_names():
    from app.db.models.compendium import SpellDefinition
    from app.db.models.reference import AreaShape, CastingTime, SpellSchool

    spell = SpellDefinition(
        school_code="evocation", casting_time_code="action", area_shape_code=None,
    )
    spell.school = SpellSchool(code="evocation", name="Evocation")
    spell.casting_time = CastingTime(code="action", name="Action")
    assert spell.school_name == "Evocation"
    assert spell.casting_time_name == "Action"
    assert spell.area_shape_name is None
    spell.area_shape = AreaShape(code="line", name="Line")
    assert spell.area_shape_name == "Line"
