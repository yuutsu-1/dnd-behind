import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import async_session
from app.db.models.user import User
from app.db.models.campaign import Campaign, CampaignMember

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db():
    async with async_session() as session:
        yield session


DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DB,
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_exc

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise credentials_exc

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_campaign_dm(
    campaign_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> Campaign:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    membership = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == current_user.id,
            CampaignMember.role == "dm",
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="DM access required")
    return campaign


async def require_campaign_member(
    campaign_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> CampaignMember:
    result = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == current_user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")
    return member
