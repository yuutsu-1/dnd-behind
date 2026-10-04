"""1:1 tables per item type (`item_definitions` is the common base) plus weapon
properties and pack contents.

Coherence between `item_definitions.item_type_code` and these tables (a `weapon` has
exactly one `weapons` row, a `pack` at least one `item_contents` row, ...) is enforced
by the application (app/services/items.py), not by the database."""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.reference import CODE_LENGTH

DIE_SIZES = (4, 6, 8, 10, 12, 20)
_DIE_SIZES_SQL = ", ".join(str(size) for size in DIE_SIZES)


def _owner_fk(target: str = "item_definitions.id") -> ForeignKey:
    """FK to the row that owns the sub-row: deleting the owner deletes it."""
    return ForeignKey(target, ondelete="CASCADE")


def _restrict_fk(target: str) -> ForeignKey:
    return ForeignKey(target, ondelete="RESTRICT")


class Weapon(Base):
    """Dice are both NULL or both set; without dice the damage is just `damage_flat`
    (Blowgun: "1 Piercing")."""

    __tablename__ = "weapons"
    __table_args__ = (
        CheckConstraint(
            "(damage_dice_count IS NULL) = (damage_die_size IS NULL)", name="ck_weapons_damage_dice_pair"
        ),
        CheckConstraint(
            "damage_dice_count IS NOT NULL OR damage_flat >= 1", name="ck_weapons_damage_flat_without_dice"
        ),
        CheckConstraint("damage_dice_count >= 1", name="ck_weapons_damage_dice_count"),
        CheckConstraint(f"damage_die_size IN ({_DIE_SIZES_SQL})", name="ck_weapons_damage_die_size"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), _owner_fk(), primary_key=True)
    category_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), _restrict_fk("weapon_categories.code"), nullable=False
    )
    is_ranged: Mapped[bool]                = mapped_column(Boolean, nullable=False)
    damage_dice_count: Mapped[int | None]  = mapped_column(Integer)
    damage_die_size: Mapped[int | None]    = mapped_column(Integer)
    damage_flat: Mapped[int]               = mapped_column(Integer, nullable=False, default=0)
    damage_type_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), _restrict_fk("damage_types.code"), nullable=False
    )
    mastery_code: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), _restrict_fk("weapon_masteries.code"), nullable=True
    )

    properties: Mapped[list["WeaponPropertyLink"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="WeaponPropertyLink.property_code",
    )


class WeaponPropertyLink(Base):
    """One property of a weapon, holding only that property's parameter: `range` ->
    distances, `versatile` -> die size, `ammunition` -> the ammunition item; any other
    property has every parameter NULL."""

    __tablename__ = "weapon_property_links"
    __table_args__ = (
        CheckConstraint("range_normal_ft > 0", name="ck_weapon_property_links_range_normal"),
        CheckConstraint("range_long_ft >= range_normal_ft", name="ck_weapon_property_links_range_long"),
        CheckConstraint(
            f"versatile_die_size IN ({_DIE_SIZES_SQL})", name="ck_weapon_property_links_versatile_die_size"
        ),
    )

    weapon_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _owner_fk("weapons.item_id"), primary_key=True
    )
    property_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), _restrict_fk("weapon_properties.code"), primary_key=True
    )
    range_normal_ft: Mapped[int | None]    = mapped_column(Integer)
    range_long_ft: Mapped[int | None]      = mapped_column(Integer)
    versatile_die_size: Mapped[int | None] = mapped_column(Integer)
    ammunition_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), _restrict_fk("item_definitions.id"), nullable=True
    )

    weapon_property: Mapped["WeaponProperty"] = relationship(lazy="joined")  # noqa: F821
    ammunition_item: Mapped["ItemDefinition | None"] = relationship(lazy="joined")  # noqa: F821

    @property
    def code(self) -> str:
        return self.property_code

    @property
    def name(self) -> str | None:
        return self.weapon_property.name if self.weapon_property else None

    @property
    def ammunition_item_name(self) -> str | None:
        return self.ammunition_item.name if self.ammunition_item else None


class Armor(Base):
    """For a shield (`category_code="shield"`), `base_ac` is the bonus it adds to AC
    (+2 in the SRD), not a base AC."""

    __tablename__ = "armors"
    __table_args__ = (
        CheckConstraint("base_ac >= 0", name="ck_armors_base_ac"),
        CheckConstraint("max_dex_modifier >= 0", name="ck_armors_max_dex_modifier"),
        CheckConstraint("strength_requirement >= 1", name="ck_armors_strength_requirement"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), _owner_fk(), primary_key=True)
    category_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), _restrict_fk("armor_categories.code"), nullable=False
    )
    base_ac: Mapped[int]                     = mapped_column(Integer, nullable=False)
    adds_dex_modifier: Mapped[bool]          = mapped_column(Boolean, nullable=False)
    max_dex_modifier: Mapped[int | None]     = mapped_column(Integer)
    strength_requirement: Mapped[int | None] = mapped_column(Integer)
    stealth_disadvantage: Mapped[bool]       = mapped_column(Boolean, nullable=False)


class Tool(Base):
    """The physical tool item. Category and ability live only in `tool_types`."""

    __tablename__ = "tools"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), _owner_fk(), primary_key=True)
    tool_type_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), _restrict_fk("tool_types.code"), nullable=False
    )

    tool_type: Mapped["ToolType"] = relationship(lazy="joined")  # noqa: F821

    @property
    def tool_type_name(self) -> str | None:
        return self.tool_type.name if self.tool_type else None

    @property
    def category_code(self) -> str | None:
        return self.tool_type.category_code if self.tool_type else None

    @property
    def ability_code(self) -> str | None:
        return self.tool_type.ability_code if self.tool_type else None


class Container(Base):
    """Only capacity in pounds is modeled (volume/count capacities are not)."""

    __tablename__ = "containers"
    __table_args__ = (
        CheckConstraint("capacity_weight_lb > 0", name="ck_containers_capacity_weight_lb"),
    )

    item_id: Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), _owner_fk(), primary_key=True)
    capacity_weight_lb: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)


class ItemContent(Base):
    """`quantity` units of `item_id` inside the pack `pack_item_id`. Deleting the pack
    removes its contents; an item used as content of a pack cannot be deleted."""

    __tablename__ = "item_contents"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_item_contents_quantity"),
        CheckConstraint("pack_item_id <> item_id", name="ck_item_contents_not_self"),
    )

    pack_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), _owner_fk(), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _restrict_fk("item_definitions.id"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    item: Mapped["ItemDefinition"] = relationship(foreign_keys=[item_id], lazy="joined")  # noqa: F821

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None
