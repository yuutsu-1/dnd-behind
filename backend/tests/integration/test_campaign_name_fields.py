from app.api.campaigns import create_campaign, join_campaign, list_members, list_my_campaigns
from app.schemas.campaign import CampaignCreate, CampaignOut, JoinRequest, MemberOut
from tests.integration.conftest import seed_campaign, seed_campaign_member, seed_user


class TestCampaignOutCreatedByName:
    async def test_populated_from_seeded_creator(self, db_session):
        creator = await seed_user(db_session, username="dm_frodo")
        campaign = await seed_campaign(db_session, creator=creator, name="The One Ring")

        await seed_campaign_member(db_session, campaign, creator, role="dm")

        campaigns = await list_my_campaigns(current_user=creator, db=db_session)
        out = [CampaignOut.model_validate(c, from_attributes=True) for c in campaigns]

        assert any(c.id == campaign.id and c.created_by_name == "dm_frodo" for c in out)


class TestMemberOutNameFields:
    async def test_populated_from_seeded_user_and_campaign(self, db_session):
        creator = await seed_user(db_session)
        campaign = await seed_campaign(db_session, creator=creator, name="Waterdeep")
        await seed_campaign_member(db_session, campaign, creator, role="dm")
        member_user = await seed_user(db_session, username="sam_player")
        await seed_campaign_member(db_session, campaign, member_user, role="player")

        members = await list_members(campaign.id, current_user=creator, db=db_session)
        out = [MemberOut.model_validate(m, from_attributes=True) for m in members]

        member_out = next(m for m in out if m.user_id == member_user.id)
        assert member_out.user_name == "sam_player"
        assert member_out.campaign_name == "Waterdeep"


class TestNoMissingGreenletOnWriteEndpoints:
    async def test_create_campaign_serializes_without_error(self, db_session):
        creator = await seed_user(db_session, username="new_dm")

        campaign = await create_campaign(CampaignCreate(name="Brand New Campaign"), current_user=creator, db=db_session)

        out = CampaignOut.model_validate(campaign, from_attributes=True)
        assert out.name == "Brand New Campaign"
        assert out.created_by_name == "new_dm"

    async def test_join_campaign_serializes_without_error(self, db_session):
        creator = await seed_user(db_session, username="owner_dm")
        campaign = await seed_campaign(db_session, creator=creator, invite_code="JOINCODE123", name="Open Table")
        joiner = await seed_user(db_session, username="new_joiner")

        member = await join_campaign(JoinRequest(invite_code="JOINCODE123"), current_user=joiner, db=db_session)

        out = MemberOut.model_validate(member, from_attributes=True)
        assert out.user_name == "new_joiner"
        assert out.campaign_name == "Open Table"