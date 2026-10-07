"""The squash seeds the 17 SRD feats, the Fighter class and the Champion subclass with
all their features (fixed numbers of the phase 4 plan, with gate #2 H5: Survivor's
"Defy Death" is one more effect)."""
import uuid

import pytest
from sqlalchemy import text

from tests.integration.conftest import squash_namespace


def _feature_id(key: str) -> uuid.UUID:
    return uuid.uuid5(squash_namespace("SRD_FEATURE_NAMESPACE"), key)


def _fighter_id() -> uuid.UUID:
    return uuid.uuid5(squash_namespace("SRD_CLASS_NAMESPACE"), "Fighter")


async def _scalar(db_session, sql: str, **params):
    return (await db_session.execute(text(sql), params)).scalar_one()


async def _rows(db_session, sql: str, **params):
    return (await db_session.execute(text(sql), params)).all()


SRD_COUNTS = {
    "feat_definitions": 17,
    "feature_definitions": 58,
    "class_definitions": 1,
    "subclass_definitions": 1,
}
TOTALS = {
    "feat_prerequisites": 16,
    "feature_effects": 45,
    "feature_choices": 20,
    "feature_choice_options": 7,
    "feature_resources": 4,
    "feature_resource_recharges": 8,
    "feature_scaling": 8,
    "proficiency_grants": 8,
}


@pytest.mark.parametrize("table,expected", list(SRD_COUNTS.items()))
async def test_srd_counts(db_session, table, expected):
    assert await _scalar(db_session, f"SELECT count(*) FROM {table} WHERE source = 'srd'") == expected


@pytest.mark.parametrize("table,expected", list(TOTALS.items()))
async def test_totals(db_session, table, expected):
    assert await _scalar(db_session, f"SELECT count(*) FROM {table}") == expected


@pytest.mark.parametrize("table", ["feat_definitions", "feature_definitions", "class_definitions",
                                   "subclass_definitions"])
async def test_seed_rows_are_srd(db_session, table):
    bad = await _scalar(
        db_session, f"SELECT count(*) FROM {table} WHERE source = 'srd' AND (is_homebrew OR created_by IS NOT NULL)"
    )
    assert bad == 0


async def test_feat_categories(db_session):
    rows = await _rows(db_session, "SELECT category_code, count(*) FROM feat_definitions GROUP BY category_code")
    assert dict(rows) == {"origin": 4, "general": 2, "fighting_style": 4, "epic_boon": 7}


async def test_feature_owners(db_session):
    rows = await _rows(db_session, """
        SELECT count(*) FILTER (WHERE class_id IS NOT NULL), count(*) FILTER (WHERE subclass_id IS NOT NULL),
               count(*) FILTER (WHERE feat_id IS NOT NULL)
        FROM feature_definitions""")
    assert tuple(rows[0]) == (20, 6, 32)


async def test_feat_ids_are_uuid5_of_the_name(db_session):
    grappler = uuid.uuid5(squash_namespace("SRD_FEAT_NAMESPACE"), "Grappler")
    assert await _scalar(db_session, "SELECT name FROM feat_definitions WHERE id = :id", id=grappler) == "Grappler"


async def test_grappler(db_session):
    grappler = uuid.uuid5(squash_namespace("SRD_FEAT_NAMESPACE"), "Grappler")
    prereqs = await _rows(db_session, """
        SELECT or_group, min_character_level, ability_code, min_score, feature_kind_code
        FROM feat_prerequisites WHERE feat_id = :id ORDER BY or_group, ability_code DESC""", id=grappler)
    assert [tuple(row) for row in prereqs] == [(1, 4, None, None, None), (2, None, "str", 13, None),
                                              (2, None, "dex", 13, None)]
    asi = _feature_id("feat:Grappler/-/Ability Score Increase")
    effect = (await _rows(db_session, """
        SELECT e.operation_code, e.value, e.max_value, c.pool_type_code, c.choose_count, c.allow_repeat, c.id
        FROM feature_effects e JOIN feature_choices c ON c.effect_id = e.id WHERE e.feature_id = :id""", id=asi))[0]
    assert tuple(effect[:6]) == ("ability_score_increase", 1, 20, "ability_score", 1, False)
    options = await _rows(db_session, "SELECT ability_code FROM feature_choice_options WHERE choice_id = :id "
                                      "ORDER BY ability_code", id=effect[6])
    assert [row[0] for row in options] == ["dex", "str"]
    assert await _scalar(db_session, "SELECT count(*) FROM feature_definitions WHERE feat_id = :id", id=grappler) == 4


async def test_boon_of_fate_resource(db_session):
    resource = (await _rows(db_session, """
        SELECT r.id, r.name, r.value FROM feature_resources r WHERE r.feature_id = :id""",
        id=_feature_id("feat:Boon of Fate/-/Improve Fate")))[0]
    assert tuple(resource[1:]) == ("Improve Fate", 1)
    recharges = await _rows(db_session, "SELECT recharge_type_code, recovers FROM feature_resource_recharges "
                                        "WHERE resource_id = :id ORDER BY recharge_type_code", id=resource[0])
    assert [tuple(r) for r in recharges] == [("initiative", None), ("long_rest", None), ("short_rest", None)]


# --- Fighter and Champion ------------------------------------------------------------

async def test_fighter_class(db_session):
    row = (await _rows(db_session, "SELECT name, hit_die, skill_choices, subclass_level, spell_ability, description "
                                   "FROM class_definitions WHERE id = :id", id=_fighter_id()))[0]
    assert tuple(row) == ("Fighter", 10, 2, 3, None, None)
    fighter = _fighter_id()
    primary = await _rows(db_session, "SELECT ability_code FROM class_primary_abilities WHERE class_id = :id "
                                      "ORDER BY ability_code", id=fighter)
    assert [r[0] for r in primary] == ["dex", "str"]
    skills = await _rows(db_session, "SELECT skill_code FROM class_skills WHERE class_id = :id", id=fighter)
    assert len(skills) == 9
    grants = await _rows(db_session, """
        SELECT coalesce(g.saving_throw_ability_code, g.weapon_category_code, g.armor_category_code)
        FROM class_proficiency_grants l JOIN proficiency_grants g ON g.id = l.grant_id WHERE l.class_id = :id""",
        id=fighter)
    assert sorted(r[0] for r in grants) == sorted(
        ["str", "con", "simple", "martial", "light", "medium", "heavy", "shield"]
    )
    equipment = await _rows(db_session, """
        SELECT e.option, i.name, e.quantity FROM class_initial_equipment e JOIN item_definitions i ON i.id = e.item_id
        WHERE e.class_id = :id""", id=fighter)
    assert len(equipment) == 15
    assert ("A", "Javelin", 8) in [tuple(r) for r in equipment]
    assert ("C", "Gold Piece", 155) in [tuple(r) for r in equipment]


async def test_champion_belongs_to_the_fighter(db_session):
    champion = uuid.uuid5(squash_namespace("SRD_SUBCLASS_NAMESPACE"), "Champion")
    row = (await _rows(db_session, "SELECT class_id, name, description FROM subclass_definitions WHERE id = :id",
                       id=champion))[0]
    assert row[0] == _fighter_id()
    assert row[1] == "Champion"
    assert row[2].startswith("_Pursue Physical Excellence in Combat_")
    assert await _scalar(db_session, "SELECT count(*) FROM feature_definitions WHERE subclass_id = :id",
                         id=champion) == 6


async def test_fighter_feature_levels(db_session):
    rows = await _rows(db_session, "SELECT level FROM feature_definitions WHERE class_id = :id "
                                   "AND name = 'Ability Score Improvement' ORDER BY level", id=_fighter_id())
    assert [r[0] for r in rows] == [4, 6, 8, 12, 14, 16]


async def test_second_wind(db_session):
    feature = _feature_id("class:Fighter/1/Second Wind")
    row = (await _rows(db_session, "SELECT name, level, action_type_code, class_id FROM feature_definitions "
                                   "WHERE id = :id", id=feature))[0]
    assert tuple(row) == ("Second Wind", 1, "bonus_action", _fighter_id())
    effect = (await _rows(db_session, """
        SELECT operation_code, target_code, dice_count, die_size, value_basis_code, value_multiplier
        FROM feature_effects WHERE feature_id = :id""", id=feature))[0]
    assert tuple(effect) == ("heal", "hit_points", 1, 10, "class_level", 1)
    resource = (await _rows(db_session, "SELECT id, name, value FROM feature_resources WHERE feature_id = :id",
                            id=feature))[0]
    assert tuple(resource[1:]) == ("Second Wind", 2)
    recharges = await _rows(db_session, "SELECT recharge_type_code, recovers FROM feature_resource_recharges "
                                        "WHERE resource_id = :id ORDER BY recharge_type_code", id=resource[0])
    assert [tuple(r) for r in recharges] == [("long_rest", None), ("short_rest", 1)]
    scaling = await _rows(db_session, "SELECT level, value FROM feature_scaling WHERE resource_id = :id "
                                      "ORDER BY level", id=resource[0])
    assert [tuple(r) for r in scaling] == [(4, 3), (10, 4)]


async def test_weapon_mastery(db_session):
    feature = _feature_id("class:Fighter/1/Weapon Mastery")
    choice = (await _rows(db_session, """
        SELECT c.id, e.operation_code, c.pool_type_code, c.choose_count, c.swap_rule_code, c.weapon_category_code
        FROM feature_effects e JOIN feature_choices c ON c.effect_id = e.id WHERE e.feature_id = :id""",
        id=feature))[0]
    assert tuple(choice[1:]) == ("grant", "weapon", 3, "on_long_rest_one", None)
    scaling = await _rows(db_session, "SELECT level, value FROM feature_scaling WHERE choice_id = :id "
                                      "ORDER BY level", id=choice[0])
    assert [tuple(r) for r in scaling] == [(4, 4), (10, 5), (16, 6)]


async def test_extra_attack_chain(db_session):
    extra = _feature_id("class:Fighter/5/Extra Attack")
    two = _feature_id("class:Fighter/11/Two Extra Attacks")
    three = _feature_id("class:Fighter/20/Three Extra Attacks")
    rows = {
        r[0]: (r[1], r[2], r[3]) for r in await _rows(db_session, """
            SELECT f.id, f.replaces_feature_id, e.target_code, e.value FROM feature_definitions f
            JOIN feature_effects e ON e.feature_id = f.id WHERE f.id IN (:a, :b, :c)""", a=extra, b=two, c=three)
    }
    assert rows == {
        extra: (None, "attacks_per_action", 2),
        two: (extra, "attacks_per_action", 3),
        three: (two, "attacks_per_action", 4),
    }


async def test_superior_critical_replaces_improved_critical(db_session):
    improved = _feature_id("subclass:Champion/3/Improved Critical")
    superior = _feature_id("subclass:Champion/15/Superior Critical")
    assert await _scalar(db_session, "SELECT replaces_feature_id FROM feature_definitions WHERE id = :id",
                         id=superior) == improved


async def test_survivor_has_the_defy_death_advantage(db_session):
    rows = await _rows(db_session, "SELECT operation_code, target_code, condition_text FROM feature_effects "
                                   "WHERE feature_id = :id", id=_feature_id("subclass:Champion/18/Survivor"))
    assert [tuple(r) for r in rows] == [("advantage", "death_saving_throw", None)]


async def test_fighting_style_kind(db_session):
    rows = await _rows(db_session, "SELECT name FROM feature_definitions WHERE feature_kind_code = 'fighting_style' "
                                   "ORDER BY name")
    assert [r[0] for r in rows] == ["Additional Fighting Style", "Fighting Style"]
