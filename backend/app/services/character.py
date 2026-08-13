import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.character import Character, CharacterAbilityScore, CharacterClass, CharacterInventory
from app.db.models.campaign import CampaignMember
from app.db.models.compendium import ClassDefinition, SubclassDefinition
from app.schemas.character import (
    AddItemRequest,
    CharacterClassCreate,
    CharacterClassUpdate,
    CharacterCreate,
    CharacterUpdate,
    HitDiceUsedUpdate,
    HPUpdate,
)
from app.services.compendium import ensure_ability_score_options

MAX_TOTAL_LEVEL = 20


def _character_eager_load_options() -> list:
    return [
        selectinload(Character.owner),
        selectinload(Character.campaign),
        selectinload(Character.species),
        selectinload(Character.background),
        selectinload(Character.classes).selectinload(CharacterClass.class_),
        selectinload(Character.classes).selectinload(CharacterClass.subclass),
        selectinload(Character.inventory).selectinload(CharacterInventory.item),
        selectinload(Character.inventory).selectinload(CharacterInventory.added_by_user),
    ]


async def get_character_or_404(db: AsyncSession, character_id: uuid.UUID) -> Character:
    result = await db.execute(
        select(Character)
        .where(Character.id == character_id, Character.is_active == True)  # noqa: E712
        .options(*_character_eager_load_options())
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return character


async def assert_owner_or_dm(
    db: AsyncSession,
    character: Character,
    requesting_user_id: uuid.UUID,
) -> None:
    if character.user_id == requesting_user_id:
        return

    if character.campaign_id:
        result = await db.execute(
            select(CampaignMember).where(
                CampaignMember.campaign_id == character.campaign_id,
                CampaignMember.user_id == requesting_user_id,
                CampaignMember.role == "dm",
            )
        )
        if result.scalar_one_or_none():
            return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to modify this character")


async def create_character(
    db: AsyncSession,
    data: CharacterCreate,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
) -> Character:
    await ensure_ability_score_options(db, set(data.ability_scores.keys()))
    character = Character(
        user_id=user_id,
        campaign_id=campaign_id,
        name=data.name,
        species_id=data.species_id,
        background_id=data.background_id,
        ability_scores=[
            CharacterAbilityScore(ability_score=name, value=value)
            for name, value in data.ability_scores.items()
        ],
        appearance=data.appearance,
        notes=data.notes,
    )
    db.add(character)
    await db.commit()
    await db.refresh(
        character,
        attribute_names=["owner", "campaign", "species", "background", "classes", "ability_scores"],
    )
    return character


async def update_character(
    db: AsyncSession,
    character: Character,
    data: CharacterUpdate,
) -> Character:
    update_data = data.model_dump(exclude_none=True)
    ability_scores_update = update_data.pop("ability_scores", None)

    for field, value in update_data.items():
        setattr(character, field, value)

    if ability_scores_update:
        existing_by_ability = {row.ability_score: row for row in character.ability_scores}
        new_ability_names = set(ability_scores_update.keys()) - set(existing_by_ability.keys())
        await ensure_ability_score_options(db, new_ability_names)
        for ability, value in ability_scores_update.items():
            if ability in existing_by_ability:
                existing_by_ability[ability].value = value
            else:
                character.ability_scores.append(
                    CharacterAbilityScore(character_id=character.id, ability_score=ability, value=value)
                )

    await db.commit()
    await db.refresh(character)
    return character


async def apply_hp_update(
    db: AsyncSession,
    character: Character,
    update: HPUpdate,
) -> Character:
    if update.is_temp:
        character.temp_hp = max(0, character.temp_hp + update.delta)
    else:
        if update.delta < 0:
            absorbed = min(character.temp_hp, abs(update.delta))
            character.temp_hp -= absorbed
            remaining_damage = abs(update.delta) - absorbed
            character.current_hp = max(0, character.current_hp - remaining_damage)
        else:
            character.current_hp = min(character.max_hp, character.current_hp + update.delta)

    await db.commit()
    await db.refresh(character)
    return character


async def add_item(
    db: AsyncSession,
    character: Character,
    data: AddItemRequest,
    added_by: uuid.UUID,
) -> CharacterInventory:
    entry = CharacterInventory(
        character_id=character.id,
        item_id=data.item_id,
        quantity=data.quantity,
        custom_notes=data.custom_notes,
        added_by=added_by,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry, attribute_names=["item", "added_by_user"])
    return entry


async def remove_item(
    db: AsyncSession,
    character: Character,
    inventory_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
) -> None:
    await assert_owner_or_dm(db, character, requesting_user_id)
    result = await db.execute(
        select(CharacterInventory).where(
            CharacterInventory.id == inventory_id,
            CharacterInventory.character_id == character.id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory entry not found")
    await db.delete(entry)
    await db.commit()


async def list_characters_for_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> list[Character]:
    result = await db.execute(
        select(Character)
        .where(Character.campaign_id == campaign_id, Character.is_active == True)  # noqa: E712
        .options(*_character_eager_load_options())
    )
    return list(result.scalars().all())


def _get_character_class_entry_or_404(character: Character, class_entry_id: uuid.UUID) -> CharacterClass:
    for entry in character.classes:
        if entry.id == class_entry_id:
            return entry
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class entry not found")


async def _get_class_definition_or_404(db: AsyncSession, class_id: uuid.UUID) -> ClassDefinition:
    result = await db.execute(select(ClassDefinition).where(ClassDefinition.id == class_id))
    klass = result.scalar_one_or_none()
    if not klass:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return klass


async def _get_subclass_definition_or_404(db: AsyncSession, subclass_id: uuid.UUID) -> SubclassDefinition:
    result = await db.execute(select(SubclassDefinition).where(SubclassDefinition.id == subclass_id))
    subclass = result.scalar_one_or_none()
    if not subclass:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subclass not found")
    return subclass


def _validate_subclass_assignment(klass: ClassDefinition, subclass: SubclassDefinition, level: int) -> None:
    if subclass.class_id != klass.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subclass does not belong to this class",
        )
    if level < klass.subclass_level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subclass requires level >= {klass.subclass_level} in this class",
        )


async def add_character_class(
    db: AsyncSession,
    character: Character,
    data: CharacterClassCreate,
) -> CharacterClass:
    klass = await _get_class_definition_or_404(db, data.class_id)

    if any(entry.class_id == data.class_id for entry in character.classes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character already has an entry for this class",
        )

    if character.total_level + data.level > MAX_TOTAL_LEVEL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Total character level cannot exceed {MAX_TOTAL_LEVEL}",
        )

    if data.subclass_id is not None:
        subclass = await _get_subclass_definition_or_404(db, data.subclass_id)
        _validate_subclass_assignment(klass, subclass, data.level)

    entry = CharacterClass(
        character_id=character.id,
        class_id=data.class_id,
        level=data.level,
        subclass_id=data.subclass_id,
        hit_dice_used=0,
    )
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character already has an entry for this class",
        )
    await db.refresh(entry, attribute_names=["class_", "subclass"])
    return entry


async def update_character_class(
    db: AsyncSession,
    character: Character,
    class_entry_id: uuid.UUID,
    data: CharacterClassUpdate,
) -> CharacterClass:
    entry = _get_character_class_entry_or_404(character, class_entry_id)
    fields_set = data.model_fields_set

    new_level = data.level if "level" in fields_set and data.level is not None else entry.level
    new_subclass_id = data.subclass_id if "subclass_id" in fields_set else entry.subclass_id

    if "level" in fields_set:
        other_levels_sum = character.total_level - entry.level
        if other_levels_sum + new_level > MAX_TOTAL_LEVEL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Total character level cannot exceed {MAX_TOTAL_LEVEL}",
            )

    if new_subclass_id is not None:
        if "subclass_id" in fields_set:
            subclass = await _get_subclass_definition_or_404(db, new_subclass_id)
        else:
            subclass = entry.subclass
        klass = entry.class_ or await _get_class_definition_or_404(db, entry.class_id)
        _validate_subclass_assignment(klass, subclass, new_level)

    entry.level = new_level
    entry.subclass_id = new_subclass_id
    await db.commit()
    await db.refresh(entry, attribute_names=["class_", "subclass"])
    return entry


async def remove_character_class(
    db: AsyncSession,
    character: Character,
    class_entry_id: uuid.UUID,
) -> None:
    entry = _get_character_class_entry_or_404(character, class_entry_id)
    await db.delete(entry)
    await db.commit()


async def update_hit_dice_used(
    db: AsyncSession,
    character: Character,
    class_entry_id: uuid.UUID,
    data: HitDiceUsedUpdate,
) -> CharacterClass:
    entry = _get_character_class_entry_or_404(character, class_entry_id)
    if data.hit_dice_used > entry.level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"hit_dice_used cannot exceed the entry's level ({entry.level})",
        )
    entry.hit_dice_used = data.hit_dice_used
    await db.commit()
    await db.refresh(entry, attribute_names=["class_", "subclass"])
    return entry
