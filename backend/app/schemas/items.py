"""Schemas of /api/compendium/items.

An item is a base (name, type, cost in GP, weight in lb) plus at most one sub-object
that depends on its type (see `SUB_OBJECTS`). Create/Update forbid extra fields:
`source`, `is_homebrew`, `created_by` (and, on PATCH, `item_type_code`/`id`) give 422.
Codes are only checked for shape here; existence/visibility is checked by the
endpoint (400, app/services/items.py)."""
import uuid
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.schemas.reference import INT32_MAX, Code, Int32, JsonNumber, Name, NonNegativeInt, PositiveInt, _Update, _Write

DieSize = Literal[4, 6, 8, 10, 12, 20]
# NUMERIC(12,4): more decimals or integer digits would be rounded/overflow -> 422 instead.
Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=4)]
Capacity = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=4)]

# Item type -> (sub-objects allowed, sub-objects required). Any other type (homebrew)
# takes no sub-object.
SUB_OBJECTS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "weapon": (frozenset({"weapon"}), frozenset({"weapon"})),
    "armor": (frozenset({"armor"}), frozenset({"armor"})),
    "tool": (frozenset({"tool"}), frozenset({"tool"})),
    "pack": (frozenset({"contents"}), frozenset({"contents"})),
    "adventuring_gear": (frozenset({"container"}), frozenset()),
    "ammunition": (frozenset(), frozenset()),
    "currency": (frozenset(), frozenset()),
}
SUB_OBJECT_FIELDS = ("weapon", "armor", "tool", "container", "contents")


def sub_object_error(item_type_code: str, present: set[str]) -> str | None:
    """Why `present` sub-objects do not fit `item_type_code` (None if they do)."""
    allowed, required = SUB_OBJECTS.get(item_type_code, (frozenset(), frozenset()))
    if extra := sorted(present - allowed):
        return f"an item of type '{item_type_code}' cannot have: {', '.join(extra)}"
    if missing := sorted(required - present):
        return f"an item of type '{item_type_code}' needs: {', '.join(missing)}"
    return None


def _unique_by(attribute: str, label: str):
    def check(values: list | None) -> list | None:
        if values is not None:
            keys = [getattr(value, attribute) for value in values]
            if len(set(keys)) != len(keys):
                raise ValueError(f"{label} must not contain duplicates")
        return values
    return AfterValidator(check)


# --- write side ------------------------------------------------------------------

class WeaponPropertyIn(_Write):
    """Only the parameter of the property itself: `range` -> distances, `versatile`
    -> die size, `ammunition` -> ammunition item (checked by the endpoint, 400)."""

    code: Code
    range_normal_ft: PositiveInt | None = None
    range_long_ft: PositiveInt | None = None
    versatile_die_size: DieSize | None = None
    ammunition_item_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _long_range_not_shorter(self):
        if self.range_normal_ft is not None and self.range_long_ft is not None:
            if self.range_long_ft < self.range_normal_ft:
                raise ValueError("range_long_ft must be >= range_normal_ft")
        return self


class WeaponIn(_Write):
    category_code: Code
    is_ranged: bool
    damage_dice_count: Annotated[int, Field(ge=1, le=INT32_MAX)] | None = None
    damage_die_size: DieSize | None = None
    damage_flat: Int32 = 0
    damage_type_code: Code
    mastery_code: Code | None = None
    properties: Annotated[list[WeaponPropertyIn], _unique_by("code", "properties")] = Field(default_factory=list)

    @model_validator(mode="after")
    def _damage(self):
        if (self.damage_dice_count is None) != (self.damage_die_size is None):
            raise ValueError("damage_dice_count and damage_die_size go together")
        if self.damage_dice_count is None and self.damage_flat < 1:
            raise ValueError("without dice, damage_flat must be >= 1")
        return self


class ArmorIn(_Write):
    """For a shield, `base_ac` is the bonus it adds."""

    category_code: Code
    base_ac: NonNegativeInt
    adds_dex_modifier: bool = False
    max_dex_modifier: NonNegativeInt | None = None
    strength_requirement: PositiveInt | None = None
    stealth_disadvantage: bool = False


class ToolIn(_Write):
    tool_type_code: Code


class ContainerIn(_Write):
    capacity_weight_lb: Capacity


class ItemContentIn(_Write):
    item_id: uuid.UUID
    quantity: PositiveInt = 1


Contents = Annotated[list[ItemContentIn], _unique_by("item_id", "contents")]


class ItemCreate(_Write):
    name: Name
    item_type_code: Code
    cost_gp: Amount | None = None
    weight_lb: Amount | None = None
    description: str | None = None
    weapon: WeaponIn | None = None
    armor: ArmorIn | None = None
    tool: ToolIn | None = None
    container: ContainerIn | None = None
    contents: Contents | None = None

    @model_validator(mode="after")
    def _sub_objects_fit_the_type(self):
        present = {name for name in SUB_OBJECT_FIELDS if getattr(self, name) is not None}
        if self.contents == []:
            present.discard("contents")
        if error := sub_object_error(self.item_type_code, present):
            raise ValueError(error)
        return self


class ItemUpdate(_Update):
    """A sub-object sent replaces the current one entirely (`container: null` removes
    it). Fit with the item's current type is checked by the endpoint (422)."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"description", "cost_gp", "weight_lb", *SUB_OBJECT_FIELDS}
    )

    name: Name | None = None
    description: str | None = None
    cost_gp: Amount | None = None
    weight_lb: Amount | None = None
    weapon: WeaponIn | None = None
    armor: ArmorIn | None = None
    tool: ToolIn | None = None
    container: ContainerIn | None = None
    contents: Contents | None = None


# --- read side --------------------------------------------------------------------

class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WeaponPropertyOut(_Out):
    code: str
    name: str | None
    range_normal_ft: int | None
    range_long_ft: int | None
    versatile_die_size: int | None
    ammunition_item_id: uuid.UUID | None
    ammunition_item_name: str | None


class WeaponOut(_Out):
    category_code: str
    is_ranged: bool
    damage_dice_count: int | None
    damage_die_size: int | None
    damage_flat: int
    damage_type_code: str
    mastery_code: str | None
    properties: list[WeaponPropertyOut]


class ArmorOut(_Out):
    category_code: str
    base_ac: int
    adds_dex_modifier: bool
    max_dex_modifier: int | None
    strength_requirement: int | None
    stealth_disadvantage: bool


class ToolOut(_Out):
    tool_type_code: str
    tool_type_name: str | None
    category_code: str | None
    ability_code: str | None


class ContainerOut(_Out):
    capacity_weight_lb: JsonNumber


class ItemContentOut(_Out):
    item_id: uuid.UUID
    item_name: str | None
    quantity: int


class ItemOut(_Out):
    """Base + sub-objects; the ones that do not apply to the type are null."""

    id: uuid.UUID
    name: str
    item_type_code: str
    cost_gp: JsonNumber | None
    weight_lb: JsonNumber | None
    description: str | None
    source: str
    is_homebrew: bool
    weapon: WeaponOut | None = None
    armor: ArmorOut | None = None
    tool: ToolOut | None = None
    container: ContainerOut | None = None
    contents: list[ItemContentOut] | None = None

    @model_validator(mode="after")
    def _contents_only_for_packs(self):
        if self.item_type_code != "pack":
            self.contents = None
        return self
