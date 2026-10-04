"""The migration history is a single squashed revision (phase 1 rewrites it)."""
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
