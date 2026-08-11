import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, DB
from app.db.models.compendium import (
    AbilityScoreOption,
    ArmorProficiencyOption,
    BackgroundDefinition,
    ClassDefinition,
    FeatDefinition,
    FeatureGrant,
    ItemDefinition,
    SpellDefinition,
    SpeciesDefinition,
    SubclassDefinition,
    ToolProficiencyOption,
    WeaponProficiencyOption,
    spell_class_lists,
)
from app.schemas.compendium import (
    BackgroundCreate, BackgroundOut,
    ClassCreate, ClassOut,
    FeatCreate, FeatOut,
    FeatureGrantCreate, FeatureGrantOut,
    ItemCreate, ItemOut,
    SpellCreate, SpellOut,
    SpeciesCreate, SpeciesOut,
    SubclassCreate, SubclassOut,
)

router = APIRouter(prefix="/compendium", tags=["compendium"])

async def _resolve_options(db: AsyncSession, model, names: list[str]) -> list:
    if not names:
        return []
    result = await db.execute(select(model).where(model.name.in_(names)))
    existing = {obj.name: obj for obj in result.scalars()}
    output = []
    for name in names:
        if name in existing:
            output.append(existing[name])
        else:
            new_obj = model(name=name)
            db.add(new_obj)
            await db.flush()
            output.append(new_obj)
    return output


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
    obj = ClassDefinition(
        name=data.name,
        description=data.description,
        hit_die=data.hit_die,
        skill_choices=data.skill_choices,
        skill_pool=data.skill_pool,
        subclass_level=data.subclass_level,
        spell_ability=data.spell_ability.value if data.spell_ability else None,
        spellcasting_type=data.spellcasting_type,
        is_homebrew=True,
        created_by=current_user.id,
    )
    db.add(obj)
    await db.flush()

    obj.primary_ability = await _resolve_options(
        db, AbilityScoreOption, [a.value for a in data.primary_ability]
    )
    obj.saving_throw_proficiencies = await _resolve_options(
        db, AbilityScoreOption, [a.value for a in data.saving_throw_proficiencies]
    )
    obj.armor_proficiencies = await _resolve_options(db, ArmorProficiencyOption, data.armor_proficiencies)
    obj.weapon_proficiencies = await _resolve_options(db, WeaponProficiencyOption, data.weapon_proficiencies)
    obj.tool_proficiencies = await _resolve_options(db, ToolProficiencyOption, data.tool_proficiencies)

    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/subclasses", response_model=list[SubclassOut])
async def list_subclasses(db: DB, class_id: uuid.UUID | None = Query(default=None)):
    q = select(SubclassDefinition)
    if class_id:
        q = q.where(SubclassDefinition.class_id == class_id)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/subclasses", response_model=SubclassOut, status_code=201)
async def create_subclass(data: SubclassCreate, current_user: CurrentUser, db: DB):
    obj = SubclassDefinition(**data.model_dump(), is_homebrew=True, created_by=current_user.id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/backgrounds", response_model=list[BackgroundOut])
async def list_backgrounds(db: DB, search: str | None = Query(default=None)):
    q = select(BackgroundDefinition)
    if search:
        q = q.where(BackgroundDefinition.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/backgrounds", response_model=BackgroundOut, status_code=201)
async def create_background(data: BackgroundCreate, current_user: CurrentUser, db: DB):
    obj = BackgroundDefinition(**data.model_dump(), is_homebrew=True, created_by=current_user.id)
    db.add(obj)
    await db.commit()
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

@router.get("/items", response_model=list[ItemOut])
async def list_items(
    db: DB,
    item_type: str | None = Query(default=None),
    rarity: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    q = select(ItemDefinition)
    if item_type:
        q = q.where(ItemDefinition.item_type == item_type)
    if rarity:
        q = q.where(ItemDefinition.rarity == rarity)
    if search:
        q = q.where(ItemDefinition.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: uuid.UUID, db: DB):
    result = await db.execute(select(ItemDefinition).where(ItemDefinition.id == item_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Item not found")
    return obj


@router.post("/items", response_model=ItemOut, status_code=201)
async def create_item(data: ItemCreate, current_user: CurrentUser, db: DB):
    obj = ItemDefinition(**data.model_dump(), is_homebrew=True, created_by=current_user.id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj

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
