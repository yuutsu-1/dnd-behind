"""GET /api/compendium/spells (list and detail): public, deterministic, with the
reference names, materials and lists of each spell."""
import uuid

import pytest

from tests.integration.conftest import auth_headers, seed_spell, seed_user, srd_spell_id

BASE = "/api/compendium/spells"


async def _list(api_client, **params) -> list[dict]:
    response = await api_client.get(BASE, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def _names(api_client, **params) -> list[str]:
    return [spell["name"] for spell in await _list(api_client, **params)]


class TestList:
    async def test_anonymous_gets_all_339_srd_spells(self, api_client):
        spells = await _list(api_client)
        assert len(spells) == 339
        assert all(s["source"] == "srd" and s["is_homebrew"] is False for s in spells)
        assert all("created_by" not in s for s in spells)

    async def test_order_is_level_then_name_and_deterministic(self, api_client):
        first = await _list(api_client)
        assert [(s["level"], s["name"]) for s in first] == sorted((s["level"], s["name"]) for s in first)
        second = await _list(api_client)
        assert [s["id"] for s in first] == [s["id"] for s in second]

    async def test_ties_on_level_and_name_are_broken_by_id(self, api_client, db_session):
        author = await seed_user(db_session)
        ids = sorted([uuid.uuid4(), uuid.uuid4()], key=str)
        for spell_id in reversed(ids):
            await seed_spell(db_session, author=author, id=spell_id, name="Acid Arrow", level=2)
        spells = await _list(api_client, search="Acid Arrow")
        assert [s["id"] for s in spells if s["is_homebrew"]] == [str(i) for i in sorted(ids)]

    async def test_list_has_the_same_shape_as_the_detail(self, api_client):
        [listed] = [s for s in await _list(api_client, search="Acid Arrow")]
        detail = (await api_client.get(f"{BASE}/{listed['id']}")).json()
        assert listed == detail

    @pytest.mark.parametrize("params,count", [
        ({"level": 0}, 27),
        ({"ritual": "true"}, 29),
        ({"concentration": "true"}, 133),
        ({"spell_list": "wizard"}, 218),
        ({"school": "evocation", "level": 3}, None),
    ])
    async def test_filters(self, api_client, params, count):
        spells = await _list(api_client, **params)
        if count is not None:
            assert len(spells) == count
        for spell in spells:
            if "level" in params:
                assert spell["level"] == params["level"]
            if "ritual" in params:
                assert spell["ritual"] is True
            if "concentration" in params:
                assert spell["concentration"] is True
            if "school" in params:
                assert spell["school_code"] == params["school"]
            if "spell_list" in params:
                assert params["spell_list"] in [lst["code"] for lst in spell["spell_lists"]]

    async def test_false_filters(self, api_client):
        assert len(await _list(api_client, ritual="false")) == 339 - 29
        assert len(await _list(api_client, concentration="false")) == 339 - 133

    async def test_wizard_list_follows_the_spell_headers(self, api_client):
        names = await _names(api_client, spell_list="wizard")
        assert "Phantasmal Force" in names and "Mind Spike" in names

    async def test_evocation_level_3_includes_fireball(self, api_client):
        assert "Fireball" in await _names(api_client, school="evocation", level=3)

    @pytest.mark.parametrize("param", ["school", "spell_list"])
    async def test_unknown_code_matches_nothing(self, api_client, param):
        assert await _list(api_client, **{param: "foo"}) == []

    @pytest.mark.parametrize("level", [-1, 10, "x"])
    async def test_level_out_of_range_is_422(self, api_client, level):
        assert (await api_client.get(BASE, params={"level": level})).status_code == 422

    async def test_search_is_case_insensitive(self, api_client):
        upper = await _names(api_client, search="FIRE")
        lower = await _names(api_client, search="fire")
        assert upper == lower
        assert "Fireball" in upper and "Delayed Blast Fireball" in upper

    async def test_search_escapes_like_wildcards(self, api_client, db_session):
        author = await seed_user(db_session)
        await seed_spell(db_session, author=author, name="100% Sure_Shot")
        assert await _names(api_client, search="%") == ["100% Sure_Shot"]
        assert await _names(api_client, search="_") == ["100% Sure_Shot"]

    async def test_homebrew_spells_are_global(self, api_client, db_session):
        author = await seed_user(db_session)
        other = await seed_user(db_session)
        await seed_spell(db_session, author=author, name="Global Homebrew Spell")
        assert await _names(api_client, search="Global Homebrew") == ["Global Homebrew Spell"]
        response = await api_client.get(BASE, params={"search": "Global Homebrew"}, headers=auth_headers(other))
        assert [s["name"] for s in response.json()] == ["Global Homebrew Spell"]

    async def test_invalid_token_is_401(self, api_client):
        response = await api_client.get(BASE, headers={"Authorization": "Bearer nope"})
        assert response.status_code == 401


class TestDetail:
    async def _get(self, api_client, name: str) -> dict:
        response = await api_client.get(f"{BASE}/{srd_spell_id(name)}")
        assert response.status_code == 200, response.text
        return response.json()

    async def test_acid_arrow(self, api_client):
        body = await self._get(api_client, "Acid Arrow")
        assert body["id"] == str(srd_spell_id("Acid Arrow"))
        assert (body["school_code"], body["school_name"]) == ("evocation", "Evocation")
        assert (body["casting_time_code"], body["casting_time_name"]) == ("action", "Action")
        assert body["spell_lists"] == [{"code": "wizard", "name": "Wizard"}]
        assert body["materials"] == [{
            "description": "powdered rhubarb leaf", "cost_gp": None, "consumed": False, "per_target": False,
            "quantity": 1,
        }]
        assert (body["range"], body["duration"], body["level"]) == ("90 feet", "Instantaneous", 2)
        assert (body["area"], body["area_shape_code"], body["area_shape_name"]) == (None, None, None)
        assert body["higher_levels"] and body["cantrip_upgrade"] is None
        assert "created_by" not in body

    async def test_clone_materials_in_order(self, api_client):
        body = await self._get(api_client, "Clone")
        assert [(m["cost_gp"], m["consumed"]) for m in body["materials"]] == [(1000, True), (2000, False)]

    async def test_gentle_repose_cost_is_a_json_number(self, api_client):
        body = await self._get(api_client, "Gentle Repose")
        assert body["materials"][0]["cost_gp"] == 0.01
        assert body["materials"][0]["quantity"] == 2

    async def test_lightning_bolt_area(self, api_client):
        body = await self._get(api_client, "Lightning Bolt")
        assert (body["area"], body["area_shape_code"], body["area_shape_name"]) == (
            "100-foot Line, 5 feet wide", "line", "Line",
        )

    async def test_lists_sorted_by_code(self, api_client):
        body = await self._get(api_client, "Phantasmal Force")
        assert body["spell_lists"] == [
            {"code": "bard", "name": "Bard"}, {"code": "sorcerer", "name": "Sorcerer"},
            {"code": "wizard", "name": "Wizard"},
        ]

    async def test_unknown_id_is_404(self, api_client):
        assert (await api_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404

    async def test_invalid_token_is_401(self, api_client):
        response = await api_client.get(f"{BASE}/{srd_spell_id('Fireball')}", headers={"Authorization": "Bearer x"})
        assert response.status_code == 401
