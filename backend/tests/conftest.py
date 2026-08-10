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
from app.db.models.user import RefreshToken, User  # noqa: E402


class FakeResult:
    """Stand-in for SQLAlchemy's `Result` object.

    `db.execute(...)` is awaited and returns this object; `.scalar_one_or_none()`
    and `.scalars().all()` are then called *synchronously* on it, mirroring the
    real `Result` API used throughout `app/services/*.py` and `app/core/deps.py`.
    """

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
    """Minimal async double for `AsyncSession`, shaped after the real usage:

    - `execute` is awaited, returns a `FakeResult` (configurable per test via
      `.execute.return_value` or `.execute.side_effect` for sequential calls).
    - `add` is a plain (sync) call.
    - `commit`/`refresh`/`flush`/`delete` are awaited.
    """

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
    )
    defaults.update(overrides)
    return Character(**defaults)


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
    )
    defaults.update(overrides)
    return CharacterInventory(**defaults)
