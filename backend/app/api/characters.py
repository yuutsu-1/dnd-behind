import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.db.models.campaign import CampaignMember
from app.db.models.character import Character
from app.schemas.character import (
    AddItemRequest,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    CharacterWithInventory,
    HPUpdate,
    InventoryItemOut,
    UpdateInventoryItem,
)
from app.services import character as char_service
from app.core.redis import publish
import json

router = APIRouter(prefix="/characters", tags=["characters"])


async def _broadcast(campaign_id: uuid.UUID | None, event: str, character_id: uuid.UUID, payload: dict, actor_id: uuid.UUID):
    if not campaign_id:
        return
    msg = json.dumps({
        "event": event,
        "character_id": str(character_id),
        "payload": payload,
        "actor_id": str(actor_id),
    })
    await publish(f"campaign:{campaign_id}", msg)


@router.post("", response_model=CharacterOut, status_code=201)
async def create_character(data: CharacterCreate, current_user: CurrentUser, db: DB):
    character = await char_service.create_character(db, data, current_user.id)
    return character


@router.get("/me", response_model=list[CharacterOut])
async def my_characters(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Character).where(
            Character.user_id == current_user.id,
            Character.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


@router.get("/{character_id}", response_model=CharacterWithInventory)
async def get_character(character_id: uuid.UUID, current_user: CurrentUser, db: DB):
    character = await char_service.get_character_or_404(db, character_id)

    # Owner sees their own; DM sees campaign characters; others are blocked
    if character.user_id != current_user.id:
        if character.campaign_id:
            dm_check = await db.execute(
                select(CampaignMember).where(
                    CampaignMember.campaign_id == character.campaign_id,
                    CampaignMember.user_id == current_user.id,
                    CampaignMember.role == "dm",
                )
            )
            if not dm_check.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            raise HTTPException(status_code=403, detail="Access denied")

    return character


@router.patch("/{character_id}", response_model=CharacterOut)
async def update_character(character_id: uuid.UUID, data: CharacterUpdate, current_user: CurrentUser, db: DB):
    character = await char_service.get_character_or_404(db, character_id)
    await char_service.assert_owner_or_dm(db, character, current_user.id)
    character = await char_service.update_character(db, character, data)

    await _broadcast(
        character.campaign_id, "character.update", character.id,
        data.model_dump(exclude_none=True), current_user.id,
    )
    return character


@router.post("/{character_id}/hp", response_model=CharacterOut)
async def update_hp(character_id: uuid.UUID, update: HPUpdate, current_user: CurrentUser, db: DB):
    character = await char_service.get_character_or_404(db, character_id)
    await char_service.assert_owner_or_dm(db, character, current_user.id)
    character = await char_service.apply_hp_update(db, character, update)

    await _broadcast(
        character.campaign_id, "hp.change", character.id,
        {"current_hp": character.current_hp, "temp_hp": character.temp_hp, "max_hp": character.max_hp},
        current_user.id,
    )
    return character


@router.delete("/{character_id}", status_code=204)
async def delete_character(character_id: uuid.UUID, current_user: CurrentUser, db: DB):
    character = await char_service.get_character_or_404(db, character_id)
    if character.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a character")
    character.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@router.post("/{character_id}/inventory", response_model=InventoryItemOut, status_code=201)
async def add_item(character_id: uuid.UUID, data: AddItemRequest, current_user: CurrentUser, db: DB):
    character = await char_service.get_character_or_404(db, character_id)
    await char_service.assert_owner_or_dm(db, character, current_user.id)

    entry = await char_service.add_item(db, character, data, added_by=current_user.id)

    await _broadcast(
        character.campaign_id, "inventory.add", character.id,
        {"item_id": str(data.item_id), "quantity": data.quantity},
        current_user.id,
    )
    return entry


@router.patch("/{character_id}/inventory/{inventory_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    character_id: uuid.UUID,
    inventory_id: uuid.UUID,
    data: UpdateInventoryItem,
    current_user: CurrentUser,
    db: DB,
):
    from sqlalchemy.orm import selectinload
    from app.db.models.character import CharacterInventory

    character = await char_service.get_character_or_404(db, character_id)
    await char_service.assert_owner_or_dm(db, character, current_user.id)

    result = await db.execute(
        select(CharacterInventory).where(
            CharacterInventory.id == inventory_id,
            CharacterInventory.character_id == character_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Inventory entry not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(entry, field, value)

    # Remove entry if quantity reaches 0
    if entry.quantity == 0:
        await db.delete(entry)
        await db.commit()
        raise HTTPException(status_code=204, detail="Item removed")

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{character_id}/inventory/{inventory_id}", status_code=204)
async def remove_item(character_id: uuid.UUID, inventory_id: uuid.UUID, current_user: CurrentUser, db: DB):
    character = await char_service.get_character_or_404(db, character_id)
    await char_service.remove_item(db, character, inventory_id, current_user.id)

    await _broadcast(
        character.campaign_id, "inventory.remove", character.id,
        {"inventory_id": str(inventory_id)},
        current_user.id,
    )


# ---------------------------------------------------------------------------
# Campaign-scoped view (DM sees all party characters)
# ---------------------------------------------------------------------------

@router.get("/campaign/{campaign_id}", response_model=list[CharacterWithInventory])
async def campaign_characters(campaign_id: uuid.UUID, current_user: CurrentUser, db: DB):
    member_check = await db.execute(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == current_user.id,
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this campaign")

    return await char_service.list_characters_for_campaign(db, campaign_id)
