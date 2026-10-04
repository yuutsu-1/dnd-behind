"""POST/PATCH/DELETE /api/compendium/items: homebrew items with their sub-objects."""
import uuid

import pytest
from sqlalchemy import func, select

from app.db.models.compendium import ItemDefinition
from app.db.models.items import Armor, Container, ItemContent, Tool, Weapon, WeaponPropertyLink
from app.db.models.reference import ItemType, WeaponCategory, WeaponMastery, WeaponProperty
from tests.integration.conftest import (
    auth_headers,
    seed_campaign,
    seed_campaign_member,
    seed_reference,
    seed_user,
    srd_item,
)

BASE = "/api/compendium/items"
TABLES = (ItemDefinition, Weapon, WeaponPropertyLink, Armor, Tool, Container, ItemContent)

WEAPON = {
    "category_code": "martial", "is_ranged": True, "damage_dice_count": 1, "damage_die_size": 10,
    "damage_type_code": "piercing", "mastery_code": "slow",
}


async def _counts(db_session) -> dict:
    return {model.__tablename__: await db_session.scalar(select(func.count()).select_from(model)) for model in TABLES}


@pytest.fixture
async def people(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    p = await seed_user(db_session)
    c = await seed_campaign(db_session, creator=b)
    await seed_campaign_member(db_session, c, b, role="dm")
    await seed_campaign_member(db_session, c, p, role="player")
    await db_session.commit()
    # Headers up front: a handler's rollback expires the session's objects (user.id).
    return dict(a=a, b=b, p=p, c=c, ha=auth_headers(a), hb=auth_headers(b), hp=auth_headers(p))


async def _bow(db_session, **weapon_overrides) -> dict:
    arrow = await srd_item(db_session, "Arrow")
    weapon = {**WEAPON, "properties": [
        {"code": "ammunition", "ammunition_item_id": str(arrow.id)},
        {"code": "range", "range_normal_ft": 100, "range_long_ft": 400},
        {"code": "two_handed"},
    ]}
    weapon.update(weapon_overrides)
    return {"name": "Elven Greatbow", "item_type_code": "weapon", "cost_gp": "120.5", "weight_lb": "3", "weapon": weapon}


class TestCreate:
    async def test_homebrew_weapon(self, api_client, db_session, people):
        payload = await _bow(db_session)
        response = await api_client.post(BASE, json=payload, headers=people["ha"])
        assert response.status_code == 201, response.text
        body = response.json()
        assert (body["source"], body["is_homebrew"], body["cost_gp"], body["weight_lb"]) == ("homebrew", True, 120.5, 3)
        assert "created_by" not in body
        props = {p["code"]: p for p in body["weapon"]["properties"]}
        assert props["ammunition"]["ammunition_item_name"] == "Arrow"
        assert (props["range"]["range_normal_ft"], props["range"]["range_long_ft"]) == (100, 400)
        assert body["armor"] is None and body["contents"] is None

        detail = (await api_client.get(f"{BASE}/{body['id']}")).json()
        assert detail == body
        stored = await db_session.get(ItemDefinition, uuid.UUID(body["id"]))
        assert stored.created_by == people["a"].id

    async def test_homebrew_pack(self, api_client, db_session, people):
        torch, rope = await srd_item(db_session, "Torch"), await srd_item(db_session, "Rope")
        response = await api_client.post(BASE, json={
            "name": "Spelunker's Pack", "item_type_code": "pack", "cost_gp": "8",
            "contents": [{"item_id": str(torch.id), "quantity": 5}, {"item_id": str(rope.id)}],
        }, headers=people["ha"])
        assert response.status_code == 201, response.text
        body = response.json()
        assert {(c["item_name"], c["quantity"]) for c in body["contents"]} == {("Torch", 5), ("Rope", 1)}
        assert (await api_client.get(f"{BASE}/{body['id']}")).json()["contents"] == body["contents"]

    async def test_homebrew_tool(self, api_client, people):
        response = await api_client.post(BASE, json={
            "name": "Masterwork Lute", "item_type_code": "tool", "cost_gp": "350", "tool": {"tool_type_code": "lute"},
        }, headers=people["ha"])
        assert response.status_code == 201, response.text
        assert response.json()["tool"] == {
            "tool_type_code": "lute", "tool_type_name": "Lute", "category_code": "musical_instrument",
            "ability_code": "cha",
        }

    async def test_homebrew_armor_and_container(self, api_client, people):
        headers = people["ha"]
        armor = await api_client.post(BASE, json={
            "name": "Bone Plate", "item_type_code": "armor",
            "armor": {"category_code": "heavy", "base_ac": 17, "strength_requirement": 14, "stealth_disadvantage": True},
        }, headers=headers)
        assert armor.status_code == 201, armor.text
        assert armor.json()["armor"]["base_ac"] == 17
        bag = await api_client.post(BASE, json={
            "name": "Big Sack", "item_type_code": "adventuring_gear", "container": {"capacity_weight_lb": "45.5"},
        }, headers=headers)
        assert bag.status_code == 201, bag.text
        assert bag.json()["container"] == {"capacity_weight_lb": 45.5}

    async def test_visible_homebrew_codes_are_accepted(self, api_client, db_session, people):
        relic = await seed_reference(db_session, ItemType, author=people["a"], code="relic", name="Relic")
        spiky = await seed_reference(db_session, WeaponProperty, author=people["b"], campaigns=[people["c"]])
        await db_session.commit()
        own_type = await api_client.post(BASE, json={"name": "Old Relic", "item_type_code": relic.code},
                                         headers=people["ha"])
        assert own_type.status_code == 201, own_type.text
        shared = await api_client.post(BASE, json={
            "name": "Spiked Club", "item_type_code": "weapon",
            "weapon": {**WEAPON, "is_ranged": False, "properties": [{"code": spiky.code}]},
        }, headers=people["hp"])
        assert shared.status_code == 201, shared.text

    async def test_without_token_is_401(self, api_client):
        assert (await api_client.post(BASE, json={"name": "X", "item_type_code": "currency"})).status_code == 401

    @pytest.mark.parametrize("payload", [
        {"name": "X", "item_type_code": "weapon", "armor": {"category_code": "light", "base_ac": 11}},
        {"name": "X", "item_type_code": "adventuring_gear", "tool": {"tool_type_code": "lute"}},
        {"name": "X", "item_type_code": "pack", "contents": []},
        {"name": "X", "item_type_code": "currency", "source": "srd"},
    ])
    async def test_incompatible_or_forbidden_is_422(self, api_client, db_session, people, payload):
        before = await _counts(db_session)
        response = await api_client.post(BASE, json=payload, headers=people["ha"])
        assert response.status_code == 422
        assert await _counts(db_session) == before

    async def test_homebrew_type_does_not_take_sub_objects(self, api_client, db_session, people):
        relic = await seed_reference(db_session, ItemType, author=people["a"])
        await db_session.commit()
        response = await api_client.post(BASE, json={
            "name": "X", "item_type_code": relic.code, "container": {"capacity_weight_lb": "5"},
        }, headers=people["ha"])
        assert response.status_code == 422


class TestCreateErrors400:
    """Every 400 leaves item_definitions and the sub-tables untouched."""

    async def _assert_400(self, api_client, db_session, people, payload):
        before = await _counts(db_session)
        response = await api_client.post(BASE, json=payload, headers=people["ha"])
        assert response.status_code == 400, response.text
        assert await _counts(db_session) == before
        return response

    @pytest.mark.parametrize("weapon_overrides", [
        {"mastery_code": "no_such_mastery"},
        {"damage_type_code": "sonic"},
        {"category_code": "exotic"},
    ])
    async def test_unknown_weapon_codes(self, api_client, db_session, people, weapon_overrides):
        await self._assert_400(api_client, db_session, people, await _bow(db_session, **weapon_overrides))

    async def test_unknown_item_type(self, api_client, db_session, people):
        await self._assert_400(api_client, db_session, people, {"name": "X", "item_type_code": "relic"})

    async def test_invisible_homebrew_category(self, api_client, db_session, people):
        hidden = await seed_reference(db_session, WeaponCategory, author=people["b"])
        await db_session.commit()
        payload = await _bow(db_session, category_code=hidden.code)
        await self._assert_400(api_client, db_session, people, payload)

    async def test_invisible_homebrew_mastery_has_the_unknown_message(self, api_client, db_session, people):
        hidden = await seed_reference(db_session, WeaponMastery, author=people["b"])
        await db_session.commit()
        code = hidden.code
        invisible = await self._assert_400(api_client, db_session, people, await _bow(db_session, mastery_code=code))
        unknown = await self._assert_400(api_client, db_session, people, await _bow(db_session, mastery_code="zzz"))
        assert invisible.json()["detail"].replace(code, "X") == unknown.json()["detail"].replace("zzz", "X")

    async def test_unknown_property_tool_type_and_armor_category(self, api_client, db_session, people):
        await self._assert_400(api_client, db_session, people, await _bow(db_session, properties=[{"code": "spiky"}]))
        await self._assert_400(api_client, db_session, people, {
            "name": "X", "item_type_code": "tool", "tool": {"tool_type_code": "lockpicks"},
        })
        await self._assert_400(api_client, db_session, people, {
            "name": "X", "item_type_code": "armor", "armor": {"category_code": "mithral", "base_ac": 12},
        })

    async def test_ammunition_must_be_an_ammunition_item(self, api_client, db_session, people):
        longsword = await srd_item(db_session, "Longsword")
        for ammo_id in (longsword.id, uuid.uuid4()):
            payload = await _bow(db_session, properties=[
                {"code": "ammunition", "ammunition_item_id": str(ammo_id)},
                {"code": "range", "range_normal_ft": 100, "range_long_ft": 400},
            ])
            await self._assert_400(api_client, db_session, people, payload)

    @pytest.mark.parametrize("prop", [
        {"code": "range"},
        {"code": "range", "range_normal_ft": 30},
        {"code": "versatile"},
        {"code": "ammunition"},
        {"code": "finesse", "range_normal_ft": 20, "range_long_ft": 60},
        {"code": "finesse", "versatile_die_size": 8},
        {"code": "range", "range_normal_ft": 20, "range_long_ft": 60, "versatile_die_size": 8},
    ])
    async def test_property_parameters(self, api_client, db_session, people, prop):
        payload = await _bow(db_session, is_ranged=False, properties=[prop])
        await self._assert_400(api_client, db_session, people, payload)

    async def test_contents_must_exist_and_not_be_packs(self, api_client, db_session, people):
        explorers = await srd_item(db_session, "Explorer's Pack")
        for content_id in (explorers.id, uuid.uuid4()):
            await self._assert_400(api_client, db_session, people, {
                "name": "Bundle", "item_type_code": "pack", "contents": [{"item_id": str(content_id)}],
            })


async def _create(api_client, headers, payload) -> dict:
    response = await api_client.post(BASE, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _links(db_session, item_id) -> set[str]:
    rows = await db_session.execute(
        select(WeaponPropertyLink.property_code).where(WeaponPropertyLink.weapon_item_id == uuid.UUID(item_id))
    )
    return set(rows.scalars())


class TestUpdate:
    async def test_author_renames_and_replaces_the_properties(self, api_client, db_session, people):
        bow = await _create(api_client, people["ha"], await _bow(db_session))
        assert await _links(db_session, bow["id"]) == {"ammunition", "range", "two_handed"}
        new_weapon = {**WEAPON, "is_ranged": False, "damage_die_size": 8, "properties": [
            {"code": "finesse"}, {"code": "versatile", "versatile_die_size": 10},
        ]}
        response = await api_client.patch(
            f"{BASE}/{bow['id']}", json={"name": "Elven Blade", "weapon": new_weapon}, headers=people["ha"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "Elven Blade"
        assert (body["weapon"]["is_ranged"], body["weapon"]["damage_die_size"]) == (False, 8)
        assert {p["code"] for p in body["weapon"]["properties"]} == {"finesse", "versatile"}
        assert await _links(db_session, bow["id"]) == {"finesse", "versatile"}
        assert (await api_client.get(f"{BASE}/{bow['id']}")).json() == body
        # Untouched fields keep their values.
        assert (body["cost_gp"], body["weight_lb"]) == (120.5, 3)

    async def test_base_fields(self, api_client, people):
        item = await _create(api_client, people["ha"], {
            "name": "Lucky Coin", "item_type_code": "currency", "cost_gp": "1", "description": "Shiny",
        })
        response = await api_client.patch(f"{BASE}/{item['id']}", json={
            "cost_gp": None, "weight_lb": "0.02", "description": None,
        }, headers=people["ha"])
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["cost_gp"], body["weight_lb"], body["description"], body["name"]) == (None, 0.02, None, "Lucky Coin")

    async def test_container_can_be_replaced_and_removed(self, api_client, people):
        bag = await _create(api_client, people["ha"], {
            "name": "Bag", "item_type_code": "adventuring_gear", "container": {"capacity_weight_lb": "10"},
        })
        url = f"{BASE}/{bag['id']}"
        replaced = await api_client.patch(url, json={"container": {"capacity_weight_lb": "20"}}, headers=people["ha"])
        assert replaced.json()["container"] == {"capacity_weight_lb": 20}
        removed = await api_client.patch(url, json={"container": None}, headers=people["ha"])
        assert removed.status_code == 200
        assert removed.json()["container"] is None
        added = await api_client.patch(url, json={"container": {"capacity_weight_lb": "5"}}, headers=people["ha"])
        assert added.json()["container"] == {"capacity_weight_lb": 5}

    async def test_pack_contents_and_tool_and_armor_are_replaced(self, api_client, db_session, people):
        torch, rope = await srd_item(db_session, "Torch"), await srd_item(db_session, "Rope")
        torch_id, rope_id = str(torch.id), str(rope.id)
        pack = await _create(api_client, people["ha"], {
            "name": "Kit", "item_type_code": "pack", "contents": [{"item_id": torch_id, "quantity": 2}],
        })
        response = await api_client.patch(f"{BASE}/{pack['id']}", json={
            "contents": [{"item_id": rope_id, "quantity": 3}],
        }, headers=people["ha"])
        assert [(c["item_name"], c["quantity"]) for c in response.json()["contents"]] == [("Rope", 3)]

        tool = await _create(api_client, people["ha"], {
            "name": "Fancy Dice", "item_type_code": "tool", "tool": {"tool_type_code": "dice_set"},
        })
        response = await api_client.patch(f"{BASE}/{tool['id']}", json={"tool": {"tool_type_code": "playing_card_set"}},
                                          headers=people["ha"])
        assert response.json()["tool"]["tool_type_code"] == "playing_card_set"

        armor = await _create(api_client, people["ha"], {
            "name": "Buckler", "item_type_code": "armor", "armor": {"category_code": "shield", "base_ac": 1},
        })
        response = await api_client.patch(f"{BASE}/{armor['id']}", json={
            "armor": {"category_code": "shield", "base_ac": 2},
        }, headers=people["ha"])
        assert response.json()["armor"]["base_ac"] == 2

    @pytest.mark.parametrize("field,value", [
        ("item_type_code", "armor"), ("source", "srd"), ("is_homebrew", False), ("id", str(uuid.uuid4())),
    ])
    async def test_forbidden_fields_are_422(self, api_client, db_session, people, field, value):
        bow = await _create(api_client, people["ha"], await _bow(db_session))
        response = await api_client.patch(f"{BASE}/{bow['id']}", json={field: value}, headers=people["ha"])
        assert response.status_code == 422

    @pytest.mark.parametrize("payload", [
        {"armor": {"category_code": "light", "base_ac": 11}},
        {"weapon": None},
        {"container": {"capacity_weight_lb": "5"}},
        {"contents": []},
    ])
    async def test_sub_object_must_fit_the_current_type(self, api_client, db_session, people, payload):
        bow = await _create(api_client, people["ha"], await _bow(db_session))
        response = await api_client.patch(f"{BASE}/{bow['id']}", json=payload, headers=people["ha"])
        assert response.status_code == 422

    async def test_pack_needs_contents(self, api_client, db_session, people):
        torch = await srd_item(db_session, "Torch")
        pack = await _create(api_client, people["ha"], {
            "name": "Kit", "item_type_code": "pack", "contents": [{"item_id": str(torch.id)}],
        })
        for contents in ([], None):
            response = await api_client.patch(f"{BASE}/{pack['id']}", json={"contents": contents}, headers=people["ha"])
            assert response.status_code == 422

    async def test_pack_cannot_contain_itself(self, api_client, db_session, people):
        torch = await srd_item(db_session, "Torch")
        pack = await _create(api_client, people["ha"], {
            "name": "Kit", "item_type_code": "pack", "contents": [{"item_id": str(torch.id)}],
        })
        response = await api_client.patch(
            f"{BASE}/{pack['id']}", json={"contents": [{"item_id": pack["id"]}]}, headers=people["ha"],
        )
        assert response.status_code == 400

    async def test_400_changes_nothing(self, api_client, db_session, people):
        bow = await _create(api_client, people["ha"], await _bow(db_session))
        before = await _counts(db_session)
        response = await api_client.patch(f"{BASE}/{bow['id']}", json={
            "name": "Renamed", "weapon": {**WEAPON, "mastery_code": "zzz", "properties": [{"code": "light"}]},
        }, headers=people["ha"])
        assert response.status_code == 400
        assert await _counts(db_session) == before
        detail = (await api_client.get(f"{BASE}/{bow['id']}")).json()
        assert detail == bow

    async def test_permissions(self, api_client, db_session, people):
        mine = await _create(api_client, people["ha"], {"name": "Mine", "item_type_code": "currency"})
        gold = await srd_item(db_session, "Gold Piece")
        payload = {"name": "Renamed"}
        assert (await api_client.patch(f"{BASE}/{gold.id}", json=payload, headers=people["ha"])).status_code == 403
        assert (await api_client.patch(f"{BASE}/{mine['id']}", json=payload, headers=people["hb"])).status_code == 403
        assert (await api_client.patch(f"{BASE}/{uuid.uuid4()}", json=payload, headers=people["ha"])).status_code == 404
        assert (await api_client.patch(f"{BASE}/{mine['id']}", json=payload)).status_code == 401
        assert (await api_client.get(f"{BASE}/{mine['id']}")).json()["name"] == "Mine"


async def _exists(db_session, item_id) -> bool:
    return await db_session.scalar(
        select(func.count()).select_from(ItemDefinition).where(ItemDefinition.id == uuid.UUID(str(item_id)))
    ) == 1


class TestDelete:
    async def test_weapon_without_references_is_deleted_with_its_sub_rows(self, api_client, db_session, people):
        bow = await _create(api_client, people["ha"], await _bow(db_session))
        response = await api_client.delete(f"{BASE}/{bow['id']}", headers=people["ha"])
        assert response.status_code == 204
        item_id = uuid.UUID(bow["id"])
        assert not await _exists(db_session, item_id)
        assert await db_session.scalar(select(func.count()).select_from(Weapon).where(Weapon.item_id == item_id)) == 0
        assert await _links(db_session, bow["id"]) == set()
        assert (await api_client.get(f"{BASE}/{bow['id']}")).status_code == 404

    async def test_pack_is_deleted_with_its_contents_rows(self, api_client, db_session, people):
        torch = await srd_item(db_session, "Torch")
        pack = await _create(api_client, people["ha"], {
            "name": "Kit", "item_type_code": "pack", "contents": [{"item_id": str(torch.id), "quantity": 3}],
        })
        assert (await api_client.delete(f"{BASE}/{pack['id']}", headers=people["ha"])).status_code == 204
        assert await db_session.scalar(select(func.count()).select_from(ItemContent).where(
            ItemContent.pack_item_id == uuid.UUID(pack["id"])
        )) == 0
        assert await _exists(db_session, torch.id)

    async def test_armor_tool_and_container_go_with_the_item(self, api_client, db_session, people):
        for payload, model in (
            ({"name": "A", "item_type_code": "armor", "armor": {"category_code": "light", "base_ac": 11}}, Armor),
            ({"name": "T", "item_type_code": "tool", "tool": {"tool_type_code": "lute"}}, Tool),
            ({"name": "C", "item_type_code": "adventuring_gear", "container": {"capacity_weight_lb": "3"}}, Container),
        ):
            item = await _create(api_client, people["ha"], payload)
            assert (await api_client.delete(f"{BASE}/{item['id']}", headers=people["ha"])).status_code == 204
            assert await db_session.scalar(
                select(func.count()).select_from(model).where(model.item_id == uuid.UUID(item["id"]))
            ) == 0

    async def _assert_409(self, api_client, db_session, people, item_id):
        response = await api_client.delete(f"{BASE}/{item_id}", headers=people["ha"])
        assert response.status_code == 409, response.text
        assert await _exists(db_session, item_id)

    async def test_409_when_in_a_character_inventory(self, api_client, db_session, people):
        from tests.integration.conftest import seed_character, seed_inventory_entry, seed_item

        item = await seed_item(db_session, author=people["a"])
        character = await seed_character(db_session, owner=people["b"])
        await seed_inventory_entry(db_session, character, item)
        await db_session.commit()
        await self._assert_409(api_client, db_session, people, item.id)

    async def test_409_when_in_class_initial_equipment(self, api_client, db_session, people):
        from tests.integration.conftest import seed_class, seed_class_initial_equipment, seed_item

        item = await seed_item(db_session, author=people["a"])
        await seed_class_initial_equipment(db_session, await seed_class(db_session), item)
        await db_session.commit()
        await self._assert_409(api_client, db_session, people, item.id)

    async def test_409_when_in_background_initial_equipment(self, api_client, db_session, people):
        from tests.integration.conftest import seed_background, seed_background_initial_equipment, seed_item

        item = await seed_item(db_session, author=people["a"])
        await seed_background_initial_equipment(db_session, await seed_background(db_session), item)
        await db_session.commit()
        await self._assert_409(api_client, db_session, people, item.id)

    async def test_409_when_content_of_another_pack(self, api_client, db_session, people):
        trinket = await _create(api_client, people["ha"], {"name": "Trinket", "item_type_code": "adventuring_gear"})
        await _create(api_client, people["hb"], {
            "name": "Their Kit", "item_type_code": "pack", "contents": [{"item_id": trinket["id"]}],
        })
        await self._assert_409(api_client, db_session, people, trinket["id"])

    async def test_409_when_ammunition_of_another_weapon(self, api_client, db_session, people):
        dart = await _create(api_client, people["ha"], {"name": "Glass Dart", "item_type_code": "ammunition"})
        await _create(api_client, people["hb"], {
            "name": "Dart Gun", "item_type_code": "weapon", "weapon": {**WEAPON, "properties": [
                {"code": "ammunition", "ammunition_item_id": dart["id"]},
                {"code": "range", "range_normal_ft": 20, "range_long_ft": 60},
            ]},
        })
        await self._assert_409(api_client, db_session, people, dart["id"])

    async def test_permissions(self, api_client, db_session, people):
        mine = await _create(api_client, people["ha"], {"name": "Mine", "item_type_code": "currency"})
        gold = await srd_item(db_session, "Gold Piece")
        gold_id = gold.id
        assert (await api_client.delete(f"{BASE}/{gold_id}", headers=people["ha"])).status_code == 403
        assert (await api_client.delete(f"{BASE}/{mine['id']}", headers=people["hb"])).status_code == 403
        assert (await api_client.delete(f"{BASE}/{uuid.uuid4()}", headers=people["ha"])).status_code == 404
        assert (await api_client.delete(f"{BASE}/{mine['id']}")).status_code == 401
        assert await _exists(db_session, mine["id"]) and await _exists(db_session, gold_id)
