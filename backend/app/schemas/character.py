import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

class InventoryItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    quantity: int
    equipped: bool
    attuned: bool
    custom_notes: str | None
    added_by: uuid.UUID | None
    added_by_name: str | None
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

_ABILITY_SCORES_DEFAULT = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    species_id: uuid.UUID | None = None
    background_id: uuid.UUID | None = None
    ability_scores: dict = Field(default_factory=lambda: dict(_ABILITY_SCORES_DEFAULT))
    appearance: dict = Field(default_factory=dict)
    notes: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    experience_points: int | None = Field(default=None, ge=0)
    current_hp: int | None = None
    max_hp: int | None = None
    temp_hp: int | None = Field(default=None, ge=0)
    ability_scores: dict | None = None
    conditions: list[str] | None = None
    exhaustion_level: int | None = Field(default=None, ge=0, le=6)
    inspiration: bool | None = None
    death_saves: dict | None = None
    spell_slots_remaining: dict | None = None
    choices: dict | None = None
    appearance: dict | None = None
    notes: str | None = None
    custom_data: dict | None = None


class HPUpdate(BaseModel):
    delta: int  # positive = heal, negative = damage
    is_temp: bool = False  # True = apply to temp HP instead


class CharacterClassOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    class_id: uuid.UUID
    class_name: str | None
    level: int
    subclass_id: uuid.UUID | None
    subclass_name: str | None
    hit_die: int | None
    hit_dice_total: int
    hit_dice_used: int
    hit_dice_remaining: int


class CharacterClassCreate(BaseModel):
    class_id: uuid.UUID
    level: int = Field(default=1, ge=1, le=20)
    subclass_id: uuid.UUID | None = None


class CharacterClassUpdate(BaseModel):
    level: int | None = Field(default=None, ge=1, le=20)
    subclass_id: uuid.UUID | None = None
    # Distinguishes "field not sent" from "explicitly cleared to null";
    # populated via `model_fields_set` by the caller.


class HitDiceUsedUpdate(BaseModel):
    hit_dice_used: int = Field(ge=0)


class CharacterOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    campaign_id: uuid.UUID | None
    campaign_name: str | None
    name: str
    total_level: int
    experience_points: int
    species_id: uuid.UUID | None
    species_name: str | None
    background_id: uuid.UUID | None
    background_name: str | None
    classes: list[CharacterClassOut]
    ability_scores: dict[str, int]
    current_hp: int
    max_hp: int
    temp_hp: int
    death_saves: dict
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

    @field_validator("ability_scores", mode="before")
    @classmethod
    def _ability_scores_as_dict(cls, v):
        # ORM side is a list of `CharacterAbilityScore` rows (one per ability);
        # the public API shape keeps the flat `{"STR": 16, ...}` dict clients
        # already rely on.
        if isinstance(v, dict):
            return v
        return {row.ability_score: row.value for row in v}


class CharacterWithInventory(CharacterOut):
    inventory: list[InventoryItemOut] = Field(default_factory=list)

class WSEvent(BaseModel):
    event: str
    character_id: uuid.UUID | None = None
    payload: dict = Field(default_factory=dict)
    actor_id: uuid.UUID | None = None
