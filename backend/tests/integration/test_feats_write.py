"""POST/PATCH/DELETE /api/compendium/feats with embedded prerequisites and features."""
import uuid

import pytest
from sqlalchemy import func, select, text

from app.db.models.compendium import FeatDefinition
from app.db.models.features import FeatureDefinition
from app.db.models.reference import EffectOperation, FeatCategory
from tests.integration.conftest import auth_headers, seed_reference, seed_user, srd_feat_id

URL = "/api/compendium/feats"
FEATURE_TABLES = (
    "feat_definitions", "feat_prerequisites", "feature_definitions", "feature_effects", "feature_choices",
    "feature_choice_options", "feature_resources", "feature_resource_recharges", "feature_scaling",
)


async def table_counts(db_session) -> dict[str, int]:
    return {t: (await db_session.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one() for t in FEATURE_TABLES}


@pytest.fixture
async def users(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    await db_session.commit()
    return {"a": a, "b": b, "ha": auth_headers(a), "hb": auth_headers(b)}


def feat_payload(**overrides) -> dict:
    payload = {
        "name": "Lucky Brawler",
        "description": "A homebrew feat.",
        "category_code": "general",
        "repeatable": True,
        "prerequisites": [
            {"or_group": 1, "min_character_level": 4},
            {"or_group": 2, "ability_code": "str", "min_score": 13},
            {"or_group": 2, "ability_code": "con", "min_score": 13},
        ],
        "features": [
            {"name": "Tough Training", "description": "Grow stronger.", "effects": [{
                "operation_code": "ability_score_increase", "value": 1, "max_value": 20,
                "choice": {"pool_type_code": "ability_score", "choose_count": 1,
                           "options": [{"ability_code": "str"}, {"ability_code": "con"}],
                           "scaling": [{"level": 10, "value": 2}]},
            }]},
            {"name": "Lucky Break", "action_type_code": "reaction", "resources": [{
                "name": "Luck", "value": 1,
                "recharges": [{"recharge_type_code": "short_rest", "recovers": 1},
                              {"recharge_type_code": "long_rest"}],
                "scaling": [{"level": 5, "value": 2}, {"level": 11, "value": 3}],
            }], "effects": [{"operation_code": "bonus", "target_code": "saving_throw", "value": 2,
                             "resource_index": 0, "condition_text": "when you spend Luck"}]},
        ],
    }
    payload.update(overrides)
    return payload


# --- POST ----------------------------------------------------------------------

async def test_create_with_two_complete_features(api_client, db_session, users):
    response = await api_client.post(URL, json=feat_payload(), headers=users["ha"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["name"], body["category_code"], body["category_name"], body["repeatable"]) == (
        "Lucky Brawler", "general", "General", True,
    )
    assert (body["source"], body["is_homebrew"]) == ("homebrew", True)
    assert [(p["or_group"], p["min_character_level"], p["ability_code"], p["min_score"])
            for p in body["prerequisites"]] == [(1, 4, None, None), (2, None, "con", 13), (2, None, "str", 13)]

    training, luck = body["features"]
    assert (training["name"], training["description"], training["level"], training["feat_id"],
            training["sort_order"]) == ("Tough Training", "Grow stronger.", None, body["id"], 0)
    assert (training["source"], training["is_homebrew"]) == ("homebrew", True)
    (asi,) = training["effects"]
    assert (asi["operation_code"], asi["value"], asi["max_value"], asi["value_multiplier"]) == (
        "ability_score_increase", 1, 20, 1,
    )
    choice = asi["choice"]
    assert (choice["pool_type_code"], choice["choose_count"], choice["allow_repeat"]) == ("ability_score", 1, False)
    assert [o["ability_code"] for o in choice["options"]] == ["con", "str"]
    assert [(s["level"], s["value"]) for s in choice["scaling"]] == [(10, 2)]

    assert (luck["name"], luck["action_type_code"], luck["action_type_name"], luck["sort_order"]) == (
        "Lucky Break", "reaction", "Reaction", 1,
    )
    (resource,) = luck["resources"]
    assert (resource["name"], resource["value"]) == ("Luck", 1)
    assert [(r["recharge_type_code"], r["recovers"]) for r in resource["recharges"]] == [
        ("long_rest", None), ("short_rest", 1),
    ]
    assert [(s["level"], s["value"]) for s in resource["scaling"]] == [(5, 2), (11, 3)]
    (bonus,) = luck["effects"]
    assert bonus["resource_id"] == resource["id"]
    assert bonus["condition_text"] == "when you spend Luck"

    detail = (await api_client.get(f"{URL}/{body['id']}")).json()
    assert detail == body
    authors = (await db_session.execute(
        select(FeatureDefinition.created_by).where(FeatureDefinition.feat_id == uuid.UUID(body["id"]))
    )).scalars().all()
    assert set(authors) == {users["a"].id}
    feat = (await db_session.execute(select(FeatDefinition).where(FeatDefinition.id == uuid.UUID(body["id"])))
            ).scalar_one()
    assert feat.created_by == users["a"].id


async def test_create_without_features_or_prerequisites(api_client, users):
    response = await api_client.post(URL, json={"name": "Plain", "category_code": "origin"}, headers=users["ha"])
    assert response.status_code == 201, response.text
    assert response.json()["features"] == [] and response.json()["prerequisites"] == []


async def test_same_name_as_an_srd_feat_is_allowed(api_client, users):
    response = await api_client.post(URL, json=feat_payload(name="Grappler"), headers=users["ha"])
    assert response.status_code == 201
    assert response.json()["id"] != str(srd_feat_id("Grappler"))


async def test_without_token_is_401(api_client):
    assert (await api_client.post(URL, json=feat_payload())).status_code == 401


async def test_invisible_category_is_400_and_writes_nothing(api_client, db_session, users):
    category = await seed_reference(db_session, FeatCategory, author=users["b"])
    await db_session.commit()
    before = await table_counts(db_session)
    response = await api_client.post(URL, json=feat_payload(category_code=category.code), headers=users["ha"])
    assert response.status_code == 400
    assert await table_counts(db_session) == before


async def test_invisible_operation_is_400_and_writes_nothing(api_client, db_session, users):
    op = await seed_reference(db_session, EffectOperation, author=users["b"])
    await db_session.commit()
    before = await table_counts(db_session)
    payload = feat_payload()
    payload["features"][1]["effects"][0]["operation_code"] = op.code
    assert (await api_client.post(URL, json=payload, headers=users["ha"])).status_code == 400
    assert await table_counts(db_session) == before


@pytest.mark.parametrize("prerequisite", [
    {"or_group": 1, "ability_code": "luck", "min_score": 13},
    {"or_group": 1, "feature_kind_code": "no_such_kind"},
])
async def test_unknown_prerequisite_code_is_400(api_client, db_session, users, prerequisite):
    before = await table_counts(db_session)
    response = await api_client.post(URL, json=feat_payload(prerequisites=[prerequisite]), headers=users["ha"])
    assert response.status_code == 400
    assert await table_counts(db_session) == before


@pytest.mark.parametrize("change", [
    {"prerequisites": [{"or_group": 1}]},
    {"prerequisites": [{"or_group": 1, "ability_code": "str", "min_score": 31}]},
    {"category_code": None},
    {"name": ""},
    {"source": "srd"},
    {"is_homebrew": False},
    {"category": "origin"},
    {"level_prerequisite": 4},
])
async def test_shape_errors_are_422_and_write_nothing(api_client, db_session, users, change):
    before = await table_counts(db_session)
    response = await api_client.post(URL, json=feat_payload(**change), headers=users["ha"])
    assert response.status_code == 422
    assert await table_counts(db_session) == before


async def test_coherence_error_late_in_the_payload_writes_nothing(api_client, db_session, users):
    before = await table_counts(db_session)
    payload = feat_payload()
    payload["features"][1]["level"] = 3  # a feat feature has no level
    assert (await api_client.post(URL, json=payload, headers=users["ha"])).status_code == 422
    assert await table_counts(db_session) == before
    count = await db_session.scalar(select(func.count()).select_from(FeatDefinition).where(
        FeatDefinition.name == "Lucky Brawler"))
    assert count == 0


# --- PATCH -------------------------------------------------------------------------

async def _create(api_client, headers, **overrides) -> dict:
    response = await api_client.post(URL, json=feat_payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_patch_replaces_features_and_prerequisites(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    old_ids = {f["id"] for f in created["features"]}
    response = await api_client.patch(f"{URL}/{created['id']}", json={
        "name": "Renamed", "repeatable": False,
        "prerequisites": [{"or_group": 1, "feature_kind_code": "spellcasting"}],
        "features": [{"name": "Only One", "effects": [
            {"operation_code": "bonus", "target_code": "initiative", "value_basis_code": "proficiency_bonus"}]}],
    }, headers=users["ha"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["repeatable"], body["description"], body["category_code"]) == (
        "Renamed", False, "A homebrew feat.", "general",
    )
    assert [(p["or_group"], p["feature_kind_code"]) for p in body["prerequisites"]] == [(1, "spellcasting")]
    assert [f["name"] for f in body["features"]] == ["Only One"]
    assert body["features"][0]["id"] not in old_ids
    remaining = (await db_session.execute(
        select(func.count()).select_from(FeatureDefinition).where(FeatureDefinition.id.in_(
            [uuid.UUID(i) for i in old_ids])))).scalar_one()
    assert remaining == 0
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == body


async def test_patch_without_collections_keeps_them(api_client, users):
    created = await _create(api_client, users["ha"])
    body = (await api_client.patch(f"{URL}/{created['id']}", json={"description": None},
                                   headers=users["ha"])).json()
    assert body["description"] is None
    assert body["features"] == created["features"]
    assert body["prerequisites"] == created["prerequisites"]


async def test_patch_with_empty_lists_removes_everything(api_client, users):
    created = await _create(api_client, users["ha"])
    body = (await api_client.patch(f"{URL}/{created['id']}", json={"features": [], "prerequisites": []},
                                   headers=users["ha"])).json()
    assert body["features"] == [] and body["prerequisites"] == []


@pytest.mark.parametrize("change,status", [
    ({"name": None}, 422),
    ({"category_code": None}, 422),
    ({"repeatable": None}, 422),
    ({"features": [{"name": "Bad", "level": 2}]}, 422),
    ({"features": [{"name": "Bad", "effects": [{"operation_code": "set", "target_code": "speed"}]}]}, 422),
    ({"features": [{"name": "Bad", "effects": [{"operation_code": "no_such_op"}]}]}, 400),
    ({"category_code": "no_such_category"}, 400),
    ({"prerequisites": [{"or_group": 1, "feature_kind_code": "no_such_kind"}]}, 400),
    ({"id": str(uuid.uuid4())}, 422),
    ({"source": "srd"}, 422),
])
async def test_patch_errors_change_nothing(api_client, db_session, users, change, status):
    created = await _create(api_client, users["ha"])
    before = await table_counts(db_session)
    response = await api_client.patch(f"{URL}/{created['id']}", json={"name": "Changed", **change},
                                      headers=users["ha"])
    assert response.status_code == status, response.text
    assert await table_counts(db_session) == before
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


async def test_patch_replacing_a_feature_referenced_from_outside_is_409(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    referenced = created["features"][0]["id"]
    other = await _create(api_client, users["ha"], name="Pointer", features=[{"name": "Points", "effects": [
        {"operation_code": "grant", "granted_feature_id": referenced}]}], prerequisites=[])
    before = await table_counts(db_session)
    response = await api_client.patch(f"{URL}/{created['id']}", json={"name": "Changed", "features": []},
                                      headers=users["ha"])
    assert response.status_code == 409
    assert await table_counts(db_session) == before
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created
    assert (await api_client.get(f"{URL}/{other['id']}")).status_code == 200


# --- DELETE ------------------------------------------------------------------------

async def test_delete_removes_the_feat_and_its_children(api_client, db_session, users):
    before = await table_counts(db_session)
    created = await _create(api_client, users["ha"])
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 204
    assert (await api_client.get(f"{URL}/{created['id']}")).status_code == 404
    assert await table_counts(db_session) == before


async def test_delete_of_a_feat_used_by_a_background_is_409(api_client, db_session, users):
    from tests.integration.conftest import seed_background

    created = await _create(api_client, users["ha"])
    await seed_background(db_session, feat_id=uuid.UUID(created["id"]))
    await db_session.commit()
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


async def test_delete_of_a_feat_taken_by_a_character_is_409(api_client, db_session, users):
    from app.db.models.character import CharacterFeat
    from tests.integration.conftest import seed_character

    created = await _create(api_client, users["ha"])
    character = await seed_character(db_session, owner=users["a"])
    db_session.add(CharacterFeat(character_id=character.id, feat_id=uuid.UUID(created["id"]), source="feat",
                                 choices={}))
    await db_session.commit()
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409


def _fixed_pointer(feat_id: str) -> dict:
    return {"operation_code": "grant", "feat_id": feat_id}


def _option_pointer(feat_id: str) -> dict:
    return {"operation_code": "grant", "choice": {"pool_type_code": "feat", "choose_count": 1,
                                                  "options": [{"feat_id": feat_id}]}}


@pytest.mark.parametrize("pointer", [_fixed_pointer, _option_pointer])
async def test_delete_of_a_feat_targeted_by_another_feature_is_409(api_client, db_session, users, pointer):
    created = await _create(api_client, users["ha"])
    await _create(api_client, users["ha"], name="Pointer", prerequisites=[],
                  features=[{"name": "Points", "effects": [pointer(created["id"])]}])
    before = await table_counts(db_session)
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409
    assert await table_counts(db_session) == before


async def test_delete_of_a_feat_whose_feature_is_referenced_from_outside_is_409(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    await _create(api_client, users["ha"], name="Pointer", prerequisites=[], features=[{"name": "Points", "effects": [
        {"operation_code": "grant", "choice": {"pool_type_code": "feature", "choose_count": 1,
                                               "options": [{"feature_id": created["features"][1]["id"]}]}}]}])
    before = await table_counts(db_session)
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409
    assert await table_counts(db_session) == before


# --- permission matrix (PATCH and DELETE) ---------------------------------------------

async def _patch(api_client, url, headers):
    return await api_client.patch(url, json={"name": "X"}, headers=headers)


async def _delete(api_client, url, headers):
    return await api_client.delete(url, headers=headers)


@pytest.mark.parametrize("call", [_patch, _delete])
async def test_permission_matrix(api_client, users, call):
    srd = f"{URL}/{srd_feat_id('Alert')}"
    assert (await call(api_client, srd, users["ha"])).status_code == 403
    created = await _create(api_client, users["ha"])
    mine = f"{URL}/{created['id']}"
    assert (await call(api_client, mine, users["hb"])).status_code == 403
    assert (await call(api_client, f"{URL}/{uuid.uuid4()}", users["ha"])).status_code == 404
    assert (await call(api_client, mine, {})).status_code == 401
    assert (await api_client.get(mine)).json() == created
