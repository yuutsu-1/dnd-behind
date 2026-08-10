import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.enums import AbilityScore, CreatureSize


# ---------------------------------------------------------------------------
# FeatureGrant
# ---------------------------------------------------------------------------

class FeatureGrantOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    name: str
    description: str | None
    effect_type: str
    effect_data: dict
    level_requirement: int
    is_optional: bool
    sort_order: int


class FeatureGrantCreate(BaseModel):
    source_type: str
    source_id: uuid.UUID
    name: str
    description: str | None = None
    effect_type: str
    effect_data: dict
    level_requirement: int = 1
    is_optional: bool = False
    sort_order: int = 0


# ---------------------------------------------------------------------------
# Species
# ---------------------------------------------------------------------------

class SpeciesOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    size: CreatureSize
    base_speed: int
    source: str
    is_homebrew: bool


class SpeciesCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    size: CreatureSize = CreatureSize.medium
    base_speed: int = 30


# ---------------------------------------------------------------------------
# Class
# ---------------------------------------------------------------------------

def _pluck(v: list) -> list:
    """Convert a list of lookup-table ORM objects to their string names."""
    if v and hasattr(v[0], "name"):
        return [item.name for item in v]
    return v


class ClassOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    hit_die: int
    primary_ability: list[AbilityScore]
    saving_throw_proficiencies: list[AbilityScore]
    armor_proficiencies: list[str]
    weapon_proficiencies: list[str]
    tool_proficiencies: list[str]
    skill_choices: int
    skill_pool: list
    subclass_level: int
    spell_ability: str | None
    spellcasting_type: str | None
    source: str
    is_homebrew: bool

    @field_validator("primary_ability", "saving_throw_proficiencies", mode="before")
    @classmethod
    def _ability_names(cls, v: list) -> list:
        return _pluck(v)

    @field_validator("armor_proficiencies", "weapon_proficiencies", "tool_proficiencies", mode="before")
    @classmethod
    def _proficiency_names(cls, v: list) -> list:
        return _pluck(v)


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    hit_die: int
    primary_ability: list[AbilityScore]
    saving_throw_proficiencies: list[AbilityScore]
    armor_proficiencies: list[str] = Field(default_factory=list)
    weapon_proficiencies: list[str] = Field(default_factory=list)
    tool_proficiencies: list[str] = Field(default_factory=list)
    skill_choices: int = 2
    skill_pool: list[str] = Field(default_factory=list)
    subclass_level: int = 3
    spell_ability: AbilityScore | None = None
    spellcasting_type: str | None = None


# ---------------------------------------------------------------------------
# Subclass
# ---------------------------------------------------------------------------

class SubclassOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    class_id: uuid.UUID
    name: str
    description: str | None
    source: str
    is_homebrew: bool


class SubclassCreate(BaseModel):
    class_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------

class BackgroundOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    source: str
    is_homebrew: bool


class BackgroundCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


# ---------------------------------------------------------------------------
# Feat
# ---------------------------------------------------------------------------

class FeatOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    category: str
    level_prerequisite: int
    prerequisite_description: str | None
    repeatable: bool
    source: str
    is_homebrew: bool


class FeatCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    category: str
    level_prerequisite: int = 0
    prerequisite_description: str | None = None
    repeatable: bool = False


# ---------------------------------------------------------------------------
# Spell
# ---------------------------------------------------------------------------

class SpellOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    level: int
    school: str
    casting_time: str
    range: str
    components: list
    material_component: str | None
    duration: str
    concentration: bool
    ritual: bool
    description: str
    higher_levels: str | None
    # Returns the names of ClassDefinition objects from the M2M relationship
    class_list: list[str]
    source: str
    is_homebrew: bool

    @field_validator("class_list", mode="before")
    @classmethod
    def _class_names(cls, v: list) -> list:
        return _pluck(v)


class SpellCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    level: int = Field(ge=0, le=9)
    school: str
    casting_time: str
    range: str
    components: list[str]
    material_component: str | None = None
    duration: str
    concentration: bool = False
    ritual: bool = False
    description: str
    higher_levels: str | None = None
    # IDs of existing ClassDefinition rows to link
    class_ids: list[uuid.UUID] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class ItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    item_type: str
    subtype: str | None
    rarity: str
    requires_attunement: bool
    attunement_prerequisite: str | None
    weight: float | None
    cost_gp: float | None
    description: str | None
    properties: dict
    source: str
    is_homebrew: bool


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    item_type: str
    subtype: str | None = None
    rarity: str = "common"
    requires_attunement: bool = False
    attunement_prerequisite: str | None = None
    weight: float | None = None
    cost_gp: float | None = None
    description: str | None = None
    properties: dict = Field(default_factory=dict)
