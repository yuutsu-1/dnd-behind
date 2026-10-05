"""Schemas of /api/compendium/spells.

Create/Update forbid extra fields: `id`, `source`, `is_homebrew`, `created_by` give 422.
Only the shape of each field is checked here. Codes (existence/visibility, 400) and the
coherence between fields (components, materials, area, level texts: 422) are checked by
the endpoint on the final state of the spell (app/services/spells.py)."""
import uuid
from typing import Annotated, ClassVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.items import Amount
from app.schemas.reference import Code, CodeList, JsonNumber, Name, PositiveInt, _Update, _Write


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


# Display text: kept as written, but never empty or only whitespace.
Text = Annotated[str, StringConstraints(min_length=1), AfterValidator(_not_blank)]
Level = Annotated[int, Field(ge=0, le=9)]


class SpellMaterialIn(_Write):
    """`cost_gp` is the minimum cost per unit, in gold (null when there is none)."""

    description: Text
    cost_gp: Amount | None = None
    consumed: bool = False
    per_target: bool = False
    quantity: PositiveInt = 1


class SpellCreate(_Write):
    """`materials` are stored in the given order; `spell_list_codes` link the spell to lists."""

    name: Name
    level: Level
    school_code: Code
    has_verbal: bool = False
    has_somatic: bool = False
    has_material: bool = False
    casting_time_code: Code
    ritual: bool = False
    concentration: bool = False
    range: Text
    duration: Text
    area: Text | None = None
    area_shape_code: Code | None = None
    description: Text
    higher_levels: Text | None = None
    cantrip_upgrade: Text | None = None
    materials: list[SpellMaterialIn] = Field(default_factory=list)
    spell_list_codes: CodeList = Field(default_factory=list)


class SpellUpdate(_Update):
    """Fields sent are set; `materials` and `spell_list_codes` replace the whole set."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"area", "area_shape_code", "higher_levels", "cantrip_upgrade"}
    )

    name: Name | None = None
    level: Level | None = None
    school_code: Code | None = None
    has_verbal: bool | None = None
    has_somatic: bool | None = None
    has_material: bool | None = None
    casting_time_code: Code | None = None
    ritual: bool | None = None
    concentration: bool | None = None
    range: Text | None = None
    duration: Text | None = None
    area: Text | None = None
    area_shape_code: Code | None = None
    description: Text | None = None
    higher_levels: Text | None = None
    cantrip_upgrade: Text | None = None
    materials: list[SpellMaterialIn] | None = None
    spell_list_codes: CodeList | None = None


# --- read side --------------------------------------------------------------------

class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SpellMaterialOut(_Out):
    description: str
    cost_gp: JsonNumber | None
    consumed: bool
    per_target: bool
    quantity: int


class SpellListOut(_Out):
    code: str
    name: str


class SpellOut(_Out):
    id: uuid.UUID
    name: str
    level: int
    school_code: str
    school_name: str | None
    has_verbal: bool
    has_somatic: bool
    has_material: bool
    casting_time_code: str
    casting_time_name: str | None
    ritual: bool
    concentration: bool
    range: str
    duration: str
    area: str | None
    area_shape_code: str | None
    area_shape_name: str | None
    description: str
    higher_levels: str | None
    cantrip_upgrade: str | None
    materials: list[SpellMaterialOut]
    spell_lists: list[SpellListOut]
    source: str
    is_homebrew: bool

    @field_validator("spell_lists", mode="after")
    @classmethod
    def _sorted_by_code(cls, lists: list[SpellListOut]) -> list[SpellListOut]:
        return sorted(lists, key=lambda spell_list: spell_list.code)

