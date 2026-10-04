"""Classes with proficiency grants, end to end over HTTP (spec acceptance scenarios)."""
import uuid

import pytest
from sqlalchemy import func, select

from app.db.models.compendium import ClassDefinition, ProficiencyGrant
from app.db.models.reference import ArmorCategory
from tests.integration.conftest import auth_headers, seed_reference, seed_user

BASE = "/api/compendium/classes"

SPEC_GRANTS = [
    {"saving_throw_ability_code": "str"},
    {"saving_throw_ability_code": "con"},
    {"weapon_category_code": "simple"},
    {"weapon_category_code": "martial", "required_weapon_property_code": "light"},
    {"armor_category_code": "light"},
    {"armor_category_code": "shield"},
    {"tool_type_code": "herbalism_kit"},
]


def _payload(**overrides) -> dict:
    payload = dict(name=f"Class-{uuid.uuid4().hex[:8]}", hit_die=10, primary_ability=["str"])
    payload.update(overrides)
    return payload


async def _count(db_session, model, *where) -> int:
    return await db_session.scalar(select(func.count()).select_from(model).where(*where))


@pytest.fixture
async def users(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    await db_session.commit()
    return dict(a=a, b=b)


async def test_create_with_the_spec_grants(api_client, users):
    response = await api_client.post(
        BASE, json=_payload(proficiency_grants=SPEC_GRANTS), headers=auth_headers(users["a"])
    )
    assert response.status_code == 201, response.text
    body = response.json()
    grants = body["proficiency_grants"]
    assert len(grants) == 7
    kinds = sorted(g["kind"] for g in grants)
    assert kinds == ["armor_category", "armor_category", "saving_throw", "saving_throw", "tool",
                     "weapon_category", "weapon_category"]
    martial = next(g for g in grants if g["weapon_category_code"] == "martial")
    assert (martial["required_weapon_property_code"], martial["target_name"], martial["required_weapon_property_name"]) \
        == ("light", "Martial", "Light")
    herbalism = next(g for g in grants if g["kind"] == "tool")
    assert (herbalism["tool_type_code"], herbalism["target_name"]) == ("herbalism_kit", "Herbalism Kit")
    assert body["saving_throw_proficiencies"] == ["con", "str"]
    for old in ("armor_proficiencies", "weapon_proficiencies", "tool_proficiencies"):
        assert old not in body


async def test_second_class_reuses_the_same_grant(api_client, db_session, users):
    first = (await api_client.post(
        BASE, json=_payload(proficiency_grants=[{"weapon_category_code": "simple"}]), headers=auth_headers(users["a"]),
    )).json()
    second = (await api_client.post(
        BASE, json=_payload(proficiency_grants=[{"weapon_category_code": "simple"}]), headers=auth_headers(users["b"]),
    )).json()
    assert first["proficiency_grants"][0]["id"] == second["proficiency_grants"][0]["id"]
    assert await _count(
        db_session, ProficiencyGrant,
        ProficiencyGrant.weapon_category_code == "simple", ProficiencyGrant.required_weapon_property_code.is_(None),
    ) == 1


@pytest.mark.parametrize("grants", [
    [{"weapon_category_code": "simple", "armor_category_code": "light"}],
    [{"skill_code": "stealth"}, {"skill_code": "stealth"}],
    [{"required_weapon_property_code": "light"}],
])
async def test_invalid_descriptor_is_422(api_client, users, grants):
    response = await api_client.post(BASE, json=_payload(proficiency_grants=grants), headers=auth_headers(users["a"]))
    assert response.status_code == 422


async def test_invisible_code_is_400_and_writes_nothing(api_client, db_session, users):
    hidden = await seed_reference(db_session, ArmorCategory, author=users["b"])
    await db_session.commit()
    grants_before = await _count(db_session, ProficiencyGrant)
    payload = _payload(proficiency_grants=[{"saving_throw_ability_code": "wis"}, {"armor_category_code": hidden.code}])
    response = await api_client.post(BASE, json=payload, headers=auth_headers(users["a"]))
    assert response.status_code == 400
    assert await _count(db_session, ClassDefinition, ClassDefinition.name == payload["name"]) == 0
    assert await _count(db_session, ProficiencyGrant) == grants_before


async def test_error_after_new_grants_rolls_them_back(api_client, db_session, users):
    grants_before = await _count(db_session, ProficiencyGrant)
    payload = _payload(
        proficiency_grants=[{"language_code": "sylvan"}],
        initial_equipment=[{"item_id": str(uuid.uuid4()), "option": "A", "quantity": 1}],
    )
    response = await api_client.post(BASE, json=payload, headers=auth_headers(users["a"]))
    assert response.status_code == 400
    assert await _count(db_session, ProficiencyGrant) == grants_before


async def test_list_and_detail_bring_the_grants(api_client, users):
    created = (await api_client.post(
        BASE, json=_payload(proficiency_grants=SPEC_GRANTS), headers=auth_headers(users["a"])
    )).json()
    detail = (await api_client.get(f"{BASE}/{created['id']}")).json()
    assert sorted(g["id"] for g in detail["proficiency_grants"]) == sorted(g["id"] for g in created["proficiency_grants"])
    assert detail["saving_throw_proficiencies"] == ["con", "str"]
    listed = (await api_client.get(BASE, params={"search": created["name"]})).json()
    assert len(listed) == 1
    assert len(listed[0]["proficiency_grants"]) == 7


def _grant_order(grant: dict) -> tuple:
    """Same key as GET /proficiency-grants: kind, target code, required property (none first)."""
    target = next(
        grant[key] for key in grant
        if key.endswith(("_code", "_id")) and key != "required_weapon_property_code" and grant[key] is not None
    )
    required = grant["required_weapon_property_code"]
    return (grant["kind"], target, required is not None, required or "", grant["id"])


async def test_grants_come_out_in_the_grant_list_order(api_client, users):
    shuffled = list(reversed(SPEC_GRANTS))
    response = await api_client.post(
        BASE, json=_payload(proficiency_grants=shuffled), headers=auth_headers(users["a"])
    )
    assert response.status_code == 201, response.text
    grants = response.json()["proficiency_grants"]
    assert grants == sorted(grants, key=_grant_order)
    detail = await api_client.get(f"{BASE}/{response.json()['id']}")
    assert detail.json()["proficiency_grants"] == grants


@pytest.mark.parametrize("old_field,value", [
    ("saving_throw_proficiencies", ["str"]),
    ("armor_proficiencies", ["light"]),
    ("weapon_proficiencies", ["simple"]),
    ("tool_proficiencies", ["herbalism_kit"]),
    ("unknown_field", 1),
])
async def test_unknown_or_removed_fields_are_422(api_client, db_session, users, old_field, value):
    before = await _count(db_session, ClassDefinition)
    response = await api_client.post(
        BASE, json=_payload(**{old_field: value}), headers=auth_headers(users["a"])
    )
    assert response.status_code == 422
    assert await _count(db_session, ClassDefinition) == before
