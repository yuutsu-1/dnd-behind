import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID]                   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    campaign_id: Mapped[uuid.UUID | None]   = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
  
    name: Mapped[str]                       = mapped_column(String(100), nullable=False)
    experience_points: Mapped[int]          = mapped_column(Integer, nullable=False, default=0)
  
    species_id: Mapped[uuid.UUID | None]    = mapped_column(UUID(as_uuid=True), ForeignKey("species_definitions.id"), nullable=True)
    background_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("background_definitions.id"), nullable=True)

    current_hp: Mapped[int]                 = mapped_column(Integer, nullable=False, default=0)
    max_hp: Mapped[int]                     = mapped_column(Integer, nullable=False, default=0)
    temp_hp: Mapped[int]                    = mapped_column(Integer, nullable=False, default=0)
    death_saves: Mapped[dict]               = mapped_column(JSONB, nullable=False, default=lambda: {"successes": 0, "failures": 0})

    conditions: Mapped[list]                = mapped_column(JSONB, nullable=False, default=list)
    exhaustion_level: Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    inspiration: Mapped[bool]               = mapped_column(Boolean, default=False)
    choices: Mapped[dict]                   = mapped_column(JSONB, nullable=False, default=dict) #TODO: Criar tabela de traços de classes e especies ganhos por nível e se um traço é múltipla escolha então salvarei o traço escolhido em outra tabela de many to one.
    spell_slots_remaining: Mapped[dict]     = mapped_column(JSONB, nullable=False, default=dict)
    appearance: Mapped[dict]                = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None]               = mapped_column(Text)
    custom_data: Mapped[dict]               = mapped_column(JSONB, nullable=False, default=dict) #TODO: Vai virar a tabela de traços de classes e especies

    is_active: Mapped[bool]                 = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]            = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]            = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"]                   = relationship(back_populates="characters")  # noqa: F821
    campaign: Mapped["Campaign"]            = relationship(back_populates="characters")  # noqa: F821
    species: Mapped["SpeciesDefinition"]    = relationship(foreign_keys=[species_id])  # noqa: F821
    background: Mapped["BackgroundDefinition"] = relationship(foreign_keys=[background_id])  # noqa: F821
    classes: Mapped[list["CharacterClass"]] = relationship(back_populates="character", cascade="all, delete-orphan", lazy="selectin")
    ability_scores: Mapped[list["CharacterAbilityScore"]] = relationship(back_populates="character", cascade="all, delete-orphan", lazy="selectin")
    inventory: Mapped[list["CharacterInventory"]] = relationship(back_populates="character", cascade="all, delete-orphan")
    feats: Mapped[list["CharacterFeat"]]    = relationship(back_populates="character", cascade="all, delete-orphan")
    spells: Mapped[list["CharacterSpell"]]  = relationship(back_populates="character", cascade="all, delete-orphan")
    resources: Mapped[list["CharacterResource"]]  = relationship(back_populates="character", cascade="all, delete-orphan")

    @property
    def user_name(self) -> str | None:
        return self.owner.username if self.owner else None

    @property
    def campaign_name(self) -> str | None:
        return self.campaign.name if self.campaign else None

    @property
    def species_name(self) -> str | None:
        return self.species.name if self.species else None

    @property
    def background_name(self) -> str | None:
        return self.background.name if self.background else None

    @property
    def total_level(self) -> int:
        return sum(entry.level for entry in self.classes) if self.classes else 0


class CharacterClass(Base):
    """One entry per class a character has levels in (supports multiclassing)."""
    __tablename__ = "character_classes"
    __table_args__ = (UniqueConstraint("character_id", "class_id"),)

    id: Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"))
    class_id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), ForeignKey("class_definitions.id"), nullable=False)
    level: Mapped[int]                    = mapped_column(Integer, nullable=False, default=1)
    subclass_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subclass_definitions.id"), nullable=True)
    hit_dice_used: Mapped[int]            = mapped_column(Integer, nullable=False, default=0)

    character: Mapped["Character"]          = relationship(back_populates="classes")
    class_: Mapped["ClassDefinition"]       = relationship(foreign_keys=[class_id], lazy="selectin")  # noqa: F821
    subclass: Mapped["SubclassDefinition | None"] = relationship(foreign_keys=[subclass_id], lazy="selectin")  # noqa: F821

    @property
    def class_name(self) -> str | None:
        return self.class_.name if self.class_ else None

    @property
    def subclass_name(self) -> str | None:
        return self.subclass.name if self.subclass else None

    @property
    def hit_die(self) -> int | None:
        return self.class_.hit_die if self.class_ else None

    @property
    def hit_dice_total(self) -> int:
        return self.level

    @property
    def hit_dice_remaining(self) -> int:
        return self.level - self.hit_dice_used


class CharacterAbilityScore(Base):
    """One row per ability score a character has a value for (STR/DEX/CON/INT/WIS/CHA)."""
    __tablename__ = "character_ability_scores"
    __table_args__ = (
        UniqueConstraint("character_id", "ability_score"),
        # D&D 5e/5.5 ability score bounds: 1 is the practical floor (0 has special
        # rules engine-side and isn't a normal assignable value), 30 is the usual
        # hard cap (e.g. Wish/epic boons). Assumption documented for QA/review.
        CheckConstraint("value >= 1 AND value <= 30", name="ck_character_ability_scores_value_bounds"),
    )

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"))
    ability_score: Mapped[str]      = mapped_column(String(3), ForeignKey("ability_score_options.name"), nullable=False)
    value: Mapped[int]              = mapped_column(Integer, nullable=False, default=10)

    character: Mapped["Character"] = relationship(back_populates="ability_scores")


class CharacterInventory(Base):
    __tablename__ = "character_inventory"

    id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"))
    item_id: Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("item_definitions.id"), nullable=False)
    quantity: Mapped[int]              = mapped_column(Integer, nullable=False, default=1)
    equipped: Mapped[bool]             = mapped_column(Boolean, default=False)
    attuned: Mapped[bool]              = mapped_column(Boolean, default=False)
    custom_notes: Mapped[str | None]   = mapped_column(Text)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    added_at: Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())

    character: Mapped["Character"]     = relationship(back_populates="inventory")
    item: Mapped["ItemDefinition"]     = relationship()  # noqa: F821
    added_by_user: Mapped["User"]      = relationship(foreign_keys=[added_by])  # noqa: F821

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def added_by_name(self) -> str | None:
        return self.added_by_user.username if self.added_by_user else None


class CharacterFeat(Base):
    __tablename__ = "character_feats"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"))
    feat_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("feat_definitions.id"), nullable=False)
    source: Mapped[str]             = mapped_column(String(20), nullable=False)     # How the feat was obtained: "background", "asi_replacement", "class_feature", "epic_boon"
    choices: Mapped[dict]           = mapped_column(JSONB, nullable=False, default=dict)
 
    character: Mapped["Character"]  = relationship(back_populates="feats")
    feat: Mapped["FeatDefinition"]  = relationship()  # noqa: F821


class CharacterSpell(Base):
    __tablename__ = "character_spells"

    id: Mapped[uuid.UUID]            = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"))
    spell_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("spell_definitions.id"), nullable=False)
    is_prepared: Mapped[bool]        = mapped_column(Boolean, default=False)
    is_always_prepared: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str]              = mapped_column(String(20), nullable=False, default="class")     # "class" | "feat" | "item" | "species"

    character: Mapped["Character"]   = relationship(back_populates="spells")
    spell: Mapped["SpellDefinition"] = relationship()  # noqa: F821


class CharacterResource(Base):
    """Registro usos do recurso (Rage, Ki Points, Bardic Inspiration, ...)."""
    __tablename__ = "character_resources"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"))
    resource_name: Mapped[str]      = mapped_column(String(50), nullable=False)
    max_uses: Mapped[int]           = mapped_column(Integer, nullable=False)
    remaining_uses: Mapped[int]     = mapped_column(Integer, nullable=False)
    reset_on: Mapped[str]           = mapped_column(String(15), nullable=False, default="long_rest")     # "long_rest" | "short_rest" | "dawn" | "turn"

    character: Mapped["Character"] = relationship(back_populates="resources")


class CharacterSpellSlots(Base):
    """Remaining spell slots per level. Max is computed by the engine from class/level."""
    __tablename__ = "character_spell_slots"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"))
    spell_level: Mapped[int]        = mapped_column(Integer, nullable=False)
    remaining_slots: Mapped[int]    = mapped_column(Integer, nullable=False)

    character: Mapped["Character"]  = relationship()
