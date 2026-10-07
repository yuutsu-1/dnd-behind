"""The migration history is a single squashed revision (phases 1 and 2 rewrite it)."""
import os

import pytest

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _script_directory() -> ScriptDirectory:
    config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    return ScriptDirectory.from_config(config)


def test_history_has_a_single_revision():
    revisions = list(_script_directory().walk_revisions())
    assert [r.revision for r in revisions] == ["c1fcfd7fe014"]


def test_character_skills_revision_file_is_gone():
    versions = os.listdir(os.path.join(BACKEND_DIR, "alembic", "versions"))
    assert not any(name.startswith("a7d3e91b4c52") for name in versions)


def test_squash_does_not_reference_legacy_lookups():
    path = os.path.join(BACKEND_DIR, "alembic", "versions", "c1fcfd7fe014_initial_schema.py")
    source = open(path, encoding="utf-8").read()
    for legacy in ("ability_score_options", "skill_definitions", "armor_proficiency_options",
                   "weapon_proficiency_options", "creaturesize"):
        assert legacy not in source


PHASE2_REMOVED = (
    "tool_proficiency_options", "ToolProficiencyOption",
    "class_saving_throws", "class_armor_proficiencies", "class_weapon_proficiencies", "class_tool_proficiencies",
    "background_skills", "background_tool_proficiencies",
)


def test_squash_does_not_reference_phase2_removed_tables():
    path = os.path.join(BACKEND_DIR, "alembic", "versions", "c1fcfd7fe014_initial_schema.py")
    source = open(path, encoding="utf-8").read()
    for legacy in PHASE2_REMOVED:
        assert legacy not in source, legacy


def test_squash_creates_phase2_tables():
    path = os.path.join(BACKEND_DIR, "alembic", "versions", "c1fcfd7fe014_initial_schema.py")
    source = open(path, encoding="utf-8").read()
    for table in ("item_types", "tool_types", "weapons", "weapon_property_links", "armors", "tools",
                  "containers", "item_contents", "proficiency_grants", "class_proficiency_grants",
                  "background_proficiency_grants"):
        assert f"op.create_table('{table}'" in source, table
        assert f"op.drop_table('{table}')" in source, table


def test_downgrade_drops_every_table_after_the_tables_that_reference_it():
    """`downgrade()` must drop a table only after every table with a FK to it."""
    import re

    import app.db.models  # noqa: F401
    from app.db.base import Base

    path = os.path.join(BACKEND_DIR, "alembic", "versions", "c1fcfd7fe014_initial_schema.py")
    source = open(path, encoding="utf-8").read()
    downgrade = source[source.index("def downgrade()"):]
    order = re.findall(r"op\.drop_table\('([a-z_]+)'\)", downgrade)
    assert set(order) == set(Base.metadata.tables), "downgrade must drop every table"
    position = {table: index for index, table in enumerate(order)}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            target = fk.column.table.name
            if target != table.name:
                assert position[table.name] < position[target], f"{table.name} must be dropped before {target}"


def _squash_source() -> str:
    path = os.path.join(BACKEND_DIR, "alembic", "versions", "c1fcfd7fe014_initial_schema.py")
    return open(path, encoding="utf-8").read()


# Phase 3: old spell columns/tables and the ones dropped by the gate #2 review.
PHASE3_REMOVED = (
    "spell_class_lists", "material_component", "time_units", "range_types", "duration_types", "spell_areas",
    "casting_trigger", "'components'",
)


@pytest.mark.parametrize("legacy", PHASE3_REMOVED)
def test_squash_does_not_reference_phase3_removed_names(legacy):
    assert legacy not in _squash_source()


@pytest.mark.parametrize("table", ["area_shapes", "spell_lists", "casting_times", "spell_materials", "spell_list_spells"])
def test_squash_creates_and_drops_phase3_tables(table):
    source = _squash_source()
    assert f"op.create_table('{table}'" in source
    assert f"op.drop_table('{table}')" in source


def test_squash_share_check_lists_the_33_reference_tables():
    from app.db.models.reference import REFERENCE_TABLE_NAMES

    source = _squash_source()
    expected = "resource_table IN (" + ", ".join(f"'{name}'" for name in REFERENCE_TABLE_NAMES) + ")"
    assert expected in source


def test_squash_spell_name_is_not_unique():
    source = _squash_source()
    spells = source[source.index("op.create_table('spell_definitions'"):]
    spells = spells[:spells.index("op.create_table(", 10)]
    assert "UniqueConstraint('name')" not in spells


# Phase 4: FeatureGrant (JSONB effect_data) and the old feat columns are gone.
PHASE4_REMOVED = ("feature_grants", "effect_data", "effect_type", "level_prerequisite", "prerequisite_description")


@pytest.mark.parametrize("legacy", PHASE4_REMOVED)
def test_squash_does_not_reference_phase4_removed_names(legacy):
    assert legacy not in _squash_source()


PHASE4_TABLES = (
    "effect_operations", "effect_targets", "value_bases", "choice_pool_types", "choice_swap_rules", "feature_kinds",
    "feat_prerequisites", "feature_definitions", "feature_effects", "feature_choices", "feature_choice_options",
    "feature_resources", "feature_resource_recharges", "feature_scaling",
)


@pytest.mark.parametrize("table", PHASE4_TABLES)
def test_squash_creates_and_drops_phase4_tables(table):
    source = _squash_source()
    assert f"op.create_table('{table}'" in source
    assert f"op.drop_table('{table}')" in source


def test_squash_feat_name_is_not_unique_and_has_category_code():
    source = _squash_source()
    feats = source[source.index("op.create_table('feat_definitions'"):]
    feats = feats[:feats.index("op.create_table(", 10)]
    assert "UniqueConstraint('name')" not in feats
    assert "sa.Column('category_code'" in feats
    assert "sa.Column('category'," not in feats


def test_squash_class_name_stays_unique():
    """Gate #2, B1: the class name stays UNIQUE."""
    source = _squash_source()
    classes = source[source.index("op.create_table('class_definitions'"):]
    classes = classes[:classes.index("op.create_table(", 10)]
    assert "sa.UniqueConstraint('name')" in classes
