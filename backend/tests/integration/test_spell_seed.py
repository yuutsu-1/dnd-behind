"""The squashed migration seeds the 339 SRD 2024 spells, their materials and list links
(checked by SQL against the test database, with the fixed numbers of the plan)."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests.integration.conftest import _srd_spell_namespace, srd_spell_id


async def _scalar(db_session, sql: str, **params):
    return (await db_session.execute(text(sql), params)).scalar_one()


async def _rows(db_session, sql: str, **params):
    return (await db_session.execute(text(sql), params)).all()


SRD = "source = 'srd'"


@pytest.mark.parametrize("where,expected", [
    ("TRUE", 339),
    ("level = 0", 27),
    ("ritual", 29),
    ("concentration", 133),
    ("higher_levels IS NOT NULL OR cantrip_upgrade IS NOT NULL", 124),
    ("has_material", 189),
    ("area IS NOT NULL", 91),
])
async def test_spell_counts(db_session, where, expected):
    assert await _scalar(db_session, f"SELECT count(*) FROM spell_definitions WHERE {SRD} AND ({where})") == expected


async def test_every_seed_spell_is_srd_and_not_homebrew(db_session):
    bad = await _scalar(
        db_session, f"SELECT count(*) FROM spell_definitions WHERE {SRD} AND (is_homebrew OR created_by IS NOT NULL)"
    )
    assert bad == 0
    assert await _scalar(db_session, "SELECT count(DISTINCT name) FROM spell_definitions WHERE source = 'srd'") == 339


async def test_193_material_rows_and_879_list_links(db_session):
    materials = await _scalar(
        db_session,
        f"SELECT count(*) FROM spell_materials m JOIN spell_definitions s ON s.id = m.spell_id WHERE s.{SRD}",
    )
    assert materials == 193
    links = await _scalar(
        db_session,
        f"SELECT count(*) FROM spell_list_spells l JOIN spell_definitions s ON s.id = l.spell_id WHERE s.{SRD}",
    )
    assert links == 879


async def test_has_material_iff_materials(db_session):
    incoherent = await _scalar(db_session, f"""
        SELECT count(*) FROM spell_definitions s
        WHERE s.{SRD} AND s.has_material <> EXISTS (SELECT 1 FROM spell_materials m WHERE m.spell_id = s.id)
    """)
    assert incoherent == 0


async def test_every_srd_spell_has_a_list(db_session):
    without = await _scalar(db_session, f"""
        SELECT count(*) FROM spell_definitions s
        WHERE s.{SRD} AND NOT EXISTS (SELECT 1 FROM spell_list_spells l WHERE l.spell_id = s.id)
    """)
    assert without == 0


async def test_casting_time_distribution(db_session):
    rows = await _rows(
        db_session, f"SELECT casting_time_code, count(*) FROM spell_definitions WHERE {SRD} GROUP BY 1"
    )
    assert dict(rows) == {
        "action": 257, "bonus_action": 23, "reaction": 4, "1_minute": 28, "10_minutes": 13,
        "1_hour": 11, "8_hours": 1, "12_hours": 1, "24_hours": 1,
    }


async def test_conditional_casting_times_are_in_the_description(db_session):
    rows = await _rows(db_session, f"""
        SELECT casting_time_code, count(*) FROM spell_definitions
        WHERE {SRD} AND description LIKE '%' || chr(10) || chr(10) || 'Casting Time: % which you take %'
        GROUP BY 1
    """)
    assert dict(rows) == {"reaction": 4, "bonus_action": 4}


async def test_area_shape_distribution(db_session):
    rows = await _rows(
        db_session,
        f"SELECT area_shape_code, count(*) FROM spell_definitions WHERE {SRD} AND area_shape_code IS NOT NULL GROUP BY 1",
    )
    assert dict(rows) == {
        "sphere": 28, "cube": 19, "cone": 6, "cylinder": 8, "emanation": 11, "line": 3, "radius": 10, "square": 6,
    }


async def test_list_sizes(db_session):
    rows = await _rows(db_session, f"""
        SELECT l.spell_list_code, count(*) FROM spell_list_spells l
        JOIN spell_definitions s ON s.id = l.spell_id WHERE s.{SRD} GROUP BY 1
    """)
    assert dict(rows) == {
        "bard": 130, "cleric": 109, "druid": 124, "paladin": 38, "ranger": 48,
        "sorcerer": 140, "warlock": 72, "wizard": 218,
    }


async def _spell(db_session, name: str):
    return (await db_session.execute(
        text(f"SELECT * FROM spell_definitions WHERE {SRD} AND name = :name"), {"name": name}
    )).mappings().one()


async def _materials(db_session, name: str) -> list[tuple]:
    return [tuple(r) for r in await _rows(db_session, f"""
        SELECT m.sort_order, m.cost_gp, m.consumed, m.per_target, m.quantity FROM spell_materials m
        JOIN spell_definitions s ON s.id = m.spell_id WHERE s.{SRD} AND s.name = :name ORDER BY m.sort_order
    """, name=name)]


async def _lists(db_session, name: str) -> list[str]:
    return [r[0] for r in await _rows(db_session, f"""
        SELECT l.spell_list_code FROM spell_list_spells l
        JOIN spell_definitions s ON s.id = l.spell_id WHERE s.{SRD} AND s.name = :name ORDER BY 1
    """, name=name)]


async def test_acid_arrow(db_session):
    s = await _spell(db_session, "Acid Arrow")
    assert (s["level"], s["school_code"], s["casting_time_code"], s["range"]) == (2, "evocation", "action", "90 feet")
    assert (s["has_verbal"], s["has_somatic"], s["has_material"]) == (True, True, True)
    assert (s["duration"], s["concentration"], s["ritual"]) == ("Instantaneous", False, False)
    assert s["higher_levels"] and s["cantrip_upgrade"] is None
    assert (s["area"], s["area_shape_code"]) == (None, None)
    assert await _materials(db_session, "Acid Arrow") == [(0, None, False, False, 1)]
    assert await _lists(db_session, "Acid Arrow") == ["wizard"]


async def test_acid_arrow_id_is_uuid5_of_its_name(db_session):
    s = await _spell(db_session, "Acid Arrow")
    assert s["id"] == srd_spell_id("Acid Arrow")


async def test_alarm(db_session):
    s = await _spell(db_session, "Alarm")
    assert (s["casting_time_code"], s["ritual"], s["duration"]) == ("1_minute", True, "8 hours")
    assert (s["area"], s["area_shape_code"]) == ("20-foot Cube", "cube")


async def test_counterspell(db_session):
    s = await _spell(db_session, "Counterspell")
    assert s["casting_time_code"] == "reaction"
    assert s["description"].endswith(
        "\n\nCasting Time: Reaction, which you take when you see a creature within 60 feet of yourself "
        "casting a spell with Verbal, Somatic, or Material components"
    )


@pytest.mark.parametrize("name,area,shape", [
    ("Ice Storm", "20-foot-radius, 40-foot-high Cylinder", "cylinder"),
    ("Lightning Bolt", "100-foot Line, 5 feet wide", "line"),
    ("Light", "20-foot radius", "radius"),
    ("Teleportation Circle", None, None),
])
async def test_areas(db_session, name, area, shape):
    s = await _spell(db_session, name)
    assert (s["area"], s["area_shape_code"]) == (area, shape)


async def test_clone(db_session):
    assert await _materials(db_session, "Clone") == [
        (0, Decimal("1000"), True, False, 1), (1, Decimal("2000"), False, False, 1),
    ]


async def test_gentle_repose(db_session):
    assert await _materials(db_session, "Gentle Repose") == [(0, Decimal("0.01"), True, False, 2)]


async def test_material_ids_are_uuid5(db_session):
    rows = await _rows(db_session, f"""
        SELECT m.id, m.sort_order FROM spell_materials m
        JOIN spell_definitions s ON s.id = m.spell_id WHERE s.{SRD} AND s.name = 'Clone' ORDER BY m.sort_order
    """)
    assert [r[0] for r in rows] == [uuid.uuid5(_srd_spell_namespace(), f"Clone/material/{n}") for n in (0, 1)]
