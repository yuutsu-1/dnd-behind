"""Features and what they do (phase 4 of the model redesign).

- `feature_definitions`: a feature of exactly one owner (class, subclass or feat). Class
  and subclass features have a `level` (1..20); feat features have none. The values of
  `source`/`is_homebrew`/`created_by` are copied from the owner.
- `feature_effects`: what a feature does (operation + one typed target or a choice).
- `feature_choices` + `feature_choice_options`: "choose N of ...".
- `feature_resources` + `feature_resource_recharges`: uses and how they come back.
- `feature_scaling`: values by level of an effect, a choice or a resource.
- `feat_prerequisites`: what a feat requires. Rows with the same `or_group` are
  alternatives (OR); different groups must all hold (AND).

Child rows are loaded explicitly by the services (app/services/features.py,
app/services/feats.py), never implicitly; names of referenced codes come joined and
referenced entities (feat, spell, item, feature, grant) come in one query per batch.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.reference import (
    CODE_LENGTH,
    Ability,
    ActionType,
    ChoicePoolType,
    ChoiceSwapRule,
    Condition,
    DamageType,
    EffectOperation,
    EffectTarget,
    FeatCategory,
    FeatureKind,
    MovementMode,
    RechargeType,
    Sense,
    Skill,
    SpellList,
    ToolCategory,
    ToolType,
    ValueBasis,
    WeaponCategory,
)

# Typed targets of an effect (at most one) and of a choice option (exactly one).
EFFECT_TARGET_COLUMNS: tuple[str, ...] = (
    "feat_id", "spell_id", "granted_feature_id", "proficiency_grant_id", "skill_code", "ability_code",
    "damage_type_code", "condition_code", "sense_code", "movement_mode_code", "item_id",
)
OPTION_TARGET_COLUMNS: tuple[str, ...] = (
    "feat_id", "spell_id", "skill_code", "tool_type_code", "ability_code", "item_id", "spell_list_code",
    "feature_id",
)
DIE_SIZES: tuple[int, ...] = (4, 6, 8, 10, 12, 20)
_DIE_SIZE_CHECK = f"die_size IN ({', '.join(str(size) for size in DIE_SIZES)})"


def _code_fk(target: str) -> ForeignKey:
    return ForeignKey(target, ondelete="RESTRICT")


def _code(target: str, nullable: bool = True):
    return mapped_column(String(CODE_LENGTH), _code_fk(target), nullable=nullable)


def _entity(target: str):
    """FK to an entity that blocks its delete (NO ACTION, checked at the end of the statement)."""
    return mapped_column(UUID(as_uuid=True), ForeignKey(target), nullable=True)


def _name_of(relation) -> str | None:
    return relation.name if relation is not None else None


class FeatPrerequisite(Base):
    """One requirement of a feat: exactly one of a character level, an ability score
    (`ability_code` + `min_score`) or a feature kind."""

    __tablename__ = "feat_prerequisites"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(min_character_level, ability_code, feature_kind_code) = 1",
            name="ck_feat_prerequisites_single_target",
        ),
        CheckConstraint("(ability_code IS NULL) = (min_score IS NULL)", name="ck_feat_prerequisites_ability_pair"),
        CheckConstraint(
            "min_character_level BETWEEN 1 AND 20", name="ck_feat_prerequisites_min_character_level"
        ),
        CheckConstraint("min_score BETWEEN 1 AND 30", name="ck_feat_prerequisites_min_score"),
    )

    id: Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feat_id: Mapped[uuid.UUID]  = mapped_column(
        UUID(as_uuid=True), ForeignKey("feat_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    or_group: Mapped[int]                   = mapped_column(Integer, nullable=False)
    min_character_level: Mapped[int | None] = mapped_column(Integer)
    ability_code: Mapped[str | None]        = _code("ability_scores.code")
    min_score: Mapped[int | None]           = mapped_column(Integer)
    feature_kind_code: Mapped[str | None]   = _code("feature_kinds.code")

    ability: Mapped[Ability | None]          = relationship(lazy="joined")
    feature_kind: Mapped[FeatureKind | None] = relationship(lazy="joined")

    @property
    def ability_name(self) -> str | None:
        return _name_of(self.ability)

    @property
    def feature_kind_name(self) -> str | None:
        return _name_of(self.feature_kind)

    @property
    def sort_key(self) -> tuple:
        """Canonical order: group, then level, ability, feature kind (each kind together)."""
        return (
            self.or_group, self.min_character_level is None, self.min_character_level or 0,
            self.ability_code or "", self.feature_kind_code or "", str(self.id),
        )


def _owner(target: str):
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete="CASCADE"), nullable=True, index=True)


class FeatureDefinition(Base):
    """A feature of exactly one owner. `replaces_feature_id` points to a feature of the
    same owner and a lower level that stops applying from this feature's level on (the
    FK is NO ACTION so the owner's cascade can delete a whole chain in one statement).
    `is_choice_option`: the feature is only an option of a choice, never granted by itself."""

    __tablename__ = "feature_definitions"
    __table_args__ = (
        CheckConstraint("num_nonnulls(class_id, subclass_id, feat_id) = 1", name="ck_feature_definitions_single_owner"),
        CheckConstraint("(level IS NULL) = (feat_id IS NOT NULL)", name="ck_feature_definitions_level_by_owner"),
        CheckConstraint("level BETWEEN 1 AND 20", name="ck_feature_definitions_level"),
        CheckConstraint("replaces_feature_id <> id", name="ck_feature_definitions_not_self_replacing"),
    )

    id: Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]                     = mapped_column(String(100), nullable=False)
    description: Mapped[str | None]       = mapped_column(Text)
    sort_order: Mapped[int]               = mapped_column(Integer, nullable=False, default=0)
    class_id: Mapped[uuid.UUID | None]    = _owner("class_definitions.id")
    subclass_id: Mapped[uuid.UUID | None] = _owner("subclass_definitions.id")
    feat_id: Mapped[uuid.UUID | None]     = _owner("feat_definitions.id")
    level: Mapped[int | None]             = mapped_column(Integer)
    action_type_code: Mapped[str | None]  = _code("action_types.code")
    feature_kind_code: Mapped[str | None] = _code("feature_kinds.code")
    replaces_feature_id: Mapped[uuid.UUID | None] = _entity("feature_definitions.id")
    is_choice_option: Mapped[bool]        = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str]                   = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]             = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now())

    action_type: Mapped[ActionType | None]   = relationship(lazy="joined")
    feature_kind: Mapped[FeatureKind | None] = relationship(lazy="joined")
    replaces: Mapped["FeatureDefinition | None"] = relationship(
        remote_side=[id], foreign_keys=[replaces_feature_id], lazy="joined", join_depth=1,
    )
    effects: Mapped[list["FeatureEffect"]] = relationship(
        foreign_keys="FeatureEffect.feature_id", passive_deletes=True, order_by="FeatureEffect.sort_order",
    )

    @property
    def action_type_name(self) -> str | None:
        return _name_of(self.action_type)

    @property
    def feature_kind_name(self) -> str | None:
        return _name_of(self.feature_kind)

    @property
    def replaces_feature_name(self) -> str | None:
        return _name_of(self.replaces)


class FeatureEffect(Base):
    """What a feature does: `operation_code` (how) on either one fixed typed target or the
    target(s) picked through its `choice` (never both). The value is
    `dice_count d die_size + basis * value_multiplier + value`, bounded by `min_value` and
    `max_value`; `feature_scaling` rows change it by level. `condition_text` is the
    restriction shown on the sheet ("while wearing Light, Medium, or Heavy armor")."""

    __tablename__ = "feature_effects"
    __table_args__ = (
        CheckConstraint(
            f"num_nonnulls({', '.join(EFFECT_TARGET_COLUMNS)}) <= 1", name="ck_feature_effects_single_target"
        ),
        CheckConstraint("(dice_count IS NULL) = (die_size IS NULL)", name="ck_feature_effects_dice_pair"),
        CheckConstraint(_DIE_SIZE_CHECK, name="ck_feature_effects_die_size"),
        CheckConstraint("dice_count >= 1", name="ck_feature_effects_dice_count"),
        CheckConstraint(
            "value_basis_ability_code IS NULL OR value_basis_code IS NOT NULL", name="ck_feature_effects_basis_ability"
        ),
        CheckConstraint("min_value <= max_value", name="ck_feature_effects_min_max"),
        UniqueConstraint("feature_id", "sort_order", name="uq_feature_effects_sort_order"),
    )

    id: Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_definitions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int]       = mapped_column(Integer, nullable=False)
    operation_code: Mapped[str]   = _code("effect_operations.code", nullable=False)
    target_code: Mapped[str | None] = _code("effect_targets.code")
    feat_id: Mapped[uuid.UUID | None]              = _entity("feat_definitions.id")
    spell_id: Mapped[uuid.UUID | None]             = _entity("spell_definitions.id")
    granted_feature_id: Mapped[uuid.UUID | None]   = _entity("feature_definitions.id")
    proficiency_grant_id: Mapped[uuid.UUID | None] = _entity("proficiency_grants.id")
    skill_code: Mapped[str | None]         = _code("skills.code")
    ability_code: Mapped[str | None]       = _code("ability_scores.code")
    damage_type_code: Mapped[str | None]   = _code("damage_types.code")
    condition_code: Mapped[str | None]     = _code("conditions.code")
    sense_code: Mapped[str | None]         = _code("senses.code")
    movement_mode_code: Mapped[str | None] = _code("movement_modes.code")
    item_id: Mapped[uuid.UUID | None]      = _entity("item_definitions.id")
    value: Mapped[int | None]       = mapped_column(Integer)
    dice_count: Mapped[int | None]  = mapped_column(Integer)
    die_size: Mapped[int | None]    = mapped_column(Integer)
    value_basis_code: Mapped[str | None]         = _code("value_bases.code")
    value_basis_ability_code: Mapped[str | None] = _code("ability_scores.code")
    value_multiplier: Mapped[int]   = mapped_column(Integer, nullable=False, default=1)
    min_value: Mapped[int | None]   = mapped_column(Integer)
    max_value: Mapped[int | None]   = mapped_column(Integer)
    spell_ability_code: Mapped[str | None] = _code("ability_scores.code")
    always_prepared: Mapped[bool]   = mapped_column(Boolean, nullable=False, default=False)
    resource_id: Mapped[uuid.UUID | None] = _entity("feature_resources.id")
    condition_text: Mapped[str | None] = mapped_column(Text)

    operation: Mapped[EffectOperation]         = relationship(lazy="joined")
    target: Mapped[EffectTarget | None]        = relationship(lazy="joined")
    skill: Mapped[Skill | None]                = relationship(lazy="joined")
    ability: Mapped[Ability | None]            = relationship(foreign_keys=[ability_code], lazy="joined")
    damage_type: Mapped[DamageType | None]     = relationship(lazy="joined")
    condition: Mapped[Condition | None]        = relationship(lazy="joined")
    sense: Mapped[Sense | None]                = relationship(lazy="joined")
    movement_mode: Mapped[MovementMode | None] = relationship(lazy="joined")
    value_basis: Mapped[ValueBasis | None]     = relationship(lazy="joined")
    # Entities: one query per batch, only when some row points to one.
    feat: Mapped["FeatDefinition | None"]      = relationship(lazy="selectin")  # noqa: F821
    spell: Mapped["SpellDefinition | None"]    = relationship(lazy="selectin")  # noqa: F821
    granted_feature: Mapped[FeatureDefinition | None] = relationship(
        foreign_keys=[granted_feature_id], lazy="selectin",
    )
    proficiency_grant: Mapped["ProficiencyGrant | None"] = relationship(lazy="selectin")  # noqa: F821
    item: Mapped["ItemDefinition | None"]      = relationship(lazy="selectin")  # noqa: F821
    choice: Mapped["FeatureChoice | None"]     = relationship(uselist=False, passive_deletes=True)

    @property
    def operation_name(self) -> str | None:
        return _name_of(self.operation)

    @property
    def target_name(self) -> str | None:
        return _name_of(self.target)

    @property
    def feat_name(self) -> str | None:
        return _name_of(self.feat)

    @property
    def spell_name(self) -> str | None:
        return _name_of(self.spell)

    @property
    def granted_feature_name(self) -> str | None:
        return _name_of(self.granted_feature)

    @property
    def proficiency_grant_name(self) -> str | None:
        return self.proficiency_grant.target_name if self.proficiency_grant is not None else None

    @property
    def skill_name(self) -> str | None:
        return _name_of(self.skill)

    @property
    def ability_name(self) -> str | None:
        return _name_of(self.ability)

    @property
    def damage_type_name(self) -> str | None:
        return _name_of(self.damage_type)

    @property
    def condition_name(self) -> str | None:
        return _name_of(self.condition)

    @property
    def sense_name(self) -> str | None:
        return _name_of(self.sense)

    @property
    def movement_mode_name(self) -> str | None:
        return _name_of(self.movement_mode)

    @property
    def item_name(self) -> str | None:
        return _name_of(self.item)

    @property
    def value_basis_name(self) -> str | None:
        return _name_of(self.value_basis)


class FeatureChoice(Base):
    """'Choose `choose_count` of ...' for one effect: the pool, optional filters, an
    optional explicit list of options (none = the whole pool) and when the choice can
    be swapped. `spell_list_from_choice_id`: the spell list comes from another choice
    (pool `spell_list`)."""

    __tablename__ = "feature_choices"
    __table_args__ = (
        CheckConstraint("choose_count >= 1", name="ck_feature_choices_choose_count"),
        CheckConstraint("spell_level BETWEEN 0 AND 9", name="ck_feature_choices_spell_level"),
        CheckConstraint("spell_list_from_choice_id <> id", name="ck_feature_choices_not_self_spell_list"),
        UniqueConstraint("effect_id", name="uq_feature_choices_effect_id"),
    )

    id: Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_effects.id", ondelete="CASCADE"), nullable=False
    )
    choose_count: Mapped[int]    = mapped_column(Integer, nullable=False)
    allow_repeat: Mapped[bool]   = mapped_column(Boolean, nullable=False, default=False)
    pool_type_code: Mapped[str]  = _code("choice_pool_types.code", nullable=False)
    feat_category_code: Mapped[str | None]   = _code("feat_categories.code")
    spell_list_code: Mapped[str | None]      = _code("spell_lists.code")
    spell_level: Mapped[int | None]          = mapped_column(Integer)
    weapon_category_code: Mapped[str | None] = _code("weapon_categories.code")
    tool_category_code: Mapped[str | None]   = _code("tool_categories.code")
    spell_list_from_choice_id: Mapped[uuid.UUID | None] = _entity("feature_choices.id")
    swap_rule_code: Mapped[str | None]       = _code("choice_swap_rules.code")

    pool_type: Mapped[ChoicePoolType]              = relationship(lazy="joined")
    feat_category: Mapped[FeatCategory | None]     = relationship(lazy="joined")
    spell_list: Mapped[SpellList | None]           = relationship(lazy="joined")
    weapon_category: Mapped[WeaponCategory | None] = relationship(lazy="joined")
    tool_category: Mapped[ToolCategory | None]     = relationship(lazy="joined")
    swap_rule: Mapped[ChoiceSwapRule | None]       = relationship(lazy="joined")
    options: Mapped[list["FeatureChoiceOption"]]   = relationship(passive_deletes=True)

    @property
    def pool_type_name(self) -> str | None:
        return _name_of(self.pool_type)

    @property
    def feat_category_name(self) -> str | None:
        return _name_of(self.feat_category)

    @property
    def spell_list_name(self) -> str | None:
        return _name_of(self.spell_list)

    @property
    def weapon_category_name(self) -> str | None:
        return _name_of(self.weapon_category)

    @property
    def tool_category_name(self) -> str | None:
        return _name_of(self.tool_category)

    @property
    def swap_rule_name(self) -> str | None:
        return _name_of(self.swap_rule)


class FeatureChoiceOption(Base):
    """One explicit option of a choice: exactly one typed target, never repeated."""

    __tablename__ = "feature_choice_options"
    __table_args__ = (
        CheckConstraint(
            f"num_nonnulls({', '.join(OPTION_TARGET_COLUMNS)}) = 1", name="ck_feature_choice_options_single_target"
        ),
        UniqueConstraint(
            "choice_id", *OPTION_TARGET_COLUMNS, name="uq_feature_choice_options_target",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    choice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_choices.id", ondelete="CASCADE"), nullable=False
    )
    feat_id: Mapped[uuid.UUID | None]    = _entity("feat_definitions.id")
    spell_id: Mapped[uuid.UUID | None]   = _entity("spell_definitions.id")
    skill_code: Mapped[str | None]       = _code("skills.code")
    tool_type_code: Mapped[str | None]   = _code("tool_types.code")
    ability_code: Mapped[str | None]     = _code("ability_scores.code")
    item_id: Mapped[uuid.UUID | None]    = _entity("item_definitions.id")
    spell_list_code: Mapped[str | None]  = _code("spell_lists.code")
    feature_id: Mapped[uuid.UUID | None] = _entity("feature_definitions.id")

    skill: Mapped[Skill | None]          = relationship(lazy="joined")
    tool_type: Mapped[ToolType | None]   = relationship(lazy="joined")
    ability: Mapped[Ability | None]      = relationship(lazy="joined")
    spell_list: Mapped[SpellList | None] = relationship(lazy="joined")
    feat: Mapped["FeatDefinition | None"]   = relationship(lazy="selectin")  # noqa: F821
    spell: Mapped["SpellDefinition | None"] = relationship(lazy="selectin")  # noqa: F821
    item: Mapped["ItemDefinition | None"]   = relationship(lazy="selectin")  # noqa: F821
    feature: Mapped[FeatureDefinition | None] = relationship(lazy="selectin")

    @property
    def target_name(self) -> str | None:
        for relation in (self.feat, self.spell, self.skill, self.tool_type, self.ability, self.item,
                         self.spell_list, self.feature):
            if relation is not None:
                return relation.name
        return None

    @property
    def sort_key(self) -> tuple:
        """Canonical order of the options: by target (codes, then ids)."""
        return tuple(str(getattr(self, column) or "") for column in OPTION_TARGET_COLUMNS)


class FeatureResource(Base):
    """Uses of a feature shown on the sheet (`name`): `value` and/or
    `basis * value_multiplier`, at least `min_value`. Recovered by its recharges."""

    __tablename__ = "feature_resources"
    __table_args__ = (
        CheckConstraint("value IS NOT NULL OR value_basis_code IS NOT NULL", name="ck_feature_resources_has_uses"),
        CheckConstraint(
            "value_basis_ability_code IS NULL OR value_basis_code IS NOT NULL",
            name="ck_feature_resources_basis_ability",
        ),
        UniqueConstraint("feature_id", "sort_order", name="uq_feature_resources_sort_order"),
    )

    id: Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_definitions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int]       = mapped_column(Integer, nullable=False)
    name: Mapped[str]             = mapped_column(String(100), nullable=False)
    value: Mapped[int | None]     = mapped_column(Integer)
    value_basis_code: Mapped[str | None]         = _code("value_bases.code")
    value_basis_ability_code: Mapped[str | None] = _code("ability_scores.code")
    value_multiplier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_value: Mapped[int | None] = mapped_column(Integer)

    value_basis: Mapped[ValueBasis | None] = relationship(lazy="joined")
    recharges: Mapped[list["FeatureResourceRecharge"]] = relationship(
        passive_deletes=True, order_by="FeatureResourceRecharge.recharge_type_code",
    )
    scaling: Mapped[list["FeatureScaling"]] = relationship(
        foreign_keys="FeatureScaling.resource_id", passive_deletes=True, order_by="FeatureScaling.level",
    )

    @property
    def value_basis_name(self) -> str | None:
        return _name_of(self.value_basis)


class FeatureResourceRecharge(Base):
    """How a resource is recovered: `recovers` uses (NULL = all) on `recharge_type_code`.
    Recorded literally as the SRD writes it (the "short rest is part of a long rest" rule
    belongs to the engine)."""

    __tablename__ = "feature_resource_recharges"
    __table_args__ = (
        CheckConstraint("recovers >= 1", name="ck_feature_resource_recharges_recovers"),
        UniqueConstraint("resource_id", "recharge_type_code", name="uq_feature_resource_recharges_type"),
    )

    id: Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_resources.id", ondelete="CASCADE"), nullable=False
    )
    recharge_type_code: Mapped[str] = _code("recharge_types.code", nullable=False)
    recovers: Mapped[int | None]    = mapped_column(Integer)

    recharge_type: Mapped["RechargeType"] = relationship(lazy="joined")

    @property
    def recharge_type_name(self) -> str | None:
        return _name_of(self.recharge_type)


class FeatureScaling(Base):
    """The value of one target (effect, choice or resource) from `level` on, until the
    next row. The level is the class level for class/subclass features and the character
    level for feats (derived from the owner)."""

    __tablename__ = "feature_scaling"
    __table_args__ = (
        CheckConstraint("num_nonnulls(effect_id, choice_id, resource_id) = 1", name="ck_feature_scaling_single_target"),
        CheckConstraint("level BETWEEN 1 AND 20", name="ck_feature_scaling_level"),
        CheckConstraint("(dice_count IS NULL) = (die_size IS NULL)", name="ck_feature_scaling_dice_pair"),
        CheckConstraint(_DIE_SIZE_CHECK, name="ck_feature_scaling_die_size"),
        CheckConstraint("dice_count >= 1", name="ck_feature_scaling_dice_count"),
        CheckConstraint("value IS NOT NULL OR dice_count IS NOT NULL", name="ck_feature_scaling_has_value"),
        UniqueConstraint(
            "effect_id", "choice_id", "resource_id", "level", name="uq_feature_scaling_level",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effect_id: Mapped[uuid.UUID | None]   = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_effects.id", ondelete="CASCADE"), nullable=True
    )
    choice_id: Mapped[uuid.UUID | None]   = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_choices.id", ondelete="CASCADE"), nullable=True
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_resources.id", ondelete="CASCADE"), nullable=True
    )
    level: Mapped[int]              = mapped_column(Integer, nullable=False)
    value: Mapped[int | None]       = mapped_column(Integer)
    dice_count: Mapped[int | None]  = mapped_column(Integer)
    die_size: Mapped[int | None]    = mapped_column(Integer)


FeatureDefinition.resources = relationship(
    FeatureResource, passive_deletes=True, order_by=FeatureResource.sort_order,
)
FeatureEffect.scaling = relationship(
    FeatureScaling, foreign_keys=FeatureScaling.effect_id, passive_deletes=True, order_by=FeatureScaling.level,
)
FeatureChoice.scaling = relationship(
    FeatureScaling, foreign_keys=FeatureScaling.choice_id, passive_deletes=True, order_by=FeatureScaling.level,
)
