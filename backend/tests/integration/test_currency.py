"""Coins are ordinary items: money in the inventory and in starting equipment is just
an item row with a quantity (no change, no automatic sums)."""
import uuid

import pytest

from tests.integration.conftest import auth_headers, seed_character, seed_feat, seed_user, srd_item

API = "/api"


@pytest.fixture
async def owner(db_session):
    user = await seed_user(db_session)
    character = await seed_character(db_session, owner=user)
    gold = await srd_item(db_session, "Gold Piece")
    await db_session.commit()
    return dict(headers=auth_headers(user), character_id=character.id, gold_id=gold.id)


async def test_gold_in_the_inventory(api_client, owner, no_redis):
    url = f"{API}/characters/{owner['character_id']}/inventory"
    response = await api_client.post(url, json={"item_id": str(owner["gold_id"]), "quantity": 14},
                                     headers=owner["headers"])
    assert response.status_code == 201, response.text
    entry = response.json()
    assert (entry["item_name"], entry["quantity"]) == ("Gold Piece", 14)

    spent = await api_client.patch(f"{url}/{entry['id']}", json={"quantity": 9}, headers=owner["headers"])
    assert spent.status_code == 200
    assert spent.json()["quantity"] == 9


async def test_coin_quantity_can_go_to_zero(api_client, owner, no_redis):
    url = f"{API}/characters/{owner['character_id']}/inventory"
    entry = (await api_client.post(url, json={"item_id": str(owner["gold_id"]), "quantity": 14},
                                   headers=owner["headers"])).json()
    response = await api_client.patch(f"{url}/{entry['id']}", json={"quantity": 0}, headers=owner["headers"])
    # Accepted; the existing inventory rule removes an entry that reaches 0 (204).
    assert response.status_code == 204


async def test_gold_as_class_starting_equipment(api_client, owner):
    response = await api_client.post(f"{API}/compendium/classes", json={
        "name": f"Class-{uuid.uuid4().hex[:8]}", "hit_die": 8, "primary_ability": ["str"],
        "initial_equipment": [{"item_id": str(owner["gold_id"]), "option": "B", "quantity": 8}],
    }, headers=owner["headers"])
    assert response.status_code == 201, response.text
    [entry] = response.json()["initial_equipment"]
    assert (entry["item_name"], entry["quantity"], entry["option"]) == ("Gold Piece", 8, "B")


async def test_gold_as_background_starting_equipment(api_client, db_session, owner):
    feat = await seed_feat(db_session)
    await db_session.commit()
    response = await api_client.post(f"{API}/compendium/backgrounds", json={
        "name": f"Background-{uuid.uuid4().hex[:8]}", "ability_scores": ["str", "dex", "con"],
        "feat_id": str(feat.id),
        "proficiency_grants": [{"skill_code": "athletics"}, {"skill_code": "survival"},
                               {"tool_type_code": "navigators_tools"}],
        "initial_equipment": [{"item_id": str(owner["gold_id"]), "option": "B", "quantity": 50}],
    }, headers=owner["headers"])
    assert response.status_code == 201, response.text
    [entry] = response.json()["initial_equipment"]
    assert (entry["item_name"], entry["quantity"]) == ("Gold Piece", 50)
