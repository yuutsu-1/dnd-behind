"""GET /api/compendium/proficiency-grants (list and detail): public, optional auth."""
import uuid

from tests.integration.conftest import auth_headers, seed_grant, seed_user

BASE = "/api/compendium/proficiency-grants"


def _order_key(row):
    target = next(row[c] for c in (
        "weapon_category_code", "armor_category_code", "tool_type_code", "tool_category_code", "skill_code",
        "saving_throw_ability_code", "language_code",
    ) if row[c] is not None)
    required = row["required_weapon_property_code"]
    return (row["kind"], target, required is not None, required or "", row["id"])


async def test_list_is_public_and_described(api_client, db_session):
    await seed_grant(db_session, skill_code="stealth")
    await seed_grant(db_session, weapon_category_code="martial", required_weapon_property_code="light")
    await db_session.commit()

    response = await api_client.get(BASE)
    assert response.status_code == 200
    rows = response.json()
    stealth = next(r for r in rows if r["skill_code"] == "stealth")
    assert (stealth["kind"], stealth["target_name"], stealth["required_weapon_property_name"]) == (
        "skill", "Stealth", None,
    )
    martial_light = next(r for r in rows if r["required_weapon_property_code"] == "light")
    assert (martial_light["kind"], martial_light["target_name"], martial_light["required_weapon_property_name"]) == (
        "weapon_category", "Martial", "Light",
    )


async def test_list_order_is_deterministic(api_client, db_session):
    for target in (
        {"weapon_category_code": "martial", "required_weapon_property_code": "light"},
        {"weapon_category_code": "martial"},
        {"weapon_category_code": "martial", "required_weapon_property_code": "finesse"},
        {"saving_throw_ability_code": "str"},
        {"armor_category_code": "shield"},
        {"tool_type_code": "lute"},
        {"language_code": "elvish"},
        {"skill_code": "arcana"},
    ):
        await seed_grant(db_session, **target)
    await db_session.commit()
    first = (await api_client.get(BASE)).json()
    second = (await api_client.get(BASE)).json()
    assert first == second
    assert first == sorted(first, key=_order_key)
    martial = [r["required_weapon_property_code"] for r in first if r["weapon_category_code"] == "martial"]
    assert martial == [None, "finesse", "light"]


async def test_detail(api_client, db_session):
    grant = await seed_grant(db_session, tool_category_code="gaming_set")
    await db_session.commit()
    response = await api_client.get(f"{BASE}/{grant.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(grant.id)
    assert (body["kind"], body["tool_category_code"], body["target_name"]) == ("tool_category", "gaming_set", "Gaming Set")


async def test_detail_unknown_is_404(api_client):
    assert (await api_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404


async def test_detail_with_a_valid_token(api_client, db_session):
    user = await seed_user(db_session)
    grant = await seed_grant(db_session, language_code="elvish")
    await db_session.commit()
    response = await api_client.get(f"{BASE}/{grant.id}", headers=auth_headers(user))
    assert response.status_code == 200
    assert response.json()["target_name"] == "Elvish"


async def test_invalid_token_is_401(api_client, db_session):
    grant = await seed_grant(db_session, language_code="elvish")
    await db_session.commit()
    headers = {"Authorization": "Bearer not-a-jwt"}
    assert (await api_client.get(BASE, headers=headers)).status_code == 401
    assert (await api_client.get(f"{BASE}/{grant.id}", headers=headers)).status_code == 401
