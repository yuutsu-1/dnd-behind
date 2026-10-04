"""Backgrounds with proficiency grants, end to end over HTTP (spec acceptance scenarios)."""
import uuid

import pytest
from sqlalchemy import func, select

from app.db.models.compendium import BackgroundDefinition, ProficiencyGrant
from app.db.models.reference import ToolCategory
from tests.integration.conftest import auth_headers, seed_feat, seed_reference, seed_user

BASE = "/api/compendium/backgrounds"

SOLDIER_GRANTS = [
    {"skill_code": "athletics"},
    {"skill_code": "intimidation"},
    {"tool_category_code": "gaming_set"},
]


async def _count(db_session, model, *where) -> int:
    return await db_session.scalar(select(func.count()).select_from(model).where(*where))


@pytest.fixture
async def setup(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    feat = await seed_feat(db_session, name=f"Savage Attacker {uuid.uuid4().hex[:6]}")
    await db_session.commit()
    return dict(a=a, b=b, feat=feat)


def _payload(setup, **overrides) -> dict:
    payload = dict(
        name=f"Soldier-{uuid.uuid4().hex[:8]}",
        ability_scores=["str", "dex", "con"],
        feat_id=str(setup["feat"].id),
        proficiency_grants=SOLDIER_GRANTS,
    )
    payload.update(overrides)
    return payload


async def test_create_soldier(api_client, setup):
    response = await api_client.post(BASE, json=_payload(setup), headers=auth_headers(setup["a"]))
    assert response.status_code == 201, response.text
    body = response.json()
    assert [s["code"] for s in body["skills"]] == ["athletics", "intimidation"]
    assert [s["name"] for s in body["skills"]] == ["Athletics", "Intimidation"]
    gaming = next(g for g in body["proficiency_grants"] if g["kind"] == "tool_category")
    assert (gaming["tool_category_code"], gaming["target_name"]) == ("gaming_set", "Gaming Set")
    assert len(body["proficiency_grants"]) == 3
    assert "tool_proficiencies" not in body


@pytest.mark.parametrize("grants", [
    [{"skill_code": "athletics"}, {"tool_category_code": "gaming_set"}],
    [{"skill_code": "athletics"}, {"skill_code": "insight"}, {"skill_code": "stealth"},
     {"tool_category_code": "gaming_set"}],
    [{"skill_code": "athletics"}, {"skill_code": "intimidation"}],
    SOLDIER_GRANTS + [{"armor_category_code": "light"}],
    SOLDIER_GRANTS + [{"skill_code": "athletics"}],
    [{"skill_code": "athletics"}, {"skill_code": "intimidation"}, {"tool_category_code": "gaming_set", "skill_code": "x"}],
])
async def test_invalid_grants_are_422(api_client, setup, grants):
    response = await api_client.post(
        BASE, json=_payload(setup, proficiency_grants=grants), headers=auth_headers(setup["a"])
    )
    assert response.status_code == 422


async def test_invisible_code_is_400_and_writes_nothing(api_client, db_session, setup):
    hidden = await seed_reference(db_session, ToolCategory, author=setup["b"])
    await db_session.commit()
    grants_before = await _count(db_session, ProficiencyGrant)
    payload = _payload(setup, proficiency_grants=[
        {"skill_code": "athletics"}, {"skill_code": "survival"}, {"tool_category_code": hidden.code},
    ])
    response = await api_client.post(BASE, json=payload, headers=auth_headers(setup["a"]))
    assert response.status_code == 400
    assert await _count(db_session, BackgroundDefinition, BackgroundDefinition.name == payload["name"]) == 0
    assert await _count(db_session, ProficiencyGrant) == grants_before


async def test_patch_replaces_the_grants(api_client, db_session, setup):
    headers = auth_headers(setup["a"])
    created = (await api_client.post(BASE, json=_payload(setup), headers=headers)).json()
    old_ids = {g["id"] for g in created["proficiency_grants"]}

    response = await api_client.patch(f"{BASE}/{created['id']}", json={"proficiency_grants": [
        {"skill_code": "history"}, {"skill_code": "arcana"}, {"tool_type_code": "calligraphers_supplies"},
    ]}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["code"] for s in body["skills"]] == ["arcana", "history"]
    assert [g["tool_type_code"] for g in body["proficiency_grants"] if g["kind"] == "tool"] == ["calligraphers_supplies"]
    assert old_ids.isdisjoint({g["id"] for g in body["proficiency_grants"]})
    # The old grants are still in the database (orphans are kept).
    assert await _count(db_session, ProficiencyGrant, ProficiencyGrant.id.in_([uuid.UUID(i) for i in old_ids])) == 3

    detail = (await api_client.get(f"{BASE}/{created['id']}")).json()
    assert [s["code"] for s in detail["skills"]] == ["arcana", "history"]


async def test_patch_with_invalid_grants_is_422_and_with_unknown_code_is_400(api_client, setup):
    headers = auth_headers(setup["a"])
    created = (await api_client.post(BASE, json=_payload(setup), headers=headers)).json()
    url = f"{BASE}/{created['id']}"
    assert (await api_client.patch(url, json={"proficiency_grants": [{"skill_code": "history"}]}, headers=headers)
            ).status_code == 422
    bad = await api_client.patch(url, json={"proficiency_grants": [
        {"skill_code": "history"}, {"skill_code": "arcana"}, {"tool_type_code": "no_such_tool"},
    ]}, headers=headers)
    assert bad.status_code == 400
    detail = (await api_client.get(url)).json()
    assert [s["code"] for s in detail["skills"]] == ["athletics", "intimidation"]


async def test_patch_without_grants_keeps_them(api_client, setup):
    headers = auth_headers(setup["a"])
    created = (await api_client.post(BASE, json=_payload(setup), headers=headers)).json()
    response = await api_client.patch(f"{BASE}/{created['id']}", json={"name": "Veteran"}, headers=headers)
    assert response.status_code == 200
    assert sorted(g["id"] for g in response.json()["proficiency_grants"]) == sorted(
        g["id"] for g in created["proficiency_grants"]
    )


async def test_grants_come_out_in_the_grant_list_order(api_client, setup):
    shuffled = list(reversed(SOLDIER_GRANTS))
    response = await api_client.post(
        BASE, json=_payload(setup, proficiency_grants=shuffled), headers=auth_headers(setup["a"])
    )
    assert response.status_code == 201, response.text
    kinds = [(g["kind"], g["skill_code"] or g["tool_category_code"]) for g in response.json()["proficiency_grants"]]
    assert kinds == [("skill", "athletics"), ("skill", "intimidation"), ("tool_category", "gaming_set")]


@pytest.mark.parametrize("old_field,value", [
    ("skills", ["athletics", "intimidation"]),
    ("tool_proficiencies", ["dice_set"]),
    ("unknown_field", 1),
])
async def test_unknown_or_removed_fields_are_422_on_create_and_patch(api_client, db_session, setup, old_field, value):
    headers = auth_headers(setup["a"])
    before = await _count(db_session, BackgroundDefinition)
    response = await api_client.post(BASE, json=_payload(setup, **{old_field: value}), headers=headers)
    assert response.status_code == 422
    assert await _count(db_session, BackgroundDefinition) == before

    created = await api_client.post(BASE, json=_payload(setup), headers=headers)
    assert created.status_code == 201, created.text
    patched = await api_client.patch(f"{BASE}/{created.json()['id']}", json={old_field: value}, headers=headers)
    assert patched.status_code == 422
