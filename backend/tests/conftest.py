import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")

import pytest  # noqa: E402

from app.db.models.campaign import Campaign, CampaignMember  # noqa: E402
from app.db.models.character import Character, CharacterInventory  # noqa: E402
from app.db.models.compendium import (  # noqa: E402
    BackgroundDefinition,
    ClassDefinition,
    ItemDefinition,
    SpeciesDefinition,
    SubclassDefinition,
)
from app.db.models.user import RefreshToken, User  # noqa: E402
from app.enums import CreatureSize  # noqa: E402


class FakeResult:
    def __init__(self, scalar=None, scalars_list=None):
        self._scalar = scalar
        self._scalars_list = scalars_list if scalars_list is not None else []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        mock = MagicMock()
        mock.all.return_value = self._scalars_list
        return mock


def make_result(scalar=None, scalars_list=None) -> FakeResult:
    return FakeResult(scalar=scalar, scalars_list=scalars_list)


class FakeAsyncSession:
    def __init__(self):
        self.execute = AsyncMock(return_value=make_result())
        self.add = MagicMock()
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.flush = AsyncMock()
        self.delete = AsyncMock()


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    return FakeAsyncSession()


def make_user(**overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="user@example.com",
        username="testuser",
        hashed_password="hashed-password",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return User(**defaults)


def make_refresh_token(**overrides) -> RefreshToken:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash="deadbeef",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        revoked=False,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return RefreshToken(**defaults)


def make_campaign(**overrides) -> Campaign:
    defaults = dict(
        id=uuid.uuid4(),
        name="Test Campaign",
        description=None,
        created_by=uuid.uuid4(),
        invite_code="ABCDEF123456",
        is_active=True,
        settings={},
        created_at=datetime.now(timezone.utc),
        creator=make_user(),
    )
    defaults.update(overrides)
    return Campaign(**defaults)


def make_campaign_member(**overrides) -> CampaignMember:
    defaults = dict(
        id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role="player",
        joined_at=datetime.now(timezone.utc),
        # Defaults so `MemberOut.user_name`/`campaign_name` (required fields)
        # validate out of the box; override explicitly in tests that care.
        user=make_user(),
        campaign=make_campaign(),
    )
    defaults.update(overrides)
    return CampaignMember(**defaults)


def make_character(**overrides) -> Character:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        campaign_id=None,
        name="Test Character",
        level=1,
        experience_points=0,
        species_id=None,
        background_id=None,
        class_id=None,
        subclass_id=None,
        ability_scores={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        current_hp=10,
        max_hp=10,
        temp_hp=0,
        death_saves={"successes": 0, "failures": 0},
        hit_dice_remaining={},
        conditions=[],
        exhaustion_level=0,
        inspiration=False,
        choices={},
        spell_slots_remaining={},
        appearance={},
        notes=None,
        custom_data={},
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        # Default relationship so `CharacterOut.user_name` (a required field)
        # validates out of the box; override explicitly in tests that care
        # about this relationship specifically.
        owner=make_user(),
    )
    defaults.update(overrides)
    return Character(**defaults)


def make_species(**overrides) -> SpeciesDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name="Elf",
        description=None,
        creature_type="humanoid",
        size=CreatureSize.medium,
        base_speed=30,
        special_traits=[],
        source="srd",
        is_homebrew=False,
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SpeciesDefinition(**defaults)


def make_background(**overrides) -> BackgroundDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name="Soldier",
        description=None,
        source="srd",
        is_homebrew=False,
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return BackgroundDefinition(**defaults)


def make_class(**overrides) -> ClassDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name="Fighter",
        description=None,
        hit_die=10,
        skill_choices=2,
        skill_pool=[],
        subclass_level=3,
        spell_ability=None,
        spellcasting_type=None,
        source="srd",
        is_homebrew=False,
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return ClassDefinition(**defaults)


def make_subclass(**overrides) -> SubclassDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        name="Champion",
        description=None,
        source="srd",
        is_homebrew=False,
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SubclassDefinition(**defaults)


def make_item(**overrides) -> ItemDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name="Longsword",
        item_type="weapon",
        subtype=None,
        rarity="common",
        requires_attunement=False,
        attunement_prerequisite=None,
        weight=3.0,
        cost_gp=15.0,
        description=None,
        properties={},
        source="srd",
        is_homebrew=False,
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return ItemDefinition(**defaults)


def make_inventory_entry(**overrides) -> CharacterInventory:
    defaults = dict(
        id=uuid.uuid4(),
        character_id=uuid.uuid4(),
        item_id=uuid.uuid4(),
        quantity=1,
        equipped=False,
        attuned=False,
        custom_notes=None,
        added_by=uuid.uuid4(),
        added_at=datetime.now(timezone.utc),
        item=make_item(),
    )
    defaults.update(overrides)
    return CharacterInventory(**defaults)
