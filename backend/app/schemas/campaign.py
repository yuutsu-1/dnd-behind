import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    settings: dict = Field(default_factory=dict)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    settings: dict | None = None
    is_active: bool | None = None


class CampaignOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    invite_code: str
    is_active: bool
    settings: dict
    created_by: uuid.UUID
    created_by_name: str
    created_at: datetime


class MemberOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    campaign_id: uuid.UUID
    campaign_name: str
    role: str
    joined_at: datetime


class JoinRequest(BaseModel):
    invite_code: str
