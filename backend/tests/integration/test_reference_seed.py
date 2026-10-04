"""The squashed initial migration seeds the SRD 2024 reference tables."""
from decimal import Decimal

import pytest
from sqlalchemy import text

EXPECTED_COUNTS = {
    "ability_scores": 6,
    "skills": 18,
    "damage_types": 13,
    "conditions": 15,
    "condition_implications": 5,
    "creature_types": 14,
    "sizes": 6,
    "alignments": 10,
    "languages": 19,
    "senses": 4,
    "movement_modes": 5,
    "weapon_categories": 2,
    "weapon_properties": 10,
    "weapon_masteries": 8,
    "armor_categories": 4,
    "tool_categories": 3,
    "spell_schools": 8,
    "recharge_types": 5,
    "action_types": 3,
    "feat_categories": 4,
    "character_levels": 20,
    "challenge_ratings": 34,
    "point_buy_costs": 8,
    "tool_proficiency_options": 25,
}

SEEDED_REFERENCE_TABLES = [t for t in EXPECTED_COUNTS if t != "condition_implications"]


async def _scalar(db_session, sql: str, **params):
    return (await db_session.execute(text(sql), params)).scalar_one()


@pytest.mark.parametrize("table,expected", list(EXPECTED_COUNTS.items()))
async def test_seed_counts(db_session, table, expected):
    # Only SRD rows: tests may leave no homebrew behind (transactions are rolled
    # back), but filter anyway so the check is about the seed.
    if table == "condition_implications":
        count = await _scalar(db_session, "SELECT count(*) FROM condition_implications")
    else:
        count = await _scalar(db_session, f"SELECT count(*) FROM {table} WHERE source = 'srd'")
    assert count == expected


@pytest.mark.parametrize("table", SEEDED_REFERENCE_TABLES)
async def test_every_seed_row_is_srd_and_not_homebrew(db_session, table):
    bad = await _scalar(
        db_session,
        f"SELECT count(*) FROM {table} WHERE source = 'srd' AND (is_homebrew OR created_by IS NOT NULL)",
    )
    assert bad == 0
    non_srd = await _scalar(db_session, f"SELECT count(*) FROM {table} WHERE source <> 'srd'")
    assert non_srd == 0


async def test_ability_score_codes(db_session):
    rows = (await db_session.execute(text("SELECT code, name FROM ability_scores ORDER BY code"))).all()
    assert dict(rows) == {
        "cha": "Charisma", "con": "Constitution", "dex": "Dexterity",
        "int": "Intelligence", "str": "Strength", "wis": "Wisdom",
    }


async def test_skills_map_to_srd_abilities(db_session):
    rows = dict((await db_session.execute(text("SELECT code, ability_code FROM skills"))).all())
    assert rows == {
        "acrobatics": "dex", "sleight_of_hand": "dex", "stealth": "dex",
        "athletics": "str",
        "arcana": "int", "history": "int", "investigation": "int", "nature": "int", "religion": "int",
        "animal_handling": "wis", "insight": "wis", "medicine": "wis", "perception": "wis", "survival": "wis",
        "deception": "cha", "intimidation": "cha", "performance": "cha", "persuasion": "cha",
    }


async def test_sizes_values(db_session):
    rows = {
        r.code: (r.hit_die, r.carry_multiplier, r.sort_order)
        for r in (await db_session.execute(text("SELECT * FROM sizes"))).all()
    }
    assert rows == {
        "tiny": (4, Decimal("7.5"), 1),
        "small": (6, Decimal("15"), 2),
        "medium": (8, Decimal("15"), 3),
        "large": (10, Decimal("30"), 4),
        "huge": (12, Decimal("60"), 5),
        "gargantuan": (20, Decimal("120"), 6),
    }


async def test_character_levels_spot_values(db_session):
    rows = {
        r.level: (r.min_xp, r.proficiency_bonus)
        for r in (await db_session.execute(text("SELECT * FROM character_levels"))).all()
    }
    assert sorted(rows) == list(range(1, 21))
    assert rows[1] == (0, 2)
    assert rows[5] == (6500, 3)
    assert rows[20] == (355000, 6)


async def test_challenge_ratings_spot_values(db_session):
    rows = {
        r.code: (r.name, r.numeric_value, r.proficiency_bonus)
        for r in (await db_session.execute(text("SELECT * FROM challenge_ratings"))).all()
    }
    assert rows["0"] == ("0", Decimal("0"), 2)
    assert rows["1_8"] == ("1/8", Decimal("0.125"), 2)
    assert rows["1_4"] == ("1/4", Decimal("0.25"), 2)
    assert rows["1_2"] == ("1/2", Decimal("0.5"), 2)
    assert rows["4"][2] == 2
    assert rows["5"][2] == 3
    assert rows["17"][2] == 6
    assert rows["30"] == ("30", Decimal("30"), 9)
    assert {str(n) for n in range(1, 31)} <= set(rows)


async def test_point_buy_costs(db_session):
    rows = dict((await db_session.execute(text("SELECT score, cost FROM point_buy_costs"))).all())
    assert rows == {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}


async def test_languages_rarity(db_session):
    rows = dict((await db_session.execute(text("SELECT code, rarity FROM languages"))).all())
    assert rows["thieves_cant"] == "rare"
    assert rows["common"] == "standard"
    assert sum(1 for r in rows.values() if r == "standard") == 10
    assert sum(1 for r in rows.values() if r == "rare") == 9


async def test_condition_implications(db_session):
    rows = set((await db_session.execute(
        text("SELECT condition_code, implied_condition_code FROM condition_implications")
    )).all())
    assert rows == {
        ("paralyzed", "incapacitated"),
        ("petrified", "incapacitated"),
        ("stunned", "incapacitated"),
        ("unconscious", "incapacitated"),
        ("unconscious", "prone"),
    }


async def test_tool_proficiency_options_include_generic_sets(db_session):
    codes = set((await db_session.execute(text("SELECT code FROM tool_proficiency_options"))).scalars())
    assert {"alchemists_supplies", "thieves_tools", "gaming_set", "musical_instrument", "woodcarvers_tools"} <= codes


async def test_legacy_tables_do_not_exist(db_session):
    for name in ("ability_score_options", "skill_definitions", "armor_proficiency_options", "weapon_proficiency_options"):
        assert await _scalar(db_session, "SELECT to_regclass(:n) IS NULL", n=name)
    assert await _scalar(db_session, "SELECT count(*) FROM pg_type WHERE typname = 'creaturesize'") == 0


async def test_single_alembic_revision_applied(db_session):
    assert await _scalar(db_session, "SELECT version_num FROM alembic_version") == "c1fcfd7fe014"
