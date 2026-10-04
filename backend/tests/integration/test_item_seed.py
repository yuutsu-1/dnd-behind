"""The squashed initial migration seeds the SRD 2024 equipment (equipment.md) as
structured items: base rows in `item_definitions` + 1:1 sub-rows per type."""
import importlib.util
import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _migration_module():
    path = os.path.join(BACKEND_DIR, "alembic", "versions", "c1fcfd7fe014_initial_schema.py")
    spec = importlib.util.spec_from_file_location("squash_c1fcfd7fe014", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _scalar(db_session, sql: str, **params):
    return (await db_session.execute(text(sql), params)).scalar_one()


async def _rows(db_session, sql: str, **params):
    return (await db_session.execute(text(sql), params)).all()


async def _item(db_session, name: str):
    return (await db_session.execute(
        text("SELECT * FROM item_definitions WHERE name = :n AND source = 'srd'"), {"n": name}
    )).one()


async def _weapon(db_session, name: str):
    return (await db_session.execute(text(
        "SELECT w.* FROM weapons w JOIN item_definitions i ON i.id = w.item_id WHERE i.name = :n AND i.source = 'srd'"
    ), {"n": name})).one()


async def _properties(db_session, name: str) -> dict:
    rows = await _rows(db_session, """
        SELECT l.property_code, l.range_normal_ft, l.range_long_ft, l.versatile_die_size, a.name AS ammunition
        FROM weapon_property_links l
        JOIN item_definitions i ON i.id = l.weapon_item_id
        LEFT JOIN item_definitions a ON a.id = l.ammunition_item_id
        WHERE i.name = :n AND i.source = 'srd'
    """, n=name)
    return {r.property_code: (r.range_normal_ft, r.range_long_ft, r.versatile_die_size, r.ammunition) for r in rows}


async def _armor(db_session, name: str):
    return (await db_session.execute(text(
        "SELECT a.* FROM armors a JOIN item_definitions i ON i.id = a.item_id WHERE i.name = :n AND i.source = 'srd'"
    ), {"n": name})).one()


# --- counts --------------------------------------------------------------------

@pytest.mark.parametrize("item_type,count", [
    ("currency", 5), ("weapon", 38), ("armor", 13), ("tool", 37), ("ammunition", 5), ("pack", 7),
    ("adventuring_gear", 82),
])
async def test_items_per_type(db_session, item_type, count):
    assert await _scalar(
        db_session, "SELECT count(*) FROM item_definitions WHERE source = 'srd' AND item_type_code = :t", t=item_type
    ) == count


async def test_total_items(db_session):
    assert await _scalar(db_session, "SELECT count(*) FROM item_definitions WHERE source = 'srd'") == 187


@pytest.mark.parametrize("table,count", [
    ("weapons", 38), ("armors", 13), ("tools", 37), ("containers", 4), ("item_contents", 64),
    # Derived by the planner (DV3): "Thrown (Range x/y)" and "Ammunition (Range x/y; Type)" are 2 links each.
    ("weapon_property_links", 86),
])
async def test_sub_table_counts(db_session, table, count):
    owner = "pack_item_id" if table == "item_contents" else (
        "weapon_item_id" if table == "weapon_property_links" else "item_id"
    )
    assert await _scalar(db_session, f"""
        SELECT count(*) FROM {table} t JOIN item_definitions i ON i.id = t.{owner} WHERE i.source = 'srd'
    """) == count


async def test_weapons_by_category_and_range(db_session):
    rows = await _rows(db_session, "SELECT category_code, is_ranged, count(*) FROM weapons GROUP BY 1, 2")
    assert {(c, r): n for c, r, n in rows} == {
        ("simple", False): 10, ("simple", True): 4, ("martial", False): 18, ("martial", True): 6,
    }


async def test_property_link_counts_from_the_srd(db_session):
    # Counted from equipment.md: 7 Thrown + 9 Ammunition weapons -> 16 `range` links.
    # (The plan's DV3 breakdown said 17/10; the table has 9 Ammunition weapons.)
    rows = dict(await _rows(db_session, "SELECT property_code, count(*) FROM weapon_property_links GROUP BY 1"))
    assert rows == {
        "range": 16, "ammunition": 9, "thrown": 7, "versatile": 7, "light": 8, "finesse": 6,
        "heavy": 9, "reach": 5, "two_handed": 13, "loading": 6,
    }


async def test_property_links_per_weapon_group(db_session):
    rows = await _rows(db_session, """
        SELECT w.category_code, w.is_ranged, count(*) FROM weapon_property_links l
        JOIN weapons w ON w.item_id = l.weapon_item_id GROUP BY 1, 2
    """)
    assert {(c, r): n for c, r, n in rows} == {
        ("simple", False): 19, ("simple", True): 12, ("martial", False): 32, ("martial", True): 23,
    }


# --- provenance & coherence ----------------------------------------------------------

async def test_every_seed_item_is_srd(db_session):
    assert await _scalar(db_session, """
        SELECT count(*) FROM item_definitions
        WHERE source = 'srd' AND (is_homebrew OR created_by IS NOT NULL)
    """) == 0
    assert await _scalar(db_session, "SELECT count(*) FROM item_types WHERE source <> 'srd'") == 0


async def test_seed_item_names_are_unique(db_session):
    assert await _scalar(db_session, """
        SELECT count(*) FROM (SELECT name FROM item_definitions WHERE source = 'srd' GROUP BY name HAVING count(*) > 1) d
    """) == 0


async def test_seed_ids_are_deterministic(db_session):
    namespace = _migration_module().SRD_ITEM_NAMESPACE
    rows = await _rows(db_session, "SELECT id, name FROM item_definitions WHERE source = 'srd'")
    assert len(rows) == 187
    for item_id, name in rows:
        assert item_id == uuid.uuid5(namespace, name), name


async def test_every_seed_weapon_has_a_mastery(db_session):
    assert await _scalar(db_session, "SELECT count(*) FROM weapons WHERE mastery_code IS NULL") == 0


SUB_TABLES = {"weapon": "weapons", "armor": "armors", "tool": "tools", "container": "containers"}


async def _sub_row_counts(db_session):
    rows = await _rows(db_session, """
        SELECT i.name, i.item_type_code,
               (SELECT count(*) FROM weapons w WHERE w.item_id = i.id) AS weapon,
               (SELECT count(*) FROM armors a WHERE a.item_id = i.id) AS armor,
               (SELECT count(*) FROM tools t WHERE t.item_id = i.id) AS tool,
               (SELECT count(*) FROM containers c WHERE c.item_id = i.id) AS container,
               (SELECT count(*) FROM item_contents ic WHERE ic.pack_item_id = i.id) AS contents
        FROM item_definitions i WHERE i.source = 'srd'
    """)
    return rows


async def test_type_and_sub_tables_are_coherent(db_session):
    for row in await _sub_row_counts(db_session):
        expected = {"weapon": 0, "armor": 0, "tool": 0, "container": row.container}
        if row.item_type_code in ("weapon", "armor", "tool"):
            expected[row.item_type_code] = 1
        if row.item_type_code != "adventuring_gear":
            expected["container"] = 0
        actual = {key: getattr(row, key) for key in expected}
        assert actual == expected, row.name
        if row.item_type_code == "pack":
            assert row.contents >= 1, row.name
        else:
            assert row.contents == 0, row.name


async def test_containers(db_session):
    rows = dict(await _rows(db_session, """
        SELECT i.name, c.capacity_weight_lb FROM containers c JOIN item_definitions i ON i.id = c.item_id
    """))
    assert rows == {"Backpack": Decimal("30"), "Basket": Decimal("40"), "Pouch": Decimal("6"), "Sack": Decimal("30")}


async def test_contents_never_hold_packs(db_session):
    assert await _scalar(db_session, """
        SELECT count(*) FROM item_contents ic JOIN item_definitions i ON i.id = ic.item_id
        WHERE i.item_type_code = 'pack'
    """) == 0


async def test_tool_items_point_to_the_tool_type_of_the_same_name(db_session):
    rows = await _rows(db_session, """
        SELECT i.name, tt.name AS tool_type_name FROM tools t
        JOIN item_definitions i ON i.id = t.item_id JOIN tool_types tt ON tt.code = t.tool_type_code
    """)
    assert len(rows) == 37
    assert all(name == tool_type_name for name, tool_type_name in rows)


# --- spot values (spec acceptance table) ---------------------------------------------

async def test_dagger(db_session):
    w = await _weapon(db_session, "Dagger")
    assert (w.category_code, w.is_ranged, w.damage_dice_count, w.damage_die_size, w.damage_flat,
            w.damage_type_code, w.mastery_code) == ("simple", False, 1, 4, 0, "piercing", "nick")
    assert await _properties(db_session, "Dagger") == {
        "finesse": (None, None, None, None), "light": (None, None, None, None),
        "thrown": (None, None, None, None), "range": (20, 60, None, None),
    }
    item = await _item(db_session, "Dagger")
    assert (item.cost_gp, item.weight_lb) == (Decimal("2"), Decimal("1"))


async def test_longbow(db_session):
    w = await _weapon(db_session, "Longbow")
    assert (w.category_code, w.is_ranged, w.damage_dice_count, w.damage_die_size) == ("martial", True, 1, 8)
    assert await _properties(db_session, "Longbow") == {
        "ammunition": (None, None, None, "Arrow"), "range": (150, 600, None, None),
        "heavy": (None, None, None, None), "two_handed": (None, None, None, None),
    }


async def test_longsword_is_versatile_d10(db_session):
    assert await _properties(db_session, "Longsword") == {"versatile": (None, None, 10, None)}


async def test_blowgun_has_flat_damage(db_session):
    w = await _weapon(db_session, "Blowgun")
    assert (w.damage_dice_count, w.damage_die_size, w.damage_flat) == (None, None, 1)
    assert (await _properties(db_session, "Blowgun"))["ammunition"][3] == "Needle"


async def test_greatsword_is_2d6(db_session):
    w = await _weapon(db_session, "Greatsword")
    assert (w.damage_dice_count, w.damage_die_size, w.damage_type_code) == (2, 6, "slashing")


async def test_sling_has_no_weight(db_session):
    item = await _item(db_session, "Sling")
    assert (item.cost_gp, item.weight_lb) == (Decimal("0.1"), Decimal("0"))


async def test_dart_is_ranged_with_quarter_pound(db_session):
    w = await _weapon(db_session, "Dart")
    assert (w.category_code, w.is_ranged) == ("simple", True)
    item = await _item(db_session, "Dart")
    assert (item.cost_gp, item.weight_lb) == (Decimal("0.05"), Decimal("0.25"))


@pytest.mark.parametrize("weapon,ammunition", [
    ("Sling", "Bullet, Sling"), ("Musket", "Bullet, Firearm"), ("Pistol", "Bullet, Firearm"),
    ("Light Crossbow", "Bolt"), ("Hand Crossbow", "Bolt"), ("Heavy Crossbow", "Bolt"),
    ("Shortbow", "Arrow"), ("Longbow", "Arrow"), ("Blowgun", "Needle"),
])
async def test_ammunition_of_each_weapon(db_session, weapon, ammunition):
    assert (await _properties(db_session, weapon))["ammunition"][3] == ammunition


async def test_lance_has_only_heavy_reach_two_handed_and_the_exception_in_description(db_session):
    assert set(await _properties(db_session, "Lance")) == {"heavy", "reach", "two_handed"}
    assert "mounted" in (await _item(db_session, "Lance")).description.lower()


async def test_plate_armor(db_session):
    a = await _armor(db_session, "Plate Armor")
    assert (a.category_code, a.base_ac, a.adds_dex_modifier, a.max_dex_modifier, a.strength_requirement,
            a.stealth_disadvantage) == ("heavy", 18, False, None, 15, True)
    item = await _item(db_session, "Plate Armor")
    assert (item.cost_gp, item.weight_lb) == (Decimal("1500"), Decimal("65"))


async def test_hide_armor(db_session):
    a = await _armor(db_session, "Hide Armor")
    assert (a.category_code, a.base_ac, a.adds_dex_modifier, a.max_dex_modifier, a.strength_requirement,
            a.stealth_disadvantage) == ("medium", 12, True, 2, None, False)


async def test_chain_mail_strength(db_session):
    assert (await _armor(db_session, "Chain Mail")).strength_requirement == 13


async def test_shield(db_session):
    a = await _armor(db_session, "Shield")
    assert (a.category_code, a.base_ac, a.adds_dex_modifier, a.max_dex_modifier) == ("shield", 2, False, None)


async def test_armor_categories(db_session):
    rows = dict(await _rows(db_session, "SELECT category_code, count(*) FROM armors GROUP BY 1"))
    assert rows == {"light": 3, "medium": 5, "heavy": 4, "shield": 1}
    assert await _scalar(db_session, "SELECT count(*) FROM armors WHERE category_code = 'medium' AND max_dex_modifier <> 2") == 0


@pytest.mark.parametrize("name,tool_type,cost,weight", [
    ("Lute", "lute", "35", "2"),
    ("Dice Set", "dice_set", "0.1", "0"),
    ("Thieves' Tools", "thieves_tools", "25", "1"),
])
async def test_tool_items(db_session, name, tool_type, cost, weight):
    item = await _item(db_session, name)
    assert (item.item_type_code, item.cost_gp, item.weight_lb) == ("tool", Decimal(cost), Decimal(weight))
    assert await _scalar(db_session, "SELECT tool_type_code FROM tools WHERE item_id = :i", i=item.id) == tool_type


@pytest.mark.parametrize("name,cost,weight", [
    ("Arrow", "0.05", "0.05"),
    ("Bolt", "0.05", "0.075"),
    ("Bullet, Sling", "0.002", "0.075"),
    ("Bullet, Firearm", "0.3", "0.2"),
    ("Needle", "0.02", "0.02"),
])
async def test_ammunition_is_priced_per_unit(db_session, name, cost, weight):
    item = await _item(db_session, name)
    assert (item.item_type_code, item.cost_gp, item.weight_lb) == ("ammunition", Decimal(cost), Decimal(weight))


@pytest.mark.parametrize("name,cost", [
    ("Copper Piece", "0.01"), ("Silver Piece", "0.1"), ("Electrum Piece", "0.5"),
    ("Gold Piece", "1"), ("Platinum Piece", "10"),
])
async def test_coins(db_session, name, cost):
    item = await _item(db_session, name)
    assert (item.item_type_code, item.cost_gp, item.weight_lb) == ("currency", Decimal(cost), Decimal("0.02"))


async def _contents(db_session, pack: str) -> dict:
    return dict(await _rows(db_session, """
        SELECT c.name, ic.quantity FROM item_contents ic
        JOIN item_definitions p ON p.id = ic.pack_item_id JOIN item_definitions c ON c.id = ic.item_id
        WHERE p.name = :n
    """, n=pack))


async def test_explorers_pack(db_session):
    item = await _item(db_session, "Explorer's Pack")
    assert (item.item_type_code, item.cost_gp, item.weight_lb) == ("pack", Decimal("10"), Decimal("55"))
    assert await _contents(db_session, "Explorer's Pack") == {
        "Backpack": 1, "Bedroll": 1, "Oil": 2, "Rations": 10, "Rope": 1, "Tinderbox": 1, "Torch": 10,
        "Waterskin": 1,
    }


@pytest.mark.parametrize("pack,count", [
    ("Burglar's Pack", 11), ("Diplomat's Pack", 11), ("Dungeoneer's Pack", 9), ("Entertainer's Pack", 10),
    ("Explorer's Pack", 8), ("Priest's Pack", 7), ("Scholar's Pack", 8),
])
async def test_pack_content_counts(db_session, pack, count):
    assert len(await _contents(db_session, pack)) == count


async def test_diplomats_pack_contents(db_session):
    assert await _contents(db_session, "Diplomat's Pack") == {
        "Chest": 1, "Clothes, Fine": 1, "Ink": 1, "Ink Pen": 5, "Lamp": 1, "Case, Map or Scroll": 2, "Oil": 4,
        "Paper": 5, "Parchment": 5, "Perfume": 1, "Tinderbox": 1,
    }


async def test_entertainers_pack_weight(db_session):
    assert (await _item(db_session, "Entertainer's Pack")).weight_lb == Decimal("58.5")


@pytest.mark.parametrize("name,cost,weight", [
    ("Spyglass", "1000", "1"), ("Mirror", "5", "0.5"), ("Potion of Healing", "50", "0.5"), ("Sack", "0.01", "0.5"),
    ("Waterskin", "0.2", "5"), ("Antitoxin", "50", "0"), ("Candle", "0.01", "0"),
    ("Spell Scroll (Cantrip)", "30", "0"), ("Spell Scroll (Level 1)", "50", "0"),
])
async def test_adventuring_gear_spot_values(db_session, name, cost, weight):
    item = await _item(db_session, name)
    assert (item.item_type_code, item.cost_gp, item.weight_lb) == ("adventuring_gear", Decimal(cost), Decimal(weight))


@pytest.mark.parametrize("name,cost,weight,annotation", [
    ("Arcane Focus (Crystal)", "10", "1", None),
    ("Arcane Focus (Orb)", "20", "3", None),
    ("Arcane Focus (Rod)", "10", "2", None),
    ("Arcane Focus (Staff)", "5", "4", "quarterstaff"),
    ("Arcane Focus (Wand)", "10", "1", None),
    ("Druidic Focus (Sprig of Mistletoe)", "1", "0", None),
    ("Druidic Focus (Wooden Staff)", "5", "4", "quarterstaff"),
    ("Druidic Focus (Yew Wand)", "10", "1", None),
    ("Holy Symbol (Amulet)", "5", "1", "worn or held"),
    ("Holy Symbol (Emblem)", "5", "0", "borne on fabric or a shield"),
    ("Holy Symbol (Reliquary)", "5", "2", "held"),
])
async def test_focuses(db_session, name, cost, weight, annotation):
    item = await _item(db_session, name)
    assert (item.item_type_code, item.cost_gp, item.weight_lb) == ("adventuring_gear", Decimal(cost), Decimal(weight))
    if annotation is None:
        assert item.description is None
    else:
        assert annotation in item.description.lower()


async def test_only_lance_and_focuses_have_descriptions(db_session):
    names = set((await db_session.execute(text(
        "SELECT name FROM item_definitions WHERE source = 'srd' AND description IS NOT NULL"
    ))).scalars())
    assert names == {
        "Lance", "Arcane Focus (Staff)", "Druidic Focus (Wooden Staff)",
        "Holy Symbol (Amulet)", "Holy Symbol (Emblem)", "Holy Symbol (Reliquary)",
    }


async def test_no_generic_variant_items(db_session):
    for generic in ("Gaming Set", "Musical Instrument", "Arcane Focus", "Druidic Focus", "Holy Symbol", "Ammunition"):
        assert await _scalar(db_session, "SELECT count(*) FROM item_definitions WHERE name = :n", n=generic) == 0


# --- proficiency_grants catalog (R2) -----------------------------------------------------

async def test_proficiency_grants_unique_is_nulls_not_distinct(db_session):
    assert await _scalar(db_session, """
        SELECT i.indnullsnotdistinct FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid WHERE c.relname = 'uq_proficiency_grants_target'
    """) is True
