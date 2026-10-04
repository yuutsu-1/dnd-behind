import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class SpeciesOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    size_code: str
    base_speed: int
    source: str
    is_homebrew: bool


class SpeciesCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    # Code of a `sizes` row visible to the caller (400 otherwise).
    size_code: str = "medium"
    base_speed: int = 30


def _pluck(v: list) -> list: #pra casos das lookup tables, deixa a vida mais fácil
    if v and hasattr(v[0], "name"):
        return [item.name for item in v]
    return v


def _pluck_codes(v: list) -> list:
    """Reference rows (ORM) -> their codes; plain lists of codes pass through."""
    if v and hasattr(v[0], "code"):
        return [item.code for item in v]
    return v


class SkillOut(BaseModel):
    model_config = {"from_attributes": True}

    code: str
    name: str
    ability_code: str


class ClassInitialEquipmentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    class_id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    option: str
    quantity: int


class ClassInitialEquipmentCreate(BaseModel):
    item_id: uuid.UUID
    option: str = Field(min_length=1, max_length=10)
    quantity: int = Field(default=1, ge=1)


class ClassOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    hit_die: int
    # Codes of `ability_scores`.
    primary_ability: list[str]
    saving_throw_proficiencies: list[str]
    # Codes of `armor_categories`, `weapon_categories` and `tool_proficiency_options`.
    armor_proficiencies: list[str]
    weapon_proficiencies: list[str]
    tool_proficiencies: list[str]
    skill_choices: int
    skills: list[SkillOut]
    initial_equipment: list[ClassInitialEquipmentOut]
    subclass_level: int
    spell_ability: str | None
    spellcasting_type: str | None
    source: str
    is_homebrew: bool

    @field_validator(
        "primary_ability", "saving_throw_proficiencies",
        "armor_proficiencies", "weapon_proficiencies", "tool_proficiencies",
        mode="before",
    )
    @classmethod
    def _codes(cls, v: list) -> list:
        return _pluck_codes(v)


class ClassCreate(BaseModel):
    """Every reference field takes codes that must exist and be visible to the caller
    (400 otherwise; same message whether the code is unknown or invisible)."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    hit_die: int
    primary_ability: list[str]
    saving_throw_proficiencies: list[str]
    armor_proficiencies: list[str] = Field(default_factory=list)
    weapon_proficiencies: list[str] = Field(default_factory=list)
    tool_proficiencies: list[str] = Field(default_factory=list)
    skill_choices: int = 2
    skills: list[str] = Field(default_factory=list)
    initial_equipment: list[ClassInitialEquipmentCreate] = Field(default_factory=list)
    subclass_level: int = 3
    spell_ability: str | None = None
    spellcasting_type: str | None = None


class SubclassOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    name: str
    description: str | None
    source: str
    is_homebrew: bool


class SubclassCreate(BaseModel):
    class_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class BackgroundInitialEquipmentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    background_id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    option: str
    quantity: int


class BackgroundInitialEquipmentCreate(BaseModel):
    item_id: uuid.UUID
    option: str = Field(min_length=1, max_length=10)
    quantity: int = Field(default=1, ge=1)


def _validate_ability_scores_cardinality(v: list) -> list:
    if len(v) != 3:
        raise ValueError("ability_scores must have exactly 3 entries")
    if len(set(v)) != len(v):
        raise ValueError("ability_scores must not contain duplicates")
    return v


def _validate_skills_cardinality(v: list) -> list:
    if len(v) != 2:
        raise ValueError("skills must have exactly 2 entries")
    if len(set(v)) != len(v):
        raise ValueError("skills must not contain duplicates")
    return v


def _validate_tool_proficiencies(v: list) -> list:
    if not v:
        raise ValueError("tool_proficiencies must have at least 1 entry")
    if len(set(v)) != len(v):
        raise ValueError("tool_proficiencies must not contain duplicates")
    return v


class BackgroundOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    # Codes of `ability_scores`.
    ability_scores: list[str]
    feat_id: uuid.UUID
    feat_name: str
    skills: list[SkillOut]
    # Codes of `tool_proficiency_options`. One entry = fixed proficiency; several =
    # the character picks one.
    tool_proficiencies: list[str]
    initial_equipment: list[BackgroundInitialEquipmentOut]
    source: str
    is_homebrew: bool

    @field_validator("ability_scores", "tool_proficiencies", mode="before")
    @classmethod
    def _codes(cls, v: list) -> list:
        return _pluck_codes(v)


class BackgroundCreate(BaseModel):
    """Reference fields take codes that must exist and be visible to the caller (400)."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    ability_scores: list[str]
    feat_id: uuid.UUID
    skills: list[str]
    tool_proficiencies: list[str]
    initial_equipment: list[BackgroundInitialEquipmentCreate] = Field(default_factory=list)

    @field_validator("ability_scores")
    @classmethod
    def _check_ability_scores(cls, v: list) -> list:
        return _validate_ability_scores_cardinality(v)

    @field_validator("skills")
    @classmethod
    def _check_skills(cls, v: list) -> list:
        return _validate_skills_cardinality(v)

    @field_validator("tool_proficiencies")
    @classmethod
    def _check_tool_proficiencies(cls, v: list) -> list:
        return _validate_tool_proficiencies(v)


class BackgroundUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    ability_scores: list[str] | None = None
    feat_id: uuid.UUID | None = None
    skills: list[str] | None = None
    tool_proficiencies: list[str] | None = None
    initial_equipment: list[BackgroundInitialEquipmentCreate] | None = None

    @field_validator("ability_scores")
    @classmethod
    def _check_ability_scores(cls, v: list | None) -> list | None:
        if v is None:
            return v
        return _validate_ability_scores_cardinality(v)

    @field_validator("skills")
    @classmethod
    def _check_skills(cls, v: list | None) -> list | None:
        if v is None:
            return v
        return _validate_skills_cardinality(v)

    @field_validator("tool_proficiencies")
    @classmethod
    def _check_tool_proficiencies(cls, v: list | None) -> list | None:
        if v is None:
            return v
        return _validate_tool_proficiencies(v)


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
