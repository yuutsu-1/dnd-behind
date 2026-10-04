import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import DB, CurrentUser, OptionalUser
from app.db.models.compendium import (
    BackgroundDefinition,
    BackgroundInitialEquipment,
    ClassDefinition,
    ClassInitialEquipment,
    FeatDefinition,
    FeatureGrant,
    ItemDefinition,
    SpellDefinition,
    SpeciesDefinition,
    SubclassDefinition,
    spell_class_lists,
)
from app.db.models.reference import Ability, Size, Skill
from app.db.models.user import User
from app.schemas.compendium import (
    BackgroundCreate, BackgroundOut, BackgroundUpdate,
    ClassCreate, ClassOut,
    FeatCreate, FeatOut,
    FeatureGrantCreate, FeatureGrantOut,
    SpellCreate, SpellOut,
    SpeciesCreate, SpeciesOut,
    SubclassCreate, SubclassOut,
)
from app.schemas.items import ItemCreate, ItemOut, ItemUpdate
from app.schemas.proficiency_grants import ProficiencyGrantOut
from app.services import items as item_service
from app.services import proficiency_grants as grant_service
from app.services.reference import resolve_codes

router = APIRouter(prefix="/compendium", tags=["compendium"])


async def _resolve(db: AsyncSession, model, codes: list[str], user: User, label: str) -> list:
    """Reference rows for `codes` (duplicates collapsed); 400 if any is unknown/invisible."""
    return await resolve_codes(db, model, list(dict.fromkeys(codes)), user, label=label)


async def validate_species_size(db: AsyncSession, size_code: str, user: User) -> None:
    await resolve_codes(db, Size, [size_code], user, label="size")

@router.get("/species", response_model=list[SpeciesOut])
async def list_species(db: DB, search: str | None = Query(default=None)):
    q = select(SpeciesDefinition)
    if search:
        q = q.where(SpeciesDefinition.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/species/{species_id}", response_model=SpeciesOut)
async def get_species(species_id: uuid.UUID, db: DB):
    result = await db.execute(select(SpeciesDefinition).where(SpeciesDefinition.id == species_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Species not found")
    return obj


@router.post("/species", response_model=SpeciesOut, status_code=201)
async def create_species(data: SpeciesCreate, current_user: CurrentUser, db: DB):
    await validate_species_size(db, data.size_code, current_user)
    obj = SpeciesDefinition(**data.model_dump(), is_homebrew=True, created_by=current_user.id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj

@router.get("/classes", response_model=list[ClassOut])
async def list_classes(db: DB, search: str | None = Query(default=None)):
    q = select(ClassDefinition)
    if search:
        q = q.where(ClassDefinition.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/classes/{class_id}", response_model=ClassOut)
async def get_class(class_id: uuid.UUID, db: DB):
    result = await db.execute(select(ClassDefinition).where(ClassDefinition.id == class_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Class not found")
    return obj


@router.post("/classes", response_model=ClassOut, status_code=201)
async def create_class(data: ClassCreate, current_user: CurrentUser, db: DB):
    # Everything is validated before anything is written; any error rolls back.
    try:
        primary_ability = await _resolve(db, Ability, data.primary_ability, current_user, "ability score")
        skills = await _resolve(db, Skill, data.skills, current_user, "skill")
        if data.spell_ability is not None:
            await _resolve(db, Ability, [data.spell_ability], current_user, "ability score")
        await _validate_items_exist(db, data.initial_equipment)
        # May create grants: they are discarded by the rollback if anything fails later.
        grants = await grant_service.resolve_grants(db, data.proficiency_grants, current_user)

        obj = ClassDefinition(
            name=data.name,
            description=data.description,
            hit_die=data.hit_die,
            skill_choices=data.skill_choices,
            subclass_level=data.subclass_level,
            spell_ability=data.spell_ability,
            spellcasting_type=data.spellcasting_type,
            is_homebrew=True,
            created_by=current_user.id,
            primary_ability=primary_ability,
            proficiency_grants=grants,
            skills=skills,
            initial_equipment=[
                ClassInitialEquipment(item_id=e.item_id, option=e.option, quantity=e.quantity)
                for e in data.initial_equipment
            ],
        )
        db.add(obj)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    await db.refresh(obj)
    return obj


@router.get("/subclasses", response_model=list[SubclassOut])
async def list_subclasses(db: DB, class_id: uuid.UUID | None = Query(default=None)):
    q = select(SubclassDefinition).options(selectinload(SubclassDefinition.class_def))
    if class_id:
        q = q.where(SubclassDefinition.class_id == class_id)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/subclasses", response_model=SubclassOut, status_code=201)
async def create_subclass(data: SubclassCreate, current_user: CurrentUser, db: DB):
    obj = SubclassDefinition(**data.model_dump(), is_homebrew=True, created_by=current_user.id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj, attribute_names=["class_def"])
    return obj


@router.get("/backgrounds", response_model=list[BackgroundOut])
async def list_backgrounds(db: DB, search: str | None = Query(default=None)):
    q = select(BackgroundDefinition)
    if search:
        q = q.where(BackgroundDefinition.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/backgrounds/{background_id}", response_model=BackgroundOut)
async def get_background(background_id: uuid.UUID, db: DB):
    result = await db.execute(select(BackgroundDefinition).where(BackgroundDefinition.id == background_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Background not found")
    return obj


async def _validate_feat_exists(db: AsyncSession, feat_id: uuid.UUID) -> None:
    feat_result = await db.execute(select(FeatDefinition).where(FeatDefinition.id == feat_id))
    if not feat_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Feat {feat_id} not found")


async def _validate_items_exist(db: AsyncSession, equipment: list) -> None:
    for entry in equipment:
        item_result = await db.execute(select(ItemDefinition).where(ItemDefinition.id == entry.item_id))
        if not item_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Item {entry.item_id} not found")


@router.post("/backgrounds", response_model=BackgroundOut, status_code=201)
async def create_background(data: BackgroundCreate, current_user: CurrentUser, db: DB):
    # Everything is validated before anything is written; any error rolls back.
    try:
        await _validate_feat_exists(db, data.feat_id)
        await _validate_items_exist(db, data.initial_equipment)
        ability_scores = await _resolve(db, Ability, data.ability_scores, current_user, "ability score")
        grants = await grant_service.resolve_grants(db, data.proficiency_grants, current_user)

        obj = BackgroundDefinition(
            name=data.name,
            description=data.description,
            feat_id=data.feat_id,
            is_homebrew=True,
            created_by=current_user.id,
            ability_scores=ability_scores,
            proficiency_grants=grants,
            initial_equipment=[
                BackgroundInitialEquipment(item_id=e.item_id, option=e.option, quantity=e.quantity)
                for e in data.initial_equipment
            ],
        )
        db.add(obj)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    await db.refresh(obj)
    return obj


@router.patch("/backgrounds/{background_id}", response_model=BackgroundOut)
async def update_background(background_id: uuid.UUID, data: BackgroundUpdate, current_user: CurrentUser, db: DB):
    result = await db.execute(select(BackgroundDefinition).where(BackgroundDefinition.id == background_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Background not found")

    # Validate every referenced id/code before changing anything; any error rolls back.
    try:
        if data.feat_id is not None:
            await _validate_feat_exists(db, data.feat_id)
        if data.initial_equipment is not None:
            await _validate_items_exist(db, data.initial_equipment)
        ability_scores = (
            await _resolve(db, Ability, data.ability_scores, current_user, "ability score")
            if data.ability_scores is not None else None
        )
        grants = (
            await grant_service.resolve_grants(db, data.proficiency_grants, current_user)
            if data.proficiency_grants is not None else None
        )

        if data.feat_id is not None:
            obj.feat_id = data.feat_id
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        if ability_scores is not None:
            obj.ability_scores = ability_scores
        if grants is not None:
            # Replaces the whole set; grants left without owner stay in the database.
            obj.proficiency_grants = grants
        if data.initial_equipment is not None:
            for entry in list(obj.initial_equipment):
                await db.delete(entry)
            await db.flush()
            for equipment in data.initial_equipment:
                db.add(BackgroundInitialEquipment(
                    background_id=obj.id,
                    item_id=equipment.item_id,
                    option=equipment.option,
                    quantity=equipment.quantity,
                ))

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    await db.refresh(obj)
    return obj

@router.get("/feats", response_model=list[FeatOut])
async def list_feats(
    db: DB,
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    q = select(FeatDefinition)
    if category:
        q = q.where(FeatDefinition.category == category)
    if search:
        q = q.where(FeatDefinition.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/feats", response_model=FeatOut, status_code=201)
async def create_feat(data: FeatCreate, current_user: CurrentUser, db: DB):
    obj = FeatDefinition(**data.model_dump(), is_homebrew=True, created_by=current_user.id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj

@router.get("/spells", response_model=list[SpellOut])
async def list_spells(
    db: DB,
    level: int | None = Query(default=None, ge=0, le=9),
    class_name: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    q = select(SpellDefinition)
    if level is not None:
        q = q.where(SpellDefinition.level == level)
    if search:
        q = q.where(SpellDefinition.name.ilike(f"%{search}%"))
    if class_name:
        # Subquery avoids conflicting with the selectin eager-load on class_list
        subq = (
            select(spell_class_lists.c.spell_id)
            .join(ClassDefinition, ClassDefinition.id == spell_class_lists.c.class_id)
            .where(ClassDefinition.name.ilike(class_name))
        )
        q = q.where(SpellDefinition.id.in_(subq))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/spells/{spell_id}", response_model=SpellOut)
async def get_spell(spell_id: uuid.UUID, db: DB):
    result = await db.execute(select(SpellDefinition).where(SpellDefinition.id == spell_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Spell not found")
    return obj


@router.post("/spells", response_model=SpellOut, status_code=201)
async def create_spell(data: SpellCreate, current_user: CurrentUser, db: DB):
    obj = SpellDefinition(
        name=data.name,
        level=data.level,
        school=data.school,
        casting_time=data.casting_time,
        range=data.range,
        components=data.components,
        material_component=data.material_component,
        duration=data.duration,
        concentration=data.concentration,
        ritual=data.ritual,
        description=data.description,
        higher_levels=data.higher_levels,
        is_homebrew=True,
        created_by=current_user.id,
    )
    db.add(obj)
    await db.flush()

    if data.class_ids:
        result = await db.execute(
            select(ClassDefinition).where(ClassDefinition.id.in_(data.class_ids))
        )
        obj.class_list = list(result.scalars())

    await db.commit()
    await db.refresh(obj)
    return obj

# Items are global (every user sees every item); `user` is optional: no token ->
# anonymous, invalid token -> 401. Filters take codes; an unknown code matches nothing.
@router.get("/items", response_model=list[ItemOut])
async def list_items(
    db: DB,
    user: OptionalUser,
    item_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    weapon_category: str | None = Query(default=None),
    armor_category: str | None = Query(default=None),
    tool_category: str | None = Query(default=None),
    tool_type: str | None = Query(default=None),
):
    return await item_service.list_items(
        db, item_type=item_type, search=search, weapon_category=weapon_category,
        armor_category=armor_category, tool_category=tool_category, tool_type=tool_type,
    )


@router.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: uuid.UUID, db: DB, user: OptionalUser):
    obj = await item_service.get_item(db, item_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return obj


@router.post("/items", response_model=ItemOut, status_code=201)
async def create_item(data: ItemCreate, current_user: CurrentUser, db: DB):
    return await item_service.create_item(db, data, current_user)


@router.patch("/items/{item_id}", response_model=ItemOut)
async def update_item(item_id: uuid.UUID, data: ItemUpdate, current_user: CurrentUser, db: DB):
    """Only the author, only homebrew (SRD/other author -> 403, missing -> 404)."""
    return await item_service.update_item(db, item_id, data, current_user)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Only the author, only homebrew; 409 while the item is referenced."""
    await item_service.delete_item(db, item_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Grants are global (shared by every class/background) and created only through them.
# `user` is optional: no token -> anonymous; invalid token -> 401.
@router.get("/proficiency-grants", response_model=list[ProficiencyGrantOut])
async def list_proficiency_grants(db: DB, user: OptionalUser):
    return await grant_service.list_grants(db)


@router.get("/proficiency-grants/{grant_id}", response_model=ProficiencyGrantOut)
async def get_proficiency_grant(grant_id: uuid.UUID, db: DB, user: OptionalUser):
    grant = await grant_service.get_grant(db, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Proficiency grant not found")
    return grant


@router.get("/feature-grants", response_model=list[FeatureGrantOut])
async def list_feature_grants(
    db: DB,
    source_type: str | None = Query(default=None),
    source_id: uuid.UUID | None = Query(default=None),
):
    q = select(FeatureGrant)
    if source_type:
        q = q.where(FeatureGrant.source_type == source_type)
    if source_id:
        q = q.where(FeatureGrant.source_id == source_id)
    q = q.order_by(FeatureGrant.level_requirement, FeatureGrant.sort_order)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/feature-grants", response_model=FeatureGrantOut, status_code=201)
async def create_feature_grant(data: FeatureGrantCreate, current_user: CurrentUser, db: DB):
    obj = FeatureGrant(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj
