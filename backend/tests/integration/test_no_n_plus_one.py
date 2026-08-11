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