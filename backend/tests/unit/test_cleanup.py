"""No leftovers of the pre-phase-1 model (lookups with get-or-create, enums) in app/alembic.

Same intent as the spec's grep. `\\bAbilityScore\\b` is anchored on both sides so the
`CharacterAbilityScore` model (kept by the spec; only its column was renamed) does not match.
"""
import os
import re

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FORBIDDEN = re.compile(
    r"\bAbilityScore\b|CreatureSize|ability_score_options|skill_definitions"
    r"|ensure_ability_score_options|_resolve_options|resolve_skills|SkillDefinition"
)


def _python_files(*roots):
    for root in roots:
        for dirpath, _, filenames in os.walk(os.path.join(BACKEND_DIR, root)):
            if "__pycache__" in dirpath:
                continue
            for name in filenames:
                if name.endswith(".py"):
                    yield os.path.join(dirpath, name)


@pytest.mark.parametrize("path", sorted(_python_files("app", "alembic")))
def test_no_legacy_symbols(path):
    with open(path, encoding="utf-8") as handle:
        offending = [
            f"{os.path.relpath(path, BACKEND_DIR)}:{number}: {line.strip()}"
            for number, line in enumerate(handle, start=1)
            if FORBIDDEN.search(line)
        ]
    assert offending == []


# Phase 2: the spec's grep (tool_proficiency_options and the six old proficiency tables).
PHASE2_FORBIDDEN = re.compile(
    r"tool_proficiency_options|ToolProficiencyOption|class_saving_throws|class_armor_proficiencies"
    r"|class_weapon_proficiencies|class_tool_proficiencies|background_skills|background_tool_proficiencies"
)


@pytest.mark.parametrize("path", sorted(_python_files("app", "alembic")))
def test_no_phase2_legacy_symbols(path):
    with open(path, encoding="utf-8") as handle:
        offending = [
            f"{os.path.relpath(path, BACKEND_DIR)}:{number}: {line.strip()}"
            for number, line in enumerate(handle, start=1)
            if PHASE2_FORBIDDEN.search(line)
        ]
    assert offending == []


def test_item_definition_has_no_jsonb_column():
    from sqlalchemy.dialects.postgresql import JSONB

    from app.db.models.compendium import ItemDefinition

    assert not any(isinstance(col.type, JSONB) for col in ItemDefinition.__table__.columns)


def test_get_or_create_service_module_is_gone():
    assert not os.path.exists(os.path.join(BACKEND_DIR, "app", "services", "compendium.py"))


# Phase 3: the spec's grep (old spell class lists and the textual material column).
PHASE3_FORBIDDEN = re.compile(r"spell_class_lists|material_component")


@pytest.mark.parametrize("path", sorted(_python_files("app", "alembic")))
def test_no_phase3_legacy_symbols(path):
    with open(path, encoding="utf-8") as handle:
        offending = [
            f"{os.path.relpath(path, BACKEND_DIR)}:{number}: {line.strip()}"
            for number, line in enumerate(handle, start=1)
            if PHASE3_FORBIDDEN.search(line)
        ]
    assert offending == []


def test_only_two_jsonb_columns_left_in_the_compendium():
    """The spec's grep would also match the JSONB import line, so check the metadata."""
    from sqlalchemy.dialects.postgresql import JSONB

    import app.db.models.compendium as compendium
    import app.db.models.items as items
    import app.db.models.spells as spells
    from app.db.base import Base

    modules = (compendium, items, spells)
    tables = {
        table for table in Base.metadata.tables.values()
        if any(getattr(module, name, None) is table or getattr(getattr(module, name, None), "__table__", None) is table
               for module in modules for name in dir(module))
    }
    assert {"spell_definitions", "spell_materials", "spell_list_spells", "item_definitions"} <= {t.name for t in tables}
    jsonb = sorted(f"{t.name}.{c.name}" for t in tables for c in t.columns if isinstance(c.type, JSONB))
    assert jsonb == ["feature_grants.effect_data", "species_definitions.special_traits"]


# Tests never read the SRD files: they are reference only (built so this file does not match itself).
DOCS_REFERENCE = re.compile(r"\b" + "docs" + r"[/\\]")


@pytest.mark.parametrize("path", sorted(_python_files("tests")))
def test_tests_do_not_reference_the_docs_folder(path):
    with open(path, encoding="utf-8") as handle:
        offending = [
            f"{os.path.relpath(path, BACKEND_DIR)}:{number}: {line.strip()}"
            for number, line in enumerate(handle, start=1)
            if DOCS_REFERENCE.search(line)
        ]
    assert offending == []
