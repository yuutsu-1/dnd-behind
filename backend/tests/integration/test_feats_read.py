"""GET /api/compendium/feats (list and detail) with prerequisites and full features."""
import uuid

import pytest

from tests.integration.conftest import count_queries, seed_feat, seed_feature, seed_user, srd_feat_id

URL = "/api/compendium/feats"


async def _get(api_client, **params) -> list[dict]:
    response = await api_client.get(URL, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_lists_the_17_srd_feats_by_name(api_client):
    rows = await _get(api_client)
    assert len(rows) == 17
    assert [r["name"] for r in rows] == sorted(r["name"] for r in rows)
    assert all(r["source"] == "srd" and r["is_homebrew"] is False for r in rows)


async def test_category_filter(api_client):
    rows = await _get(api_client, category="epic_boon")
    assert len(rows) == 7
    assert {(r["category_code"], r["category_name"]) for r in rows} == {("epic_boon", "Epic Boon")}
    assert await _get(api_client, category="no_such_category") == []


@pytest.mark.parametrize("term", ["boon", "BOON", "Boon of"])
async def test_search_is_case_insensitive(api_client, term):
    assert len(await _get(api_client, search=term)) == 7


@pytest.mark.parametrize("term", ["%", "_"])
async def test_search_wildcards_are_literal(api_client, term):
    assert await _get(api_client, search=term) == []


async def test_grappler_detail(api_client):
    response = await api_client.get(f"{URL}/{srd_feat_id('Grappler')}")
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["category_code"], body["category_name"], body["repeatable"]) == (
        "Grappler", "general", "General", False,
    )
    prereqs = [(p["or_group"], p["min_character_level"], p["ability_code"], p["ability_name"], p["min_score"])
               for p in body["prerequisites"]]
    assert prereqs == [(1, 4, None, None, None), (2, None, "dex", "Dexterity", 13), (2, None, "str", "Strength", 13)]
    assert len({p["or_group"] for p in body["prerequisites"]}) == 2
    assert [f["name"] for f in body["features"]] == [
        "Ability Score Increase", "Punch and Grab", "Attack Advantage", "Fast Wrestler",
    ]
    asi = body["features"][0]["effects"][0]
    assert (asi["operation_code"], asi["value"], asi["max_value"]) == ("ability_score_increase", 1, 20)
    assert body["features"][0]["feat_id"] == body["id"]
    assert "level_prerequisite" not in body and "prerequisite_description" not in body and "category" not in body


async def test_spell_recall_prerequisites(api_client):
    body = (await api_client.get(f"{URL}/{srd_feat_id('Boon of Spell Recall')}")).json()
    assert [(p["or_group"], p["min_character_level"], p["feature_kind_code"], p["feature_kind_name"])
            for p in body["prerequisites"]] == [(1, 19, None, None), (2, None, "spellcasting", "Spellcasting")]


async def test_list_has_the_detail_format(api_client):
    rows = await _get(api_client, search="Alert")
    (alert,) = [r for r in rows if r["name"] == "Alert"]
    detail = (await api_client.get(f"{URL}/{alert['id']}")).json()
    assert alert == detail
    assert [f["name"] for f in detail["features"]] == ["Initiative Proficiency", "Initiative Swap"]


async def test_missing_feat_is_404(api_client):
    assert (await api_client.get(f"{URL}/{uuid.uuid4()}")).status_code == 404


async def test_invalid_token_is_401(api_client):
    assert (await api_client.get(URL, headers={"Authorization": "Bearer nope"})).status_code == 401


class TestListFeatsNoNPlusOne:
    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        from app.schemas.compendium import FeatOut
        from app.services.feats import list_feats

        author = await seed_user(db_session)
        marker = uuid.uuid4().hex[:8]
        for i in range(n):
            feat = await seed_feat(db_session, author=author, name=f"NPlusOne-{marker}-{i}")
            from app.db.models.features import FeatPrerequisite

            db_session.add(FeatPrerequisite(feat_id=feat.id, or_group=1, min_character_level=4))
            await seed_feature(db_session, feat=feat, effects=[dict(
                operation_code="ability_score_increase", value=1,
                choice=dict(pool_type_code="ability_score", choose_count=1, options=[dict(ability_code="str")]))])
            await seed_feature(db_session, feat=feat, resources=[dict(
                name="Uses", value=1, recharges=[dict(recharge_type_code="long_rest")])])
        await db_session.flush()
        db_session.expunge_all()

        with count_queries(db_engine) as counter:
            feats = await list_feats(db_session, search=f"NPlusOne-{marker}")
            outs = [FeatOut.model_validate(f) for f in feats]
        assert len(outs) == n
        assert all(len(o.features) == 2 and len(o.prerequisites) == 1 for o in outs)
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, f"query count grew with N: {count_n2} vs {count_n6} -- N+1 in `list_feats`"


async def test_entity_targets_under_a_feat_are_loaded(api_client, db_session):
    """feat -> features -> effects -> feat/feature repeats the mapper in the load path."""
    from tests.integration.conftest import srd_feature_id

    author = await seed_user(db_session)
    feat = await seed_feat(db_session, author=author, name=f"Loader-{uuid.uuid4().hex[:6]}")
    other = await seed_feat(db_session, author=author, name="Other Feat")
    await seed_feature(db_session, feat=feat, effects=[
        dict(operation_code="grant", granted_feature_id=srd_feature_id("class:Fighter/1/Second Wind")),
        dict(operation_code="grant", feat_id=other.id),
        dict(operation_code="grant", choice=dict(pool_type_code="feat", choose_count=1,
                                                 options=[dict(feat_id=other.id)])),
    ])
    await db_session.commit()
    db_session.expunge_all()
    body = (await api_client.get(f"{URL}/{feat.id}")).json()
    granted, fixed, chosen = body["features"][0]["effects"]
    assert granted["granted_feature_name"] == "Second Wind"
    assert fixed["feat_name"] == "Other Feat"
    assert chosen["choice"]["options"][0]["target_name"] == "Other Feat"
    listed = await _get(api_client, search=body["name"])
    assert listed == [body]
