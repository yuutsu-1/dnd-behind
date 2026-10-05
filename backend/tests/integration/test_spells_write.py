"""POST/PATCH/DELETE /api/compendium/spells: homebrew spells with materials and lists."""
import uuid

import pytest
from sqlalchemy import func, select

from app.db.models.compendium import SpellDefinition
from app.db.models.reference import CastingTime, SpellList, SpellSchool
from app.db.models.spells import SpellMaterial, spell_list_spells
from tests.integration.conftest import (
    auth_headers,
    seed_campaign,
    seed_campaign_member,
    seed_reference,
    seed_user,
    srd_spell_id,
)

BASE = "/api/compendium/spells"


async def _counts(db_session) -> dict:
    return {
        "spell_definitions": await db_session.scalar(select(func.count()).select_from(SpellDefinition)),
        "spell_materials": await db_session.scalar(select(func.count()).select_from(SpellMaterial)),
        "spell_list_spells": await db_session.scalar(select(func.count()).select_from(spell_list_spells)),
    }


@pytest.fixture
async def people(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    p = await seed_user(db_session)
    c = await seed_campaign(db_session, creator=b)
    await seed_campaign_member(db_session, c, b, role="dm")
    await seed_campaign_member(db_session, c, p, role="player")
    await db_session.commit()
    # Headers up front: a handler's rollback expires the session's objects (user.id).
    return dict(a=a, b=b, p=p, c=c, ha=auth_headers(a), hb=auth_headers(b), hp=auth_headers(p))


def spell_payload(**overrides) -> dict:
    data = {
        "name": "Ember Burst", "level": 3, "school_code": "evocation", "has_verbal": True, "has_somatic": True,
        "has_material": True, "casting_time_code": "action", "ritual": False, "concentration": False,
        "range": "150 feet", "duration": "Instantaneous", "area": "20-foot-radius Sphere",
        "area_shape_code": "sphere", "description": "A burst of embers.", "higher_levels": "More embers.",
        "materials": [
            {"description": "a ruby worth 50+ GP, which the spell consumes", "cost_gp": "50", "consumed": True},
            {"description": "a pinch of ash"},
        ],
        "spell_list_codes": ["sorcerer"],
    }
    data.update(overrides)
    return data


async def _post(api_client, people, payload, who="ha"):
    return await api_client.post(BASE, json=payload, headers=people[who])


class TestCreate:
    async def test_homebrew_spell_with_two_materials_area_and_a_list(self, api_client, db_session, people):
        response = await _post(api_client, people, spell_payload())
        assert response.status_code == 201, response.text
        body = response.json()
        assert (body["source"], body["is_homebrew"]) == ("homebrew", True)
        assert "created_by" not in body
        assert (body["school_name"], body["casting_time_name"]) == ("Evocation", "Action")
        assert (body["area"], body["area_shape_code"], body["area_shape_name"]) == (
            "20-foot-radius Sphere", "sphere", "Sphere",
        )
        assert body["materials"] == [
            {"description": "a ruby worth 50+ GP, which the spell consumes", "cost_gp": 50, "consumed": True,
             "per_target": False, "quantity": 1},
            {"description": "a pinch of ash", "cost_gp": None, "consumed": False, "per_target": False, "quantity": 1},
        ]
        assert body["spell_lists"] == [{"code": "sorcerer", "name": "Sorcerer"}]
        assert body["higher_levels"] == "More embers." and body["cantrip_upgrade"] is None

        detail = (await api_client.get(f"{BASE}/{body['id']}")).json()
        assert detail == body
        stored = await db_session.get(SpellDefinition, uuid.UUID(body["id"]))
        assert stored.created_by == people["a"].id
        orders = (await db_session.execute(
            select(SpellMaterial.sort_order).where(SpellMaterial.spell_id == stored.id).order_by(SpellMaterial.sort_order)
        )).scalars().all()
        assert orders == [0, 1]

    async def test_minimal_spell_without_material_area_or_list(self, api_client, people):
        response = await _post(api_client, people, {
            "name": "Whisper", "level": 0, "school_code": "illusion", "has_verbal": True,
            "casting_time_code": "action", "range": "Touch", "duration": "1 round", "description": "Shh.",
            "cantrip_upgrade": "Louder.",
        })
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["materials"] == [] and body["spell_lists"] == [] and body["area"] is None
        assert (body["level"], body["cantrip_upgrade"]) == (0, "Louder.")

    async def test_same_name_as_an_srd_spell(self, api_client, people):
        response = await _post(api_client, people, spell_payload(name="Fireball"))
        assert response.status_code == 201, response.text
        assert response.json()["id"] != str(srd_spell_id("Fireball"))

    async def test_reaction_and_bonus_action_need_nothing_else(self, api_client, people):
        for code in ("reaction", "bonus_action", "10_minutes"):
            response = await _post(api_client, people, spell_payload(casting_time_code=code))
            assert response.status_code == 201, (code, response.text)

    async def test_own_homebrew_codes_are_accepted(self, api_client, db_session, people):
        school = await seed_reference(db_session, SpellSchool, author=people["a"])
        casting = await seed_reference(db_session, CastingTime, author=people["a"])
        spell_list = await seed_reference(db_session, SpellList, author=people["a"])
        await db_session.commit()
        response = await _post(api_client, people, spell_payload(
            school_code=school.code, casting_time_code=casting.code, spell_list_codes=[spell_list.code],
        ))
        assert response.status_code == 201, response.text
        assert response.json()["spell_lists"] == [{"code": spell_list.code, "name": spell_list.name}]

    async def test_homebrew_codes_shared_with_my_campaign_are_accepted(self, api_client, db_session, people):
        school = await seed_reference(db_session, SpellSchool, author=people["b"], campaigns=[people["c"]])
        await db_session.commit()
        response = await _post(api_client, people, spell_payload(school_code=school.code), who="hp")
        assert response.status_code == 201, response.text

    async def test_without_token_is_401(self, api_client):
        assert (await api_client.post(BASE, json=spell_payload())).status_code == 401


# 422 of the schema (shape of each field).
SCHEMA_ERRORS = {
    "level_below_0": dict(level=-1),
    "level_above_9": dict(level=10),
    "blank_name": dict(name=" "),
    "blank_range": dict(range=""),
    "blank_duration": dict(duration=" "),
    "blank_description": dict(description=""),
    "quantity_below_1": dict(materials=[{"description": "ash", "quantity": 0}]),
    "negative_cost": dict(materials=[{"description": "ash", "cost_gp": "-1"}]),
    "duplicate_lists": dict(spell_list_codes=["wizard", "wizard"]),
    "id": dict(id=str(uuid.uuid4())),
    "source": dict(source="srd"),
    "is_homebrew": dict(is_homebrew=False),
    "created_by": dict(created_by=str(uuid.uuid4())),
    "unknown_field": dict(components=["V"]),
    "casting_trigger": dict(casting_trigger="which you take when..."),
}

# 422 of coherence between fields (checked by the endpoint on the final state).
COHERENCE_ERRORS = {
    "no_component": dict(has_verbal=False, has_somatic=False, has_material=False, materials=[]),
    "material_flag_without_materials": dict(has_material=True, materials=[]),
    "materials_without_material_flag": dict(has_material=False),
    "area_without_shape": dict(area_shape_code=None),
    "shape_without_area": dict(area=None),
    "cantrip_upgrade_in_leveled_spell": dict(higher_levels=None, cantrip_upgrade="More."),
    "higher_levels_in_cantrip": dict(level=0),
}

# 400: codes that do not exist (or are not visible).
CODE_ERRORS = {
    "school": dict(school_code="pyromancy"),
    "casting_time": dict(casting_time_code="2_rounds"),
    "area_shape": dict(area_shape_code="hexagon"),
    "spell_list": dict(spell_list_codes=["artificer"]),
}


class TestCreateErrors:
    @pytest.mark.parametrize("overrides", list(SCHEMA_ERRORS.values()), ids=list(SCHEMA_ERRORS))
    async def test_schema_errors_are_422_and_write_nothing(self, api_client, db_session, people, overrides):
        before = await _counts(db_session)
        response = await _post(api_client, people, spell_payload(**overrides))
        assert response.status_code == 422, response.text
        assert await _counts(db_session) == before

    @pytest.mark.parametrize("overrides", list(COHERENCE_ERRORS.values()), ids=list(COHERENCE_ERRORS))
    async def test_coherence_errors_are_422_and_write_nothing(self, api_client, db_session, people, overrides):
        before = await _counts(db_session)
        response = await _post(api_client, people, spell_payload(**overrides))
        assert response.status_code == 422, response.text
        assert await _counts(db_session) == before

    @pytest.mark.parametrize("overrides", list(CODE_ERRORS.values()), ids=list(CODE_ERRORS))
    async def test_unknown_codes_are_400_and_write_nothing(self, api_client, db_session, people, overrides):
        before = await _counts(db_session)
        response = await _post(api_client, people, spell_payload(**overrides))
        assert response.status_code == 400, response.text
        assert await _counts(db_session) == before

    async def test_invisible_homebrew_school_is_400_with_the_unknown_message(self, api_client, db_session, people):
        hidden = (await seed_reference(db_session, SpellSchool, author=people["b"])).code
        await db_session.commit()
        before = await _counts(db_session)
        invisible = await _post(api_client, people, spell_payload(school_code=hidden))
        missing = await _post(api_client, people, spell_payload(school_code="no_such_school"))
        assert invisible.status_code == missing.status_code == 400
        assert invisible.json()["detail"] == missing.json()["detail"].replace("no_such_school", hidden)
        assert await _counts(db_session) == before

    async def test_invisible_homebrew_list_is_400(self, api_client, db_session, people):
        hidden = await seed_reference(db_session, SpellList, author=people["b"])
        await db_session.commit()
        response = await _post(api_client, people, spell_payload(spell_list_codes=["wizard", hidden.code]))
        assert response.status_code == 400

    async def test_codes_are_checked_before_coherence(self, api_client, people):
        response = await _post(api_client, people, spell_payload(school_code="pyromancy", has_material=False))
        assert response.status_code == 400


async def _create(api_client, people, who="ha", **overrides) -> dict:
    response = await _post(api_client, people, spell_payload(**overrides), who=who)
    assert response.status_code == 201, response.text
    return response.json()


async def _children(db_session, spell_id) -> tuple[list, list]:
    spell_id = uuid.UUID(str(spell_id))
    materials = (await db_session.execute(
        select(SpellMaterial.description).where(SpellMaterial.spell_id == spell_id).order_by(SpellMaterial.sort_order)
    )).scalars().all()
    lists = (await db_session.execute(
        select(spell_list_spells.c.spell_list_code).where(spell_list_spells.c.spell_id == spell_id)
        .order_by(spell_list_spells.c.spell_list_code)
    )).scalars().all()
    return list(materials), list(lists)


ORIGINAL_CHILDREN = (["a ruby worth 50+ GP, which the spell consumes", "a pinch of ash"], ["sorcerer"])


class TestUpdate:
    async def test_replace_materials(self, api_client, db_session, people):
        spell = await _create(api_client, people)
        response = await api_client.patch(f"{BASE}/{spell['id']}", json={
            "materials": [{"description": "a sapphire", "cost_gp": "0.01", "quantity": 3}],
        }, headers=people["ha"])
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["materials"] == [
            {"description": "a sapphire", "cost_gp": 0.01, "consumed": False, "per_target": False, "quantity": 3},
        ]
        assert await _children(db_session, spell["id"]) == (["a sapphire"], ["sorcerer"])

    async def test_fields_sent_are_set_and_the_rest_is_kept(self, api_client, people):
        spell = await _create(api_client, people)
        response = await api_client.patch(f"{BASE}/{spell['id']}", json={
            "name": "Renamed", "concentration": True, "duration": "Concentration, up to 1 minute",
            "spell_list_codes": ["wizard", "bard"], "area": None, "area_shape_code": None,
        }, headers=people["ha"])
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["name"], body["concentration"], body["duration"]) == (
            "Renamed", True, "Concentration, up to 1 minute",
        )
        assert [lst["code"] for lst in body["spell_lists"]] == ["bard", "wizard"]
        assert (body["area"], body["area_shape_code"]) == (None, None)
        assert len(body["materials"]) == 2 and body["range"] == "150 feet"
        assert (await api_client.get(f"{BASE}/{spell['id']}")).json() == body

    async def test_removing_materials_needs_has_material_false(self, api_client, db_session, people):
        spell = await _create(api_client, people)
        bad = await api_client.patch(f"{BASE}/{spell['id']}", json={"materials": []}, headers=people["ha"])
        assert bad.status_code == 422
        good = await api_client.patch(
            f"{BASE}/{spell['id']}", json={"materials": [], "has_material": False}, headers=people["ha"]
        )
        assert good.status_code == 200, good.text
        assert good.json()["materials"] == []
        assert await _children(db_session, spell["id"]) == ([], ["sorcerer"])

    async def test_level_0_with_higher_levels_is_422_and_changes_nothing(self, api_client, db_session, people):
        spell = await _create(api_client, people)
        before = await _counts(db_session)
        response = await api_client.patch(f"{BASE}/{spell['id']}", json={
            "level": 0, "materials": [{"description": "new"}], "spell_list_codes": ["wizard"],
        }, headers=people["ha"])
        assert response.status_code == 422
        assert (await api_client.get(f"{BASE}/{spell['id']}")).json() == spell
        assert await _counts(db_session) == before
        assert await _children(db_session, spell["id"]) == ORIGINAL_CHILDREN

    async def test_coherence_is_checked_on_the_final_state(self, api_client, people):
        spell = await _create(api_client, people)
        # Becomes a cantrip and drops `higher_levels` in the same request: coherent.
        response = await api_client.patch(f"{BASE}/{spell['id']}", json={
            "level": 0, "higher_levels": None, "cantrip_upgrade": "Stronger.",
        }, headers=people["ha"])
        assert response.status_code == 200, response.text
        assert (response.json()["level"], response.json()["cantrip_upgrade"]) == (0, "Stronger.")

    @pytest.mark.parametrize("payload", [
        {"has_verbal": False, "has_somatic": False, "has_material": False, "materials": []},
        {"area": None},
        {"area_shape_code": None},
        {"higher_levels": None, "cantrip_upgrade": "x"},
        {"has_material": False},
    ], ids=["no_component", "area_without_shape", "shape_without_area", "cantrip_upgrade_level_3",
            "materials_without_flag"])
    async def test_coherence_errors_are_422(self, api_client, people, payload):
        spell = await _create(api_client, people)
        response = await api_client.patch(f"{BASE}/{spell['id']}", json=payload, headers=people["ha"])
        assert response.status_code == 422
        assert (await api_client.get(f"{BASE}/{spell['id']}")).json() == spell

    @pytest.mark.parametrize("payload", [
        {"source": "srd"}, {"is_homebrew": False}, {"id": str(uuid.uuid4())}, {"created_by": None},
        {"level": 10}, {"name": None}, {"materials": None}, {"spell_list_codes": ["bard", "bard"]},
        {"casting_trigger": "x"},
    ])
    async def test_schema_errors_are_422(self, api_client, people, payload):
        spell = await _create(api_client, people)
        response = await api_client.patch(f"{BASE}/{spell['id']}", json=payload, headers=people["ha"])
        assert response.status_code == 422

    @pytest.mark.parametrize("payload", [
        {"school_code": "pyromancy"}, {"casting_time_code": "2_rounds"}, {"area_shape_code": "hexagon"},
        {"spell_list_codes": ["artificer"]},
        {"school_code": "pyromancy", "has_verbal": False, "has_somatic": False, "has_material": False},
    ])
    async def test_unknown_codes_are_400_and_change_nothing(self, api_client, db_session, people, payload):
        spell = await _create(api_client, people)
        before = await _counts(db_session)
        response = await api_client.patch(
            f"{BASE}/{spell['id']}", json={**payload, "materials": [{"description": "x"}]}, headers=people["ha"]
        )
        assert response.status_code == 400
        assert (await api_client.get(f"{BASE}/{spell['id']}")).json() == spell
        assert await _counts(db_session) == before

    async def test_srd_spell_is_403(self, api_client, people):
        response = await api_client.patch(
            f"{BASE}/{srd_spell_id('Fireball')}", json={"name": "Mine"}, headers=people["ha"]
        )
        assert response.status_code == 403

    async def test_other_authors_spell_is_403(self, api_client, people):
        spell = await _create(api_client, people, who="hb")
        response = await api_client.patch(f"{BASE}/{spell['id']}", json={"name": "Mine"}, headers=people["ha"])
        assert response.status_code == 403
        assert (await api_client.get(f"{BASE}/{spell['id']}")).json()["name"] == spell["name"]

    async def test_unknown_spell_is_404(self, api_client, people):
        response = await api_client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "X"}, headers=people["ha"])
        assert response.status_code == 404

    async def test_without_token_is_401(self, api_client, people):
        spell = await _create(api_client, people)
        assert (await api_client.patch(f"{BASE}/{spell['id']}", json={"name": "X"})).status_code == 401


class TestDelete:
    async def test_unused_homebrew_is_204_and_children_go_with_it(self, api_client, db_session, people):
        spell = await _create(api_client, people)
        before = await _counts(db_session)
        response = await api_client.delete(f"{BASE}/{spell['id']}", headers=people["ha"])
        assert response.status_code == 204
        assert (await api_client.get(f"{BASE}/{spell['id']}")).status_code == 404
        assert await _children(db_session, spell["id"]) == ([], [])
        assert await _counts(db_session) == {
            "spell_definitions": before["spell_definitions"] - 1,
            "spell_materials": before["spell_materials"] - 2,
            "spell_list_spells": before["spell_list_spells"] - 1,
        }

    async def test_spell_known_by_a_character_is_409_and_kept(self, api_client, db_session, people):
        from tests.integration.conftest import seed_character, seed_character_spell

        spell = await _create(api_client, people)
        stored = await db_session.get(SpellDefinition, uuid.UUID(spell["id"]))
        character = await seed_character(db_session, owner=people["a"])
        await seed_character_spell(db_session, character, stored)
        await db_session.commit()
        response = await api_client.delete(f"{BASE}/{spell['id']}", headers=people["ha"])
        assert response.status_code == 409
        assert (await api_client.get(f"{BASE}/{spell['id']}")).json() == spell
        assert await _children(db_session, spell["id"]) == ORIGINAL_CHILDREN

    async def test_srd_spell_is_403(self, api_client, people):
        response = await api_client.delete(f"{BASE}/{srd_spell_id('Fireball')}", headers=people["ha"])
        assert response.status_code == 403

    async def test_other_authors_spell_is_403(self, api_client, people):
        spell = await _create(api_client, people, who="hb")
        assert (await api_client.delete(f"{BASE}/{spell['id']}", headers=people["ha"])).status_code == 403
        assert (await api_client.get(f"{BASE}/{spell['id']}")).status_code == 200

    async def test_unknown_spell_is_404(self, api_client, people):
        assert (await api_client.delete(f"{BASE}/{uuid.uuid4()}", headers=people["ha"])).status_code == 404

    async def test_without_token_is_401(self, api_client, people):
        spell = await _create(api_client, people)
        assert (await api_client.delete(f"{BASE}/{spell['id']}")).status_code == 401
