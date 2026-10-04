"""The migration history is a single squashed revision (phases 1 and 2 rewrite it)."""
import os

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
