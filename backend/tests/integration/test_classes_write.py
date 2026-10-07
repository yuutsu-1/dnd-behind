"""Classes with embedded features: GET (list/detail), POST, PATCH, DELETE (phase 4)."""
import uuid

import pytest
from sqlalchemy import text

from app.db.models.compendium import ClassDefinition

from tests.integration.conftest import (
    auth_headers,
    count_queries,
    seed_character,
    seed_character_class,
    seed_class,
    seed_feature,
    seed_subclass,
    seed_user,
    srd_class_id,
    srd_feature_id,
    srd_item,
)

URL = "/api/compendium/classes"
COUNTED = (
    "class_definitions", "class_initial_equipment", "class_skills", "class_primary_abilities",
    "class_proficiency_grants", "feature_definitions", "feature_effects", "feature_choices", "feature_resources",
    "feature_resource_recharges", "feature_scaling",
)


async def counts(db_session) -> dict[str, int]:
    return {t: (await db_session.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one() for t in COUNTED}


@pytest.fixture
async def users(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    await db_session.commit()
    return {"a": a, "b": b, "ha": auth_headers(a), "hb": auth_headers(b)}


ATTACKS = [
    {"name": "Extra Attack", "level": 5,
     "effects": [{"operation_code": "set", "target_code": "attacks_per_action", "value": 2}]},
    {"name": "Two Extra Attacks", "level": 11, "replaces_index": 0,
     "effects": [{"operation_code": "set", "target_code": "attacks_per_action", "value": 3}]},
    {"name": "Three Extra Attacks", "level": 20, "replaces_index": 1,
     "effects": [{"operation_code": "set", "target_code": "attacks_per_action", "value": 4}]},
    {"name": "Second Wind", "level": 1, "action_type_code": "bonus_action",
     "effects": [{"operation_code": "heal", "target_code": "hit_points", "dice_count": 1, "die_size": 10,
                  "value_basis_code": "class_level"}],
     "resources": [{"name": "Second Wind", "value": 2,
                    "recharges": [{"recharge_type_code": "short_rest", "recovers": 1},
                                  {"recharge_type_code": "long_rest", "recovers": None}],
                    "scaling": [{"level": 4, "value": 3}, {"level": 10, "value": 4}]}]},
]


def class_payload(**overrides) -> dict:
    payload = {
        "name": f"Brute-{uuid.uuid4().hex[:8]}", "hit_die": 12, "primary_ability": ["str"],
        "proficiency_grants": [{"saving_throw_ability_code": "str"}], "skills": ["athletics"],
        "features": ATTACKS,
    }
    payload.update(overrides)
    return payload


async def _create(api_client, headers, **overrides) -> dict:
    response = await api_client.post(URL, json=class_payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- read ---------------------------------------------------------------------------

async def test_fighter_detail_brings_everything(api_client):
    response = await api_client.get(f"{URL}/{srd_class_id('Fighter')}")
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["hit_die"], body["source"], body["is_homebrew"]) == ("Fighter", 10, "srd", False)
    assert len(body["features"]) == 20
    assert len(body["proficiency_grants"]) == 8
    assert len(body["skills"]) == 9
    assert len(body["initial_equipment"]) == 15
    assert body["primary_ability"] == ["dex", "str"]
    assert body["saving_throw_proficiencies"] == ["con", "str"]
    assert [f["level"] for f in body["features"] if f["name"] == "Ability Score Improvement"] == [
        4, 6, 8, 12, 14, 16,
    ]
    second_wind = next(f for f in body["features"] if f["name"] == "Second Wind")
    assert second_wind["id"] == str(srd_feature_id("class:Fighter/1/Second Wind"))
    assert second_wind["resources"][0]["value"] == 2


async def test_list_is_ordered_by_name_and_has_the_detail_format(api_client, db_session):
    await seed_class(db_session, name="Aaa First Class")
    await db_session.commit()
    rows = (await api_client.get(URL)).json()
    assert [r["name"] for r in rows] == sorted(r["name"] for r in rows)
    fighter = next(r for r in rows if r["name"] == "Fighter")
    assert fighter == (await api_client.get(f"{URL}/{fighter['id']}")).json()


@pytest.mark.parametrize("term,expected", [("fight", ["Fighter"]), ("%", []), ("_", [])])
async def test_search(api_client, term, expected):
    assert [r["name"] for r in (await api_client.get(URL, params={"search": term})).json()] == expected


async def test_missing_class_is_404_and_invalid_token_401(api_client):
    assert (await api_client.get(f"{URL}/{uuid.uuid4()}")).status_code == 404
    assert (await api_client.get(URL, headers={"Authorization": "Bearer nope"})).status_code == 401


class TestListClassesNoNPlusOne:
    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        from app.schemas.compendium import ClassOut
        from app.services.classes import list_classes

        marker = uuid.uuid4().hex[:8]
        for i in range(n):
            klass = await seed_class(db_session, name=f"NPlusOne-{marker}-{i}")
            await seed_feature(db_session, class_def=klass, level=1, effects=[dict(
                operation_code="grant", choice=dict(pool_type_code="weapon", choose_count=2,
                                                    scaling=[dict(level=4, value=3)]))])
            await seed_feature(db_session, class_def=klass, level=2, resources=[dict(
                name="Uses", value=1, recharges=[dict(recharge_type_code="short_rest")])])
        db_session.expunge_all()

        with count_queries(db_engine) as counter:
            classes = await list_classes(db_session, search=f"NPlusOne-{marker}")
            outs = [ClassOut.model_validate(c) for c in classes]
        assert len(outs) == n and all(len(o.features) == 2 for o in outs)
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, f"query count grew with N: {count_n2} vs {count_n6} -- N+1 in `list_classes`"


# --- POST ---------------------------------------------------------------------------

async def test_create_with_a_replacement_chain(api_client, users):
    body = await _create(api_client, users["ha"])
    assert (body["source"], body["is_homebrew"]) == ("homebrew", True)
    by_name = {f["name"]: f for f in body["features"]}
    assert [f["name"] for f in body["features"]] == [
        "Second Wind", "Extra Attack", "Two Extra Attacks", "Three Extra Attacks",
    ]
    assert by_name["Two Extra Attacks"]["replaces_feature_id"] == by_name["Extra Attack"]["id"]
    assert by_name["Two Extra Attacks"]["replaces_feature_name"] == "Extra Attack"
    assert by_name["Three Extra Attacks"]["replaces_feature_id"] == by_name["Two Extra Attacks"]["id"]
    assert all(f["class_id"] == body["id"] and f["is_homebrew"] for f in body["features"])
    resource = by_name["Second Wind"]["resources"][0]
    assert [(s["level"], s["value"]) for s in resource["scaling"]] == [(4, 3), (10, 4)]
    assert (await api_client.get(f"{URL}/{body['id']}")).json() == body


async def test_duplicate_class_name_is_409(api_client, db_session, users):
    before = await counts(db_session)
    response = await api_client.post(URL, json=class_payload(name="Fighter"), headers=users["ha"])
    assert response.status_code == 409
    assert await counts(db_session) == before


async def test_feature_error_writes_nothing(api_client, db_session, users):
    before = await counts(db_session)
    bad = [*ATTACKS, {"name": "No Level", "effects": []}]
    assert (await api_client.post(URL, json=class_payload(features=bad), headers=users["ha"])).status_code == 422
    unknown = [{"name": "X", "level": 1, "action_type_code": "no_such_action"}]
    assert (await api_client.post(URL, json=class_payload(features=unknown), headers=users["ha"])).status_code == 400
    assert await counts(db_session) == before


async def test_create_without_token_is_401(api_client):
    assert (await api_client.post(URL, json=class_payload())).status_code == 401


# --- PATCH --------------------------------------------------------------------------

async def test_patch_replaces_features_and_the_sent_collections(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    gold = await srd_item(db_session, "Gold Piece")
    response = await api_client.patch(f"{URL}/{created['id']}", json={
        "hit_die": 8, "skills": ["stealth", "acrobatics"], "primary_ability": ["dex"],
        "proficiency_grants": [{"saving_throw_ability_code": "dex"}],
        "initial_equipment": [{"item_id": str(gold.id), "option": "A", "quantity": 10}],
        "features": [{"name": "Nimble", "level": 1, "effects": [
            {"operation_code": "bonus", "target_code": "speed", "value": 10}]}],
    }, headers=users["ha"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hit_die"] == 8 and body["name"] == created["name"]
    assert sorted(s["code"] for s in body["skills"]) == ["acrobatics", "stealth"]
    assert body["primary_ability"] == ["dex"]
    assert body["saving_throw_proficiencies"] == ["dex"]
    assert [(e["item_name"], e["quantity"]) for e in body["initial_equipment"]] == [("Gold Piece", 10)]
    assert [f["name"] for f in body["features"]] == ["Nimble"]
    old_ids = {uuid.UUID(f["id"]) for f in created["features"]}
    left = (await db_session.execute(text("SELECT count(*) FROM feature_definitions WHERE id = ANY(:ids)"),
                                     {"ids": list(old_ids)})).scalar_one()
    assert left == 0
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == body


async def test_patch_without_features_keeps_them(api_client, users):
    created = await _create(api_client, users["ha"])
    body = (await api_client.patch(f"{URL}/{created['id']}", json={"description": "New"},
                                   headers=users["ha"])).json()
    assert body["description"] == "New"
    assert body["features"] == created["features"]


async def test_patch_to_an_existing_name_is_409(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    response = await api_client.patch(f"{URL}/{created['id']}", json={"name": "Fighter"}, headers=users["ha"])
    assert response.status_code == 409
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


@pytest.mark.parametrize("change,status", [
    ({"features": [{"name": "No Level"}]}, 422),
    ({"features": [{"name": "Bad", "level": 1, "effects": [{"operation_code": "heal", "target_code": "speed",
                                                            "value": 1}]}]}, 422),
    ({"skills": ["psionics"]}, 400),
    ({"hit_die": None}, 422),
    ({"id": str(uuid.uuid4())}, 422),
])
async def test_patch_errors_change_nothing(api_client, db_session, users, change, status):
    created = await _create(api_client, users["ha"])
    before = await counts(db_session)
    response = await api_client.patch(f"{URL}/{created['id']}", json={"hit_die": 6, **change}, headers=users["ha"])
    assert response.status_code == status, response.text
    assert await counts(db_session) == before
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


# --- DELETE -------------------------------------------------------------------------

async def test_delete_with_a_replacement_chain_cascades(api_client, db_session, users):
    """Risk R4: Extra -> Two -> Three Extra Attacks go with the class in one statement."""
    before = await counts(db_session)
    created = await _create(api_client, users["ha"])
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 204
    assert (await api_client.get(f"{URL}/{created['id']}")).status_code == 404
    assert await counts(db_session) == before


async def test_delete_of_a_class_used_by_a_character_is_409(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    character = await seed_character(db_session, owner=users["a"])
    klass = await db_session.get(ClassDefinition, uuid.UUID(created["id"]))
    await seed_character_class(db_session, character, klass)
    await db_session.commit()
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


async def test_delete_of_a_class_with_a_subclass_is_409(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    klass = await db_session.get(ClassDefinition, uuid.UUID(created["id"]))
    await seed_subclass(db_session, klass, author=users["a"])
    await db_session.commit()
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409


async def test_delete_of_a_class_whose_feature_is_referenced_from_outside_is_409(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    pointer = {"name": "Pointer", "category_code": "origin", "features": [{"name": "Points", "effects": [
        {"operation_code": "grant", "granted_feature_id": created["features"][0]["id"]}]}]}
    assert (await api_client.post("/api/compendium/feats", json=pointer, headers=users["ha"])).status_code == 201
    before = await counts(db_session)
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409
    assert await counts(db_session) == before
    response = await api_client.patch(f"{URL}/{created['id']}", json={"features": []}, headers=users["ha"])
    assert response.status_code == 409


# --- permission matrix ----------------------------------------------------------------

@pytest.mark.parametrize("method", ["patch", "delete"])
async def test_permission_matrix(api_client, users, method):
    async def call(url, headers):
        if method == "patch":
            return await api_client.patch(url, json={"description": "x"}, headers=headers)
        return await api_client.delete(url, headers=headers)

    assert (await call(f"{URL}/{srd_class_id('Fighter')}", users["ha"])).status_code == 403
    created = await _create(api_client, users["ha"])
    mine = f"{URL}/{created['id']}"
    assert (await call(mine, users["hb"])).status_code == 403
    assert (await call(f"{URL}/{uuid.uuid4()}", users["ha"])).status_code == 404
    assert (await call(mine, {})).status_code == 401
    assert (await api_client.get(mine)).json() == created


# --- QA cycle 1: integers are bounded (422, never a 500 DataError) ----------------------

OUT_OF_RANGE = [
    ("hit_die", 10**12), ("hit_die", 0), ("skill_choices", 10**12), ("skill_choices", -1),
    ("subclass_level", 0), ("subclass_level", 21), ("subclass_level", 10**12),
]


@pytest.mark.parametrize("field,value", OUT_OF_RANGE)
async def test_out_of_range_integer_on_post_is_422(api_client, db_session, users, field, value):
    before = await counts(db_session)
    response = await api_client.post(URL, json=class_payload(**{field: value}), headers=users["ha"])
    assert response.status_code == 422, response.text
    assert await counts(db_session) == before


@pytest.mark.parametrize("field,value", OUT_OF_RANGE)
async def test_out_of_range_integer_on_patch_is_422(api_client, users, field, value):
    created = await _create(api_client, users["ha"])
    response = await api_client.patch(f"{URL}/{created['id']}", json={field: value}, headers=users["ha"])
    assert response.status_code == 422, response.text
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


@pytest.mark.parametrize("quantity", [10**12, 0])
async def test_equipment_quantity_is_bounded(api_client, db_session, users, quantity):
    gold = await srd_item(db_session, "Gold Piece")
    equipment = [{"item_id": str(gold.id), "option": "A", "quantity": quantity}]
    response = await api_client.post(URL, json=class_payload(initial_equipment=equipment), headers=users["ha"])
    assert response.status_code == 422, response.text
    created = await _create(api_client, users["ha"])
    response = await api_client.patch(f"{URL}/{created['id']}", json={"initial_equipment": equipment},
                                      headers=users["ha"])
    assert response.status_code == 422, response.text


def test_background_equipment_quantity_is_bounded():
    from pydantic import ValidationError

    from app.schemas.compendium import BackgroundInitialEquipmentCreate

    with pytest.raises(ValidationError):
        BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=10**12)
