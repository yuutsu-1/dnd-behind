"""Subclasses with embedded features: GET (list/detail), POST, PATCH, DELETE (phase 4)."""
import uuid

import pytest
from sqlalchemy import text

from app.db.models.compendium import SubclassDefinition
from tests.integration.conftest import (
    auth_headers,
    count_queries,
    seed_character,
    seed_character_class,
    seed_class,
    seed_feature,
    seed_subclass,
    seed_user,
    srd_class,
    srd_class_id,
    srd_feature_id,
    srd_subclass_id,
)

URL = "/api/compendium/subclasses"
COUNTED = ("subclass_definitions", "feature_definitions", "feature_effects", "feature_choices", "feature_resources",
           "feature_resource_recharges", "feature_scaling")


async def counts(db_session) -> dict[str, int]:
    return {t: (await db_session.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one() for t in COUNTED}


@pytest.fixture
async def users(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    await db_session.commit()
    return {"a": a, "b": b, "ha": auth_headers(a), "hb": auth_headers(b)}


CRITICALS = [
    {"name": "Keen Edge", "level": 3,
     "effects": [{"operation_code": "set", "target_code": "critical_range", "value": 19}]},
    {"name": "Keener Edge", "level": 15, "replaces_index": 0,
     "effects": [{"operation_code": "set", "target_code": "critical_range", "value": 18}]},
]


def payload(**overrides) -> dict:
    data = {"class_id": str(srd_class_id("Fighter")), "name": "Duelist", "description": "Homebrew.",
            "features": CRITICALS}
    data.update(overrides)
    return data


async def _create(api_client, headers, **overrides) -> dict:
    response = await api_client.post(URL, json=payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- read ---------------------------------------------------------------------------

async def test_champion_detail(api_client):
    response = await api_client.get(f"{URL}/{srd_subclass_id('Champion')}")
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["class_id"], body["class_name"], body["source"]) == (
        "Champion", str(srd_class_id("Fighter")), "Fighter", "srd",
    )
    assert body["description"].startswith("_Pursue Physical Excellence in Combat_")
    assert [(f["level"], f["name"]) for f in body["features"]] == [
        (3, "Improved Critical"), (3, "Remarkable Athlete"), (7, "Additional Fighting Style"),
        (10, "Heroic Warrior"), (15, "Superior Critical"), (18, "Survivor"),
    ]
    superior = body["features"][4]
    assert superior["replaces_feature_id"] == str(srd_feature_id("subclass:Champion/3/Improved Critical"))
    assert superior["replaces_feature_name"] == "Improved Critical"
    survivor = body["features"][5]
    assert [(e["operation_code"], e["target_code"]) for e in survivor["effects"]] == [
        ("advantage", "death_saving_throw"),
    ]


async def test_list_by_class_and_order(api_client):
    rows = (await api_client.get(URL, params={"class_id": str(srd_class_id("Fighter"))})).json()
    assert [r["name"] for r in rows] == ["Champion"]
    assert rows[0] == (await api_client.get(f"{URL}/{rows[0]['id']}")).json()
    every = (await api_client.get(URL)).json()
    assert [(r["name"], r["id"]) for r in every] == sorted((r["name"], r["id"]) for r in every)


async def test_missing_subclass_is_404_and_invalid_token_401(api_client):
    assert (await api_client.get(f"{URL}/{uuid.uuid4()}")).status_code == 404
    assert (await api_client.get(URL, headers={"Authorization": "Bearer nope"})).status_code == 401


class TestListSubclassesNoNPlusOne:
    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        from app.schemas.compendium import SubclassOut
        from app.services.classes import list_subclasses

        klass = await seed_class(db_session)
        for i in range(n):
            sub = await seed_subclass(db_session, klass, name=f"Sub-{i}")
            await seed_feature(db_session, subclass=sub, level=3, effects=[dict(
                operation_code="set", target_code="critical_range", value=19)])
        db_session.expunge_all()
        with count_queries(db_engine) as counter:
            subs = await list_subclasses(db_session, class_id=klass.id)
            outs = [SubclassOut.model_validate(s) for s in subs]
        assert len(outs) == n and all(len(o.features) == 1 and o.class_name for o in outs)
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, f"query count grew with N: {count_n2} vs {count_n6}"


# --- POST ---------------------------------------------------------------------------

async def test_create_homebrew_subclass_of_the_srd_fighter(api_client, users):
    body = await _create(api_client, users["ha"])
    assert (body["class_id"], body["class_name"], body["is_homebrew"], body["source"]) == (
        str(srd_class_id("Fighter")), "Fighter", True, "homebrew",
    )
    keen, keener = body["features"]
    assert keener["replaces_feature_id"] == keen["id"]
    assert all(f["subclass_id"] == body["id"] for f in body["features"])
    assert (await api_client.get(f"{URL}/{body['id']}")).json() == body


async def test_unknown_class_is_400_and_writes_nothing(api_client, db_session, users):
    before = await counts(db_session)
    response = await api_client.post(URL, json=payload(class_id=str(uuid.uuid4())), headers=users["ha"])
    assert response.status_code == 400
    assert await counts(db_session) == before


async def test_feature_without_level_is_422_and_writes_nothing(api_client, db_session, users):
    before = await counts(db_session)
    response = await api_client.post(URL, json=payload(features=[{"name": "No Level"}]), headers=users["ha"])
    assert response.status_code == 422
    assert await counts(db_session) == before


async def test_create_without_token_is_401(api_client):
    assert (await api_client.post(URL, json=payload())).status_code == 401


# --- PATCH --------------------------------------------------------------------------

async def test_patch_replaces_features(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    response = await api_client.patch(f"{URL}/{created['id']}", json={
        "name": "Fencer", "features": [{"name": "Riposte", "level": 3, "action_type_code": "reaction"}],
    }, headers=users["ha"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["description"], body["class_id"]) == ("Fencer", "Homebrew.", created["class_id"])
    assert [f["name"] for f in body["features"]] == ["Riposte"]
    left = (await db_session.execute(text("SELECT count(*) FROM feature_definitions WHERE id = ANY(:ids)"),
                                     {"ids": [uuid.UUID(f["id"]) for f in created["features"]]})).scalar_one()
    assert left == 0


@pytest.mark.parametrize("change,status", [
    ({"class_id": str(uuid.uuid4())}, 422),  # B17: class_id cannot change
    ({"name": None}, 422),
    ({"features": [{"name": "Bad", "level": 2, "replaces_index": 0}]}, 422),
    ({"features": [{"name": "Bad", "level": 2, "feature_kind_code": "no_such_kind"}]}, 400),
])
async def test_patch_errors_change_nothing(api_client, db_session, users, change, status):
    created = await _create(api_client, users["ha"])
    before = await counts(db_session)
    response = await api_client.patch(f"{URL}/{created['id']}", json={"name": "Changed", **change},
                                      headers=users["ha"])
    assert response.status_code == status, response.text
    assert await counts(db_session) == before
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


# --- DELETE -------------------------------------------------------------------------

async def test_delete_cascades_the_features(api_client, db_session, users):
    before = await counts(db_session)
    created = await _create(api_client, users["ha"])
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 204
    assert (await api_client.get(f"{URL}/{created['id']}")).status_code == 404
    assert await counts(db_session) == before


async def test_delete_of_a_subclass_used_by_a_character_is_409(api_client, db_session, users):
    created = await _create(api_client, users["ha"])
    character = await seed_character(db_session, owner=users["a"])
    await seed_character_class(db_session, character, await srd_class(db_session),
                               subclass_id=uuid.UUID(created["id"]), level=3)
    await db_session.commit()
    assert (await api_client.delete(f"{URL}/{created['id']}", headers=users["ha"])).status_code == 409
    assert (await api_client.get(f"{URL}/{created['id']}")).json() == created


# --- permission matrix ----------------------------------------------------------------

@pytest.mark.parametrize("method", ["patch", "delete"])
async def test_permission_matrix(api_client, users, method):
    async def call(url, headers):
        if method == "patch":
            return await api_client.patch(url, json={"description": "x"}, headers=headers)
        return await api_client.delete(url, headers=headers)

    assert (await call(f"{URL}/{srd_subclass_id('Champion')}", users["ha"])).status_code == 403
    created = await _create(api_client, users["ha"])
    mine = f"{URL}/{created['id']}"
    assert (await call(mine, users["hb"])).status_code == 403
    assert (await call(f"{URL}/{uuid.uuid4()}", users["ha"])).status_code == 404
    assert (await call(mine, {})).status_code == 401
    assert (await api_client.get(mine)).json() == created


def test_subclass_model_unchanged():
    assert "class_id" in SubclassDefinition.__table__.c
