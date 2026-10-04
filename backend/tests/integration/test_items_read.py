"""GET /api/compendium/items (list with filters, detail). Items are global; auth optional."""
import uuid

import pytest

from tests.integration.conftest import auth_headers, count_queries, seed_user, srd_item

BASE = "/api/compendium/items"


async def _get(api_client, **params):
    response = await api_client.get(BASE, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("params,count", [
    ({"item_type": "weapon"}, 38),
    ({"item_type": "armor"}, 13),
    ({"item_type": "tool"}, 37),
    ({"item_type": "currency"}, 5),
    ({"weapon_category": "martial"}, 24),
    ({"weapon_category": "simple"}, 14),
    ({"armor_category": "heavy"}, 4),
    ({"tool_category": "gaming_set"}, 4),
    ({"tool_category": "musical_instrument"}, 10),
    ({"tool_type": "lute"}, 1),
    ({"item_type": "weapon", "weapon_category": "martial", "search": "bow"}, 3),  # Longbow + 2 crossbows
])
async def test_filters(api_client, params, count):
    assert len(await _get(api_client, **params)) == count


async def test_all_srd_items(api_client):
    assert len(await _get(api_client)) == 187


async def test_unknown_filter_code_is_an_empty_list(api_client):
    assert await _get(api_client, weapon_category="exotic") == []
    assert await _get(api_client, item_type="relic") == []


async def test_search_is_case_insensitive(api_client):
    upper = {r["name"] for r in await _get(api_client, search="SWORD")}
    lower = {r["name"] for r in await _get(api_client, search="sword")}
    assert upper == lower == {"Greatsword", "Longsword", "Shortsword"}


@pytest.mark.parametrize("term", ["%", "_", "\\"])
async def test_like_wildcards_are_literal(api_client, term):
    assert await _get(api_client, search=term) == []


async def test_order_is_name_then_id_and_deterministic(api_client):
    first = await _get(api_client)
    second = await _get(api_client)
    assert first == second
    assert [(r["name"], r["id"]) for r in first] == sorted((r["name"], r["id"]) for r in first)


async def test_list_rows_carry_their_sub_objects(api_client):
    rows = {r["name"]: r for r in await _get(api_client, search="Longbow")}
    longbow = rows["Longbow"]
    assert longbow["weapon"]["category_code"] == "martial"
    assert longbow["armor"] is None


async def test_longbow_detail(api_client, db_session):
    longbow = await srd_item(db_session, "Longbow")
    arrow = await srd_item(db_session, "Arrow")
    response = await api_client.get(f"{BASE}/{longbow.id}")
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["item_type_code"], body["cost_gp"], body["weight_lb"]) == ("Longbow", "weapon", 50, 2)
    assert (body["source"], body["is_homebrew"]) == ("srd", False)
    assert body["armor"] is None and body["tool"] is None and body["container"] is None and body["contents"] is None
    assert "created_by" not in body
    weapon = body["weapon"]
    assert (weapon["category_code"], weapon["is_ranged"], weapon["damage_dice_count"], weapon["damage_die_size"],
            weapon["damage_flat"], weapon["damage_type_code"], weapon["mastery_code"]) == (
        "martial", True, 1, 8, 0, "piercing", "slow",
    )
    props = {p["code"]: p for p in weapon["properties"]}
    assert set(props) == {"ammunition", "range", "heavy", "two_handed"}
    assert (props["ammunition"]["ammunition_item_id"], props["ammunition"]["ammunition_item_name"]) == (
        str(arrow.id), "Arrow",
    )
    assert (props["range"]["range_normal_ft"], props["range"]["range_long_ft"]) == (150, 600)
    assert props["heavy"]["name"] == "Heavy"


async def test_explorers_pack_detail(api_client, db_session):
    pack = await srd_item(db_session, "Explorer's Pack")
    body = (await api_client.get(f"{BASE}/{pack.id}")).json()
    assert (body["cost_gp"], body["weight_lb"]) == (10, 55)
    assert len(body["contents"]) == 8
    contents = {c["item_name"]: c["quantity"] for c in body["contents"]}
    assert contents["Torch"] == 10 and contents["Rations"] == 10
    assert body["weapon"] is None and body["container"] is None


async def test_lute_detail(api_client, db_session):
    lute = await srd_item(db_session, "Lute")
    body = (await api_client.get(f"{BASE}/{lute.id}")).json()
    assert body["tool"] == {
        "tool_type_code": "lute", "tool_type_name": "Lute", "category_code": "musical_instrument", "ability_code": "cha",
    }
    assert (body["cost_gp"], body["weight_lb"]) == (35, 2)


async def test_backpack_and_ammunition_numbers(api_client, db_session):
    backpack = await srd_item(db_session, "Backpack")
    assert (await api_client.get(f"{BASE}/{backpack.id}")).json()["container"] == {"capacity_weight_lb": 30}
    sling_bullet = await srd_item(db_session, "Bullet, Sling")
    raw = (await api_client.get(f"{BASE}/{sling_bullet.id}")).text
    assert '"cost_gp":0.002' in raw and '"weight_lb":0.075' in raw
    entertainer = await srd_item(db_session, "Entertainer's Pack")
    assert (await api_client.get(f"{BASE}/{entertainer.id}")).json()["weight_lb"] == 58.5


async def test_plate_and_shield(api_client, db_session):
    plate = (await api_client.get(f"{BASE}/{(await srd_item(db_session, 'Plate Armor')).id}")).json()
    assert plate["cost_gp"] == 1500
    assert plate["armor"] == {
        "category_code": "heavy", "base_ac": 18, "adds_dex_modifier": False, "max_dex_modifier": None,
        "strength_requirement": 15, "stealth_disadvantage": True,
    }
    shield = (await api_client.get(f"{BASE}/{(await srd_item(db_session, 'Shield')).id}")).json()
    assert (shield["armor"]["category_code"], shield["armor"]["base_ac"]) == ("shield", 2)


async def test_unknown_item_is_404(api_client):
    assert (await api_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404


async def test_auth_is_optional_but_invalid_token_is_401(api_client, db_session):
    user = await seed_user(db_session)
    await db_session.commit()
    assert (await api_client.get(BASE, params={"item_type": "currency"}, headers=auth_headers(user))).status_code == 200
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert (await api_client.get(BASE, headers=bad)).status_code == 401
    gold = await srd_item(db_session, "Gold Piece")
    assert (await api_client.get(f"{BASE}/{gold.id}", headers=bad)).status_code == 401


async def test_list_has_no_n_plus_one(api_client, db_engine):
    with count_queries(db_engine) as small:
        assert len(await _get(api_client, item_type="currency")) == 5
    with count_queries(db_engine) as large:
        assert len(await _get(api_client)) == 187
    assert small.count == large.count
