import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class InventoryItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    item_id: uuid.UUID
    quantity: int
    equipped: bool
    attuned: bool
    custom_notes: str | None
    added_by: uuid.UUID | None
    added_at: datetime


class AddItemRequest(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)
    custom_notes: str | None = None


class UpdateInventoryItem(BaseModel):
    quantity: int | None = Field(default=None, ge=0)
    equipped: bool | None = None
    attuned: bool | None = None
    custom_notes: str | None = None


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------

_ABILITY_SCORES_DEFAULT = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    species_id: uuid.UUID | None = None
    background_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None
    ability_scores: dict = Field(default_factory=lambda: dict(_ABILITY_SCORES_DEFAULT))
    appearance: dict = Field(default_factory=dict)
    notes: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    level: int | None = Field(default=None, ge=1, le=20)
    experience_points: int | None = Field(default=None, ge=0)
    subclass_id: uuid.UUID | None = None
    current_hp: int | None = None
    max_hp: int | None = None
    temp_hp: int | None = Field(default=None, ge=0)
    ability_scores: dict | None = None
    conditions: list[str] | None = None
    exhaustion_level: int | None = Field(default=None, ge=0, le=6)
    inspiration: bool | None = None
    death_saves: dict | None = None
    hit_dice_remaining: dict | None = None
    spell_slots_remaining: dict | None = None
    choices: dict | None = None
    appearance: dict | None = None
    notes: str | None = None
    custom_data: dict | None = None


class HPUpdate(BaseModel):
    """Convenience body for quick HP changes from the DM panel."""
    delta: int  # positive = heal, negative = damage
    is_temp: bool = False  # True = apply to temp HP instead


class CharacterOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    campaign_id: uuid.UUID | None
    name: str
    level: int
    experience_points: int
    species_id: uuid.UUID | None
    background_id: uuid.UUID | None
    class_id: uuid.UUID | None
    subclass_id: uuid.UUID | None
    ability_scores: dict
    current_hp: int
    max_hp: int
    temp_hp: int
    death_saves: dict
    hit_dice_remaining: dict
    conditions: list
    exhaustion_level: int
    inspiration: bool
    choices: dict
    spell_slots_remaining: dict
    appearance: dict
    notes: str | None
    custom_data: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CharacterWithInventory(CharacterOut):
    inventory: list[InventoryItemOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------

class WSEvent(BaseModel):
    """Envelope for all WebSocket messages in a campaign room."""
    event: str
    character_id: uuid.UUID | None = None
    payload: dict = Field(default_factory=dict)
    actor_id: uuid.UUID | None = None
