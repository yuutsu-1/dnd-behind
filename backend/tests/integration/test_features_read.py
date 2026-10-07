"""GET /api/compendium/features (read only): filters, order, detail, 405 on writes and
404 of the removed /feature-grants."""
import uuid

import pytest

from tests.integration.conftest import (
    auth_headers,
    seed_class,
    seed_feat,
    seed_feature,
    seed_user,
    srd_class_id,
    srd_feat_id,
    srd_feature_id,
    srd_subclass_id,
)

URL = "/api/compendium/features"


async def _get(api_client, **params) -> list[dict]:
    response = await api_client.get(URL, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_fighter_features_in_level_order(api_client):
    rows = await _get(api_client, class_id=str(srd_class_id("Fighter")))
    assert len(rows) == 20
    assert [r["level"] for r in rows] == sorted(r["level"] for r in rows)
    assert [r["level"] for r in rows if r["name"] == "Ability Score Improvement"] == [4, 6, 8, 12, 14, 16]
    assert [r["name"] for r in rows[:3]] == ["Fighting Style", "Second Wind", "Weapon Mastery"]


async def test_filters(api_client):
    assert len(await _get(api_client, subclass_id=str(srd_subclass_id("Champion")))) == 6
    grappler = await _get(api_client, feat_id=str(srd_feat_id("Grappler")))
    assert [r["name"] for r in grappler] == ["Ability Score Increase", "Punch and Grab", "Attack Advantage",
                                             "Fast Wrestler"]
    assert sorted(r["name"] for r in await _get(api_client, kind="fighting_style")) == [
        "Additional Fighting Style", "Fighting Style",
    ]
    level_one = await _get(api_client, level=1, class_id=str(srd_class_id("Fighter")))
    assert [r["name"] for r in level_one] == ["Fighting Style", "Second Wind", "Weapon Mastery"]


async def test_unknown_filters_match_nothing(api_client):
    assert await _get(api_client, kind="no_such_kind") == []
    assert await _get(api_client, class_id=str(uuid.uuid4())) == []


@pytest.mark.parametrize("level", [0, 21])
async def test_level_out_of_range_is_422(api_client, level):
    assert (await api_client.get(URL, params={"level": level})).status_code == 422


async def test_order_is_class_then_subclass_then_feat(api_client):
    rows = await _get(api_client)
    srd = [r for r in rows if not r["is_homebrew"]]
    assert len(srd) == 58
    owners = ["class" if r["class_id"] else "subclass" if r["subclass_id"] else "feat" for r in srd]
    assert owners == ["class"] * 20 + ["subclass"] * 6 + ["feat"] * 32
    assert srd[20]["name"] == "Improved Critical"
    # Feats in name order (Ability Score Improvement first, Two-Weapon Fighting last), level NULL.
    assert srd[26]["feat_id"] == str(srd_feat_id("Ability Score Improvement"))
    assert srd[-1]["feat_id"] == str(srd_feat_id("Two-Weapon Fighting"))
    alert = [r["name"] for r in srd if r["feat_id"] == str(srd_feat_id("Alert"))]
    assert alert == ["Initiative Proficiency", "Initiative Swap"]


async def test_list_has_the_detail_format(api_client):
    rows = await _get(api_client, class_id=str(srd_class_id("Fighter")), level=1)
    second_wind = next(r for r in rows if r["name"] == "Second Wind")
    detail = (await api_client.get(f"{URL}/{second_wind['id']}")).json()
    assert second_wind == detail


async def test_second_wind_detail(api_client):
    response = await api_client.get(f"{URL}/{srd_feature_id('class:Fighter/1/Second Wind')}")
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["level"], body["class_id"]) == ("Second Wind", 1, str(srd_class_id("Fighter")))
    assert (body["action_type_code"], body["action_type_name"]) == ("bonus_action", "Bonus Action")
    assert body["source"] == "srd" and body["is_homebrew"] is False
    (effect,) = body["effects"]
    assert (effect["operation_code"], effect["operation_name"]) == ("heal", "Heal")
    assert (effect["target_code"], effect["target_name"]) == ("hit_points", "Hit Points")
    assert (effect["dice_count"], effect["die_size"], effect["value_basis_code"], effect["value_basis_name"],
            effect["value_multiplier"]) == (1, 10, "class_level", "Class Level", 1)
    assert effect["choice"] is None and effect["scaling"] == []
    (resource,) = body["resources"]
    assert (resource["name"], resource["value"]) == ("Second Wind", 2)
    assert [(r["recharge_type_code"], r["recharge_type_name"], r["recovers"]) for r in resource["recharges"]] == [
        ("long_rest", "Long Rest", None), ("short_rest", "Short Rest", 1),
    ]
    assert [(s["level"], s["value"]) for s in resource["scaling"]] == [(4, 3), (10, 4)]


async def test_replaced_feature_and_choice_details(api_client):
    two = (await api_client.get(f"{URL}/{srd_feature_id('class:Fighter/11/Two Extra Attacks')}")).json()
    assert two["replaces_feature_id"] == str(srd_feature_id("class:Fighter/5/Extra Attack"))
    assert two["replaces_feature_name"] == "Extra Attack"
    style = (await api_client.get(f"{URL}/{srd_feature_id('class:Fighter/1/Fighting Style')}")).json()
    assert (style["feature_kind_code"], style["feature_kind_name"]) == ("fighting_style", "Fighting Style")
    choice = style["effects"][0]["choice"]
    assert (choice["pool_type_code"], choice["choose_count"], choice["feat_category_code"],
            choice["feat_category_name"], choice["swap_rule_code"], choice["swap_rule_name"]) == (
        "feat", 1, "fighting_style", "Fighting Style", "on_class_level_up", "On Class Level Up",
    )
    grappler = (await api_client.get(f"{URL}/{srd_feature_id('feat:Grappler/-/Ability Score Increase')}")).json()
    options = grappler["effects"][0]["choice"]["options"]
    assert [(o["ability_code"], o["target_name"]) for o in options] == [("dex", "Dexterity"), ("str", "Strength")]
    assert grappler["level"] is None and grappler["feat_id"] == str(srd_feat_id("Grappler"))


async def test_entity_target_names(api_client, db_session):
    author = await seed_user(db_session)
    feat = await seed_feat(db_session, author=author, name="Granting Feat")
    target = await seed_feat(db_session, author=author, name="Target Feat")
    feature = await seed_feature(db_session, feat=feat, effects=[dict(operation_code="grant", feat_id=target.id)])
    await db_session.commit()
    body = (await api_client.get(f"{URL}/{feature.id}")).json()
    assert (body["effects"][0]["feat_id"], body["effects"][0]["feat_name"]) == (str(target.id), "Target Feat")


async def test_missing_feature_is_404(api_client):
    assert (await api_client.get(f"{URL}/{uuid.uuid4()}")).status_code == 404


async def test_invalid_token_is_401(api_client):
    assert (await api_client.get(URL, headers={"Authorization": "Bearer nope"})).status_code == 401


async def test_writes_are_405(api_client, db_session):
    user = await seed_user(db_session)
    headers = auth_headers(user)
    feature_url = f"{URL}/{srd_feature_id('class:Fighter/1/Second Wind')}"
    assert (await api_client.post(URL, json={"name": "x"}, headers=headers)).status_code == 405
    assert (await api_client.patch(feature_url, json={"name": "x"}, headers=headers)).status_code == 405
    assert (await api_client.delete(feature_url, headers=headers)).status_code == 405
    assert (await api_client.put(feature_url, json={"name": "x"}, headers=headers)).status_code == 405


async def test_feature_grants_route_is_gone(api_client):
    assert (await api_client.get("/api/compendium/feature-grants")).status_code == 404


async def test_homebrew_class_features_are_listed(api_client, db_session):
    author = await seed_user(db_session)
    klass = await seed_class(db_session, author=author, name=f"Reader-{uuid.uuid4().hex[:6]}")
    await seed_feature(db_session, class_def=klass, name="Late", level=5)
    await seed_feature(db_session, class_def=klass, name="Early", level=1)
    await db_session.commit()
    rows = await _get(api_client, class_id=str(klass.id))
    assert [(r["name"], r["level"], r["is_homebrew"]) for r in rows] == [("Early", 1, True), ("Late", 5, True)]
