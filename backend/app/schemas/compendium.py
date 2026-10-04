import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.proficiency_grants import GrantDescriptors, ProficiencyGrantDescriptor, ProficiencyGrantOut


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


def _sorted_grants(v: list) -> list:
    """ORM grants -> the canonical order of GET /proficiency-grants."""
    if v and hasattr(v[0], "sort_key"):
        return sorted(v, key=lambda grant: grant.sort_key)
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
    # Every grant is fixed, except `tool_category` ("choose one tool of the category").
    proficiency_grants: list[ProficiencyGrantOut]
    # Read-only: codes of the `saving_throw` grants, sorted.
    saving_throw_proficiencies: list[str]
    skill_choices: int
    skills: list[SkillOut]
    initial_equipment: list[ClassInitialEquipmentOut]
    subclass_level: int
    spell_ability: str | None
    spellcasting_type: str | None
    source: str
    is_homebrew: bool

    @field_validator("primary_ability", mode="before")
    @classmethod
    def _codes(cls, v: list) -> list:
        return _pluck_codes(v)

    @field_validator("proficiency_grants", mode="before")
    @classmethod
    def _grant_order(cls, v: list) -> list:
        return _sorted_grants(v)


class ClassCreate(BaseModel):
    """Every reference field takes codes that must exist and be visible to the caller
    (400 otherwise; same message whether the code is unknown or invisible).
    `proficiency_grants` takes descriptors of any kind (saving throws included); the
    server reuses the existing grant for each target or creates it. Unknown fields
    (e.g. the removed `armor_proficiencies`) are a 422."""

    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    hit_die: int
    primary_ability: list[str]
    proficiency_grants: GrantDescriptors = Field(default_factory=list)
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


BACKGROUND_GRANT_KINDS = frozenset({"skill", "tool", "tool_category"})


def _validate_background_grants(grants: list[ProficiencyGrantDescriptor]) -> list[ProficiencyGrantDescriptor]:
    """Exactly 2 (distinct) skills, at least one tool or tool category, nothing else.
    Duplicates are already rejected by `GrantDescriptors`."""
    kinds = [grant.kind for grant in grants]
    if set(kinds) - BACKGROUND_GRANT_KINDS:
        raise ValueError("a background only grants skills, tools and tool categories")
    if kinds.count("skill") != 2:
        raise ValueError("a background grants exactly 2 skills")
    if not {"tool", "tool_category"} & set(kinds):
        raise ValueError("a background grants at least 1 tool or tool category")
    return grants


class BackgroundOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    # Codes of `ability_scores`.
    ability_scores: list[str]
    feat_id: uuid.UUID
    feat_name: str
    # Every grant is fixed; "choose one tool of the category" is a `tool_category` grant.
    proficiency_grants: list[ProficiencyGrantOut]
    # Read-only: the skills of the `skill` grants, sorted by name.
    skills: list[SkillOut]
    initial_equipment: list[BackgroundInitialEquipmentOut]
    source: str
    is_homebrew: bool

    @field_validator("ability_scores", mode="before")
    @classmethod
    def _codes(cls, v: list) -> list:
        return _pluck_codes(v)

    @field_validator("proficiency_grants", mode="before")
    @classmethod
    def _grant_order(cls, v: list) -> list:
        return _sorted_grants(v)


class BackgroundCreate(BaseModel):
    """Reference fields take codes that must exist and be visible to the caller (400).
    `proficiency_grants`: exactly 2 skills, at least 1 tool or tool category, no other kind.
    Unknown fields (e.g. the removed `skills`) are a 422."""

    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    ability_scores: list[str]
    feat_id: uuid.UUID
    proficiency_grants: GrantDescriptors
    initial_equipment: list[BackgroundInitialEquipmentCreate] = Field(default_factory=list)

    @field_validator("ability_scores")
    @classmethod
    def _check_ability_scores(cls, v: list) -> list:
        return _validate_ability_scores_cardinality(v)

    @field_validator("proficiency_grants")
    @classmethod
    def _check_grants(cls, v: list) -> list:
        return _validate_background_grants(v)


class BackgroundUpdate(BaseModel):
    """`proficiency_grants`, when sent, replaces the whole set (same rules as on create).
    Unknown fields are a 422."""

    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    ability_scores: list[str] | None = None
    feat_id: uuid.UUID | None = None
    proficiency_grants: GrantDescriptors | None = None
    initial_equipment: list[BackgroundInitialEquipmentCreate] | None = None

    @field_validator("ability_scores")
    @classmethod
    def _check_ability_scores(cls, v: list | None) -> list | None:
        if v is None:
            return v
        return _validate_ability_scores_cardinality(v)

    @field_validator("proficiency_grants")
    @classmethod
    def _check_grants(cls, v: list | None) -> list | None:
        if v is None:
            return v
        return _validate_background_grants(v)


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

