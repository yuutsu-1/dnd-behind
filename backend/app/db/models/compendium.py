import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum, Float,
    ForeignKey, Integer, String, Table, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import CreatureSize



class AbilityScoreOption(Base):
    __tablename__ = "ability_score_options"
    name: Mapped[str] = mapped_column(String(3), primary_key=True)


class ArmorProficiencyOption(Base):
    __tablename__ = "armor_proficiency_options"
    name: Mapped[str] = mapped_column(String(30), primary_key=True)


class WeaponProficiencyOption(Base):
    __tablename__ = "weapon_proficiency_options"
    name: Mapped[str] = mapped_column(String(50), primary_key=True)


class ToolProficiencyOption(Base):
    __tablename__ = "tool_proficiency_options"
    name: Mapped[str] = mapped_column(String(60), primary_key=True)


# ---------------------------------------------------------------------------


class_primary_abilities = Table(
    "class_primary_abilities",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("ability_score", String(3), ForeignKey("ability_score_options.name"), primary_key=True),
)

class_saving_throws = Table(
    "class_saving_throws",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("ability_score", String(3), ForeignKey("ability_score_options.name"), primary_key=True),
)

class_armor_proficiencies = Table(
    "class_armor_proficiencies",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("armor_proficiency", String(30), ForeignKey("armor_proficiency_options.name"), primary_key=True),
)

class_weapon_proficiencies = Table(
    "class_weapon_proficiencies",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("weapon_proficiency", String(50), ForeignKey("weapon_proficiency_options.name"), primary_key=True),
)

class_tool_proficiencies = Table(
    "class_tool_proficiencies",
    Base.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("tool_proficiency", String(60), ForeignKey("tool_proficiency_options.name"), primary_key=True),
)

spell_class_lists = Table(
    "spell_class_lists",
    Base.metadata,
    Column("spell_id", UUID(as_uuid=True), ForeignKey("spell_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", UUID(as_uuid=True), ForeignKey("class_definitions.id", ondelete="CASCADE"), primary_key=True),
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
    size: Mapped[CreatureSize]      = mapped_column(SAEnum(CreatureSize), nullable=False, default=CreatureSize.medium)
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
    skill_pool: Mapped[list]        = mapped_column(JSONB, nullable=False, default=list)
    subclass_level: Mapped[int]     = mapped_column(Integer, nullable=False, default=3)
    spell_ability: Mapped[str | None] = mapped_column(String(3), foreign_key="ability_score_options.name")
    spellcasting_type: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    primary_ability: Mapped[list[AbilityScoreOption]] = relationship(
        secondary=class_primary_abilities, lazy="selectin"
    )
    saving_throw_proficiencies: Mapped[list[AbilityScoreOption]] = relationship(
        secondary=class_saving_throws, lazy="selectin"
    )
    armor_proficiencies: Mapped[list[ArmorProficiencyOption]] = relationship(
        secondary=class_armor_proficiencies, lazy="selectin"
    )
    weapon_proficiencies: Mapped[list[WeaponProficiencyOption]] = relationship(
        secondary=class_weapon_proficiencies, lazy="selectin"
    )
    tool_proficiencies: Mapped[list[ToolProficiencyOption]] = relationship(
        secondary=class_tool_proficiencies, lazy="selectin"
    )
    subclasses: Mapped[list["SubclassDefinition"]] = relationship(back_populates="class_def")


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


class BackgroundDefinition(Base):
    __tablename__ = "background_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class ItemDefinition(Base):
    __tablename__ = "item_definitions"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    item_type: Mapped[str]          = mapped_column(String(20), nullable=False)
    subtype: Mapped[str | None]     = mapped_column(String(30))
    rarity: Mapped[str]             = mapped_column(String(15), nullable=False, default="common")
    requires_attunement: Mapped[bool] = mapped_column(Boolean, default=False)
    attunement_prerequisite: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float | None]    = mapped_column(Float)
    cost_gp: Mapped[float | None]   = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    properties: Mapped[dict]        = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str]             = mapped_column(String(20), nullable=False, default="srd")
    is_homebrew: Mapped[bool]       = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())
