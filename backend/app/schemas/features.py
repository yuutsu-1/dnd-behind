"""Schemas of features and their children (phase 4), embedded in the payloads of feats,
classes and subclasses (there is no write route of its own for a feature).

Write side (`FeatureIn` and children) forbids extra fields: ids, provenance, the owner,
`replaces_feature_id`, `resource_id` and `spell_list_from_choice_id` are a 422. References
inside the payload are positions, because nothing has an id before it is written:
- `replaces_index`: position of the replaced feature in the owner's `features`;
- `resource_index`: position of a resource in the same feature's `resources`;
- `spell_list_from_effect_index`: position of the effect (same feature) whose choice gives
  the spell list.
`sort_order` is the position in the list. Scaling rows are nested in their target.

Only the shape is checked here. Codes and ids (400) and the coherence that depends on
codes or on other rows (422) are checked by app/services/features.py."""
import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.features import EFFECT_TARGET_COLUMNS, OPTION_TARGET_COLUMNS
from app.schemas.items import DieSize
from app.schemas.reference import INT32_MAX, Code, Int32, Name, _Write
from app.schemas.spells import Text

Level = Annotated[int, Field(ge=1, le=20)]
Position = Annotated[int, Field(ge=0, le=INT32_MAX)]
AtLeastOne = Annotated[int, Field(ge=1, le=INT32_MAX)]
SpellLevel = Annotated[int, Field(ge=0, le=9)]
MinScore = Annotated[int, Field(ge=1, le=30)]

# The value basis that needs `value_basis_ability_code` (and is the only one taking it).
ABILITY_MODIFIER = "ability_modifier"


def _check_dice(row) -> None:
    if (row.dice_count is None) != (row.die_size is None):
        raise ValueError("dice_count and die_size go together")


def _check_basis(row) -> None:
    if row.value_basis_code == ABILITY_MODIFIER and row.value_basis_ability_code is None:
        raise ValueError("value_basis 'ability_modifier' needs value_basis_ability_code")
    if row.value_basis_ability_code is not None and row.value_basis_code != ABILITY_MODIFIER:
        raise ValueError("value_basis_ability_code only goes with value_basis 'ability_modifier'")


def _unique_levels(rows: list) -> list:
    levels = [row.level for row in rows]
    if len(set(levels)) != len(levels):
        raise ValueError("scaling levels must not repeat")
    return rows


# --- write side ------------------------------------------------------------------------

class ScalingIn(_Write):
    """The value of the target from `level` on (until the next row)."""

    level: Level
    value: Int32 | None = None
    dice_count: AtLeastOne | None = None
    die_size: DieSize | None = None

    @model_validator(mode="after")
    def _shape(self):
        _check_dice(self)
        if self.value is None and self.dice_count is None:
            raise ValueError("a scaling row needs a value or dice")
        return self


Scaling = Annotated[list[ScalingIn], AfterValidator(_unique_levels)]


class OptionIn(_Write):
    """One explicit option of a choice: exactly one target."""

    feat_id: uuid.UUID | None = None
    spell_id: uuid.UUID | None = None
    skill_code: Code | None = None
    tool_type_code: Code | None = None
    ability_code: Code | None = None
    item_id: uuid.UUID | None = None
    spell_list_code: Code | None = None
    feature_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if len(self.targets) != 1:
            raise ValueError("an option needs exactly one target")
        return self

    @property
    def targets(self) -> list[str]:
        return [column for column in OPTION_TARGET_COLUMNS if getattr(self, column) is not None]

    @property
    def key(self) -> tuple:
        return tuple(getattr(self, column) for column in OPTION_TARGET_COLUMNS)


class ChoiceIn(_Write):
    """'Choose `choose_count` of the pool' (only of `options` when they are given)."""

    choose_count: AtLeastOne
    allow_repeat: bool = False
    pool_type_code: Code
    feat_category_code: Code | None = None
    spell_list_code: Code | None = None
    spell_level: SpellLevel | None = None
    weapon_category_code: Code | None = None
    tool_category_code: Code | None = None
    spell_list_from_effect_index: Position | None = None
    swap_rule_code: Code | None = None
    options: list[OptionIn] = Field(default_factory=list)
    scaling: Scaling = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self):
        keys = [option.key for option in self.options]
        if len(set(keys)) != len(keys):
            raise ValueError("options must not repeat")
        if self.options and not self.allow_repeat and self.choose_count > len(self.options):
            raise ValueError("choose_count is greater than the number of options (and allow_repeat is false)")
        return self


class EffectIn(_Write):
    """`operation_code` on one fixed typed target or on the targets of `choice` (not both).
    Value: `dice_count d die_size + basis * value_multiplier + value`, within
    `min_value`..`max_value`."""

    operation_code: Code
    target_code: Code | None = None
    feat_id: uuid.UUID | None = None
    spell_id: uuid.UUID | None = None
    granted_feature_id: uuid.UUID | None = None
    proficiency_grant_id: uuid.UUID | None = None
    skill_code: Code | None = None
    ability_code: Code | None = None
    damage_type_code: Code | None = None
    condition_code: Code | None = None
    sense_code: Code | None = None
    movement_mode_code: Code | None = None
    item_id: uuid.UUID | None = None
    value: Int32 | None = None
    dice_count: AtLeastOne | None = None
    die_size: DieSize | None = None
    value_basis_code: Code | None = None
    value_basis_ability_code: Code | None = None
    value_multiplier: Int32 = 1
    min_value: Int32 | None = None
    max_value: Int32 | None = None
    spell_ability_code: Code | None = None
    always_prepared: bool = False
    resource_index: Position | None = None
    condition_text: Text | None = None
    choice: ChoiceIn | None = None
    scaling: Scaling = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self):
        targets = self.targets
        if len(targets) > 1:
            raise ValueError(f"an effect has at most one fixed target (got {', '.join(targets)})")
        if targets and self.choice is not None:
            raise ValueError("an effect has either a fixed target or a choice, not both")
        _check_dice(self)
        _check_basis(self)
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must be <= max_value")
        return self

    @property
    def targets(self) -> list[str]:
        return [column for column in EFFECT_TARGET_COLUMNS if getattr(self, column) is not None]

    @property
    def has_amount(self) -> bool:
        """A fixed value, dice or a formula basis."""
        return self.value is not None or self.dice_count is not None or self.value_basis_code is not None


class RechargeIn(_Write):
    """`recovers` uses on `recharge_type_code`; null = every use."""

    recharge_type_code: Code
    recovers: AtLeastOne | None = None


def _one_recharge_per_type(recharges: list[RechargeIn]) -> list[RechargeIn]:
    if not recharges:
        raise ValueError("a resource needs at least one recharge")
    codes = [recharge.recharge_type_code for recharge in recharges]
    if len(set(codes)) != len(codes):
        raise ValueError("a recharge type must not repeat in the same resource")
    return recharges


class ResourceIn(_Write):
    """Uses shown on the sheet: `value` and/or `basis * value_multiplier`, at least `min_value`."""

    name: Name
    value: Int32 | None = None
    value_basis_code: Code | None = None
    value_basis_ability_code: Code | None = None
    value_multiplier: Int32 = 1
    min_value: Int32 | None = None
    recharges: Annotated[list[RechargeIn], AfterValidator(_one_recharge_per_type)]
    scaling: Scaling = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self):
        if self.value is None and self.value_basis_code is None:
            raise ValueError("a resource needs a value or a value basis")
        _check_basis(self)
        return self


class FeatureIn(_Write):
    """A feature written with its owner. `level` (1..20) is required for class/subclass
    features and forbidden for feat features (checked by the service, 422)."""

    name: Name
    description: Text | None = None
    level: Level | None = None
    action_type_code: Code | None = None
    feature_kind_code: Code | None = None
    is_choice_option: bool = False
    replaces_index: Position | None = None
    effects: list[EffectIn] = Field(default_factory=list)
    resources: list[ResourceIn] = Field(default_factory=list)


class PrerequisiteIn(_Write):
    """Exactly one of: `min_character_level`, `ability_code` + `min_score`,
    `feature_kind_code`. Rows of the same `or_group` are alternatives (OR); groups are AND."""

    or_group: AtLeastOne
    min_character_level: Level | None = None
    ability_code: Code | None = None
    min_score: MinScore | None = None
    feature_kind_code: Code | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if (self.ability_code is None) != (self.min_score is None):
            raise ValueError("ability_code and min_score go together")
        targets = [self.min_character_level, self.ability_code, self.feature_kind_code]
        if sum(target is not None for target in targets) != 1:
            raise ValueError("a prerequisite needs exactly one of level, ability score or feature kind")
        return self


# --- read side ---------------------------------------------------------------------

def _sorted_by_key(rows: list) -> list:
    """ORM rows -> their canonical order (`sort_key`)."""
    if rows and hasattr(rows[0], "sort_key"):
        return sorted(rows, key=lambda row: row.sort_key)
    return rows


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ScalingOut(_Out):
    id: uuid.UUID
    level: int
    value: int | None
    dice_count: int | None
    die_size: int | None


class OptionOut(_Out):
    id: uuid.UUID
    feat_id: uuid.UUID | None
    spell_id: uuid.UUID | None
    skill_code: str | None
    tool_type_code: str | None
    ability_code: str | None
    item_id: uuid.UUID | None
    spell_list_code: str | None
    feature_id: uuid.UUID | None
    # Name of the target (feat, spell, skill, tool, ability, item, list or feature).
    target_name: str | None


class ChoiceOut(_Out):
    id: uuid.UUID
    choose_count: int
    allow_repeat: bool
    pool_type_code: str
    pool_type_name: str | None
    feat_category_code: str | None
    feat_category_name: str | None
    spell_list_code: str | None
    spell_list_name: str | None
    spell_level: int | None
    weapon_category_code: str | None
    weapon_category_name: str | None
    tool_category_code: str | None
    tool_category_name: str | None
    spell_list_from_choice_id: uuid.UUID | None
    swap_rule_code: str | None
    swap_rule_name: str | None
    options: list[OptionOut]
    scaling: list[ScalingOut]

    @field_validator("options", mode="before")
    @classmethod
    def _option_order(cls, v: list) -> list:
        return _sorted_by_key(v)


class EffectOut(_Out):
    id: uuid.UUID
    sort_order: int
    operation_code: str
    operation_name: str | None
    target_code: str | None
    target_name: str | None
    feat_id: uuid.UUID | None
    feat_name: str | None
    spell_id: uuid.UUID | None
    spell_name: str | None
    granted_feature_id: uuid.UUID | None
    granted_feature_name: str | None
    proficiency_grant_id: uuid.UUID | None
    proficiency_grant_name: str | None
    skill_code: str | None
    skill_name: str | None
    ability_code: str | None
    ability_name: str | None
    damage_type_code: str | None
    damage_type_name: str | None
    condition_code: str | None
    condition_name: str | None
    sense_code: str | None
    sense_name: str | None
    movement_mode_code: str | None
    movement_mode_name: str | None
    item_id: uuid.UUID | None
    item_name: str | None
    value: int | None
    dice_count: int | None
    die_size: int | None
    value_basis_code: str | None
    value_basis_name: str | None
    value_basis_ability_code: str | None
    value_multiplier: int
    min_value: int | None
    max_value: int | None
    spell_ability_code: str | None
    always_prepared: bool
    resource_id: uuid.UUID | None
    condition_text: str | None
    choice: ChoiceOut | None
    scaling: list[ScalingOut]


class RechargeOut(_Out):
    id: uuid.UUID
    recharge_type_code: str
    recharge_type_name: str | None
    recovers: int | None


class ResourceOut(_Out):
    id: uuid.UUID
    sort_order: int
    name: str
    value: int | None
    value_basis_code: str | None
    value_basis_name: str | None
    value_basis_ability_code: str | None
    value_multiplier: int
    min_value: int | None
    recharges: list[RechargeOut]
    scaling: list[ScalingOut]


class FeatureOut(_Out):
    id: uuid.UUID
    name: str
    description: str | None
    sort_order: int
    class_id: uuid.UUID | None
    subclass_id: uuid.UUID | None
    feat_id: uuid.UUID | None
    level: int | None
    action_type_code: str | None
    action_type_name: str | None
    feature_kind_code: str | None
    feature_kind_name: str | None
    replaces_feature_id: uuid.UUID | None
    replaces_feature_name: str | None
    is_choice_option: bool
    source: str
    is_homebrew: bool
    effects: list[EffectOut]
    resources: list[ResourceOut]


class PrerequisiteOut(_Out):
    id: uuid.UUID
    or_group: int
    min_character_level: int | None
    ability_code: str | None
    ability_name: str | None
    min_score: int | None
    feature_kind_code: str | None
    feature_kind_name: str | None


def sorted_prerequisites(rows: list) -> list:
    return _sorted_by_key(rows)
