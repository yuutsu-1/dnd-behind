"""Items (`item_definitions` + 1:1 sub-tables). Items are global: every user sees every
item; codes referenced by an item must exist and be visible to the writer (400)."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.compendium import ItemDefinition
from app.db.models.items import Armor, Container, ItemContent, Tool, Weapon, WeaponPropertyLink
from app.db.models.reference import (
    ArmorCategory,
    DamageType,
    ItemType,
    ToolType,
    WeaponCategory,
    WeaponMastery,
    WeaponProperty,
)
from app.db.models.user import User
from app.schemas.items import (
    SUB_OBJECT_FIELDS,
    SUB_OBJECTS,
    ItemContentIn,
    ItemCreate,
    ItemUpdate,
    WeaponIn,
    WeaponPropertyIn,
)
from app.services.reference import resolve_codes
from app.services.search import name_contains


def _load_options() -> tuple:
    """Every sub-object in a fixed number of queries (names come joined with each row)."""
    return (
        selectinload(ItemDefinition.weapon).selectinload(Weapon.properties),
        selectinload(ItemDefinition.armor),
        selectinload(ItemDefinition.tool),
        selectinload(ItemDefinition.container),
        selectinload(ItemDefinition.contents),
    )


async def list_items(
    db: AsyncSession,
    *,
    item_type: str | None = None,
    search: str | None = None,
    weapon_category: str | None = None,
    armor_category: str | None = None,
    tool_category: str | None = None,
    tool_type: str | None = None,
) -> list[ItemDefinition]:
    """Ordered by name, then id. A filter with an unknown code just matches nothing."""
    query = select(ItemDefinition)
    if item_type:
        query = query.where(ItemDefinition.item_type_code == item_type)
    if search:
        query = query.where(name_contains(ItemDefinition.name, search))
    if weapon_category:
        query = query.where(ItemDefinition.id.in_(
            select(Weapon.item_id).where(Weapon.category_code == weapon_category)
        ))
    if armor_category:
        query = query.where(ItemDefinition.id.in_(
            select(Armor.item_id).where(Armor.category_code == armor_category)
        ))
    if tool_category:
        query = query.where(ItemDefinition.id.in_(
            select(Tool.item_id).join(ToolType, ToolType.code == Tool.tool_type_code)
            .where(ToolType.category_code == tool_category)
        ))
    if tool_type:
        query = query.where(ItemDefinition.id.in_(
            select(Tool.item_id).where(Tool.tool_type_code == tool_type)
        ))
    # No populate_existing here: an item of the list can also be the ammunition or the
    # content of another one, and re-populating it would reset its loaded sub-objects.
    query = query.options(*_load_options()).order_by(ItemDefinition.name, ItemDefinition.id)
    return list((await db.execute(query)).scalars().all())


async def get_item(db: AsyncSession, item_id: uuid.UUID) -> ItemDefinition | None:
    # populate_existing: the item may already be in the session with sub-rows that a
    # write just replaced. Safe here because an item never references itself.
    query = (
        select(ItemDefinition).where(ItemDefinition.id == item_id)
        .options(*_load_options()).execution_options(populate_existing=True)
    )
    return (await db.execute(query)).scalar_one_or_none()


# --- writes -------------------------------------------------------------------------

# Parameters each SRD property needs; any other property (homebrew included) takes none.
_PROPERTY_PARAMETERS: dict[str, frozenset[str]] = {
    "range": frozenset({"range_normal_ft", "range_long_ft"}),
    "versatile": frozenset({"versatile_die_size"}),
    "ammunition": frozenset({"ammunition_item_id"}),
}
_ALL_PARAMETERS = ("range_normal_ft", "range_long_ft", "versatile_die_size", "ammunition_item_id")


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _check_property_parameters(prop: WeaponPropertyIn) -> None:
    expected = _PROPERTY_PARAMETERS.get(prop.code, frozenset())
    given = {name for name in _ALL_PARAMETERS if getattr(prop, name) is not None}
    if given != expected:
        needs = ", ".join(sorted(expected)) or "no parameter"
        raise _bad_request(f"Weapon property '{prop.code}' takes {needs}")


async def _items_by_id(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, ItemDefinition]:
    if not ids:
        return {}
    rows = await db.execute(select(ItemDefinition).where(ItemDefinition.id.in_(ids)))
    return {item.id: item for item in rows.scalars().all()}


async def _check_weapon(db: AsyncSession, weapon: WeaponIn, user: User) -> None:
    await resolve_codes(db, WeaponCategory, [weapon.category_code], user, label="weapon category")
    await resolve_codes(db, DamageType, [weapon.damage_type_code], user, label="damage type")
    if weapon.mastery_code is not None:
        await resolve_codes(db, WeaponMastery, [weapon.mastery_code], user, label="weapon mastery")
    await resolve_codes(db, WeaponProperty, [p.code for p in weapon.properties], user, label="weapon property")
    for prop in weapon.properties:
        _check_property_parameters(prop)
    ammunition_ids = [p.ammunition_item_id for p in weapon.properties if p.ammunition_item_id is not None]
    found = await _items_by_id(db, ammunition_ids)
    for ammunition_id in ammunition_ids:
        item = found.get(ammunition_id)
        if item is None or item.item_type_code != "ammunition":
            raise _bad_request(f"Item {ammunition_id} is not an ammunition item")


async def _check_contents(db: AsyncSession, contents: list[ItemContentIn], pack_id: uuid.UUID | None) -> None:
    ids = [content.item_id for content in contents]
    found = await _items_by_id(db, ids)
    for item_id in ids:
        item = found.get(item_id)
        if item is None:
            raise _bad_request(f"Item {item_id} not found")
        if item_id == pack_id:
            raise _bad_request("A pack cannot contain itself")
        if item.item_type_code == "pack":
            raise _bad_request("A pack cannot contain another pack")


async def _check_sub_objects(db: AsyncSession, data, fields: set[str], user: User, item_id=None) -> None:
    """400 for every code/reference of the sub-objects in `fields` (rule 6f + item rules)."""
    if "weapon" in fields and data.weapon is not None:
        await _check_weapon(db, data.weapon, user)
    if "armor" in fields and data.armor is not None:
        await resolve_codes(db, ArmorCategory, [data.armor.category_code], user, label="armor category")
    if "tool" in fields and data.tool is not None:
        await resolve_codes(db, ToolType, [data.tool.tool_type_code], user, label="tool type")
    if "contents" in fields and data.contents:
        await _check_contents(db, data.contents, item_id)


async def _insert_sub_rows(db: AsyncSession, item_id: uuid.UUID, data, fields: set[str]) -> None:
    if "weapon" in fields and data.weapon is not None:
        weapon = data.weapon
        await db.execute(insert(Weapon).values(
            item_id=item_id, category_code=weapon.category_code, is_ranged=weapon.is_ranged,
            damage_dice_count=weapon.damage_dice_count, damage_die_size=weapon.damage_die_size,
            damage_flat=weapon.damage_flat, damage_type_code=weapon.damage_type_code,
            mastery_code=weapon.mastery_code,
        ))
        if weapon.properties:
            await db.execute(insert(WeaponPropertyLink), [
                {"weapon_item_id": item_id, "property_code": p.code, **{n: getattr(p, n) for n in _ALL_PARAMETERS}}
                for p in weapon.properties
            ])
    if "armor" in fields and data.armor is not None:
        await db.execute(insert(Armor).values(item_id=item_id, **data.armor.model_dump()))
    if "tool" in fields and data.tool is not None:
        await db.execute(insert(Tool).values(item_id=item_id, tool_type_code=data.tool.tool_type_code))
    if "container" in fields and data.container is not None:
        await db.execute(insert(Container).values(
            item_id=item_id, capacity_weight_lb=data.container.capacity_weight_lb,
        ))
    if "contents" in fields and data.contents:
        await db.execute(insert(ItemContent), [
            {"pack_item_id": item_id, "item_id": c.item_id, "quantity": c.quantity} for c in data.contents
        ])


async def _delete_sub_rows(db: AsyncSession, item_id: uuid.UUID, fields: set[str]) -> None:
    """Remove the current sub-rows of `fields` (a weapon's property links go with it)."""
    tables = {"weapon": Weapon, "armor": Armor, "tool": Tool, "container": Container}
    for field, model in tables.items():
        if field in fields:
            await db.execute(delete(model).where(model.item_id == item_id))
    if "contents" in fields:
        await db.execute(delete(ItemContent).where(ItemContent.pack_item_id == item_id))


async def _get_for_write(db: AsyncSession, item_id: uuid.UUID, user: User) -> ItemDefinition:
    """The item the author may change: 404 if missing, 403 if SRD or of another author."""
    item = (await db.execute(select(ItemDefinition).where(ItemDefinition.id == item_id))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if not item.is_homebrew or item.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can change this item")
    return item


def _check_fits_type(item_type_code: str, data: ItemUpdate, fields: set[str]) -> None:
    """422 if a sub-object sent does not fit the item's current type, or if a required
    one is removed (`null`, or `contents: []` for a pack)."""
    allowed, required = SUB_OBJECTS.get(item_type_code, (frozenset(), frozenset()))
    if extra := sorted(fields - allowed):
        raise _unprocessable(f"an item of type '{item_type_code}' cannot have: {', '.join(extra)}")
    removed = {field for field in fields if not getattr(data, field)}
    if missing := sorted(removed & required):
        raise _unprocessable(f"an item of type '{item_type_code}' needs: {', '.join(missing)}")


async def update_item(db: AsyncSession, item_id: uuid.UUID, data: ItemUpdate, user: User) -> ItemDefinition:
    """Base fields sent are set; each sub-object sent replaces the current one entirely
    (`null` removes it). Nothing is written on error."""
    fields = data.model_fields_set & set(SUB_OBJECT_FIELDS)
    try:
        item = await _get_for_write(db, item_id, user)
        _check_fits_type(item.item_type_code, data, fields)
        await _check_sub_objects(db, data, fields, user, item_id=item.id)
        for field in data.model_fields_set & {"name", "description", "cost_gp", "weight_lb"}:
            setattr(item, field, getattr(data, field))
        await db.flush()
        await _delete_sub_rows(db, item.id, fields)
        await _insert_sub_rows(db, item.id, data, fields)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    return await get_item(db, item_id)


async def delete_item(db: AsyncSession, item_id: uuid.UUID, user: User) -> None:
    """Own sub-rows go with the item (FK CASCADE). Every FK pointing at the item from
    elsewhere (inventory, initial equipment, another pack's contents, another weapon's
    ammunition) blocks the delete: the savepoint is rolled back -> 409."""
    await _get_for_write(db, item_id, user)
    try:
        async with db.begin_nested():
            await db.execute(delete(ItemDefinition).where(ItemDefinition.id == item_id))
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Item is still referenced and cannot be deleted"
        )
    await db.commit()


async def create_item(db: AsyncSession, data: ItemCreate, user: User) -> ItemDefinition:
    """A homebrew item of `user` with its sub-rows; nothing is written on error."""
    fields = set(SUB_OBJECT_FIELDS)
    try:
        await resolve_codes(db, ItemType, [data.item_type_code], user, label="item type")
        await _check_sub_objects(db, data, fields, user)
        item = ItemDefinition(
            id=uuid.uuid4(), name=data.name, item_type_code=data.item_type_code, cost_gp=data.cost_gp,
            weight_lb=data.weight_lb, description=data.description,
            source="homebrew", is_homebrew=True, created_by=user.id,
        )
        db.add(item)
        await db.flush()
        await _insert_sub_rows(db, item.id, data, fields)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    return await get_item(db, item.id)
