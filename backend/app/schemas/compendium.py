import uuid
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator

from app.schemas.features import Level, FeatureIn, FeatureOut, PrerequisiteIn, PrerequisiteOut, sorted_prerequisites
from app.schemas.proficiency_grants import GrantDescriptors, ProficiencyGrantDescriptor, ProficiencyGrantOut
from app.schemas.reference import Code, Name, NonNegativeInt, PositiveInt, _Update, _Write


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
    quantity: PositiveInt = 1


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
    # Features of every level, with every child (app/schemas/features.py).
    features: list[FeatureOut]
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
    hit_die: PositiveInt
    primary_ability: list[str]
    proficiency_grants: GrantDescriptors = Field(default_factory=list)
    skill_choices: NonNegativeInt = 2
    skills: list[str] = Field(default_factory=list)
    initial_equipment: list[ClassInitialEquipmentCreate] = Field(default_factory=list)
    subclass_level: Level = 3
    spell_ability: str | None = None
    spellcasting_type: str | None = None
    # Each with a `level` (1..20); references between them are positions.
    features: list[FeatureIn] = Field(default_factory=list)


class ClassUpdate(_Update):
    """Fields sent are set; `features`, `proficiency_grants`, `skills`, `primary_ability`
    and `initial_equipment`, when sent, replace the whole set. Unknown fields are a 422."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset({"description", "spell_ability", "spellcasting_type"})

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    hit_die: PositiveInt | None = None
    primary_ability: list[str] | None = None
    proficiency_grants: GrantDescriptors | None = None
    skill_choices: NonNegativeInt | None = None
    skills: list[str] | None = None
    initial_equipment: list[ClassInitialEquipmentCreate] | None = None
    subclass_level: Level | None = None
    spell_ability: str | None = None
    spellcasting_type: str | None = None
    features: list[FeatureIn] | None = None


class SubclassOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    name: str
    description: str | None
    features: list[FeatureOut]
    source: str
    is_homebrew: bool


class SubclassCreate(_Write):
    """`class_id` must exist (400). Each feature has a `level` (1..20)."""

    class_id: uuid.UUID
    name: Name
    description: str | None = None
    features: list[FeatureIn] = Field(default_factory=list)


class SubclassUpdate(_Update):
    """`class_id` is immutable (422). `features`, when sent, replace the whole set."""

    name: Name | None = None
    description: str | None = None
    features: list[FeatureIn] | None = None


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
    quantity: PositiveInt = 1


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
    """A feat with its prerequisites (`or_group`: same group = OR, groups = AND) and its
    complete features. The list returns the same format as the detail."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    category_code: str
    category_name: str | None
    repeatable: bool
    prerequisites: list[PrerequisiteOut]
    features: list[FeatureOut]
    source: str
    is_homebrew: bool

    @field_validator("prerequisites", mode="before")
    @classmethod
    def _prerequisite_order(cls, v: list) -> list:
        return sorted_prerequisites(v)


class FeatCreate(_Write):
    """`category_code` and every code inside `prerequisites`/`features` must exist and be
    visible to the caller (400). The features take positions to refer to each other
    (app/schemas/features.py)."""

    name: Name
    description: str | None = None
    category_code: Code
    repeatable: bool = False
    prerequisites: list[PrerequisiteIn] = Field(default_factory=list)
    features: list[FeatureIn] = Field(default_factory=list)


class FeatUpdate(_Update):
    """Fields sent are set; `prerequisites` and `features`, when sent, replace the whole set."""

    name: Name | None = None
    description: str | None = None
    category_code: Code | None = None
    repeatable: bool | None = None
    prerequisites: list[PrerequisiteIn] | None = None
    features: list[FeatureIn] | None = None
