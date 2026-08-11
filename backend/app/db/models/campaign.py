import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]               = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    invite_code: Mapped[str]        = mapped_column(String(12), unique=True, nullable=False, index=True) #TODO: Deveria ser temporário, expirar depois de um tempo e gerar outro
    is_active: Mapped[bool]         = mapped_column(Boolean, default=True)
    settings: Mapped[dict]          = mapped_column(JSONB, nullable=False, default=dict) #TODO: Criar tabela/schema de settings para validar os campos
    created_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["CampaignMember"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    characters: Mapped[list["Character"]]   = relationship(back_populates="campaign")  # noqa: F821
    creator: Mapped["User"]                 = relationship(foreign_keys=[created_by])  # noqa: F821

    @property
    def created_by_name(self) -> str | None:
        return self.creator.username if self.creator else None


class CampaignMember(Base):
    __tablename__ = "campaign_members"

    id: Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    # "dm" | "player"
    role: Mapped[str]              = mapped_column(String(10), nullable=False, default="player")
    joined_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped["Campaign"]   = relationship(back_populates="members")
    user: Mapped["User"]           = relationship(back_populates="campaign_memberships")  # noqa: F821

    @property
    def user_name(self) -> str | None:
        return self.user.username if self.user else None

    @property
    def campaign_name(self) -> str | None:
        return self.campaign.name if self.campaign else None
