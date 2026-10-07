"""Feats with their prerequisites and embedded features (phase 4). Feats are global:
every user sees every feat. Only the author changes a homebrew feat (SRD -> 403)."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.compendium import FeatDefinition
from app.db.models.features import FeatPrerequisite
from app.db.models.reference import Ability, FeatCategory, FeatureKind
from app.db.models.user import User
from app.schemas.compendium import FeatCreate, FeatUpdate
from app.services.features import insert_features, owner_features, replace_features, validate_features
from app.services.reference import resolve_codes
from app.services.search import name_contains


def _load_options() -> tuple:
    return (selectinload(FeatDefinition.prerequisites), *owner_features(FeatDefinition.features))


async def list_feats(
    db: AsyncSession, *, category: str | None = None, search: str | None = None,
) -> list[FeatDefinition]:
    """Ordered by name, then id. A filter with an unknown code just matches nothing."""
    query = select(FeatDefinition)
    if category:
        query = query.where(FeatDefinition.category_code == category)
    if search:
        query = query.where(name_contains(FeatDefinition.name, search))
    query = query.options(*_load_options()).order_by(FeatDefinition.name, FeatDefinition.id)
    return list((await db.execute(query)).unique().scalars().all())


async def get_feat(db: AsyncSession, feat_id: uuid.UUID) -> FeatDefinition | None:
    query = (
        select(FeatDefinition).where(FeatDefinition.id == feat_id)
        .options(*_load_options()).execution_options(populate_existing=True)
    )
    return (await db.execute(query)).unique().scalar_one_or_none()


# --- writes -------------------------------------------------------------------------

async def _check_feat_codes(
    db: AsyncSession, data, fields: set[str], user: User, owner_id: uuid.UUID | None = None,
) -> None:
    """400 for the category and the codes of the prerequisites (unknown or invisible)."""
    if "category_code" in fields:
        await resolve_codes(db, FeatCategory, [data.category_code], user, label="feat category")
    if "prerequisites" in fields:
        abilities = [p.ability_code for p in data.prerequisites if p.ability_code is not None]
        kinds = [p.feature_kind_code for p in data.prerequisites if p.feature_kind_code is not None]
        await resolve_codes(db, Ability, list(dict.fromkeys(abilities)), user, label="ability score")
        await resolve_codes(db, FeatureKind, list(dict.fromkeys(kinds)), user, label="feature kind")
    if "features" in fields:
        await validate_features(db, data.features, "feat", user, owner_id=owner_id)


async def _insert_prerequisites(db: AsyncSession, feat_id: uuid.UUID, prerequisites) -> None:
    if prerequisites:
        await db.execute(insert(FeatPrerequisite), [
            {"id": uuid.uuid4(), "feat_id": feat_id, **prerequisite.model_dump()} for prerequisite in prerequisites
        ])


def _provenance(feat: FeatDefinition) -> dict:
    return {"source": feat.source, "is_homebrew": feat.is_homebrew, "created_by": feat.created_by}


async def create_feat(db: AsyncSession, data: FeatCreate, user: User) -> FeatDefinition:
    """A homebrew feat of `user` with its prerequisites and features; nothing is written on error."""
    try:
        await _check_feat_codes(db, data, set(FeatCreate.model_fields), user)
        feat = FeatDefinition(
            id=uuid.uuid4(), name=data.name, description=data.description, category_code=data.category_code,
            repeatable=data.repeatable, source="homebrew", is_homebrew=True, created_by=user.id,
        )
        db.add(feat)
        await db.flush()
        await _insert_prerequisites(db, feat.id, data.prerequisites)
        await insert_features(db, "feat_id", feat.id, data.features, _provenance(feat))
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    return await get_feat(db, feat.id)


async def _get_for_write(db: AsyncSession, feat_id: uuid.UUID, user: User) -> FeatDefinition:
    """The feat the author may change: 404 if missing, 403 if SRD or of another author."""
    feat = (await db.execute(select(FeatDefinition).where(FeatDefinition.id == feat_id))).unique().scalar_one_or_none()
    if feat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feat not found")
    if not feat.is_homebrew or feat.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can change this feat")
    return feat


_COLUMNS = ("name", "description", "category_code", "repeatable")


async def update_feat(db: AsyncSession, feat_id: uuid.UUID, data: FeatUpdate, user: User) -> FeatDefinition:
    """Fields sent are set; `prerequisites`/`features` sent replace the whole set (the new
    features get new ids). Validated on the final state; nothing is written on error.
    Replacing features that are referenced from outside the feat is a 409."""
    fields = data.model_fields_set
    try:
        feat = await _get_for_write(db, feat_id, user)
        await _check_feat_codes(db, data, fields, user, owner_id=feat.id)
        for column in _COLUMNS:
            if column in fields:
                setattr(feat, column, getattr(data, column))
        await db.flush()
        if "prerequisites" in fields:
            await db.execute(delete(FeatPrerequisite).where(FeatPrerequisite.feat_id == feat.id))
            await _insert_prerequisites(db, feat.id, data.prerequisites)
        if "features" in fields:
            await replace_features(db, "feat_id", feat.id, data.features, _provenance(feat))
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="The change conflicts with data stored in the database"
        ) from None
    return await get_feat(db, feat_id)


async def delete_feat(db: AsyncSession, feat_id: uuid.UUID, user: User) -> None:
    """Prerequisites and features (with their children) go with the feat (FK CASCADE).
    A feat used by a background, a character, another feature's effect or option, or whose
    feature is referenced from outside, cannot be deleted: the savepoint is rolled back -> 409."""
    await _get_for_write(db, feat_id, user)
    try:
        async with db.begin_nested():
            await db.execute(delete(FeatDefinition).where(FeatDefinition.id == feat_id))
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Feat is still referenced and cannot be deleted"
        ) from None
    await db.commit()
