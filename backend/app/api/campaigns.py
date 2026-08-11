import secrets
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.db.models.campaign import Campaign, CampaignMember
from app.schemas.campaign import CampaignCreate, CampaignOut, CampaignUpdate, JoinRequest, MemberOut

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(data: CampaignCreate, current_user: CurrentUser, db: DB):
    campaign = Campaign(
        name=data.name,
        description=data.description,
        created_by=current_user.id,
        invite_code=secrets.token_urlsafe(8)[:12],
        settings=data.settings,
    )
    db.add(campaign)
    await db.flush()

    # Quem criou a campanha vira o DM automaticamente
    membership = CampaignMember(campaign_id=campaign.id, user_id=current_user.id, role="dm")
    db.add(membership)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("", response_model=list[CampaignOut])
async def list_my_campaigns(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Campaign)
        .join(CampaignMember, CampaignMember.campaign_id == Campaign.id)
        .where(CampaignMember.user_id == current_user.id)
    )
    return list(result.scalars().all())


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: uuid.UUID, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Campaign)
        .join(CampaignMember, CampaignMember.campaign_id == Campaign.id)
        .where(Campaign.id == campaign_id, CampaignMember.user_id == current_user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(campaign_id: uuid.UUID, data: CampaignUpdate, current_user: CurrentUser, db: DB):
    dm_check = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == current_user.id,
            CampaignMember.role == "dm",
        )
    )
    if not dm_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="DM access required")

    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)

    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.post("/join", response_model=MemberOut, status_code=201)
async def join_campaign(data: JoinRequest, current_user: CurrentUser, db: DB):
    result = await db.execute(select(Campaign).where(Campaign.invite_code == data.invite_code))
    campaign = result.scalar_one_or_none()
    if not campaign or not campaign.is_active:
        raise HTTPException(status_code=404, detail="Invalid invite code")

    existing = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already a member")

    member = CampaignMember(campaign_id=campaign.id, user_id=current_user.id, role="player")
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.get("/{campaign_id}/members", response_model=list[MemberOut])
async def list_members(campaign_id: uuid.UUID, current_user: CurrentUser, db: DB):
    member_check = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == current_user.id,
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this campaign")

    result = await db.execute(
        select(CampaignMember).where(CampaignMember.campaign_id == campaign_id)
    )
    return list(result.scalars().all())
