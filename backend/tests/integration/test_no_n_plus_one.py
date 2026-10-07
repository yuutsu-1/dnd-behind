import uuid

from app.api.campaigns import list_members, list_my_campaigns
from app.api.characters import my_characters
from app.services.character import list_characters_for_campaign
from tests.integration.conftest import (
    count_queries,
    seed_campaign,
    seed_campaign_member,
    seed_character,
    seed_user,
)


class TestMyCharactersNoNPlusOne:
    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        owner = await seed_user(db_session)
        for i in range(n):
            await seed_character(db_session, owner=owner, name=f"Char {i}")

        with count_queries(db_engine) as counter:
            characters = await my_characters(current_user=owner, db=db_session)
        assert len(characters) == n
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, (
            f"query count grew with N: {count_n2} (N=2) vs {count_n6} (N=6) -- "
            "possible N+1 in `my_characters`"
        )


class TestListCharactersForCampaignNoNPlusOne:
    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        owner = await seed_user(db_session)
        campaign = await seed_campaign(db_session, creator=owner)
        for i in range(n):
            await seed_character(db_session, owner=owner, campaign_id=campaign.id, name=f"Char {i}")

        with count_queries(db_engine) as counter:
            characters = await list_characters_for_campaign(db_session, campaign.id)
        assert len(characters) == n
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, (
            f"query count grew with N: {count_n2} (N=2) vs {count_n6} (N=6) -- "
            "possible N+1 in `list_characters_for_campaign`"
        )


class TestListMyCampaignsNoNPlusOne:
    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        user = await seed_user(db_session)
        for i in range(n):
            campaign = await seed_campaign(db_session, creator=user, name=f"Campaign {i}")
            await seed_campaign_member(db_session, campaign, user, role="dm")

        with count_queries(db_engine) as counter:
            campaigns = await list_my_campaigns(current_user=user, db=db_session)
        assert len(campaigns) == n
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, (
            f"query count grew with N: {count_n2} (N=2) vs {count_n6} (N=6) -- "
            "possible N+1 in `list_my_campaigns`"
        )


class TestListMembersNoNPlusOne:
    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        creator = await seed_user(db_session)
        campaign = await seed_campaign(db_session, creator=creator)
        await seed_campaign_member(db_session, campaign, creator, role="dm")
        for i in range(n):
            member_user = await seed_user(db_session, username=f"player-{i}-{campaign.id.hex[:6]}")
            await seed_campaign_member(db_session, campaign, member_user, role="player")

        with count_queries(db_engine) as counter:
            members = await list_members(campaign.id, current_user=creator, db=db_session)
        assert len(members) == n + 1  # +1 for the creator/dm membership
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, (
            f"query count grew with N: {count_n2} (N=2) vs {count_n6} (N=6) -- "
            "possible N+1 in `list_members`"
        )

class TestListClassesNoNPlusOne:
    """Classes eager-load their grants, and each grant its target row (joined): the query
    count for `list_classes` must not grow with the number of classes/grants."""

    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        from app.api.compendium import list_classes
        from tests.integration.conftest import seed_class, seed_class_grant

        marker = uuid.uuid4().hex[:8]
        for i in range(n):
            klass = await seed_class(db_session, name=f"NPlusOne-{marker}-{i}")
            await seed_class_grant(db_session, klass, saving_throw_ability_code="str")
            await seed_class_grant(db_session, klass, weapon_category_code="martial", required_weapon_property_code="light")
            await seed_class_grant(db_session, klass, tool_type_code="lute")
            await seed_class_grant(db_session, klass, skill_code=["stealth", "arcana", "history"][i % 3])
        db_session.expunge_all()

        with count_queries(db_engine) as counter:
            classes = await list_classes(db=db_session, search=f"NPlusOne-{marker}")
        assert len(classes) == n
        assert all(len(c.proficiency_grants) == 4 for c in classes)
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, (
            f"query count grew with N: {count_n2} (N=2) vs {count_n6} (N=6) -- possible N+1 in `list_classes`"
        )


class TestListSpellsNoNPlusOne:
    """Spells load names (joined), materials and lists in a fixed number of queries."""

    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        from app.services.spells import list_spells
        from tests.integration.conftest import seed_spell

        author = await seed_user(db_session)
        marker = uuid.uuid4().hex[:8]
        for i in range(n):
            await seed_spell(
                db_session, author=author, name=f"NPlusOne-{marker}-{i}",
                materials=[dict(description="ash"), dict(description="a gem")],
                spell_lists=["wizard", "bard"], area="5-foot Cube", area_shape_code="cube",
            )
        db_session.expunge_all()

        with count_queries(db_engine) as counter:
            spells = await list_spells(db_session, search=f"NPlusOne-{marker}")
            assert all(len(s.materials) == 2 and len(s.spell_lists) == 2 and s.area_shape_name for s in spells)
        assert len(spells) == n
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, (
            f"query count grew with N: {count_n2} (N=2) vs {count_n6} (N=6) -- possible N+1 in `list_spells`"
        )


class TestListFeaturesNoNPlusOne:
    """Features load names (joined), entities and every child level in a fixed number of
    queries: the count for `list_features` must not grow with the number of features."""

    async def _query_count_for_n(self, db_session, db_engine, n: int) -> int:
        from app.schemas.features import FeatureOut
        from app.services.features import list_features
        from tests.integration.conftest import seed_feat, seed_feature

        author = await seed_user(db_session)
        feat = await seed_feat(db_session, author=author)
        target = await seed_feat(db_session, author=author)
        for i in range(n):
            await seed_feature(
                db_session, feat=feat, name=f"F{i}", action_type_code="bonus_action",
                effects=[
                    dict(operation_code="grant", feat_id=target.id),
                    dict(operation_code="ability_score_increase", value=1, choice=dict(
                        pool_type_code="ability_score", choose_count=1, options=[dict(ability_code="str")],
                        scaling=[dict(level=5, value=2)])),
                    dict(operation_code="bonus", target_code="armor_class", value=1, scaling=[dict(level=3, value=2)]),
                ],
                resources=[dict(name="Uses", value=1, recharges=[dict(recharge_type_code="long_rest")],
                                scaling=[dict(level=4, value=2)])],
            )
        db_session.expunge_all()

        with count_queries(db_engine) as counter:
            features = await list_features(db_session, feat_id=feat.id)
            outs = [FeatureOut.model_validate(f) for f in features]
        assert len(outs) == n
        assert all(len(o.effects) == 3 and o.effects[0].feat_name and len(o.resources[0].recharges) == 1
                   for o in outs)
        return counter.count

    async def test_query_count_does_not_grow_with_n(self, db_session, db_engine):
        count_n2 = await self._query_count_for_n(db_session, db_engine, 2)
        count_n6 = await self._query_count_for_n(db_session, db_engine, 6)
        assert count_n2 == count_n6, (
            f"query count grew with N: {count_n2} (N=2) vs {count_n6} (N=6) -- possible N+1 in `list_features`"
        )
