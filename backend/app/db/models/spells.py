"""Child tables of a spell (`spell_definitions` lives in app/db/models/compendium.py).

`has_material` on the spell is true iff the spell has at least one `spell_materials`
row: that coherence is enforced by the application (app/services/spells.py), not by
the database."""
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.reference import CODE_LENGTH


class SpellMaterial(Base):
    """One material component. `cost_gp` is the minimum cost per unit, in gold (null when
    the SRD gives none); the total is `cost_gp * quantity` (times the targets when
    `per_target`)."""

    __tablename__ = "spell_materials"
    __table_args__ = (
        CheckConstraint("cost_gp >= 0", name="ck_spell_materials_cost_gp"),
        CheckConstraint("quantity >= 1", name="ck_spell_materials_quantity"),
        UniqueConstraint("spell_id", "sort_order", name="uq_spell_materials_sort_order"),
    )

    id: Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spell_id: Mapped[uuid.UUID]   = mapped_column(
        UUID(as_uuid=True), ForeignKey("spell_definitions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int]       = mapped_column(Integer, nullable=False)
    description: Mapped[str]      = mapped_column(Text, nullable=False)
    cost_gp: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    consumed: Mapped[bool]        = mapped_column(nullable=False, default=False)
    per_target: Mapped[bool]      = mapped_column(nullable=False, default=False)
    quantity: Mapped[int]         = mapped_column(Integer, nullable=False, default=1)


spell_list_spells = Table(
    "spell_list_spells",
    Base.metadata,
    Column(
        "spell_list_code", String(CODE_LENGTH), ForeignKey("spell_lists.code", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "spell_id", UUID(as_uuid=True), ForeignKey("spell_definitions.id", ondelete="CASCADE"), primary_key=True,
    ),
)
