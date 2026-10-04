"""CRUD of homebrew reference entries over HTTP (/api/compendium/<resource>).

Pilot resource: damage-types (acceptance scenarios of the phase 1 spec), plus a
parametrized public GET over every "simple" resource."""
import uuid

import pytest
from sqlalchemy import func, select

from app.db.models.reference import CampaignHomebrewRule, DamageType
from tests.integration.conftest import (
    auth_headers,
    seed_campaign,
    seed_campaign_member,
    seed_reference,
    seed_user,
)

BASE = "/api/compendium/damage-types"

# slug -> SRD row count
SIMPLE_RESOURCES = {
    "ability-scores": 6,
    "damage-types": 13,
    "creature-types": 14,
    "alignments": 10,
    "languages": 19,
    "senses": 4,
    "movement-modes": 5,
    "weapon-categories": 2,
    "weapon-properties": 10,
    "weapon-masteries": 8,
    "armor-categories": 4,
    "tool-categories": 3,
    "spell-schools": 8,
    "recharge-types": 5,
    "action-types": 3,
    "feat-categories": 4,
    "tool-proficiencies": 25,
}


@pytest.fixture
async def people(db_session):
    """A: author, DM of C. P: player of C. B: outsider. D: campaign where A is only a player."""
    a = await seed_user(db_session)
    p = await seed_user(db_session)
    b = await seed_user(db_session)
    c = await seed_campaign(db_session, creator=a)
    await seed_campaign_member(db_session, c, a, role="dm")
    p_member = await seed_campaign_member(db_session, c, p, role="player")
    d = await seed_campaign(db_session, creator=b)
    await seed_campaign_member(db_session, d, b, role="dm")
    await seed_campaign_member(db_session, d, a, role="player")
    # Commit (releases the test savepoint; the outer transaction is still rolled back
    # at the end) so a handler's rollback on error doesn't also undo the fixture data.
    await db_session.commit()
    return dict(a=a, p=p, b=b, c=c, d=d, p_member=p_member)


async def _codes(api_client, url, user=None, **params):
    headers = auth_headers(user) if user else {}
    response = await api_client.get(url, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return [row["code"] for row in response.json()]


async def _share_rows(db_session, key):
    rows = await db_session.execute(
        select(CampaignHomebrewRule.campaign_id).where(
            CampaignHomebrewRule.resource_table == "damage_types",
            CampaignHomebrewRule.resource_key == key,
        )
    )
    return set(rows.scalars())


class TestPublicGet:
    @pytest.mark.parametrize("slug,count", list(SIMPLE_RESOURCES.items()))
    async def test_anonymous_gets_srd_sorted_by_name_then_code(self, api_client, slug, count):
        response = await api_client.get(f"/api/compendium/{slug}")
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == count
        assert all(r["source"] == "srd" and r["is_homebrew"] is False for r in rows)
        assert all(r["campaign_ids"] is None for r in rows)
        assert all("created_by" not in r for r in rows)
        assert [(r["name"], r["code"]) for r in rows] == sorted((r["name"], r["code"]) for r in rows)

    async def test_ties_on_name_are_broken_by_code(self, api_client, db_session, people):
        await seed_reference(db_session, DamageType, author=people["a"], code="zz_fire", name="Fire")
        await seed_reference(db_session, DamageType, author=people["a"], code="aa_fire", name="Fire")
        codes = await _codes(api_client, BASE, people["a"], search="fire")
        assert codes == ["aa_fire", "fire", "zz_fire"]

    async def test_search_is_case_insensitive(self, api_client):
        assert await _codes(api_client, BASE, search="FiR") == ["fire"]

    async def test_search_without_results_is_empty_list(self, api_client):
        assert await _codes(api_client, BASE, search="nothing-like-this") == []

    async def test_detail(self, api_client):
        response = await api_client.get(f"{BASE}/fire")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "fire"
        assert body["name"] == "Fire"
        assert body["campaign_ids"] is None

    async def test_detail_unknown_is_404(self, api_client):
        assert (await api_client.get(f"{BASE}/nope")).status_code == 404

    async def test_invalid_token_is_401(self, api_client):
        response = await api_client.get(BASE, headers={"Authorization": "Bearer not-a-jwt"})
        assert response.status_code == 401


class TestCreate:
    async def test_post_creates_homebrew(self, api_client, people):
        response = await api_client.post(
            BASE, json={"code": "psionic", "name": "Psionic"}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["is_homebrew"] is True
        assert body["source"] == "homebrew"
        assert body["campaign_ids"] == []
        assert "created_by" not in body

    async def test_post_without_token_is_401(self, api_client):
        response = await api_client.post(BASE, json={"code": "psionic", "name": "Psionic"})
        assert response.status_code == 401

    @pytest.mark.parametrize("payload", [
        {"code": "Psionic", "name": "Psionic"},
        {"code": "psionic", "name": ""},
        {"code": "psionic", "name": "Psionic", "source": "srd"},
        {"code": "psionic", "name": "Psionic", "is_homebrew": False},
        {"code": "psionic", "name": "Psionic", "created_by": str(uuid.uuid4())},
    ])
    async def test_invalid_payload_is_422(self, api_client, people, payload):
        response = await api_client.post(BASE, json=payload, headers=auth_headers(people["a"]))
        assert response.status_code == 422

    async def test_duplicate_srd_code_is_409(self, api_client, people):
        response = await api_client.post(
            BASE, json={"code": "fire", "name": "Fire 2"}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 409

    async def test_duplicate_code_of_invisible_homebrew_is_409(self, api_client, db_session, people):
        await seed_reference(db_session, DamageType, author=people["b"], code="psionic")
        response = await api_client.post(
            BASE, json={"code": "psionic", "name": "Psionic"}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 409

    async def test_share_with_dm_campaign(self, api_client, people):
        response = await api_client.post(
            BASE,
            json={"code": "psionic", "name": "Psionic", "campaign_ids": [str(people["c"].id)]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 201
        assert response.json()["campaign_ids"] == [str(people["c"].id)]

    async def test_share_with_player_campaign_is_403_and_writes_nothing(self, api_client, db_session, people):
        response = await api_client.post(
            BASE,
            json={"code": "psionic", "name": "Psionic", "campaign_ids": [str(people["d"].id)]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 403
        assert await db_session.get(DamageType, "psionic") is None
        assert await _share_rows(db_session, "psionic") == set()

    async def test_share_with_unknown_campaign_is_400_and_writes_nothing(self, api_client, db_session, people):
        response = await api_client.post(
            BASE,
            json={"code": "psionic", "name": "Psionic", "campaign_ids": [str(uuid.uuid4())]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 400
        count = (await db_session.execute(
            select(func.count()).select_from(DamageType).where(DamageType.code == "psionic")
        )).scalar_one()
        assert count == 0
        assert await _share_rows(db_session, "psionic") == set()

    async def test_duplicate_campaign_ids_is_422(self, api_client, people):
        cid = str(people["c"].id)
        response = await api_client.post(
            BASE, json={"code": "psionic", "name": "Psionic", "campaign_ids": [cid, cid]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 422


class TestVisibilityFlow:
    async def test_unshared_homebrew(self, api_client, people):
        await api_client.post(BASE, json={"code": "psionic", "name": "Psionic"}, headers=auth_headers(people["a"]))

        a_rows = (await api_client.get(BASE, headers=auth_headers(people["a"]))).json()
        psionic = next(r for r in a_rows if r["code"] == "psionic")
        assert psionic["campaign_ids"] == []
        assert "psionic" not in await _codes(api_client, BASE, people["b"])
        assert "psionic" not in await _codes(api_client, BASE)
        assert (await api_client.get(f"{BASE}/psionic", headers=auth_headers(people["b"]))).status_code == 404
        assert (await api_client.get(f"{BASE}/psionic")).status_code == 404
        detail = await api_client.get(f"{BASE}/psionic", headers=auth_headers(people["a"]))
        assert detail.status_code == 200
        assert detail.json()["campaign_ids"] == []

    async def test_shared_homebrew(self, api_client, db_session, people):
        await api_client.post(
            BASE, json={"code": "psionic", "name": "Psionic", "campaign_ids": [str(people["c"].id)]},
            headers=auth_headers(people["a"]),
        )
        p_rows = (await api_client.get(BASE, headers=auth_headers(people["p"]))).json()
        psionic = next(r for r in p_rows if r["code"] == "psionic")
        assert psionic["campaign_ids"] is None
        p_detail = await api_client.get(f"{BASE}/psionic", headers=auth_headers(people["p"]))
        assert p_detail.status_code == 200
        assert p_detail.json()["campaign_ids"] is None
        assert "psionic" not in await _codes(api_client, BASE, people["b"])

        await db_session.delete(people["p_member"])
        await db_session.flush()
        assert "psionic" not in await _codes(api_client, BASE, people["p"])
        assert (await api_client.get(f"{BASE}/psionic", headers=auth_headers(people["p"]))).status_code == 404


class TestPatch:
    @pytest.fixture
    async def psionic(self, db_session, people):
        entry = await seed_reference(
            db_session, DamageType, author=people["a"], code="psionic", name="Psionic", campaigns=[people["c"]]
        )
        await db_session.commit()
        return entry

    async def test_author_updates_name_and_replaces_shares(self, api_client, db_session, people, psionic):
        other = await seed_campaign(db_session, creator=people["a"])
        await seed_campaign_member(db_session, other, people["a"], role="dm")
        response = await api_client.patch(
            f"{BASE}/psionic",
            json={"name": "Psychic Force", "campaign_ids": [str(other.id)]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "Psychic Force"
        assert body["campaign_ids"] == [str(other.id)]
        assert await _share_rows(db_session, "psionic") == {other.id}

    async def test_empty_campaign_ids_removes_all_shares(self, api_client, db_session, people, psionic):
        response = await api_client.patch(
            f"{BASE}/psionic", json={"campaign_ids": []}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 200
        assert response.json()["campaign_ids"] == []
        assert await _share_rows(db_session, "psionic") == set()

    async def test_omitting_campaign_ids_keeps_shares(self, api_client, db_session, people, psionic):
        response = await api_client.patch(
            f"{BASE}/psionic", json={"description": "x"}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 200
        assert await _share_rows(db_session, "psionic") == {people["c"].id}

    async def test_code_in_body_is_422(self, api_client, people, psionic):
        response = await api_client.patch(
            f"{BASE}/psionic", json={"code": "other"}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 422

    async def test_player_who_sees_it_gets_403(self, api_client, people, psionic):
        response = await api_client.patch(
            f"{BASE}/psionic", json={"name": "X"}, headers=auth_headers(people["p"])
        )
        assert response.status_code == 403

    async def test_outsider_gets_404(self, api_client, people, psionic):
        response = await api_client.patch(
            f"{BASE}/psionic", json={"name": "X"}, headers=auth_headers(people["b"])
        )
        assert response.status_code == 404

    async def test_srd_is_403(self, api_client, people):
        response = await api_client.patch(f"{BASE}/fire", json={"name": "X"}, headers=auth_headers(people["a"]))
        assert response.status_code == 403

    async def test_unknown_is_404(self, api_client, people):
        response = await api_client.patch(f"{BASE}/nope", json={"name": "X"}, headers=auth_headers(people["a"]))
        assert response.status_code == 404

    async def test_without_token_is_401(self, api_client, psionic):
        assert (await api_client.patch(f"{BASE}/psionic", json={"name": "X"})).status_code == 401

    async def test_error_writes_nothing(self, api_client, db_session, people, psionic):
        shared_with = people["c"].id
        response = await api_client.patch(
            f"{BASE}/psionic",
            json={"name": "Changed", "campaign_ids": [str(uuid.uuid4())]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 400
        name = (await db_session.execute(select(DamageType.name).where(DamageType.code == "psionic"))).scalar_one()
        assert name == "Psionic"
        assert await _share_rows(db_session, "psionic") == {shared_with}

    async def test_share_with_player_campaign_is_403(self, api_client, people, psionic):
        response = await api_client.patch(
            f"{BASE}/psionic", json={"campaign_ids": [str(people["d"].id)]}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 403


class TestDelete:
    async def test_author_deletes_unreferenced_entry(self, api_client, db_session, people):
        await seed_reference(db_session, DamageType, author=people["a"], code="psionic", campaigns=[people["c"]])
        response = await api_client.delete(f"{BASE}/psionic", headers=auth_headers(people["a"]))
        assert response.status_code == 204
        assert "psionic" not in await _codes(api_client, BASE, people["a"])
        assert (await api_client.get(f"{BASE}/psionic", headers=auth_headers(people["a"]))).status_code == 404
        assert await _share_rows(db_session, "psionic") == set()

    async def test_srd_is_403(self, api_client, people):
        assert (await api_client.delete(f"{BASE}/fire", headers=auth_headers(people["a"]))).status_code == 403

    async def test_visible_homebrew_of_other_author_is_403(self, api_client, db_session, people):
        await seed_reference(db_session, DamageType, author=people["a"], code="psionic", campaigns=[people["c"]])
        assert (await api_client.delete(f"{BASE}/psionic", headers=auth_headers(people["p"]))).status_code == 403

    async def test_invisible_homebrew_is_404(self, api_client, db_session, people):
        await seed_reference(db_session, DamageType, author=people["a"], code="psionic")
        assert (await api_client.delete(f"{BASE}/psionic", headers=auth_headers(people["b"]))).status_code == 404

    async def test_unknown_is_404(self, api_client, people):
        assert (await api_client.delete(f"{BASE}/nope", headers=auth_headers(people["a"]))).status_code == 404

    async def test_without_token_is_401(self, api_client):
        assert (await api_client.delete(f"{BASE}/fire")).status_code == 401


@pytest.mark.parametrize("slug", sorted(SIMPLE_RESOURCES))
async def test_every_simple_resource_supports_crud(api_client, people, slug):
    """Create, read, update and delete a homebrew entry on each simple resource."""
    url = f"/api/compendium/{slug}"
    headers = auth_headers(people["a"])
    payload = {"code": "hb_entry", "name": "Homebrew Entry"}
    if slug == "languages":
        payload["rarity"] = "rare"
    created = await api_client.post(url, json=payload, headers=headers)
    assert created.status_code == 201, created.text
    assert (await api_client.get(f"{url}/hb_entry", headers=headers)).status_code == 200
    patched = await api_client.patch(f"{url}/hb_entry", json={"name": "Renamed"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"
    assert (await api_client.delete(f"{url}/hb_entry", headers=headers)).status_code == 204
    assert (await api_client.get(f"{url}/hb_entry", headers=headers)).status_code == 404
