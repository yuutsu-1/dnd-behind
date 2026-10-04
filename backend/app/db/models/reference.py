"""SRD 2024 reference tables ("lookups") in the common `code` pattern.

Every table here is seeded with the SRD by the initial migration (`source="srd"`,
`is_homebrew=False`, `created_by=NULL`) and accepts homebrew rows created through
`/api/compendium/<resource>`. A homebrew row is visible to its author and, through
`campaign_homebrew_rules`, to the members of the campaigns it is shared with.
"""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.base import Base

CODE_LENGTH = 50


class HomebrewMixin:
    """Provenance columns shared by every reference table."""

    source: Mapped[str]      = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @declared_attr
    def created_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class CodeMixin(HomebrewMixin):
    """`code` PK + display name (not unique) + optional description."""

    code: Mapped[str]               = mapped_column(String(CODE_LENGTH), primary_key=True)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Ability(CodeMixin, Base):
    __tablename__ = "ability_scores"


class Skill(CodeMixin, Base):
    __tablename__ = "skills"

    ability_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), ForeignKey("ability_scores.code", ondelete="RESTRICT"), nullable=False
    )


class DamageType(CodeMixin, Base):
    __tablename__ = "damage_types"


class Condition(CodeMixin, Base):
    __tablename__ = "conditions"


class ConditionImplication(Base):
    """`condition_code` implies `implied_condition_code` (e.g. paralyzed -> incapacitated).
    Outgoing FK cascades with the implying condition; the incoming FK restricts deleting
    a condition that other conditions imply."""

    __tablename__ = "condition_implications"
    __table_args__ = (
        CheckConstraint(
            "condition_code <> implied_condition_code",
            name="ck_condition_implications_not_self",
        ),
    )

    condition_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), ForeignKey("conditions.code", ondelete="CASCADE"), primary_key=True
    )
    implied_condition_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), ForeignKey("conditions.code", ondelete="RESTRICT"), primary_key=True
    )


class CreatureType(CodeMixin, Base):
    __tablename__ = "creature_types"


class Size(CodeMixin, Base):
    __tablename__ = "sizes"
    __table_args__ = (
        CheckConstraint("hit_die > 0", name="ck_sizes_hit_die_positive"),
        CheckConstraint("carry_multiplier > 0", name="ck_sizes_carry_multiplier_positive"),
    )

    hit_die: Mapped[int]              = mapped_column(Integer, nullable=False)
    carry_multiplier: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    sort_order: Mapped[int]           = mapped_column(Integer, nullable=False, unique=True)


class Alignment(CodeMixin, Base):
    __tablename__ = "alignments"


class Language(CodeMixin, Base):
    __tablename__ = "languages"
    __table_args__ = (
        CheckConstraint("rarity IN ('standard', 'rare')", name="ck_languages_rarity"),
    )

    rarity: Mapped[str] = mapped_column(String(10), nullable=False)


class Sense(CodeMixin, Base):
    __tablename__ = "senses"


class MovementMode(CodeMixin, Base):
    __tablename__ = "movement_modes"


class WeaponCategory(CodeMixin, Base):
    __tablename__ = "weapon_categories"


class WeaponProperty(CodeMixin, Base):
    __tablename__ = "weapon_properties"


class WeaponMastery(CodeMixin, Base):
    __tablename__ = "weapon_masteries"


class ArmorCategory(CodeMixin, Base):
    __tablename__ = "armor_categories"


class ToolCategory(CodeMixin, Base):
    __tablename__ = "tool_categories"


class ToolProficiencyOption(CodeMixin, Base):
    """Transitional (until phase 2): tools a class/background can grant proficiency in."""

    __tablename__ = "tool_proficiency_options"


class SpellSchool(CodeMixin, Base):
    __tablename__ = "spell_schools"


class RechargeType(CodeMixin, Base):
    __tablename__ = "recharge_types"


class ActionType(CodeMixin, Base):
    __tablename__ = "action_types"


class FeatCategory(CodeMixin, Base):
    __tablename__ = "feat_categories"


class ChallengeRating(CodeMixin, Base):
    __tablename__ = "challenge_ratings"
    __table_args__ = (
        CheckConstraint("proficiency_bonus >= 0", name="ck_challenge_ratings_proficiency_bonus"),
    )

    numeric_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False, unique=True)
    proficiency_bonus: Mapped[int] = mapped_column(Integer, nullable=False)


class CharacterLevel(HomebrewMixin, Base):
    __tablename__ = "character_levels"
    __table_args__ = (
        CheckConstraint("level >= 1", name="ck_character_levels_level"),
        CheckConstraint("min_xp >= 0", name="ck_character_levels_min_xp"),
        CheckConstraint("proficiency_bonus >= 0", name="ck_character_levels_proficiency_bonus"),
    )

    level: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=False)
    min_xp: Mapped[int]            = mapped_column(Integer, nullable=False)
    proficiency_bonus: Mapped[int] = mapped_column(Integer, nullable=False)


class PointBuyCost(HomebrewMixin, Base):
    __tablename__ = "point_buy_costs"
    __table_args__ = (
        CheckConstraint("cost >= 0", name="ck_point_buy_costs_cost"),
    )

    score: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    cost: Mapped[int]  = mapped_column(Integer, nullable=False)


# The 23 reference models exposed under /api/compendium. `campaign_homebrew_rules`
# only accepts their table names in `resource_table`.
REFERENCE_MODELS: tuple[type[Base], ...] = (
    Ability, Skill, DamageType, Condition, CreatureType, Size,
    Alignment, Language, Sense, MovementMode,
    WeaponCategory, WeaponProperty, WeaponMastery, ArmorCategory, ToolCategory,
    SpellSchool, RechargeType, ActionType,
    CharacterLevel, ChallengeRating, PointBuyCost, FeatCategory, ToolProficiencyOption,
)
REFERENCE_TABLE_NAMES: tuple[str, ...] = tuple(m.__tablename__ for m in REFERENCE_MODELS)

_resource_table_values = ", ".join(f"'{name}'" for name in REFERENCE_TABLE_NAMES)


class CampaignHomebrewRule(Base):
    """Share of one homebrew reference row with one campaign.

    There is deliberately no FK to the shared row (one table serves all reference
    tables): the application deletes the shares when it deletes the row. The FK to
    `campaigns` cascades, so deleting a campaign removes its shares."""

    __tablename__ = "campaign_homebrew_rules"
    __table_args__ = (
        CheckConstraint(
            f"resource_table IN ({_resource_table_values})",
            name="ck_campaign_homebrew_rules_resource_table",
        ),
        Index("ix_campaign_homebrew_rules_campaign_id", "campaign_id"),
    )

    resource_table: Mapped[str]    = mapped_column(String(50), primary_key=True)
    resource_key: Mapped[str]      = mapped_column(String(CODE_LENGTH), primary_key=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
