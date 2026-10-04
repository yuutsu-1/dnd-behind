"""Metadata-level checks for the SRD reference tables (phase 1 of the model redesign)."""
import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

import app.db.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base

CODE_TABLES = [
    "ability_scores", "skills", "damage_types", "conditions", "creature_types", "sizes",
    "alignments", "languages", "senses", "movement_modes",
    "weapon_categories", "weapon_properties", "weapon_masteries", "armor_categories", "tool_categories",
    "spell_schools", "recharge_types", "action_types",
    "challenge_ratings", "feat_categories", "tool_proficiency_options",
]
KEYED_TABLES = {"character_levels": "level", "point_buy_costs": "score"}
REFERENCE_TABLES = CODE_TABLES + list(KEYED_TABLES)


def _table(name):
    assert name in Base.metadata.tables, f"table {name} not registered"
    return Base.metadata.tables[name]


def _fk(table_name, column_name):
    fks = list(_table(table_name).c[column_name].foreign_keys)
    assert len(fks) == 1, f"{table_name}.{column_name} should have exactly one FK"
    return fks[0]


def _check_texts(table_name) -> list[str]:
    return [
        str(c.sqltext) for c in _table(table_name).constraints if isinstance(c, CheckConstraint)
    ]


def _unique_column_sets(table_name) -> list[set[str]]:
    table = _table(table_name)
    sets = [{c.name for c in uc.columns} for uc in table.constraints if isinstance(uc, UniqueConstraint)]
    sets += [{c.name} for c in table.columns if c.unique]
    return sets


def test_there_are_23_reference_tables():
    assert len(REFERENCE_TABLES) == 23
    for name in REFERENCE_TABLES:
        _table(name)


@pytest.mark.parametrize("name", CODE_TABLES)
def test_code_tables_follow_the_common_pattern(name):
    table = _table(name)
    assert [c.name for c in table.primary_key.columns] == ["code"]
    assert table.c.code.type.length == 50
    assert table.c.name.nullable is False
    assert table.c.description.nullable is True
    for col in ("source", "is_homebrew", "created_by"):
        assert col in table.c
    assert "id" not in table.c
    assert "created_at" not in table.c
    assert {"name"} not in _unique_column_sets(name)
    assert _fk(name, "created_by").target_fullname == "users.id"
    assert table.c.created_by.nullable is True


@pytest.mark.parametrize("name,key", list(KEYED_TABLES.items()))
def test_keyed_tables_have_numeric_pk_and_no_name(name, key):
    table = _table(name)
    assert [c.name for c in table.primary_key.columns] == [key]
    assert "name" not in table.c
    assert "description" not in table.c
    assert "code" not in table.c
    for col in ("source", "is_homebrew", "created_by"):
        assert col in table.c


def test_no_new_table_uses_jsonb():
    for name in REFERENCE_TABLES + ["condition_implications", "campaign_homebrew_rules"]:
        for col in _table(name).columns:
            assert not isinstance(col.type, JSONB), f"{name}.{col.name} is JSONB"


def test_challenge_ratings_columns():
    table = _table("challenge_ratings")
    assert "xp" not in table.c
    assert {"numeric_value", "proficiency_bonus"} <= set(table.c.keys())
    assert {"numeric_value"} in _unique_column_sets("challenge_ratings")


def test_sizes_columns():
    table = _table("sizes")
    assert "space_ft" not in table.c
    assert {"hit_die", "carry_multiplier", "sort_order"} <= set(table.c.keys())
    assert {"sort_order"} in _unique_column_sets("sizes")
    checks = " ".join(_check_texts("sizes"))
    assert "hit_die > 0" in checks
    assert "carry_multiplier > 0" in checks


def test_languages_rarity_check():
    assert any("rarity" in t and "standard" in t and "rare" in t for t in _check_texts("languages"))
    assert _table("languages").c.rarity.nullable is False


def test_character_levels_checks():
    checks = " ".join(_check_texts("character_levels"))
    assert "level >= 1" in checks
    assert "min_xp >= 0" in checks
    assert "proficiency_bonus >= 0" in checks


def test_point_buy_costs_check():
    assert "cost >= 0" in " ".join(_check_texts("point_buy_costs"))


def test_challenge_ratings_proficiency_bonus_check():
    assert "proficiency_bonus >= 0" in " ".join(_check_texts("challenge_ratings"))


def test_skills_ability_code_is_restrict_fk():
    assert _table("skills").c.ability_code.nullable is False
    fk = _fk("skills", "ability_code")
    assert fk.target_fullname == "ability_scores.code"
    assert fk.ondelete == "RESTRICT"


def test_condition_implications_structure():
    table = _table("condition_implications")
    assert {c.name for c in table.primary_key.columns} == {"condition_code", "implied_condition_code"}
    outgoing = _fk("condition_implications", "condition_code")
    incoming = _fk("condition_implications", "implied_condition_code")
    assert outgoing.target_fullname == "conditions.code"
    assert outgoing.ondelete == "CASCADE"
    assert incoming.target_fullname == "conditions.code"
    assert incoming.ondelete == "RESTRICT"
    assert any("condition_code <> implied_condition_code" in t for t in _check_texts("condition_implications"))


def test_campaign_homebrew_rules_structure():
    table = _table("campaign_homebrew_rules")
    assert set(table.c.keys()) == {"resource_table", "resource_key", "campaign_id"}
    assert {c.name for c in table.primary_key.columns} == {"resource_table", "resource_key", "campaign_id"}
    fk = _fk("campaign_homebrew_rules", "campaign_id")
    assert fk.target_fullname == "campaigns.id"
    assert fk.ondelete == "CASCADE"
    assert not table.c.resource_key.foreign_keys
    assert not table.c.resource_table.foreign_keys


def test_campaign_homebrew_rules_resource_table_is_restricted_to_reference_tables():
    checks = " ".join(_check_texts("campaign_homebrew_rules"))
    for name in REFERENCE_TABLES:
        assert f"'{name}'" in checks
    assert "'condition_implications'" not in checks
