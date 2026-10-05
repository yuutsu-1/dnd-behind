"""Spells (`spell_definitions` + `spell_materials` + `spell_list_spells`). Spells are
global: every user sees every spell. Codes referenced by a spell must exist and be
visible to the writer (400)."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.compendium import SpellDefinition
from app.db.models.reference import AreaShape, CastingTime, SpellList, SpellSchool
from app.db.models.spells import SpellMaterial, spell_list_spells
from app.db.models.user import User
from app.schemas.spells import SpellCreate, SpellUpdate
from app.services.items import _escape_like
from app.services.reference import resolve_codes


def _load_options() -> tuple:
    """Materials and lists in a fixed number of queries (names come joined with each row)."""
    return (selectinload(SpellDefinition.materials), selectinload(SpellDefinition.spell_lists))


async def list_spells(
    db: AsyncSession,
    *,
    level: int | None = None,
    school: str | None = None,
    spell_list: str | None = None,
    concentration: bool | None = None,
    ritual: bool | None = None,
    search: str | None = None,
) -> list[SpellDefinition]:
    """Ordered by level, name, id. A filter with an unknown code just matches nothing."""
    query = select(SpellDefinition)
    if level is not None:
        query = query.where(SpellDefinition.level == level)
    if school:
        query = query.where(SpellDefinition.school_code == school)
    if spell_list:
        query = query.where(SpellDefinition.id.in_(
            select(spell_list_spells.c.spell_id).where(spell_list_spells.c.spell_list_code == spell_list)
        ))
    if concentration is not None:
        query = query.where(SpellDefinition.concentration.is_(concentration))
    if ritual is not None:
        query = query.where(SpellDefinition.ritual.is_(ritual))
    if search:
        query = query.where(SpellDefinition.name.ilike(f"%{_escape_like(search)}%", escape="\\"))
    query = query.options(*_load_options()).order_by(
        SpellDefinition.level, SpellDefinition.name, SpellDefinition.id
    )
    return list((await db.execute(query)).unique().scalars().all())


async def get_spell(db: AsyncSession, spell_id: uuid.UUID) -> SpellDefinition | None:
    # populate_existing: the spell may already be in the session with children that a
    # write just replaced.
    query = (
        select(SpellDefinition).where(SpellDefinition.id == spell_id)
        .options(*_load_options()).execution_options(populate_existing=True)
    )
    return (await db.execute(query)).unique().scalar_one_or_none()


# --- writes -------------------------------------------------------------------------

# Columns written from the payload (everything but the children).
_COLUMNS = (
    "name", "level", "school_code", "has_verbal", "has_somatic", "has_material", "casting_time_code", "ritual",
    "concentration", "range", "duration", "area", "area_shape_code", "description", "higher_levels",
    "cantrip_upgrade",
)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def _check_codes(db: AsyncSession, data, fields: set[str], user: User) -> None:
    """400 for every code sent that does not exist or is not visible to `user`."""
    if "school_code" in fields:
        await resolve_codes(db, SpellSchool, [data.school_code], user, label="spell school")
    if "casting_time_code" in fields:
        await resolve_codes(db, CastingTime, [data.casting_time_code], user, label="casting time")
    if "area_shape_code" in fields and data.area_shape_code is not None:
        await resolve_codes(db, AreaShape, [data.area_shape_code], user, label="area shape")
    if "spell_list_codes" in fields:
        await resolve_codes(db, SpellList, data.spell_list_codes, user, label="spell list")


def _check_coherence(state: dict, material_count: int) -> None:
    """422 if the final state of the spell is incoherent."""
    if not (state["has_verbal"] or state["has_somatic"] or state["has_material"]):
        raise _unprocessable("a spell needs at least one component (verbal, somatic or material)")
    if state["has_material"] != (material_count > 0):
        raise _unprocessable("has_material must be true if and only if the spell has materials")
    if (state["area"] is None) != (state["area_shape_code"] is None):
        raise _unprocessable("area and area_shape_code go together")
    if state["cantrip_upgrade"] is not None and state["level"] != 0:
        raise _unprocessable("only a cantrip (level 0) has cantrip_upgrade")
    if state["higher_levels"] is not None and state["level"] == 0:
        raise _unprocessable("a cantrip (level 0) has no higher_levels")


async def _insert_children(db: AsyncSession, spell_id: uuid.UUID, data, fields: set[str]) -> None:
    if "materials" in fields and data.materials:
        await db.execute(insert(SpellMaterial), [
            {"id": uuid.uuid4(), "spell_id": spell_id, "sort_order": sort_order, **material.model_dump()}
            for sort_order, material in enumerate(data.materials)
        ])
    if "spell_list_codes" in fields and data.spell_list_codes:
        await db.execute(insert(spell_list_spells), [
            {"spell_list_code": code, "spell_id": spell_id} for code in data.spell_list_codes
        ])


async def create_spell(db: AsyncSession, data: SpellCreate, user: User) -> SpellDefinition:
    """A homebrew spell of `user` with its materials and lists; nothing is written on error."""
    fields = set(SpellCreate.model_fields)
    try:
        await _check_codes(db, data, fields, user)
        state = {column: getattr(data, column) for column in _COLUMNS}
        _check_coherence(state, len(data.materials))
        spell = SpellDefinition(
            id=uuid.uuid4(), **state, source="homebrew", is_homebrew=True, created_by=user.id,
        )
        db.add(spell)
        await db.flush()
        await _insert_children(db, spell.id, data, fields)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    return await get_spell(db, spell.id)


async def _get_for_write(db: AsyncSession, spell_id: uuid.UUID, user: User) -> SpellDefinition:
    """The spell the author may change: 404 if missing, 403 if SRD or of another author."""
    query = select(SpellDefinition).where(SpellDefinition.id == spell_id)
    spell = (await db.execute(query)).unique().scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spell not found")
    if not spell.is_homebrew or spell.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can change this spell")
    return spell


async def _material_count(db: AsyncSession, spell_id: uuid.UUID) -> int:
    return await db.scalar(select(func.count()).where(SpellMaterial.spell_id == spell_id))


async def update_spell(db: AsyncSession, spell_id: uuid.UUID, data: SpellUpdate, user: User) -> SpellDefinition:
    """Fields sent are set; `materials`/`spell_list_codes` sent replace the whole set.
    Codes (400) and coherence (422) are checked on the final state; nothing is written
    on error."""
    fields = data.model_fields_set
    try:
        spell = await _get_for_write(db, spell_id, user)
        await _check_codes(db, data, fields, user)
        sent = {column: getattr(data, column) for column in _COLUMNS if column in fields}
        state = {column: getattr(spell, column) for column in _COLUMNS} | sent
        materials = len(data.materials) if "materials" in fields else await _material_count(db, spell.id)
        _check_coherence(state, materials)
        for column, value in sent.items():
            setattr(spell, column, value)
        await db.flush()
        if "materials" in fields:
            await db.execute(delete(SpellMaterial).where(SpellMaterial.spell_id == spell.id))
        if "spell_list_codes" in fields:
            await db.execute(delete(spell_list_spells).where(spell_list_spells.c.spell_id == spell.id))
        await _insert_children(db, spell.id, data, fields)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    return await get_spell(db, spell_id)


async def delete_spell(db: AsyncSession, spell_id: uuid.UUID, user: User) -> None:
    """Materials and list links go with the spell (FK CASCADE). A spell known by a
    character (`character_spells`) cannot be deleted: the savepoint is rolled back -> 409."""
    await _get_for_write(db, spell_id, user)
    try:
        async with db.begin_nested():
            await db.execute(delete(SpellDefinition).where(SpellDefinition.id == spell_id))
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Spell is still referenced and cannot be deleted"
        )
    await db.commit()
