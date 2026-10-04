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
    ArmorCategory,
    Language,
    Skill,
    ToolCategory,
    ToolType,
    WeaponCategory,
    WeaponProperty,
)


def _code_fk(target: str) -> ForeignKey:
    return ForeignKey(target, ondelete="RESTRICT")


class_primary_abilities = Table(
    "class_primary_abilities",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("ability_code", String(CODE_LENGTH), _code_fk("ability_scores.code"), primary_key=True),
)

spell_class_lists = Table(
    "spell_class_lists",
    Base.metadata,
    Column("spell_id", UUID(as_uuid=True), ForeignKey("spell_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
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


class FeatureGrant(Base):
    """
    Unidade atômica universal. Toda fonte (nível de classe, espécie, antecedente,
    feito, item mágico) emite N dessas. O motor lê effect_type + effect_data e 
    aplica o resultado a um personagem.
    """
    __tablename__ = "feature_grants"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str]        = mapped_column(String(30), nullable=False, index=True)
    source_id: Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    effect_type: Mapped[str]        = mapped_column(String(30), nullable=False)
    effect_data: Mapped[dict]       = mapped_column(JSONB, nullable=False)
    level_requirement: Mapped[int]  = mapped_column(Integer, nullable=False, default=1)
    is_optional: Mapped[bool]       = mapped_column(Boolean, default=False)
    sort_order: Mapped[int]         = mapped_column(Integer, default=0)


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
        secondary=class_primary_abilities, lazy="selectin"
    )
    proficiency_grants: Mapped[list[ProficiencyGrant]] = relationship(
        secondary=class_proficiency_grants, lazy="selectin"
    )
    skills: Mapped[list[Skill]] = relationship(
        secondary=class_skills, lazy="selectin"
    )
    subclasses: Mapped[list["SubclassDefinition"]] = relationship(back_populates="class_def")
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
    __tablename__ = "feat_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # "origin" | "general" | "fighting_style" | "epic_boon"
    category: Mapped[str]           = mapped_column(String(20), nullable=False)
    level_prerequisite: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prerequisite_description: Mapped[str | None] = mapped_column(Text)
    repeatable: Mapped[bool]        = mapped_column(Boolean, default=False)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpellDefinition(Base):
    __tablename__ = "spell_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), unique=True, nullable=False)
    level: Mapped[int]              = mapped_column(Integer, nullable=False)  # 0 = cantrip
    school: Mapped[str]             = mapped_column(String(20), nullable=False)
    casting_time: Mapped[str]       = mapped_column(String(50), nullable=False)
    range: Mapped[str]              = mapped_column(String(50), nullable=False)
    components: Mapped[list]        = mapped_column(JSONB, nullable=False, default=list)
    material_component: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[str]           = mapped_column(String(50), nullable=False)
    concentration: Mapped[bool]     = mapped_column(Boolean, default=False)
    ritual: Mapped[bool]            = mapped_column(Boolean, default=False)
    description: Mapped[str]        = mapped_column(Text, nullable=False)
    higher_levels: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    class_list: Mapped[list["ClassDefinition"]] = relationship(
        secondary=spell_class_lists, lazy="selectin"
    )


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
