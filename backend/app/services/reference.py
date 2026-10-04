"""Visibility, sharing and code resolution for the reference tables.

Rules (docs/plans/2026-10-04-fase1-especificacao.md):
- anonymous users see only SRD rows (`is_homebrew = false`);
- a logged-in user also sees their own homebrew and homebrew shared (through
  `campaign_homebrew_rules`) with any campaign they are a member of (dm or player),
  evaluated at query time.
"""
import uuid
from collections.abc import Iterable, Sequence

from fastapi import HTTPException, status
from sqlalchemy import String, cast, delete, exists, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.campaign import Campaign, CampaignMember
from app.db.models.reference import CampaignHomebrewRule
from app.db.models.user import User

# Whose visibility applies: a `User`, just their id, or `None` (anonymous).
Viewer = User | uuid.UUID | None


def _viewer_id(viewer: Viewer) -> uuid.UUID | None:
    if viewer is None or isinstance(viewer, uuid.UUID):
        return viewer
    return viewer.id


def key_column(model):
    """The (single-column) primary key of a reference model: `code`, `level` or `score`."""
    return next(iter(model.__table__.primary_key.columns))


def key_attribute(model):
    return getattr(model, key_column(model).key)


def _shares_of(model, key) -> ColumnElement[bool]:
    return (CampaignHomebrewRule.resource_table == model.__tablename__) & (
        CampaignHomebrewRule.resource_key == key
    )


def visible_filter(model, user: Viewer) -> ColumnElement[bool]:
    """SQL predicate selecting the rows of `model` that `user` (or an anonymous user) can see."""
    srd = model.is_homebrew.is_(false())
    user_id = _viewer_id(user)
    if user_id is None:
        return srd
    key = key_attribute(model)
    shared_with_user = exists().where(
        _shares_of(model, cast(key, String)),
        CampaignMember.campaign_id == CampaignHomebrewRule.campaign_id,
        CampaignMember.user_id == user_id,
    )
    return or_(srd, model.created_by == user_id, shared_with_user)


async def get_visible(db: AsyncSession, model, key, user: Viewer):
    result = await db.execute(
        select(model).where(key_attribute(model) == key, visible_filter(model, user))
    )
    return result.scalar_one_or_none()


async def resolve_codes(
    db: AsyncSession,
    model,
    codes: Sequence[str],
    user: Viewer,
    *,
    label: str,
) -> list:
    """Rows of `model` for `codes`, in the given order. Any code that does not exist
    or is not visible to `user` gives a 400 -- with the same message in both cases, so
    the response does not reveal whether an invisible homebrew row exists."""
    if not codes:
        return []
    unique = list(dict.fromkeys(codes))
    result = await db.execute(
        select(model).where(key_attribute(model).in_(unique), visible_filter(model, user))
    )
    found = {getattr(row, key_column(model).key): row for row in result.scalars().all()}
    missing = [code for code in unique if code not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown {label} code(s): {', '.join(missing)}",
        )
    return [found[code] for code in codes]


async def validate_campaign_ids(db: AsyncSession, user: User, campaign_ids: Iterable[uuid.UUID]) -> None:
    """400 if a campaign does not exist; 403 if `user` is not its DM."""
    ids = set(campaign_ids)
    if not ids:
        return
    existing = set((await db.execute(select(Campaign.id).where(Campaign.id.in_(ids)))).scalars())
    if existing != ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign not found")
    dm_of = set((await db.execute(
        select(CampaignMember.campaign_id).where(
            CampaignMember.campaign_id.in_(ids),
            CampaignMember.user_id == user.id,
            CampaignMember.role == "dm",
        )
    )).scalars())
    if dm_of != ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Homebrew can only be shared with campaigns where you are the DM",
        )


async def delete_shares(db: AsyncSession, model, key) -> None:
    await db.execute(delete(CampaignHomebrewRule).where(_shares_of(model, str(key))))


async def replace_shares(db: AsyncSession, model, key, campaign_ids: Iterable[uuid.UUID]) -> None:
    await delete_shares(db, model, key)
    for campaign_id in dict.fromkeys(campaign_ids):
        db.add(CampaignHomebrewRule(
            resource_table=model.__tablename__, resource_key=str(key), campaign_id=campaign_id,
        ))


async def campaign_ids_map(db: AsyncSession, model, objs: Sequence, user: User | None) -> dict:
    """`{key: campaign_ids}` for every row of `objs`: the shared campaigns (sorted) for
    rows authored by `user`, `None` for the others. One query for the whole batch."""
    key_name = key_column(model).key
    result: dict = {getattr(obj, key_name): None for obj in objs}
    owned = [
        getattr(obj, key_name) for obj in objs
        if user is not None and obj.created_by is not None and obj.created_by == user.id
    ]
    if not owned:
        return result
    for key in owned:
        result[key] = []
    by_string = {str(key): key for key in owned}
    rows = await db.execute(
        select(CampaignHomebrewRule.resource_key, CampaignHomebrewRule.campaign_id)
        .where(
            CampaignHomebrewRule.resource_table == model.__tablename__,
            CampaignHomebrewRule.resource_key.in_(list(by_string)),
        )
        .order_by(CampaignHomebrewRule.campaign_id)
    )
    for resource_key, campaign_id in rows.all():
        result[by_string[resource_key]].append(campaign_id)
    return result


async def campaign_ids_for(db: AsyncSession, model, obj, user: User | None) -> list[uuid.UUID] | None:
    """The campaigns `obj` is shared with -- only for its author; `None` for everyone else."""
    return (await campaign_ids_map(db, model, [obj], user))[getattr(obj, key_column(model).key)]
