"""Classes (`class_definitions` + grants, skills, primary abilities, initial equipment) and
their embedded features (phase 4). Classes are global; only the author changes a homebrew
class (SRD -> 403). The class name is unique (409 on a clash)."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.compendium import ClassDefinition, ClassInitialEquipment, ItemDefinition, SubclassDefinition
from app.db.models.reference import Ability, Skill
from app.db.models.user import User
from app.schemas.compendium import ClassCreate, ClassUpdate, SubclassCreate, SubclassUpdate
from app.services import proficiency_grants as grant_service
from app.services.features import insert_features, owner_features, replace_features, validate_features
from app.services.reference import resolve_codes
from app.services.search import name_contains


def _load_options() -> tuple:
    """Features with every child; grants, skills, abilities and equipment are selectin."""
    return tuple(owner_features(ClassDefinition.features))


async def list_classes(db: AsyncSession, *, search: str | None = None) -> list[ClassDefinition]:
    """Ordered by name, then id."""
    query = select(ClassDefinition)
    if search:
        query = query.where(name_contains(ClassDefinition.name, search))
    query = query.options(*_load_options()).order_by(ClassDefinition.name, ClassDefinition.id)
    return list((await db.execute(query)).unique().scalars().all())


async def get_class(db: AsyncSession, class_id: uuid.UUID) -> ClassDefinition | None:
    query = (
        select(ClassDefinition).where(ClassDefinition.id == class_id)
        .options(*_load_options()).execution_options(populate_existing=True)
    )
    return (await db.execute(query)).unique().scalar_one_or_none()


# --- writes -------------------------------------------------------------------------

def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _integrity_conflict(error: IntegrityError) -> HTTPException:
    """409 for a write that the database refused: the name message only for the UNIQUE name."""
    if "class_definitions_name_key" in str(error.orig):
        return _conflict("A class with this name already exists")
    return _conflict("The change conflicts with data stored in the database")


async def _check_name_free(db: AsyncSession, name: str, own_id: uuid.UUID | None = None) -> None:
    query = select(ClassDefinition.id).where(ClassDefinition.name == name)
    if own_id is not None:
        query = query.where(ClassDefinition.id != own_id)
    if (await db.execute(query)).first() is not None:
        raise _conflict(f"A class named '{name}' already exists")


async def _check_items(db: AsyncSession, equipment) -> None:
    ids = {entry.item_id for entry in equipment}
    found = set((await db.execute(select(ItemDefinition.id).where(ItemDefinition.id.in_(ids)))).scalars())
    if missing := sorted(str(item_id) for item_id in ids - found):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item {missing[0]} not found")


async def _resolve(db: AsyncSession, data, fields: set[str], user: User, owner_id: uuid.UUID | None = None) -> dict:
    """400 for every code/id sent (rule 6f); returns the rows of the collections sent.
    May create grants (discarded by the rollback if anything fails later)."""
    rows: dict = {}
    if "primary_ability" in fields:
        rows["primary_ability"] = await resolve_codes(
            db, Ability, list(dict.fromkeys(data.primary_ability)), user, label="ability score")
    if "skills" in fields:
        rows["skills"] = await resolve_codes(db, Skill, list(dict.fromkeys(data.skills)), user, label="skill")
    if "spell_ability" in fields and data.spell_ability is not None:
        await resolve_codes(db, Ability, [data.spell_ability], user, label="ability score")
    if "initial_equipment" in fields:
        await _check_items(db, data.initial_equipment)
    if "features" in fields:
        await validate_features(db, data.features, "class", user, owner_id=owner_id)
    if "proficiency_grants" in fields:
        rows["proficiency_grants"] = await grant_service.resolve_grants(db, data.proficiency_grants, user)
    return rows


def _equipment(data) -> list[ClassInitialEquipment]:
    return [ClassInitialEquipment(item_id=e.item_id, option=e.option, quantity=e.quantity)
            for e in data.initial_equipment]


def _provenance(obj: ClassDefinition) -> dict:
    return {"source": obj.source, "is_homebrew": obj.is_homebrew, "created_by": obj.created_by}


_COLUMNS = ("name", "description", "hit_die", "skill_choices", "subclass_level", "spell_ability", "spellcasting_type")


async def create_class(db: AsyncSession, data: ClassCreate, user: User) -> ClassDefinition:
    """A homebrew class of `user` with everything it carries; nothing is written on error."""
    try:
        await _check_name_free(db, data.name)
        rows = await _resolve(db, data, set(ClassCreate.model_fields), user)
        obj = ClassDefinition(
            id=uuid.uuid4(), **{column: getattr(data, column) for column in _COLUMNS},
            source="homebrew", is_homebrew=True, created_by=user.id,
            primary_ability=rows["primary_ability"], proficiency_grants=rows["proficiency_grants"],
            skills=rows["skills"], initial_equipment=_equipment(data),
        )
        db.add(obj)
        await db.flush()
        await insert_features(db, "class_id", obj.id, data.features, _provenance(obj))
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as error:
        await db.rollback()
        raise _integrity_conflict(error) from None
    return await get_class(db, obj.id)


async def _get_for_write(db: AsyncSession, class_id: uuid.UUID, user: User) -> ClassDefinition:
    """The class the author may change: 404 if missing, 403 if SRD or of another author."""
    obj = (await db.execute(select(ClassDefinition).where(ClassDefinition.id == class_id))).unique().scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if not obj.is_homebrew or obj.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can change this class")
    return obj


async def update_class(db: AsyncSession, class_id: uuid.UUID, data: ClassUpdate, user: User) -> ClassDefinition:
    """Fields sent are set; `features`, `proficiency_grants`, `skills`, `primary_ability` and
    `initial_equipment` sent replace the whole set. Nothing is written on error."""
    fields = data.model_fields_set
    try:
        obj = await _get_for_write(db, class_id, user)
        if "name" in fields:
            await _check_name_free(db, data.name, own_id=obj.id)
        rows = await _resolve(db, data, fields, user, owner_id=obj.id)
        for column in _COLUMNS:
            if column in fields:
                setattr(obj, column, getattr(data, column))
        for collection, values in rows.items():
            setattr(obj, collection, values)
        if "initial_equipment" in fields:
            await db.execute(delete(ClassInitialEquipment).where(ClassInitialEquipment.class_id == obj.id))
            db.expire(obj, ["initial_equipment"])
            for entry in _equipment(data):
                entry.class_id = obj.id
                db.add(entry)
        await db.flush()
        if "features" in fields:
            await replace_features(db, "class_id", obj.id, data.features, _provenance(obj))
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as error:
        await db.rollback()
        raise _integrity_conflict(error) from None
    return await get_class(db, class_id)


async def delete_class(db: AsyncSession, class_id: uuid.UUID, user: User) -> None:
    """Features (with their children), equipment and links go with the class (CASCADE). A
    class used by a character or a subclass, or whose feature is referenced from outside,
    cannot be deleted: the savepoint is rolled back -> 409."""
    await _get_for_write(db, class_id, user)
    try:
        async with db.begin_nested():
            await db.execute(delete(ClassDefinition).where(ClassDefinition.id == class_id))
    except IntegrityError:
        await db.rollback()
        raise _conflict("Class is still referenced and cannot be deleted") from None
    await db.commit()


# --- subclasses ---------------------------------------------------------------------

def _subclass_options() -> tuple:
    return (selectinload(SubclassDefinition.class_def), *owner_features(SubclassDefinition.features))


async def list_subclasses(db: AsyncSession, *, class_id: uuid.UUID | None = None) -> list[SubclassDefinition]:
    """Ordered by name, then id."""
    query = select(SubclassDefinition)
    if class_id is not None:
        query = query.where(SubclassDefinition.class_id == class_id)
    query = query.options(*_subclass_options()).order_by(SubclassDefinition.name, SubclassDefinition.id)
    return list((await db.execute(query)).unique().scalars().all())


async def get_subclass(db: AsyncSession, subclass_id: uuid.UUID) -> SubclassDefinition | None:
    query = (
        select(SubclassDefinition).where(SubclassDefinition.id == subclass_id)
        .options(*_subclass_options()).execution_options(populate_existing=True)
    )
    return (await db.execute(query)).unique().scalar_one_or_none()


async def create_subclass(db: AsyncSession, data: SubclassCreate, user: User) -> SubclassDefinition:
    """A homebrew subclass of `user` (of any class) with its features; nothing written on error."""
    try:
        if (await db.execute(select(ClassDefinition.id).where(ClassDefinition.id == data.class_id))).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Class {data.class_id} not found")
        await validate_features(db, data.features, "subclass", user)
        obj = SubclassDefinition(
            id=uuid.uuid4(), class_id=data.class_id, name=data.name, description=data.description,
            source="homebrew", is_homebrew=True, created_by=user.id,
        )
        db.add(obj)
        await db.flush()
        await insert_features(db, "subclass_id", obj.id, data.features, _provenance(obj))
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as error:
        await db.rollback()
        raise _integrity_conflict(error) from None
    return await get_subclass(db, obj.id)


async def _get_subclass_for_write(db: AsyncSession, subclass_id: uuid.UUID, user: User) -> SubclassDefinition:
    obj = (await db.execute(
        select(SubclassDefinition).where(SubclassDefinition.id == subclass_id)
    )).unique().scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subclass not found")
    if not obj.is_homebrew or obj.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can change this subclass")
    return obj


async def update_subclass(
    db: AsyncSession, subclass_id: uuid.UUID, data: SubclassUpdate, user: User,
) -> SubclassDefinition:
    """Fields sent are set; `features` sent replace the whole set. Nothing written on error."""
    fields = data.model_fields_set
    try:
        obj = await _get_subclass_for_write(db, subclass_id, user)
        if "features" in fields:
            await validate_features(db, data.features, "subclass", user, owner_id=obj.id)
        for column in ("name", "description"):
            if column in fields:
                setattr(obj, column, getattr(data, column))
        await db.flush()
        if "features" in fields:
            await replace_features(db, "subclass_id", obj.id, data.features, _provenance(obj))
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as error:
        await db.rollback()
        raise _integrity_conflict(error) from None
    return await get_subclass(db, subclass_id)


async def delete_subclass(db: AsyncSession, subclass_id: uuid.UUID, user: User) -> None:
    """Features go with the subclass (CASCADE). A subclass used by a character, or whose
    feature is referenced from outside, cannot be deleted -> 409."""
    await _get_subclass_for_write(db, subclass_id, user)
    try:
        async with db.begin_nested():
            await db.execute(delete(SubclassDefinition).where(SubclassDefinition.id == subclass_id))
    except IntegrityError:
        await db.rollback()
        raise _conflict("Subclass is still referenced and cannot be deleted") from None
    await db.commit()
