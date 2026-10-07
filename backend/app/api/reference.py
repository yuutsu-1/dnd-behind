"""CRUD of the SRD reference tables and their homebrew entries: /compendium/<resource>.

- GET (list/detail): optional auth; shows only what the caller can see
  (app/services/reference.py).
- POST: any logged-in user; the entry is homebrew authored by them.
- PATCH/DELETE: only the author, only homebrew. SRD -> 403; homebrew of another
  author -> 403 if the caller can see it, 404 otherwise.
- Any error in POST/PATCH writes nothing (validation happens before writing, and
  the session is rolled back on failure).
"""
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DB, CurrentUser, OptionalUser
from app.db.models import reference as models
from app.db.models.user import User
from app.schemas import reference as schemas
from app.services import reference as ref_service
from app.services.search import name_contains

router = APIRouter(prefix="/compendium", tags=["compendium"])


@dataclass(frozen=True)
class Resource:
    slug: str
    model: Any
    create: type[BaseModel]
    update: type[BaseModel]
    out: type[BaseModel]
    order_by: tuple[str, ...] = ("name", "code")
    # Columns (besides the key) that must be unique: a clash gives 409.
    unique_columns: tuple[str, ...] = ()
    # Columns holding a code of another reference table: field -> (model, label).
    # The code must exist and be visible to the caller (400 otherwise).
    references: tuple[tuple[str, Any, str], ...] = ()
    # Conditions: `implies` (outgoing condition_implications).
    has_implies: bool = False

    @property
    def key(self) -> str:
        return ref_service.key_column(self.model).key

    @property
    def key_type(self) -> Any:
        if self.key == "code":
            return str
        # Numeric keys are INTEGER (int32): out-of-range path values are a 422, not a 500.
        return Annotated[int, Path(ge=schemas.INT32_MIN, le=schemas.INT32_MAX)]

    @property
    def searchable(self) -> bool:
        return "name" in self.model.__table__.c


def _simple(slug: str, model) -> Resource:
    return Resource(slug, model, schemas.ReferenceCreate, schemas.ReferenceUpdate, schemas.ReferenceOut)


RESOURCES: list[Resource] = [
    _simple("ability-scores", models.Ability),
    Resource(
        "skills", models.Skill, schemas.SkillCreate, schemas.SkillUpdate, schemas.SkillOut,
        references=(("ability_code", models.Ability, "ability score"),),
    ),
    Resource(
        "conditions", models.Condition, schemas.ConditionCreate, schemas.ConditionUpdate, schemas.ConditionOut,
        has_implies=True,
    ),
    Resource(
        "sizes", models.Size, schemas.SizeCreate, schemas.SizeUpdate, schemas.SizeOut,
        order_by=("sort_order",), unique_columns=("sort_order",),
    ),
    _simple("damage-types", models.DamageType),
    _simple("creature-types", models.CreatureType),
    _simple("alignments", models.Alignment),
    Resource("languages", models.Language, schemas.LanguageCreate, schemas.LanguageUpdate, schemas.LanguageOut),
    _simple("senses", models.Sense),
    _simple("movement-modes", models.MovementMode),
    _simple("weapon-categories", models.WeaponCategory),
    _simple("weapon-properties", models.WeaponProperty),
    _simple("weapon-masteries", models.WeaponMastery),
    _simple("armor-categories", models.ArmorCategory),
    _simple("tool-categories", models.ToolCategory),
    _simple("spell-schools", models.SpellSchool),
    _simple("recharge-types", models.RechargeType),
    _simple("action-types", models.ActionType),
    _simple("feat-categories", models.FeatCategory),
    _simple("item-types", models.ItemType),
    _simple("area-shapes", models.AreaShape),
    _simple("spell-lists", models.SpellList),
    _simple("casting-times", models.CastingTime),
    _simple("effect-operations", models.EffectOperation),
    _simple("effect-targets", models.EffectTarget),
    _simple("value-bases", models.ValueBasis),
    _simple("choice-pool-types", models.ChoicePoolType),
    _simple("choice-swap-rules", models.ChoiceSwapRule),
    _simple("feature-kinds", models.FeatureKind),
    Resource(
        "tool-types", models.ToolType, schemas.ToolTypeCreate, schemas.ToolTypeUpdate, schemas.ToolTypeOut,
        references=(
            ("category_code", models.ToolCategory, "tool category"),
            ("ability_code", models.Ability, "ability score"),
        ),
    ),
    Resource(
        "character-levels", models.CharacterLevel,
        schemas.CharacterLevelCreate, schemas.CharacterLevelUpdate, schemas.CharacterLevelOut,
        order_by=("level",),
    ),
    Resource(
        "challenge-ratings", models.ChallengeRating,
        schemas.ChallengeRatingCreate, schemas.ChallengeRatingUpdate, schemas.ChallengeRatingOut,
        order_by=("numeric_value",), unique_columns=("numeric_value",),
    ),
    Resource(
        "point-buy-costs", models.PointBuyCost,
        schemas.PointBuyCostCreate, schemas.PointBuyCostUpdate, schemas.PointBuyCostOut,
        order_by=("score",),
    ),
]


# --- helpers ---------------------------------------------------------------------

async def _visible_implications(db: AsyncSession, codes: list[str], user: User | None) -> dict[str, list[str]]:
    """Outgoing implications of `codes`, keeping only implied conditions `user` can see."""
    result: dict[str, list[str]] = {code: [] for code in codes}
    if not codes:
        return result
    rows = await db.execute(
        select(models.ConditionImplication.condition_code, models.ConditionImplication.implied_condition_code)
        .join(models.Condition, models.Condition.code == models.ConditionImplication.implied_condition_code)
        .where(
            models.ConditionImplication.condition_code.in_(codes),
            ref_service.visible_filter(models.Condition, user),
        )
        .order_by(models.ConditionImplication.implied_condition_code)
    )
    for code, implied in rows.all():
        result[code].append(implied)
    return result


async def _to_outs(db: AsyncSession, res: Resource, objs, user: User | None) -> list[BaseModel]:
    keys = [getattr(obj, res.key) for obj in objs]
    campaign_ids = await ref_service.campaign_ids_map(db, res.model, objs, user)
    implies = await _visible_implications(db, keys, user) if res.has_implies else {}
    outs = []
    for key, obj in zip(keys, objs):
        out = res.out.model_validate(obj)
        out.campaign_ids = campaign_ids[key]
        if res.has_implies:
            out.implies = implies[key]
        outs.append(out)
    return outs


async def _to_out(db: AsyncSession, res: Resource, obj, user: User | None) -> BaseModel:
    return (await _to_outs(db, res, [obj], user))[0]


async def _get_for_write(db: AsyncSession, res: Resource, key, user: User):
    """The entry the author may change; 404 if missing/invisible, 403 if SRD or not theirs."""
    obj = await ref_service.get_visible(db, res.model, key, user)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    if not obj.is_homebrew or obj.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can change this entry")
    return obj


async def _key_exists(db: AsyncSession, res: Resource, key) -> bool:
    column = ref_service.key_attribute(res.model)
    return (await db.execute(select(column).where(column == key))).first() is not None


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def _check_unique_columns(db: AsyncSession, res: Resource, values: dict, own_key=None) -> None:
    key_column = ref_service.key_attribute(res.model)
    for column in res.unique_columns:
        if column not in values:
            continue
        query = select(key_column).where(getattr(res.model, column) == values[column])
        if own_key is not None:
            query = query.where(key_column != own_key)
        if (await db.execute(query)).first() is not None:
            raise _conflict(f"{column} '{values[column]}' already exists")


async def _check_references(db: AsyncSession, res: Resource, values: dict, user: User) -> None:
    for field, model, label in res.references:
        if values.get(field) is not None:
            await ref_service.resolve_codes(db, model, [values[field]], user, label=label)


async def _resolve_implies(db: AsyncSession, code: str, implies: list[str], user: User) -> None:
    if code in implies:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A condition cannot imply itself"
        )
    await ref_service.resolve_codes(db, models.Condition, implies, user, label="condition")


async def _replace_implies(db: AsyncSession, code: str, implies: list[str]) -> None:
    await db.execute(
        delete(models.ConditionImplication).where(models.ConditionImplication.condition_code == code)
    )
    for implied in implies:
        db.add(models.ConditionImplication(condition_code=code, implied_condition_code=implied))


# --- handlers ----------------------------------------------------------------------

async def list_entries(res: Resource, db: AsyncSession, user: User | None, search: str | None) -> list[BaseModel]:
    query = select(res.model).where(ref_service.visible_filter(res.model, user))
    if search and res.searchable:
        query = query.where(name_contains(res.model.name, search))
    query = query.order_by(*(getattr(res.model, column) for column in res.order_by))
    rows = (await db.execute(query)).scalars().all()
    return await _to_outs(db, res, rows, user)


async def get_entry(res: Resource, db: AsyncSession, user: User | None, key) -> BaseModel:
    obj = await ref_service.get_visible(db, res.model, key, user)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return await _to_out(db, res, obj, user)


async def create_entry(res: Resource, db: AsyncSession, user: User, data: BaseModel) -> BaseModel:
    payload = data.model_dump(exclude={"campaign_ids", "implies"})
    key = payload[res.key]
    implies = getattr(data, "implies", None) if res.has_implies else None
    try:
        if await _key_exists(db, res, key):
            raise _conflict(f"{res.key} '{key}' already exists")
        await _check_unique_columns(db, res, payload)
        await _check_references(db, res, payload, user)
        if implies:
            await _resolve_implies(db, key, implies, user)
        await ref_service.validate_campaign_ids(db, user, data.campaign_ids or [])

        obj = res.model(**payload, source="homebrew", is_homebrew=True, created_by=user.id)
        db.add(obj)
        await db.flush()
        if implies:
            await _replace_implies(db, key, implies)
        await ref_service.replace_shares(db, res.model, key, data.campaign_ids or [])
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        # A concurrent request won the race past the pre-insert uniqueness checks.
        await db.rollback()
        raise _conflict("Entry conflicts with an existing one")
    await db.refresh(obj)
    return await _to_out(db, res, obj, user)


async def update_entry(res: Resource, db: AsyncSession, user: User, key, data: BaseModel) -> BaseModel:
    changes = data.model_dump(exclude_unset=True)
    campaign_ids = changes.pop("campaign_ids", None)
    implies = changes.pop("implies", None)
    try:
        obj = await _get_for_write(db, res, key, user)
        await _check_unique_columns(db, res, changes, own_key=key)
        await _check_references(db, res, changes, user)
        if implies is not None:
            await _resolve_implies(db, key, implies, user)
        if campaign_ids is not None:
            await ref_service.validate_campaign_ids(db, user, campaign_ids)

        for field, value in changes.items():
            setattr(obj, field, value)
        if implies is not None:
            await _replace_implies(db, key, implies)
        if campaign_ids is not None:
            await ref_service.replace_shares(db, res.model, key, campaign_ids)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        await db.rollback()
        raise _conflict("Entry conflicts with an existing one")
    await db.refresh(obj)
    return await _to_out(db, res, obj, user)


async def delete_entry(res: Resource, db: AsyncSession, user: User, key) -> None:
    """Shares and outgoing implications (FK CASCADE) go with the entry. Any other FK
    pointing at it is RESTRICT: the delete fails and the savepoint is rolled back,
    leaving entry and shares untouched -> 409."""
    obj = await _get_for_write(db, res, key, user)
    try:
        async with db.begin_nested():
            await ref_service.delete_shares(db, res.model, key)
            await db.delete(obj)
            await db.flush()
    except IntegrityError:
        await db.rollback()
        raise _conflict("Entry is still referenced and cannot be deleted")
    await db.commit()


# --- route registration --------------------------------------------------------------

def _register(res: Resource) -> None:
    path = f"/{res.slug}"
    item_path = f"{path}/{{key}}"
    KeyType = res.key_type
    CreateBody = res.create
    UpdateBody = res.update

    async def list_route(db: DB, user: OptionalUser, search: str | None = Query(default=None)):
        return await list_entries(res, db, user, search)

    async def get_route(key: KeyType, db: DB, user: OptionalUser):  # type: ignore[valid-type]
        return await get_entry(res, db, user, key)

    async def create_route(data: CreateBody, current_user: CurrentUser, db: DB):  # type: ignore[valid-type]
        return await create_entry(res, db, current_user, data)

    async def update_route(key: KeyType, data: UpdateBody, current_user: CurrentUser, db: DB):  # type: ignore[valid-type]
        return await update_entry(res, db, current_user, key, data)

    async def delete_route(key: KeyType, current_user: CurrentUser, db: DB):  # type: ignore[valid-type]
        await delete_entry(res, db, current_user, key)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    name = res.slug.replace("-", "_")
    router.add_api_route(path, list_route, methods=["GET"], response_model=list[res.out], name=f"list_{name}")
    router.add_api_route(item_path, get_route, methods=["GET"], response_model=res.out, name=f"get_{name}")
    router.add_api_route(
        path, create_route, methods=["POST"], response_model=res.out, status_code=201, name=f"create_{name}"
    )
    router.add_api_route(item_path, update_route, methods=["PATCH"], response_model=res.out, name=f"update_{name}")
    router.add_api_route(item_path, delete_route, methods=["DELETE"], status_code=204, name=f"delete_{name}")


for _resource in RESOURCES:
    _register(_resource)
