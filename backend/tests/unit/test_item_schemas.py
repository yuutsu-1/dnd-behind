"""Item schemas: every 422 of the phase 2 spec ("No item / No dano / Valores /
Conteúdo / Campos proibidos") plus the output format."""
import json
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db.models.compendium import ItemDefinition
from app.db.models.items import Container, ItemContent, Tool, Weapon, WeaponPropertyLink
from app.db.models.reference import ToolType, WeaponProperty
from app.schemas.items import ItemCreate, ItemOut, ItemUpdate, sub_object_error

WEAPON = {
    "category_code": "martial", "is_ranged": False, "damage_dice_count": 1, "damage_die_size": 8,
    "damage_type_code": "slashing", "mastery_code": "sap",
}
ARMOR = {"category_code": "light", "base_ac": 11, "adds_dex_modifier": True, "stealth_disadvantage": False}


def _item(item_type="adventuring_gear", **overrides) -> dict:
    payload = {"name": "Thing", "item_type_code": item_type}
    payload.update(overrides)
    return payload


def _weapon(**weapon_overrides) -> dict:
    return _item("weapon", weapon={**WEAPON, **weapon_overrides})


def _invalid(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)


class TestValidItems:
    def test_weapon_with_properties(self):
        data = ItemCreate(**_weapon(properties=[
            {"code": "versatile", "versatile_die_size": 10},
            {"code": "range", "range_normal_ft": 20, "range_long_ft": 60},
            {"code": "ammunition", "ammunition_item_id": str(uuid.uuid4())},
            {"code": "finesse"},
        ]))
        assert data.weapon.damage_flat == 0
        assert [p.code for p in data.weapon.properties] == ["versatile", "range", "ammunition", "finesse"]

    def test_flat_damage_weapon(self):
        data = ItemCreate(**_weapon(damage_dice_count=None, damage_die_size=None, damage_flat=1))
        assert data.weapon.damage_dice_count is None

    def test_armor_tool_pack_gear_and_plain_types(self):
        ItemCreate(**_item("armor", armor=ARMOR))
        ItemCreate(**_item("tool", tool={"tool_type_code": "lute"}))
        ItemCreate(**_item("pack", contents=[{"item_id": str(uuid.uuid4()), "quantity": 10}]))
        ItemCreate(**_item("adventuring_gear", container={"capacity_weight_lb": "30"}))
        ItemCreate(**_item("adventuring_gear"))
        ItemCreate(**_item("ammunition", cost_gp="0.002", weight_lb="0.075"))
        ItemCreate(**_item("currency"))
        ItemCreate(**_item("relic"))  # homebrew type: no sub-object

    def test_decimals(self):
        data = ItemCreate(**_item(cost_gp="0.002", weight_lb="58.5"))
        assert (data.cost_gp, data.weight_lb) == (Decimal("0.002"), Decimal("58.5"))


class TestDamage:
    @pytest.mark.parametrize("overrides", [
        {"damage_dice_count": 1, "damage_die_size": None},
        {"damage_dice_count": None, "damage_die_size": 6},
        {"damage_die_size": 7},
        {"damage_die_size": 0},
        {"damage_dice_count": 0},
        {"damage_dice_count": None, "damage_die_size": None, "damage_flat": 0},
        {"damage_dice_count": None, "damage_die_size": None},
    ])
    def test_invalid_damage(self, overrides):
        _invalid(ItemCreate, _weapon(**overrides))


class TestWeaponProperties:
    @pytest.mark.parametrize("prop", [
        {"code": "range", "range_normal_ft": 0, "range_long_ft": 60},
        {"code": "range", "range_normal_ft": -5, "range_long_ft": 60},
        {"code": "range", "range_normal_ft": 60, "range_long_ft": 20},
        {"code": "range", "range_normal_ft": 20, "range_long_ft": 0},
        {"code": "versatile", "versatile_die_size": 7},
        {"code": "Finesse"},
    ])
    def test_invalid_property(self, prop):
        _invalid(ItemCreate, _weapon(properties=[prop]))

    def test_duplicate_property(self):
        _invalid(ItemCreate, _weapon(properties=[{"code": "light"}, {"code": "light"}]))


class TestValues:
    @pytest.mark.parametrize("payload", [
        _item(cost_gp="-1"),
        _item(weight_lb="-0.5"),
        _item(cost_gp="0.00001"),  # more precision than NUMERIC(12,4)
        _item(cost_gp="123456789"),  # more integer digits than NUMERIC(12,4)
        _item("armor", armor={**ARMOR, "base_ac": -1}),
        _item("armor", armor={**ARMOR, "max_dex_modifier": -1}),
        _item("armor", armor={**ARMOR, "strength_requirement": 0}),
        _item("adventuring_gear", container={"capacity_weight_lb": "0"}),
        _item("adventuring_gear", container={"capacity_weight_lb": "-3"}),
        _item("pack", contents=[{"item_id": str(uuid.uuid4()), "quantity": 0}]),
    ])
    def test_out_of_range(self, payload):
        _invalid(ItemCreate, payload)

    def test_zero_cost_and_weight_are_fine(self):
        ItemCreate(**_item(cost_gp="0", weight_lb="0"))


class TestContents:
    def test_duplicate_content(self):
        item_id = str(uuid.uuid4())
        _invalid(ItemCreate, _item("pack", contents=[{"item_id": item_id}, {"item_id": item_id, "quantity": 2}]))

    def test_quantity_defaults_to_one(self):
        data = ItemCreate(**_item("pack", contents=[{"item_id": str(uuid.uuid4())}]))
        assert data.contents[0].quantity == 1


class TestCoherence:
    @pytest.mark.parametrize("payload", [
        _item("weapon"),
        _item("weapon", weapon=WEAPON, armor=ARMOR),
        _item("armor"),
        _item("armor", weapon=WEAPON),
        _item("tool"),
        _item("tool", tool={"tool_type_code": "lute"}, container={"capacity_weight_lb": "1"}),
        _item("pack"),
        _item("pack", contents=[]),
        _item("adventuring_gear", weapon=WEAPON),
        _item("adventuring_gear", contents=[{"item_id": str(uuid.uuid4())}]),
        _item("ammunition", container={"capacity_weight_lb": "1"}),
        _item("currency", tool={"tool_type_code": "lute"}),
        _item("relic", container={"capacity_weight_lb": "1"}),
        _item("relic", weapon=WEAPON),
    ])
    def test_incompatible_sub_object(self, payload):
        _invalid(ItemCreate, payload)

    def test_sub_object_error_helper(self):
        assert sub_object_error("weapon", {"weapon"}) is None
        assert sub_object_error("weapon", set()) is not None
        assert sub_object_error("weapon", {"weapon", "armor"}) is not None
        assert sub_object_error("adventuring_gear", set()) is None
        assert sub_object_error("relic", {"container"}) is not None


class TestForbiddenFields:
    @pytest.mark.parametrize("field,value", [
        ("source", "srd"), ("is_homebrew", False), ("created_by", str(uuid.uuid4())), ("id", str(uuid.uuid4())),
        ("rarity", "common"), ("properties", {}),
    ])
    def test_create(self, field, value):
        _invalid(ItemCreate, _item(**{field: value}))

    @pytest.mark.parametrize("field,value", [
        ("item_type_code", "weapon"), ("source", "srd"), ("is_homebrew", False),
        ("created_by", str(uuid.uuid4())), ("id", str(uuid.uuid4())),
    ])
    def test_update(self, field, value):
        _invalid(ItemUpdate, {field: value})


class TestUpdate:
    def test_everything_optional(self):
        assert ItemUpdate().model_fields_set == set()

    def test_name_cannot_be_null(self):
        _invalid(ItemUpdate, {"name": None})

    def test_nullable_fields(self):
        update = ItemUpdate(description=None, cost_gp=None, weight_lb=None, container=None)
        assert update.model_fields_set == {"description", "cost_gp", "weight_lb", "container"}

    @pytest.mark.parametrize("payload", [
        {"weapon": {**WEAPON, "damage_die_size": 7}},
        {"weapon": {**WEAPON, "properties": [{"code": "light"}, {"code": "light"}]}},
        {"contents": [{"item_id": str(uuid.uuid4()), "quantity": 0}]},
        {"cost_gp": "-1"},
        {"armor": {**ARMOR, "base_ac": -1}},
    ])
    def test_same_value_rules_as_create(self, payload):
        _invalid(ItemUpdate, payload)


def _orm_weapon() -> ItemDefinition:
    arrow = ItemDefinition(id=uuid.uuid4(), name="Arrow", item_type_code="ammunition")
    item = ItemDefinition(
        id=uuid.uuid4(), name="Longbow", item_type_code="weapon", cost_gp=Decimal("50.0000"),
        weight_lb=Decimal("2.0000"), description=None, source="srd", is_homebrew=False,
    )
    item.weapon = Weapon(
        item_id=item.id, category_code="martial", is_ranged=True, damage_dice_count=1, damage_die_size=8,
        damage_flat=0, damage_type_code="piercing", mastery_code="slow",
        properties=[
            WeaponPropertyLink(
                property_code="ammunition", ammunition_item_id=arrow.id, ammunition_item=arrow,
                weapon_property=WeaponProperty(code="ammunition", name="Ammunition"),
            ),
            WeaponPropertyLink(
                property_code="range", range_normal_ft=150, range_long_ft=600,
                weapon_property=WeaponProperty(code="range", name="Range"),
            ),
        ],
    )
    return item


class TestOut:
    def test_weapon_output(self):
        out = json.loads(ItemOut.model_validate(_orm_weapon()).model_dump_json())
        assert out["cost_gp"] == 50 and out["weight_lb"] == 2
        assert out["armor"] is None and out["tool"] is None and out["container"] is None
        assert out["contents"] is None
        assert "created_by" not in out
        weapon = out["weapon"]
        assert (weapon["category_code"], weapon["damage_dice_count"], weapon["damage_die_size"]) == ("martial", 1, 8)
        ammo, rng = weapon["properties"]
        assert (ammo["code"], ammo["name"], ammo["ammunition_item_name"]) == ("ammunition", "Ammunition", "Arrow")
        assert (rng["code"], rng["range_normal_ft"], rng["range_long_ft"], rng["ammunition_item_id"]) == (
            "range", 150, 600, None,
        )

    def test_numbers_are_exact_json_numbers(self):
        item = ItemDefinition(
            id=uuid.uuid4(), name="Bullet, Sling", item_type_code="ammunition", cost_gp=Decimal("0.0020"),
            weight_lb=Decimal("0.0750"), source="srd", is_homebrew=False,
        )
        raw = ItemOut.model_validate(item).model_dump_json()
        assert '"cost_gp":0.002' in raw and '"weight_lb":0.075' in raw

    def test_tool_container_and_pack_output(self):
        lute = ItemDefinition(id=uuid.uuid4(), name="Lute", item_type_code="tool", source="srd", is_homebrew=False)
        lute.tool = Tool(tool_type_code="lute", tool_type=ToolType(
            code="lute", name="Lute", category_code="musical_instrument", ability_code="cha",
        ))
        out = json.loads(ItemOut.model_validate(lute).model_dump_json())
        assert out["tool"] == {
            "tool_type_code": "lute", "tool_type_name": "Lute", "category_code": "musical_instrument",
            "ability_code": "cha",
        }

        backpack = ItemDefinition(
            id=uuid.uuid4(), name="Backpack", item_type_code="adventuring_gear", source="srd", is_homebrew=False,
        )
        backpack.container = Container(capacity_weight_lb=Decimal("30.0000"))
        assert json.loads(ItemOut.model_validate(backpack).model_dump_json())["container"] == {"capacity_weight_lb": 30}

        torch = ItemDefinition(id=uuid.uuid4(), name="Torch", item_type_code="adventuring_gear")
        pack = ItemDefinition(id=uuid.uuid4(), name="Pack", item_type_code="pack", source="srd", is_homebrew=False)
        pack.contents = [ItemContent(item_id=torch.id, item=torch, quantity=10)]
        out = json.loads(ItemOut.model_validate(pack).model_dump_json())
        assert out["contents"] == [{"item_id": str(torch.id), "item_name": "Torch", "quantity": 10}]
