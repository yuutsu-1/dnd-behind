import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_ABILITY_SCORES_DEFAULT = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID]                   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    campaign_id: Mapped[uuid.UUID | None]   = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
  
    name: Mapped[str]                       = mapped_column(String(100), nullable=False)
    level: Mapped[int]                      = mapped_column(Integer, nullable=False, default=1)
    experience_points: Mapped[int]          = mapped_column(Integer, nullable=False, default=0)
  
    species_id: Mapped[uuid.UUID | None]    = mapped_column(UUID(as_uuid=True), ForeignKey("species_definitions.id"), nullable=True)
    background_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("background_definitions.id"), nullable=True)
    class_id: Mapped[uuid.UUID | None]      = mapped_column(UUID(as_uuid=True), ForeignKey("class_definitions.id"), nullable=True)
    subclass_id: Mapped[uuid.UUID | None]   = mapped_column(UUID(as_uuid=True), ForeignKey("subclass_definitions.id"), nullable=True)
  
    ability_scores: Mapped[dict]            = mapped_column(JSONB, nullable=False, default=lambda: dict(_ABILITY_SCORES_DEFAULT))
  
    current_hp: Mapped[int]                 = mapped_column(Integer, nullable=False, default=0)
    max_hp: Mapped[int]                     = mapped_column(Integer, nullable=False, default=0)
    temp_hp: Mapped[int]                    = mapped_column(Integer, nullable=False, default=0)
    death_saves: Mapped[dict]               = mapped_column(JSONB, nullable=False, default=lambda: {"successes": 0, "failures": 0})

    hit_dice_remaining: Mapped[dict]        = mapped_column(JSONB, nullable=False, default=dict)

    conditions: Mapped[list]                = mapped_column(JSONB, nullable=False, default=list)
    exhaustion_level: Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    inspiration: Mapped[bool]               = mapped_column(Boolean, default=False)
    choices: Mapped[dict]                   = mapped_column(JSONB, nullable=False, default=dict)
    spell_slots_remaining: Mapped[dict]     = mapped_column(JSONB, nullable=False, default=dict)
    appearance: Mapped[dict]                = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None]               = mapped_column(Text)
    custom_data: Mapped[dict]               = mapped_column(JSONB, nullable=False, default=dict)

    is_active: Mapped[bool]                 = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]            = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]            = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"]                   = relationship(back_populates="characters")  # noqa: F821
    campaign: Mapped["Campaign"]            = relationship(back_populates="characters")  # noqa: F821
    inventory: Mapped[list["CharacterInventory"]] = relationship(back_populates="character", cascade="all, delete-orphan")
    feats: Mapped[list["CharacterFeat"]]    = relationship(back_populates="character", cascade="all, delete-orphan")
    spells: Mapped[list["CharacterSpell"]]  = relationship(back_populates="character", cascade="all, delete-orphan")
    resources: Mapped[list["CharacterResource"]]  = relationship(back_populates="character", cascade="all, delete-orphan")


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
    """Tracks current/max uses of named resources (Rage, Ki Points, Bardic Inspiration, ...)."""
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
