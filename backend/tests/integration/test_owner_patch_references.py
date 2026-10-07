"""QA cycle 1 of phase 4: a PATCH whose new features reference a CURRENT feature of the
same owner (it is deleted by the replacement), or a feat that references itself, is a
422 before anything is written; and the 409 of a class name is only for names."""
import uuid

import pytest
from sqlalchemy import text

from tests.integration.conftest import auth_headers, seed_user, srd_class_id

API = "/api/compendium"
COUNTED = (
    "feat_definitions", "class_definitions", "subclass_definitions", "feature_definitions", "feature_effects",
    "feature_choices", "feature_choice_options",
)


async def counts(db_session) -> dict[str, int]:
    return {t: (await db_session.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one() for t in COUNTED}


@pytest.fixture
async def headers(db_session):
    user = await seed_user(db_session)
    await db_session.commit()
    return auth_headers(user)


OWNERS = {
    "feats": lambda: {"name": "Owner Feat", "category_code": "origin",
                      "features": [{"name": "Current"}]},
    "classes": lambda: {"name": f"Owner-{uuid.uuid4().hex[:8]}", "hit_die": 8, "primary_ability": ["str"],
                        "features": [{"name": "Current", "level": 1}]},
    "subclasses": lambda: {"name": "Owner Subclass", "class_id": str(srd_class_id("Fighter")),
                           "features": [{"name": "Current", "level": 3}]},
}


def _granting(feature_id: str, owner: str) -> dict:
    feature = {"name": "New", "effects": [{"operation_code": "grant", "granted_feature_id": feature_id}]}
    if owner != "feats":
        feature["level"] = 3
    return feature


def _choosing(feature_id: str, owner: str) -> dict:
    feature = {"name": "New", "effects": [{"operation_code": "grant", "choice": {
        "pool_type_code": "feature", "choose_count": 1, "options": [{"feature_id": feature_id}]}}]}
    if owner != "feats":
        feature["level"] = 3
    return feature


@pytest.mark.parametrize("owner", list(OWNERS))
@pytest.mark.parametrize("build", [_granting, _choosing])
async def test_patch_referencing_a_current_feature_of_the_owner_is_422(api_client, db_session, headers, owner,
                                                                         build):
    created = await api_client.post(f"{API}/{owner}", json=OWNERS[owner](), headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    current = body["features"][0]["id"]
    before = await counts(db_session)
    response = await api_client.patch(f"{API}/{owner}/{body['id']}", json={"features": [build(current, owner)]},
                                      headers=headers)
    assert response.status_code == 422, response.text
    assert "current feature" in response.json()["detail"]
    assert await counts(db_session) == before
    assert (await api_client.get(f"{API}/{owner}/{body['id']}")).json() == body


async def test_patch_keeping_a_reference_to_another_owner_is_fine(api_client, headers):
    other = (await api_client.post(f"{API}/feats", json=OWNERS["feats"](), headers=headers)).json()
    mine = (await api_client.post(f"{API}/feats", json=OWNERS["feats"](), headers=headers)).json()
    response = await api_client.patch(f"{API}/feats/{mine['id']}", json={
        "features": [_granting(other["features"][0]["id"], "feats")]}, headers=headers)
    assert response.status_code == 200, response.text


def _self_fixed(feat_id: str) -> dict:
    return {"operation_code": "grant", "feat_id": feat_id}


def _self_option(feat_id: str) -> dict:
    return {"operation_code": "grant", "choice": {"pool_type_code": "feat", "choose_count": 1,
                                                  "options": [{"feat_id": feat_id}]}}


@pytest.mark.parametrize("effect", [_self_fixed, _self_option])
async def test_feat_referencing_itself_is_422(api_client, db_session, headers, effect):
    feat = (await api_client.post(f"{API}/feats", json=OWNERS["feats"](), headers=headers)).json()
    before = await counts(db_session)
    response = await api_client.patch(f"{API}/feats/{feat['id']}", json={
        "features": [{"name": "Loop", "effects": [effect(feat["id"])]}]}, headers=headers)
    assert response.status_code == 422, response.text
    assert await counts(db_session) == before
    assert (await api_client.get(f"{API}/feats/{feat['id']}")).status_code == 200
    assert (await api_client.delete(f"{API}/feats/{feat['id']}", headers=headers)).status_code == 204


async def test_class_name_conflict_message_is_only_for_names(api_client, headers):
    response = await api_client.post(f"{API}/classes", json={**OWNERS["classes"](), "name": "Fighter"},
                                     headers=headers)
    assert response.status_code == 409
    assert "Fighter" in response.json()["detail"]
    created = (await api_client.post(f"{API}/classes", json=OWNERS["classes"](), headers=headers)).json()
    pointer = {"name": "Pointer", "category_code": "origin", "features": [{"name": "P", "effects": [
        {"operation_code": "grant", "granted_feature_id": created["features"][0]["id"]}]}]}
    assert (await api_client.post(f"{API}/feats", json=pointer, headers=headers)).status_code == 201
    response = await api_client.patch(f"{API}/classes/{created['id']}", json={"features": []}, headers=headers)
    assert response.status_code == 409
    assert "already exists" not in response.json()["detail"]
    assert "conflicts with an existing one" not in response.json()["detail"]
