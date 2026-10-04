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


def test_get_or_create_service_module_is_gone():
    assert not os.path.exists(os.path.join(BACKEND_DIR, "app", "services", "compendium.py"))
