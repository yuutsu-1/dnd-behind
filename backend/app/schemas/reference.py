"""Schemas of the reference resources under /api/compendium/<resource>.

Create/Update forbid extra fields, so a client sending `source`, `is_homebrew`,
`created_by` (or, on PATCH, the key: `code`/`level`/`score`) gets a 422. Out
schemas never expose `created_by`; `campaign_ids` is a list for the author and
`null` for everyone else.
"""
import uuid
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints, model_validator,
)

CODE_PATTERN = r"^[a-z0-9]+(_[a-z0-9]+)*$"

Code = Annotated[str, StringConstraints(pattern=CODE_PATTERN, max_length=50)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
NonNegativeInt = Annotated[int, Field(ge=0)]
# NUMERIC columns come back from the DB as Decimal; expose them as JSON numbers.
JsonNumber = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def _no_duplicates(values: list | None) -> list | None:
    if values is not None and len(set(values)) != len(values):
        raise ValueError("must not contain duplicates")
    return values


CampaignIds = Annotated[list[uuid.UUID] | None, AfterValidator(_no_duplicates)]
CodeList = Annotated[list[Code], AfterValidator(_no_duplicates)]


class _Write(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Update(_Write):
    """PATCH base: every field is optional, but non-nullable columns cannot be set to null."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset({"description", "campaign_ids"})

    @model_validator(mode="after")
    def _reject_null_for_required_columns(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None and field not in self.nullable_fields:
                raise ValueError(f"{field} cannot be null")
        return self


# --- code-keyed resources -----------------------------------------------------

class ReferenceCreate(_Write):
    code: Code
    name: Name
    description: str | None = None
    campaign_ids: CampaignIds = None


class ReferenceUpdate(_Update):
    name: Name | None = None
    description: str | None = None
    campaign_ids: CampaignIds = None


class ReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    description: str | None
    source: str
    is_homebrew: bool
    campaign_ids: list[uuid.UUID] | None = None


class SkillCreate(ReferenceCreate):
    ability_code: Code


class SkillUpdate(ReferenceUpdate):
    ability_code: Code | None = None


class SkillOut(ReferenceOut):
    ability_code: str


class ConditionCreate(ReferenceCreate):
    implies: CodeList = Field(default_factory=list)

    @model_validator(mode="after")
    def _not_self_implied(self):
        if self.code in self.implies:
            raise ValueError("a condition cannot imply itself")
        return self


class ConditionUpdate(ReferenceUpdate):
    # The self-implication check needs the code from the URL (done by the endpoint).
    implies: CodeList | None = None


class ConditionOut(ReferenceOut):
    implies: list[str] = Field(default_factory=list)


class SizeCreate(ReferenceCreate):
    hit_die: int = Field(gt=0)
    carry_multiplier: Decimal = Field(gt=0)
    sort_order: int


class SizeUpdate(ReferenceUpdate):
    hit_die: int | None = Field(default=None, gt=0)
    carry_multiplier: Decimal | None = Field(default=None, gt=0)
    sort_order: int | None = None


class SizeOut(ReferenceOut):
    hit_die: int
    carry_multiplier: JsonNumber
    sort_order: int


Rarity = Literal["standard", "rare"]


class LanguageCreate(ReferenceCreate):
    rarity: Rarity


class LanguageUpdate(ReferenceUpdate):
    rarity: Rarity | None = None


class LanguageOut(ReferenceOut):
    rarity: str


class ChallengeRatingCreate(ReferenceCreate):
    numeric_value: Decimal
    proficiency_bonus: NonNegativeInt


class ChallengeRatingUpdate(ReferenceUpdate):
    numeric_value: Decimal | None = None
    proficiency_bonus: NonNegativeInt | None = None


class ChallengeRatingOut(ReferenceOut):
    numeric_value: JsonNumber
    proficiency_bonus: int


# --- numeric-keyed resources (no code/name/description) ----------------------

class CharacterLevelCreate(_Write):
    level: int = Field(ge=1)
    min_xp: NonNegativeInt
    proficiency_bonus: NonNegativeInt
    campaign_ids: CampaignIds = None


class CharacterLevelUpdate(_Update):
    min_xp: NonNegativeInt | None = None
    proficiency_bonus: NonNegativeInt | None = None
    campaign_ids: CampaignIds = None


class CharacterLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    level: int
    min_xp: int
    proficiency_bonus: int
    source: str
    is_homebrew: bool
    campaign_ids: list[uuid.UUID] | None = None


class PointBuyCostCreate(_Write):
    score: int
    cost: NonNegativeInt
    campaign_ids: CampaignIds = None


class PointBuyCostUpdate(_Update):
    cost: NonNegativeInt | None = None
    campaign_ids: CampaignIds = None


class PointBuyCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    cost: int
    source: str
    is_homebrew: bool
    campaign_ids: list[uuid.UUID] | None = None
