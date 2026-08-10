import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.character import Character, CharacterInventory
from app.db.models.campaign import CampaignMember
from app.schemas.character import AddItemRequest, CharacterCreate, CharacterUpdate, HPUpdate


async def get_character_or_404(db: AsyncSession, character_id: uuid.UUID) -> Character:
    result = await db.execute(
        select(Character)
        .where(Character.id == character_id, Character.is_active == True)  # noqa: E712
        .options(selectinload(Character.inventory))
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
    character = Character(
        user_id=user_id,
        campaign_id=campaign_id,
        name=data.name,
        species_id=data.species_id,
        background_id=data.background_id,
        class_id=data.class_id,
        ability_scores=data.ability_scores,
        appearance=data.appearance,
        notes=data.notes,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


async def update_character(
    db: AsyncSession,
    character: Character,
    data: CharacterUpdate,
) -> Character:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(character, field, value)
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
        # Damage absorbs temp HP first
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
    await db.refresh(entry)
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
        .options(selectinload(Character.inventory))
    )
    return list(result.scalars().all())
