"""Metadata-level checks for the structured items of phase 2 (item_definitions base +
1:1 tables per type, weapon properties and pack contents). No JSONB anywhere."""
import pytest
from sqlalchemy import CheckConstraint, Numeric
from sqlalchemy.dialects.postgresql import JSONB

import app.db.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base
from app.db.models.compendium import ItemDefinition

ITEM_TABLES = [
    "item_definitions", "weapons", "weapon_property_links", "armors", "tools", "containers", "item_contents",
]


def _table(name):
    assert name in Base.metadata.tables, f"table {name} not registered"
    return Base.metadata.tables[name]


def _fk(table_name, column_name):
    fks = list(_table(table_name).c[column_name].foreign_keys)
    assert len(fks) == 1, f"{table_name}.{column_name} should have exactly one FK"
    return fks[0]


def _check_names(table_name) -> set[str]:
    return {c.name for c in _table(table_name).constraints if isinstance(c, CheckConstraint)}


def _check_text(table_name, name) -> str:
    for c in _table(table_name).constraints:
        if isinstance(c, CheckConstraint) and c.name == name:
            return str(c.sqltext)
    raise AssertionError(f"check {name} not found on {table_name}")


@pytest.mark.parametrize("name", ITEM_TABLES)
def test_item_tables_have_no_jsonb(name):
    for col in _table(name).columns:
        assert not isinstance(col.type, JSONB), f"{name}.{col.name} is JSONB"


class TestItemDefinition:
    def test_columns(self):
        assert set(_table("item_definitions").c.keys()) == {
            "id", "name", "item_type_code", "cost_gp", "weight_lb", "description",
            "source", "is_homebrew", "created_by", "created_at",
        }

    @pytest.mark.parametrize("legacy", [
        "properties", "subtype", "rarity", "requires_attunement", "attunement_prerequisite", "weight", "item_type",
    ])
    def test_legacy_columns_are_gone(self, legacy):
        assert legacy not in _table("item_definitions").c
        assert not hasattr(ItemDefinition, legacy)

    @pytest.mark.parametrize("column", ["cost_gp", "weight_lb"])
    def test_money_and_weight_are_numeric_12_4_nullable(self, column):
        col = _table("item_definitions").c[column]
        assert isinstance(col.type, Numeric)
        assert (col.type.precision, col.type.scale) == (12, 4)
        assert col.nullable is True

    def test_name_is_not_unique(self):
        table = _table("item_definitions")
        assert not table.c.name.unique
        assert table.c.name.nullable is False

    def test_item_type_code_is_restrict_fk(self):
        fk = _fk("item_definitions", "item_type_code")
        assert fk.target_fullname == "item_types.code"
        assert fk.ondelete == "RESTRICT"
        assert _table("item_definitions").c.item_type_code.nullable is False


# (table, column, target, ondelete, nullable)
FOREIGN_KEYS = [
    ("weapons", "item_id", "item_definitions.id", "CASCADE", False),
    ("weapons", "category_code", "weapon_categories.code", "RESTRICT", False),
    ("weapons", "damage_type_code", "damage_types.code", "RESTRICT", False),
    ("weapons", "mastery_code", "weapon_masteries.code", "RESTRICT", True),
    ("weapon_property_links", "weapon_item_id", "weapons.item_id", "CASCADE", False),
    ("weapon_property_links", "property_code", "weapon_properties.code", "RESTRICT", False),
    ("weapon_property_links", "ammunition_item_id", "item_definitions.id", "RESTRICT", True),
    ("armors", "item_id", "item_definitions.id", "CASCADE", False),
    ("armors", "category_code", "armor_categories.code", "RESTRICT", False),
    ("tools", "item_id", "item_definitions.id", "CASCADE", False),
    ("tools", "tool_type_code", "tool_types.code", "RESTRICT", False),
    ("containers", "item_id", "item_definitions.id", "CASCADE", False),
    ("item_contents", "pack_item_id", "item_definitions.id", "CASCADE", False),
    ("item_contents", "item_id", "item_definitions.id", "RESTRICT", False),
]


@pytest.mark.parametrize("table,column,target,ondelete,nullable", FOREIGN_KEYS)
def test_foreign_keys(table, column, target, ondelete, nullable):
    fk = _fk(table, column)
    assert fk.target_fullname == target
    assert fk.ondelete == ondelete
    assert _table(table).c[column].nullable is nullable


@pytest.mark.parametrize("table,pk", [
    ("weapons", {"item_id"}),
    ("armors", {"item_id"}),
    ("tools", {"item_id"}),
    ("containers", {"item_id"}),
    ("weapon_property_links", {"weapon_item_id", "property_code"}),
    ("item_contents", {"pack_item_id", "item_id"}),
])
def test_primary_keys(table, pk):
    assert {c.name for c in _table(table).primary_key.columns} == pk


class TestWeapons:
    def test_columns(self):
        assert set(_table("weapons").c.keys()) == {
            "item_id", "category_code", "is_ranged", "damage_dice_count", "damage_die_size",
            "damage_flat", "damage_type_code", "mastery_code",
        }

    def test_damage_flat_defaults_to_zero(self):
        col = _table("weapons").c.damage_flat
        assert col.nullable is False
        assert col.default.arg == 0

    def test_checks(self):
        names = _check_names("weapons")
        assert {
            "ck_weapons_damage_dice_pair", "ck_weapons_damage_flat_without_dice",
            "ck_weapons_damage_dice_count", "ck_weapons_damage_die_size",
        } <= names
        assert "damage_dice_count >= 1" in _check_text("weapons", "ck_weapons_damage_dice_count")
        assert "(4, 6, 8, 10, 12, 20)" in _check_text("weapons", "ck_weapons_damage_die_size")
        assert "damage_flat >= 1" in _check_text("weapons", "ck_weapons_damage_flat_without_dice")


class TestWeaponPropertyLinks:
    def test_columns(self):
        assert set(_table("weapon_property_links").c.keys()) == {
            "weapon_item_id", "property_code", "range_normal_ft", "range_long_ft",
            "versatile_die_size", "ammunition_item_id",
        }

    def test_checks(self):
        assert {
            "ck_weapon_property_links_range_normal", "ck_weapon_property_links_range_long",
            "ck_weapon_property_links_versatile_die_size",
        } <= _check_names("weapon_property_links")
        assert "range_normal_ft > 0" in _check_text("weapon_property_links", "ck_weapon_property_links_range_normal")
        assert "range_long_ft >= range_normal_ft" in _check_text(
            "weapon_property_links", "ck_weapon_property_links_range_long"
        )


class TestArmors:
    def test_columns_and_nullability(self):
        table = _table("armors")
        assert set(table.c.keys()) == {
            "item_id", "category_code", "base_ac", "adds_dex_modifier", "max_dex_modifier",
            "strength_requirement", "stealth_disadvantage",
        }
        assert table.c.max_dex_modifier.nullable is True
        assert table.c.strength_requirement.nullable is True
        for col in ("base_ac", "adds_dex_modifier", "stealth_disadvantage"):
            assert table.c[col].nullable is False

    def test_checks(self):
        assert {
            "ck_armors_base_ac", "ck_armors_max_dex_modifier", "ck_armors_strength_requirement",
        } <= _check_names("armors")
        assert "base_ac >= 0" in _check_text("armors", "ck_armors_base_ac")
        assert "max_dex_modifier >= 0" in _check_text("armors", "ck_armors_max_dex_modifier")
        assert "strength_requirement >= 1" in _check_text("armors", "ck_armors_strength_requirement")

    def test_model_documents_that_shield_base_ac_is_a_bonus(self):
        from app.db.models.items import Armor

        assert "shield" in (Armor.__doc__ or "").lower()
        assert "bonus" in (Armor.__doc__ or "").lower()


class TestTools:
    def test_only_item_and_tool_type(self):
        assert set(_table("tools").c.keys()) == {"item_id", "tool_type_code"}


class TestContainers:
    def test_columns_and_check(self):
        table = _table("containers")
        assert set(table.c.keys()) == {"item_id", "capacity_weight_lb"}
        assert isinstance(table.c.capacity_weight_lb.type, Numeric)
        assert table.c.capacity_weight_lb.nullable is False
        assert "capacity_weight_lb > 0" in _check_text("containers", "ck_containers_capacity_weight_lb")


class TestItemContents:
    def test_columns_and_checks(self):
        table = _table("item_contents")
        assert set(table.c.keys()) == {"pack_item_id", "item_id", "quantity"}
        assert table.c.quantity.nullable is False
        assert "quantity >= 1" in _check_text("item_contents", "ck_item_contents_quantity")
        assert "pack_item_id <> item_id" in _check_text("item_contents", "ck_item_contents_not_self")


@pytest.mark.parametrize("table", ["character_inventory", "class_initial_equipment", "background_initial_equipment"])
def test_tables_pointing_at_items_are_unchanged(table):
    fk = _fk(table, "item_id")
    assert fk.target_fullname == "item_definitions.id"
    assert fk.ondelete is None
