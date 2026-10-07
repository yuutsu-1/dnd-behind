import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String, Table, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.reference import (
    CODE_LENGTH,
    Ability,
    AreaShape,
    ArmorCategory,
    CastingTime,
    FeatCategory,
    Language,
    Skill,
    SpellList,
    SpellSchool,
    ToolCategory,
    ToolType,
    WeaponCategory,
    WeaponProperty,
)
from app.db.models.features import FeatPrerequisite, FeatureDefinition
from app.db.models.spells import SpellMaterial, spell_list_spells


def _code_fk(target: str) -> ForeignKey:
    return ForeignKey(target, ondelete="RESTRICT")


def _features():
    """Features of an owner (the FK cascades in the database). Loaded explicitly by the
    services (app/services/features.py), in level, sort order, name, id order."""
    return relationship(
        FeatureDefinition, viewonly=True,
        order_by=(FeatureDefinition.level.asc().nulls_first(), FeatureDefinition.sort_order,
                  FeatureDefinition.name, FeatureDefinition.id),
    )


class_primary_abilities = Table(
    "class_primary_abilities",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("ability_code", String(CODE_LENGTH), _code_fk("ability_scores.code"), primary_key=True),
)

class_skills = Table(
    "class_skills",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_code", String(CODE_LENGTH), _code_fk("skills.code"), primary_key=True),
)

background_ability_scores = Table(
    "background_ability_scores",
    Base.metadata,
    Column("background_id", UUID(as_uuid=True), ForeignKey("background_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("ability_code", String(CODE_LENGTH), _code_fk("ability_scores.code"), primary_key=True),
)


# kind -> (target column, relationship holding the target row). `required_weapon_property_code`
# is a modifier of `weapon_category`, not a target of its own.
GRANT_TARGETS: dict[str, tuple[str, str]] = {
    "weapon_category": ("weapon_category_code", "weapon_category"),
    "armor_category": ("armor_category_code", "armor_category"),
    "tool": ("tool_type_code", "tool_type"),
    "tool_category": ("tool_category_code", "tool_category"),
    "skill": ("skill_code", "skill"),
    "saving_throw": ("saving_throw_ability_code", "saving_throw_ability"),
    "language": ("language_code", "language"),
}
GRANT_TARGET_COLUMNS: tuple[str, ...] = tuple(column for column, _ in GRANT_TARGETS.values())
# Every column that identifies a grant (the unique key).
GRANT_KEY_COLUMNS: tuple[str, ...] = (*GRANT_TARGET_COLUMNS, "required_weapon_property_code")


def _grant_target(target: str):
    return mapped_column(String(CODE_LENGTH), _code_fk(target), nullable=True)


class ProficiencyGrant(Base):
    """One reusable proficiency: exactly one target column is filled, and the same
    target is always the same row (UNIQUE NULLS NOT DISTINCT). Weapon/armor categories
    mean every weapon/armor of that category (filtered by `required_weapon_property_code`
    if set); `tool_category` means "choose one tool of the category"; the rest are fixed.
    Grants are shared by classes and backgrounds and are never deleted when orphaned."""

    __tablename__ = "proficiency_grants"
    __table_args__ = (
        CheckConstraint(
            f"num_nonnulls({', '.join(GRANT_TARGET_COLUMNS)}) = 1",
            name="ck_proficiency_grants_single_target",
        ),
        CheckConstraint(
            "required_weapon_property_code IS NULL OR weapon_category_code IS NOT NULL",
            name="ck_proficiency_grants_required_property",
        ),
        UniqueConstraint(
            *GRANT_KEY_COLUMNS, name="uq_proficiency_grants_target", postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    weapon_category_code: Mapped[str | None]          = _grant_target("weapon_categories.code")
    required_weapon_property_code: Mapped[str | None] = _grant_target("weapon_properties.code")
    armor_category_code: Mapped[str | None]           = _grant_target("armor_categories.code")
    tool_type_code: Mapped[str | None]                = _grant_target("tool_types.code")
    tool_category_code: Mapped[str | None]            = _grant_target("tool_categories.code")
    skill_code: Mapped[str | None]                    = _grant_target("skills.code")
    saving_throw_ability_code: Mapped[str | None]     = _grant_target("ability_scores.code")
    language_code: Mapped[str | None]                 = _grant_target("languages.code")

    # Loaded with the grant (one query with outer joins), so names never cost extra queries.
    weapon_category: Mapped[WeaponCategory | None]          = relationship(lazy="joined")
    required_weapon_property: Mapped[WeaponProperty | None] = relationship(lazy="joined")
    armor_category: Mapped[ArmorCategory | None]            = relationship(lazy="joined")
    tool_type: Mapped[ToolType | None]                      = relationship(lazy="joined")
    tool_category: Mapped[ToolCategory | None]              = relationship(lazy="joined")
    skill: Mapped[Skill | None]                             = relationship(lazy="joined")
    saving_throw_ability: Mapped[Ability | None]            = relationship(lazy="joined")
    language: Mapped[Language | None]                       = relationship(lazy="joined")

    @property
    def kind(self) -> str | None:
        for kind, (column, _) in GRANT_TARGETS.items():
            if getattr(self, column) is not None:
                return kind
        return None

    @property
    def target_code(self) -> str | None:
        kind = self.kind
        return getattr(self, GRANT_TARGETS[kind][0]) if kind else None

    @property
    def target_name(self) -> str | None:
        kind = self.kind
        target = getattr(self, GRANT_TARGETS[kind][1]) if kind else None
        return target.name if target is not None else None

    @property
    def required_weapon_property_name(self) -> str | None:
        prop = self.required_weapon_property
        return prop.name if prop is not None else None

    @property
    def sort_key(self) -> tuple:
        """Canonical order of grants: kind, target code, required weapon property (none first), id."""
        required = self.required_weapon_property_code
        return (self.kind or "", self.target_code or "", required is not None, required or "", str(self.id))


class_proficiency_grants = Table(
    "class_proficiency_grants",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("grant_id", UUID(as_uuid=True), _code_fk("proficiency_grants.id"), primary_key=True),
)

background_proficiency_grants = Table(
    "background_proficiency_grants",
    Base.metadata,
    Column(
        "background_id", UUID(as_uuid=True), ForeignKey("background_definitions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("grant_id", UUID(as_uuid=True), _code_fk("proficiency_grants.id"), primary_key=True),
)


class SpeciesDefinition(Base):
    __tablename__ = "species_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    creature_type: Mapped[str]      = mapped_column(String(30), nullable=False)
    size_code: Mapped[str]          = mapped_column(
        String(CODE_LENGTH), ForeignKey("sizes.code", ondelete="RESTRICT"), nullable=False, default="medium"
    )
    base_speed: Mapped[int]         = mapped_column(Integer, nullable=False, default=30)
    special_traits: Mapped[list]    = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClassDefinition(Base):
    __tablename__ = "class_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    hit_die: Mapped[int]            = mapped_column(Integer, nullable=False)
    skill_choices: Mapped[int]      = mapped_column(Integer, nullable=False, default=2)
    subclass_level: Mapped[int]     = mapped_column(Integer, nullable=False, default=3)
    spell_ability: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), ForeignKey("ability_scores.code", ondelete="RESTRICT")
    )
    spellcasting_type: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    primary_ability: Mapped[list[Ability]] = relationship(
        secondary=class_primary_abilities, lazy="selectin", order_by=Ability.code
    )
    proficiency_grants: Mapped[list[ProficiencyGrant]] = relationship(
        secondary=class_proficiency_grants, lazy="selectin"
    )
    skills: Mapped[list[Skill]] = relationship(
        secondary=class_skills, lazy="selectin", order_by=Skill.code
    )
    subclasses: Mapped[list["SubclassDefinition"]] = relationship(back_populates="class_def")
    features: Mapped[list["FeatureDefinition"]] = _features()
    initial_equipment: Mapped[list["ClassInitialEquipment"]] = relationship(
        back_populates="class_def", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def saving_throw_proficiencies(self) -> list[str]:
        """Codes of the `saving_throw` grants, sorted."""
        return sorted(
            g.saving_throw_ability_code for g in self.proficiency_grants if g.saving_throw_ability_code
        )


class SubclassDefinition(Base):
    __tablename__ = "subclass_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("class_definitions.id"), nullable=False)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    class_def: Mapped["ClassDefinition"] = relationship(back_populates="subclasses")
    features: Mapped[list["FeatureDefinition"]] = _features()

    @property
    def class_name(self) -> str | None:
        return self.class_def.name if self.class_def else None


class BackgroundDefinition(Base):
    __tablename__ = "background_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    feat_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("feat_definitions.id"), nullable=False)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    ability_scores: Mapped[list[Ability]] = relationship(
        secondary=background_ability_scores, lazy="selectin"
    )
    feat: Mapped["FeatDefinition"] = relationship(lazy="selectin")
    proficiency_grants: Mapped[list[ProficiencyGrant]] = relationship(
        secondary=background_proficiency_grants, lazy="selectin"
    )
    initial_equipment: Mapped[list["BackgroundInitialEquipment"]] = relationship(
        back_populates="background", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def feat_name(self) -> str | None:
        return self.feat.name if self.feat else None

    @property
    def skills(self) -> list[Skill]:
        """Skills of the `skill` grants, sorted by name (the background's fixed skills)."""
        skills = [g.skill for g in self.proficiency_grants if g.skill_code is not None]
        return sorted(skills, key=lambda skill: (skill.name, skill.code))


class FeatDefinition(Base):
    """A feat. `category_code` is a `feat_categories` code; the prerequisites and the
    features are child rows loaded explicitly (app/services/feats.py)."""

    __tablename__ = "feat_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_code: Mapped[str]      = mapped_column(
        String(CODE_LENGTH), _code_fk("feat_categories.code"), nullable=False
    )
    repeatable: Mapped[bool]        = mapped_column(Boolean, default=False)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped[FeatCategory] = relationship(lazy="joined")
    prerequisites: Mapped[list["FeatPrerequisite"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True,
    )
    features: Mapped[list["FeatureDefinition"]] = _features()

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None


class SpellDefinition(Base):
    """A spell: one fact per column. `range`, `duration` and `area` are display text;
    `area_shape_code` (the icon of the area) goes together with `area`. Damage, saves
    and attacks stay in the text (`description`, `higher_levels`, `cantrip_upgrade`)."""

    __tablename__ = "spell_definitions"
    __table_args__ = (
        CheckConstraint("level BETWEEN 0 AND 9", name="ck_spell_definitions_level"),
        CheckConstraint("has_verbal OR has_somatic OR has_material", name="ck_spell_definitions_has_component"),
        CheckConstraint("(area IS NULL) = (area_shape_code IS NULL)", name="ck_spell_definitions_area_pair"),
        CheckConstraint("cantrip_upgrade IS NULL OR level = 0", name="ck_spell_definitions_cantrip_upgrade"),
        CheckConstraint("higher_levels IS NULL OR level >= 1", name="ck_spell_definitions_higher_levels"),
    )

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    level: Mapped[int]              = mapped_column(Integer, nullable=False)  # 0 = cantrip
    school_code: Mapped[str]        = mapped_column(String(CODE_LENGTH), _code_fk("spell_schools.code"), nullable=False)
    has_verbal: Mapped[bool]        = mapped_column(Boolean, nullable=False, default=False)
    has_somatic: Mapped[bool]       = mapped_column(Boolean, nullable=False, default=False)
    has_material: Mapped[bool]      = mapped_column(Boolean, nullable=False, default=False)
    casting_time_code: Mapped[str]  = mapped_column(
        String(CODE_LENGTH), _code_fk("casting_times.code"), nullable=False
    )
    ritual: Mapped[bool]            = mapped_column(Boolean, nullable=False, default=False)
    concentration: Mapped[bool]     = mapped_column(Boolean, nullable=False, default=False)
    range: Mapped[str]              = mapped_column(Text, nullable=False)
    duration: Mapped[str]           = mapped_column(Text, nullable=False)
    area: Mapped[str | None]        = mapped_column(Text)
    area_shape_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), _code_fk("area_shapes.code"))
    description: Mapped[str]        = mapped_column(Text, nullable=False)
    higher_levels: Mapped[str | None]   = mapped_column(Text)
    cantrip_upgrade: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Names come joined with the spell; materials and lists are loaded explicitly
    # (app/services/spells.py), never implicitly.
    school: Mapped[SpellSchool]             = relationship(lazy="joined")
    casting_time: Mapped[CastingTime]       = relationship(lazy="joined")
    area_shape: Mapped[AreaShape | None]    = relationship(lazy="joined")
    materials: Mapped[list[SpellMaterial]]  = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by=SpellMaterial.sort_order,
    )
    spell_lists: Mapped[list[SpellList]]    = relationship(
        secondary=spell_list_spells, passive_deletes=True, order_by=SpellList.code,
    )

    @property
    def school_name(self) -> str | None:
        return self.school.name if self.school else None

    @property
    def casting_time_name(self) -> str | None:
        return self.casting_time.name if self.casting_time else None

    @property
    def area_shape_name(self) -> str | None:
        return self.area_shape.name if self.area_shape else None


def _sub_row():
    """1:1 sub-row owned by the item (the FK cascades in the database)."""
    return relationship(uselist=False, cascade="all, delete-orphan", passive_deletes=True)


class ItemDefinition(Base):
    """Common base of every item. Values are per unit (ammunition: pack price/weight
    divided by the pack size); `cost_gp` is in gold pieces. Type-specific data lives in
    the 1:1 tables of app/db/models/items.py."""

    __tablename__ = "item_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    item_type_code: Mapped[str]     = mapped_column(
        String(CODE_LENGTH), ForeignKey("item_types.code", ondelete="RESTRICT"), nullable=False
    )
    cost_gp: Mapped[Decimal | None]   = mapped_column(Numeric(12, 4))
    weight_lb: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Sub-rows are loaded explicitly (app/services/items.py), never implicitly.
    weapon: Mapped["Weapon | None"]       = _sub_row()
    armor: Mapped["Armor | None"]         = _sub_row()
    tool: Mapped["Tool | None"]           = _sub_row()
    container: Mapped["Container | None"] = _sub_row()
    contents: Mapped[list["ItemContent"]] = relationship(
        foreign_keys="ItemContent.pack_item_id", cascade="all, delete-orphan", passive_deletes=True,
        order_by="ItemContent.item_id",
    )


class ClassInitialEquipment(Base):
    __tablename__ = "class_initial_equipment"
    __table_args__ = (CheckConstraint("quantity >= 1", name="ck_class_initial_equipment_quantity_positive"),)

    id: Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("item_definitions.id"), nullable=False)
    option: Mapped[str]         = mapped_column(String(10), nullable=False)
    quantity: Mapped[int]       = mapped_column(Integer, nullable=False, default=1)

    class_def: Mapped["ClassDefinition"] = relationship(back_populates="initial_equipment")
    item: Mapped["ItemDefinition"]       = relationship(lazy="selectin")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None


class BackgroundInitialEquipment(Base):
    __tablename__ = "background_initial_equipment"
    __table_args__ = (CheckConstraint("quantity >= 1", name="ck_background_initial_equipment_quantity_positive"),)

    id: Mapped[uuid.UUID]            = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    background_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("background_definitions.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("item_definitions.id"), nullable=False)
    option: Mapped[str]              = mapped_column(String(10), nullable=False)
    quantity: Mapped[int]            = mapped_column(Integer, nullable=False, default=1)

    background: Mapped["BackgroundDefinition"] = relationship(back_populates="initial_equipment")
    item: Mapped["ItemDefinition"]             = relationship(lazy="selectin")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None
