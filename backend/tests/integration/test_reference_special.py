"""Reference resources with special rules: sizes, challenge-ratings, character-levels,
point-buy-costs, skills, conditions and tool-types; plus the public GET of all 33 resources."""
import pytest
from sqlalchemy import func, select

from app.db.models.reference import (
    Ability,
    CampaignHomebrewRule,
    CharacterLevel,
    Condition,
    ConditionImplication,
    Skill,
    ToolCategory,
    ToolType,
)
from tests.integration.conftest import (
    auth_headers,
    seed_campaign,
    seed_campaign_member,
    seed_reference,
    seed_user,
)
from tests.integration.test_reference_crud import SIMPLE_RESOURCES

API = "/api/compendium"

CR_ORDER = ["0", "1_8", "1_4", "1_2"] + [str(n) for n in range(1, 31)]


@pytest.fixture
async def people(db_session):
    a = await seed_user(db_session)
    p = await seed_user(db_session)
    b = await seed_user(db_session)
    c = await seed_campaign(db_session, creator=a)
    await seed_campaign_member(db_session, c, a, role="dm")
    await seed_campaign_member(db_session, c, p, role="player")
    await db_session.commit()
    return dict(a=a, p=p, b=b, c=c)


class TestPublicGetAll33:
    EXPECTED_KEYS = {
        "sizes": ["tiny", "small", "medium", "large", "huge", "gargantuan"],
        "character-levels": list(range(1, 21)),
        "point-buy-costs": list(range(8, 16)),
        "challenge-ratings": CR_ORDER,
    }

    def test_there_are_33_resources(self):
        from app.api.reference import RESOURCES

        # + skills, conditions, tool-types
        assert len(SIMPLE_RESOURCES) + len(self.EXPECTED_KEYS) + 3 == 33 == len(RESOURCES)
        assert "tool-proficiencies" not in {r.slug for r in RESOURCES}

    @pytest.mark.parametrize("slug,key", [
        ("sizes", "code"), ("character-levels", "level"), ("point-buy-costs", "score"),
        ("challenge-ratings", "code"),
    ])
    async def test_ordered_by_table_specific_key(self, api_client, slug, key):
        response = await api_client.get(f"{API}/{slug}")
        assert response.status_code == 200
        rows = response.json()
        assert [r[key] for r in rows] == self.EXPECTED_KEYS[slug]
        assert all(r["source"] == "srd" and r["is_homebrew"] is False and r["campaign_ids"] is None for r in rows)

    @pytest.mark.parametrize("slug,count", [("skills", 18), ("conditions", 15), ("tool-types", 37)])
    async def test_ordered_by_name(self, api_client, slug, count):
        rows = (await api_client.get(f"{API}/{slug}")).json()
        assert len(rows) == count
        assert [(r["name"], r["code"]) for r in rows] == sorted((r["name"], r["code"]) for r in rows)
        assert all(r["source"] == "srd" for r in rows)

    async def test_numeric_columns_are_json_numbers(self, api_client):
        tiny = (await api_client.get(f"{API}/sizes/tiny")).json()
        assert tiny["carry_multiplier"] == 7.5
        assert tiny["hit_die"] == 4
        gargantuan = (await api_client.get(f"{API}/sizes/gargantuan")).json()
        assert (gargantuan["hit_die"], gargantuan["carry_multiplier"]) == (20, 120)
        cr = (await api_client.get(f"{API}/challenge-ratings/1_4")).json()
        assert (cr["numeric_value"], cr["proficiency_bonus"]) == (0.25, 2)
        assert (await api_client.get(f"{API}/challenge-ratings/30")).json()["proficiency_bonus"] == 9

    async def test_numeric_key_detail(self, api_client):
        level5 = (await api_client.get(f"{API}/character-levels/5")).json()
        assert (level5["min_xp"], level5["proficiency_bonus"]) == (6500, 3)
        level20 = (await api_client.get(f"{API}/character-levels/20")).json()
        assert (level20["min_xp"], level20["proficiency_bonus"]) == (355000, 6)
        assert (await api_client.get(f"{API}/point-buy-costs/14")).json()["cost"] == 7
        assert (await api_client.get(f"{API}/character-levels/99")).status_code == 404

    async def test_skill_and_language_values(self, api_client):
        assert (await api_client.get(f"{API}/skills/stealth")).json()["ability_code"] == "dex"
        assert (await api_client.get(f"{API}/languages/thieves_cant")).json()["rarity"] == "rare"

    @pytest.mark.parametrize("slug", ["character-levels", "point-buy-costs"])
    async def test_search_is_ignored_on_tables_without_name(self, api_client, slug):
        all_rows = (await api_client.get(f"{API}/{slug}")).json()
        searched = (await api_client.get(f"{API}/{slug}", params={"search": "zzz"})).json()
        assert searched == all_rows

    async def test_search_on_sizes(self, api_client):
        rows = (await api_client.get(f"{API}/sizes", params={"search": "HUG"})).json()
        assert [r["code"] for r in rows] == ["huge"]


class TestSizes:
    PAYLOAD = {"code": "colossal", "name": "Colossal", "hit_die": 30, "carry_multiplier": 240, "sort_order": 7}

    async def test_create(self, api_client, people):
        response = await api_client.post(f"{API}/sizes", json=self.PAYLOAD, headers=auth_headers(people["a"]))
        assert response.status_code == 201, response.text
        assert response.json()["carry_multiplier"] == 240

    async def test_duplicate_sort_order_is_409(self, api_client, people):
        payload = {**self.PAYLOAD, "sort_order": 3}
        response = await api_client.post(f"{API}/sizes", json=payload, headers=auth_headers(people["a"]))
        assert response.status_code == 409

    async def test_patch_to_taken_sort_order_is_409(self, api_client, people):
        headers = auth_headers(people["a"])
        assert (await api_client.post(f"{API}/sizes", json=self.PAYLOAD, headers=headers)).status_code == 201
        response = await api_client.patch(f"{API}/sizes/colossal", json={"sort_order": 1}, headers=headers)
        assert response.status_code == 409

    async def test_patch_keeping_own_sort_order_is_ok(self, api_client, people):
        headers = auth_headers(people["a"])
        await api_client.post(f"{API}/sizes", json=self.PAYLOAD, headers=headers)
        response = await api_client.patch(f"{API}/sizes/colossal", json={"sort_order": 7, "hit_die": 40}, headers=headers)
        assert response.status_code == 200
        assert response.json()["hit_die"] == 40

    async def test_invalid_hit_die_is_422(self, api_client, people):
        payload = {**self.PAYLOAD, "hit_die": 0}
        response = await api_client.post(f"{API}/sizes", json=payload, headers=auth_headers(people["a"]))
        assert response.status_code == 422


class TestChallengeRatings:
    async def test_duplicate_numeric_value_is_409(self, api_client, people):
        payload = {"code": "quarter", "name": "Quarter", "numeric_value": 0.25, "proficiency_bonus": 2}
        response = await api_client.post(f"{API}/challenge-ratings", json=payload, headers=auth_headers(people["a"]))
        assert response.status_code == 409

    async def test_create_and_order(self, api_client, people):
        headers = auth_headers(people["a"])
        payload = {"code": "1_16", "name": "1/16", "numeric_value": 0.0625, "proficiency_bonus": 2}
        response = await api_client.post(f"{API}/challenge-ratings", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        codes = [r["code"] for r in (await api_client.get(f"{API}/challenge-ratings", headers=headers)).json()]
        assert codes[:3] == ["0", "1_16", "1_8"]


class TestNumericKeyedResources:
    async def test_character_level_create_share_patch_delete(self, api_client, db_session, people):
        headers = auth_headers(people["a"])
        response = await api_client.post(
            f"{API}/character-levels",
            json={"level": 21, "min_xp": 400000, "proficiency_bonus": 7, "campaign_ids": [str(people["c"].id)]},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["campaign_ids"] == [str(people["c"].id)]
        share_keys = (await db_session.execute(
            select(CampaignHomebrewRule.resource_key).where(CampaignHomebrewRule.resource_table == "character_levels")
        )).scalars().all()
        assert share_keys == ["21"]

        p_levels = [r["level"] for r in (await api_client.get(f"{API}/character-levels", headers=auth_headers(people["p"]))).json()]
        assert p_levels[-1] == 21
        b_levels = [r["level"] for r in (await api_client.get(f"{API}/character-levels", headers=auth_headers(people["b"]))).json()]
        assert 21 not in b_levels

        patched = await api_client.patch(f"{API}/character-levels/21", json={"min_xp": 410000}, headers=headers)
        assert patched.status_code == 200
        assert patched.json()["min_xp"] == 410000
        assert (await api_client.delete(f"{API}/character-levels/21", headers=headers)).status_code == 204

    async def test_duplicate_level_is_409(self, api_client, people):
        response = await api_client.post(
            f"{API}/character-levels", json={"level": 5, "min_xp": 1, "proficiency_bonus": 3},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 409

    async def test_duplicate_score_is_409(self, api_client, people):
        response = await api_client.post(
            f"{API}/point-buy-costs", json={"score": 14, "cost": 1}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 409

    async def test_key_in_patch_body_is_422(self, api_client, db_session, people):
        await seed_reference(db_session, CharacterLevel, author=people["a"], level=21, min_xp=1, proficiency_bonus=7)
        response = await api_client.patch(
            f"{API}/character-levels/21", json={"level": 22}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 422

    async def test_invalid_bounds_are_422(self, api_client, people):
        headers = auth_headers(people["a"])
        assert (await api_client.post(
            f"{API}/character-levels", json={"level": 0, "min_xp": 0, "proficiency_bonus": 2}, headers=headers,
        )).status_code == 422
        assert (await api_client.post(
            f"{API}/point-buy-costs", json={"score": 16, "cost": -1}, headers=headers,
        )).status_code == 422

    async def test_point_buy_create(self, api_client, people):
        response = await api_client.post(
            f"{API}/point-buy-costs", json={"score": 16, "cost": 12}, headers=auth_headers(people["a"])
        )
        assert response.status_code == 201
        assert response.json() == {
            "score": 16, "cost": 12, "source": "homebrew", "is_homebrew": True, "campaign_ids": [],
        }


class TestSkills:
    async def test_create_with_srd_ability(self, api_client, people):
        response = await api_client.post(
            f"{API}/skills", json={"code": "psionics", "name": "Psionics", "ability_code": "int"},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 201, response.text
        assert response.json()["ability_code"] == "int"

    async def test_unknown_ability_is_400(self, api_client, db_session, people):
        response = await api_client.post(
            f"{API}/skills", json={"code": "psionics", "name": "Psionics", "ability_code": "luck"},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 400
        assert await db_session.get(Skill, "psionics") is None

    async def test_invisible_homebrew_ability_is_400_with_same_message(self, api_client, db_session, people):
        await seed_reference(db_session, Ability, author=people["b"], code="luck", name="Luck")
        await db_session.commit()
        headers = auth_headers(people["a"])
        invisible = await api_client.post(
            f"{API}/skills", json={"code": "psionics", "name": "Psionics", "ability_code": "luck"}, headers=headers,
        )
        unknown = await api_client.post(
            f"{API}/skills", json={"code": "psionics", "name": "Psionics", "ability_code": "fate"}, headers=headers,
        )
        assert invisible.status_code == unknown.status_code == 400
        assert invisible.json()["detail"].replace("luck", "X") == unknown.json()["detail"].replace("fate", "X")

    async def test_own_homebrew_ability_is_accepted(self, api_client, db_session, people):
        await seed_reference(db_session, Ability, author=people["a"], code="luck", name="Luck")
        response = await api_client.post(
            f"{API}/skills", json={"code": "gambling", "name": "Gambling", "ability_code": "luck"},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 201

    async def test_patch_validates_ability(self, api_client, db_session, people):
        await seed_reference(db_session, Skill, author=people["a"], code="psionics", name="Psionics", ability_code="int")
        await db_session.commit()
        headers = auth_headers(people["a"])
        bad = await api_client.patch(f"{API}/skills/psionics", json={"ability_code": "luck"}, headers=headers)
        assert bad.status_code == 400
        good = await api_client.patch(f"{API}/skills/psionics", json={"ability_code": "wis"}, headers=headers)
        assert good.status_code == 200
        assert good.json()["ability_code"] == "wis"


class TestToolTypes:
    async def test_public_list_is_srd_only_and_deterministic(self, api_client, db_session, people):
        await seed_reference(db_session, ToolType, author=people["a"], code="harp", name="Harp", ability_code="cha")
        await db_session.commit()
        first = (await api_client.get(f"{API}/tool-types")).json()
        second = (await api_client.get(f"{API}/tool-types")).json()
        assert first == second
        assert len(first) == 37
        assert all(r["source"] == "srd" for r in first)
        lute = next(r for r in first if r["code"] == "lute")
        assert (lute["category_code"], lute["ability_code"]) == ("musical_instrument", "cha")
        thieves = (await api_client.get(f"{API}/tool-types/thieves_tools")).json()
        assert (thieves["category_code"], thieves["ability_code"]) == (None, "dex")

    async def test_item_types_public_list(self, api_client):
        rows = (await api_client.get(f"{API}/item-types")).json()
        assert {r["code"] for r in rows} == {
            "weapon", "armor", "tool", "ammunition", "adventuring_gear", "pack", "currency",
        }

    async def test_create(self, api_client, people):
        response = await api_client.post(
            f"{API}/tool-types",
            json={"code": "harp", "name": "Harp", "category_code": "musical_instrument", "ability_code": "cha"},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert (body["category_code"], body["ability_code"], body["is_homebrew"]) == ("musical_instrument", "cha", True)

    async def test_create_without_category(self, api_client, people):
        response = await api_client.post(
            f"{API}/tool-types", json={"code": "lockpicks", "name": "Lockpicks", "ability_code": "dex"},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 201, response.text
        assert response.json()["category_code"] is None

    async def test_missing_ability_is_422(self, api_client, people):
        response = await api_client.post(
            f"{API}/tool-types", json={"code": "harp", "name": "Harp"}, headers=auth_headers(people["a"]),
        )
        assert response.status_code == 422

    async def test_unknown_ability_is_400(self, api_client, db_session, people):
        response = await api_client.post(
            f"{API}/tool-types", json={"code": "harp", "name": "Harp", "ability_code": "luck"},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 400
        assert await db_session.get(ToolType, "harp") is None

    async def test_invisible_homebrew_category_is_400(self, api_client, db_session, people):
        await seed_reference(db_session, ToolCategory, author=people["b"], code="weird_kits", name="Weird Kits")
        await db_session.commit()
        response = await api_client.post(
            f"{API}/tool-types",
            json={"code": "harp", "name": "Harp", "category_code": "weird_kits", "ability_code": "cha"},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 400
        assert await db_session.get(ToolType, "harp") is None

    async def test_patch(self, api_client, db_session, people):
        await seed_reference(
            db_session, ToolType, author=people["a"], code="harp", name="Harp",
            category_code="musical_instrument", ability_code="cha",
        )
        await db_session.commit()
        headers = auth_headers(people["a"])
        assert (await api_client.patch(
            f"{API}/tool-types/harp", json={"ability_code": None}, headers=headers,
        )).status_code == 422
        assert (await api_client.patch(
            f"{API}/tool-types/harp", json={"category_code": "nope"}, headers=headers,
        )).status_code == 400
        cleared = await api_client.patch(f"{API}/tool-types/harp", json={"category_code": None}, headers=headers)
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["category_code"] is None

    async def test_invalid_token_is_401(self, api_client):
        for slug in ("tool-types", "item-types"):
            response = await api_client.get(f"{API}/{slug}", headers={"Authorization": "Bearer not-a-jwt"})
            assert response.status_code == 401

    async def test_tool_proficiencies_route_is_gone(self, api_client):
        assert (await api_client.get(f"{API}/tool-proficiencies")).status_code == 404


class TestConditions:
    async def _implications(self, db_session, code):
        rows = await db_session.execute(
            select(ConditionImplication.implied_condition_code)
            .where(ConditionImplication.condition_code == code)
        )
        return set(rows.scalars())

    async def test_srd_implications_are_returned(self, api_client):
        assert (await api_client.get(f"{API}/conditions/paralyzed")).json()["implies"] == ["incapacitated"]
        unconscious = (await api_client.get(f"{API}/conditions/unconscious")).json()
        assert unconscious["implies"] == ["incapacitated", "prone"]
        assert (await api_client.get(f"{API}/conditions/blinded")).json()["implies"] == []

    async def test_create_with_implies(self, api_client, db_session, people):
        response = await api_client.post(
            f"{API}/conditions", json={"code": "dazed", "name": "Dazed", "implies": ["incapacitated"]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 201, response.text
        assert response.json()["implies"] == ["incapacitated"]
        assert await self._implications(db_session, "dazed") == {"incapacitated"}

    async def test_implies_unknown_is_400_and_writes_nothing(self, api_client, db_session, people):
        response = await api_client.post(
            f"{API}/conditions", json={"code": "dazed", "name": "Dazed", "implies": ["incapacitated", "nope"]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 400
        count = (await db_session.execute(
            select(func.count()).select_from(Condition).where(Condition.code == "dazed")
        )).scalar_one()
        assert count == 0
        assert await self._implications(db_session, "dazed") == set()

    async def test_implies_itself_is_422(self, api_client, people):
        response = await api_client.post(
            f"{API}/conditions", json={"code": "dazed", "name": "Dazed", "implies": ["dazed"]},
            headers=auth_headers(people["a"]),
        )
        assert response.status_code == 422

    async def test_patch_replaces_implications(self, api_client, db_session, people):
        headers = auth_headers(people["a"])
        await api_client.post(
            f"{API}/conditions", json={"code": "dazed", "name": "Dazed", "implies": ["incapacitated"]}, headers=headers
        )
        response = await api_client.patch(f"{API}/conditions/dazed", json={"implies": ["prone", "blinded"]}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["implies"] == ["blinded", "prone"]
        assert await self._implications(db_session, "dazed") == {"prone", "blinded"}

        cleared = await api_client.patch(f"{API}/conditions/dazed", json={"implies": []}, headers=headers)
        assert cleared.json()["implies"] == []

    async def test_patch_implies_own_code_is_422(self, api_client, people):
        headers = auth_headers(people["a"])
        await api_client.post(f"{API}/conditions", json={"code": "dazed", "name": "Dazed"}, headers=headers)
        response = await api_client.patch(f"{API}/conditions/dazed", json={"implies": ["dazed"]}, headers=headers)
        assert response.status_code == 422

    async def test_patch_implies_unknown_is_400(self, api_client, db_session, people):
        headers = auth_headers(people["a"])
        await api_client.post(
            f"{API}/conditions", json={"code": "dazed", "name": "Dazed", "implies": ["prone"]}, headers=headers
        )
        response = await api_client.patch(f"{API}/conditions/dazed", json={"implies": ["nope"]}, headers=headers)
        assert response.status_code == 400
        assert await self._implications(db_session, "dazed") == {"prone"}

    async def test_implies_is_filtered_by_visibility(self, api_client, db_session, people):
        await seed_reference(db_session, Condition, author=people["a"], code="dazed", name="Dazed")
        await seed_reference(db_session, Condition, author=people["a"], code="woozy", name="Woozy", campaigns=[people["c"]])
        db_session.add(ConditionImplication(condition_code="woozy", implied_condition_code="dazed"))
        db_session.add(ConditionImplication(condition_code="woozy", implied_condition_code="prone"))
        await db_session.flush()

        as_author = (await api_client.get(f"{API}/conditions/woozy", headers=auth_headers(people["a"]))).json()
        assert as_author["implies"] == ["dazed", "prone"]
        as_player = (await api_client.get(f"{API}/conditions/woozy", headers=auth_headers(people["p"]))).json()
        assert as_player["implies"] == ["prone"]
        listed = (await api_client.get(f"{API}/conditions", headers=auth_headers(people["p"]))).json()
        assert next(r for r in listed if r["code"] == "woozy")["implies"] == ["prone"]


PHASE3_SLUGS = ["area-shapes", "spell-lists", "casting-times"]


class TestPhase3References:
    @pytest.mark.parametrize("slug", PHASE3_SLUGS)
    async def test_invalid_token_is_401(self, api_client, slug):
        response = await api_client.get(f"{API}/{slug}", headers={"Authorization": "Bearer not-a-token"})
        assert response.status_code == 401

    @pytest.mark.parametrize("slug", PHASE3_SLUGS)
    async def test_post_without_token_is_401(self, api_client, slug):
        response = await api_client.post(f"{API}/{slug}", json={"code": "hb_x", "name": "X"})
        assert response.status_code == 401

    @pytest.mark.parametrize("slug,srd_code", [
        ("area-shapes", "sphere"), ("spell-lists", "wizard"), ("casting-times", "action"),
    ])
    async def test_patch_and_delete_of_srd_is_403(self, api_client, people, slug, srd_code):
        headers = auth_headers(people["a"])
        assert (await api_client.patch(f"{API}/{slug}/{srd_code}", json={"name": "X"}, headers=headers)).status_code == 403
        assert (await api_client.delete(f"{API}/{slug}/{srd_code}", headers=headers)).status_code == 403

    @pytest.mark.parametrize("slug", PHASE3_SLUGS)
    async def test_homebrew_shared_with_campaign_is_visible_to_member_only(self, api_client, people, slug):
        created = await api_client.post(
            f"{API}/{slug}", json={"code": "hb_shared", "name": "Shared", "campaign_ids": [str(people["c"].id)]},
            headers=auth_headers(people["a"]),
        )
        assert created.status_code == 201, created.text
        assert (await api_client.get(f"{API}/{slug}/hb_shared", headers=auth_headers(people["p"]))).status_code == 200
        assert (await api_client.get(f"{API}/{slug}/hb_shared", headers=auth_headers(people["b"]))).status_code == 404
        other = await api_client.patch(
            f"{API}/{slug}/hb_shared", json={"name": "Mine"}, headers=auth_headers(people["p"])
        )
        assert other.status_code == 403


PHASE4_SLUGS = {
    "effect-operations": "grant", "effect-targets": "armor_class", "value-bases": "class_level",
    "choice-pool-types": "feat", "choice-swap-rules": "on_long_rest_one", "feature-kinds": "fighting_style",
}


@pytest.mark.parametrize("slug,srd_code", list(PHASE4_SLUGS.items()))
async def test_phase4_resources_follow_the_phase1_matrix(api_client, people, slug, srd_code):
    url = f"{API}/{slug}"
    # Ids/headers first: the 403 below rolls the session back and expires the fixture rows.
    campaign_id = str(people["c"].id)
    headers, other, player = (auth_headers(people[key]) for key in ("a", "b", "p"))
    assert (await api_client.get(f"{url}/{srd_code}")).status_code == 200
    bad_token = {"Authorization": "Bearer not-a-token"}
    assert (await api_client.get(url, headers=bad_token)).status_code == 401
    assert (await api_client.patch(f"{url}/{srd_code}", json={"name": "X"}, headers=headers)).status_code == 403
    assert (await api_client.delete(f"{url}/{srd_code}", headers=headers)).status_code == 403
    created = await api_client.post(url, json={"code": "hb_x", "name": "X", "campaign_ids": [campaign_id]},
                                    headers=headers)
    assert created.status_code == 201, created.text
    assert (await api_client.get(f"{url}/hb_x", headers=other)).status_code == 404
    assert (await api_client.get(f"{url}/hb_x", headers=player)).status_code == 200
