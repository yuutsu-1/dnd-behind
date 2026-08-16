import os
import uuid
from contextlib import contextmanager

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://dnd:dndpass@localhost:5432/dnd_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")

import pytest  # noqa: E402
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.db.models.campaign import Campaign, CampaignMember  # noqa: E402
from app.db.models.character import (  # noqa: E402
    Character,
    CharacterAbilityScore,
    CharacterClass,
    CharacterInventory,
)
from app.db.models.compendium import (  # noqa: E402
    AbilityScoreOption,
    BackgroundDefinition,
    BackgroundInitialEquipment,
    ClassDefinition,
    ClassInitialEquipment,
    FeatDefinition,
    ItemDefinition,
    SkillDefinition,
    SpeciesDefinition,
    SubclassDefinition,
    ToolProficiencyOption,
)
from app.db.models.user import User  # noqa: E402
from app.enums import CreatureSize  # noqa: E402

INTEGRATION_DATABASE_URL = os.environ.get(
    "INTEGRATION_DATABASE_URL",
    "postgresql+asyncpg://dnd:dndpass@localhost:5432/dnd_test",
)


_INTEGRATION_DIR = os.path.dirname(os.path.abspath(__file__))


def pytest_collection_modifyitems(config, items):
    for item in items:
        if os.path.abspath(str(item.fspath)).startswith(_INTEGRATION_DIR):
            item.add_marker(pytest.mark.integration)


@pytest.fixture
async def db_engine():
    eng = create_async_engine(INTEGRATION_DATABASE_URL, echo=False)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(db_engine):
    connection = await db_engine.connect()
    outer_transaction = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session: AsyncSession = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await outer_transaction.rollback()
        await connection.close()


class QueryCounter:
    """Counts SQL statements executed on a given engine while active."""

    def __init__(self):
        self.count = 0
        self.statements: list[str] = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.statements.append(statement)


@contextmanager
def count_queries(engine):

    counter = QueryCounter()
    event.listen(engine.sync_engine, "before_cursor_execute", counter)
    try:
        yield counter
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", counter)

async def seed_user(session: AsyncSession, **overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        username=f"user-{uuid.uuid4().hex[:10]}",
        hashed_password="hashed-password",
        is_active=True,
    )
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    await session.flush()
    return user


async def seed_species(session: AsyncSession, **overrides) -> SpeciesDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Species-{uuid.uuid4().hex[:10]}",
        description=None,
        creature_type="humanoid",
        size=CreatureSize.medium,
        base_speed=30,
        special_traits=[],
        source="srd",
        is_homebrew=False,
    )
    defaults.update(overrides)
    obj = SpeciesDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_feat(session: AsyncSession, **overrides) -> FeatDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Feat-{uuid.uuid4().hex[:10]}",
        description=None,
        category="origin",
        level_prerequisite=0,
        prerequisite_description=None,
        repeatable=False,
        source="srd",
        is_homebrew=False,
    )
    defaults.update(overrides)
    obj = FeatDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def _ensure_tool_proficiency_option(session: AsyncSession, name: str) -> None:
    """Get-or-create a `ToolProficiencyOption` row so FKs to
    `tool_proficiency_options.name` (used by `BackgroundDefinition.tool_proficiency`)
    can be safely inserted."""
    existing = await session.execute(select(ToolProficiencyOption).where(ToolProficiencyOption.name == name))
    if existing.scalar_one_or_none() is None:
        session.add(ToolProficiencyOption(name=name))
        await session.flush()


async def seed_background(session: AsyncSession, **overrides) -> BackgroundDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Background-{uuid.uuid4().hex[:10]}",
        description=None,
        feat_id=None,
        tool_proficiency=None,
        source="srd",
        is_homebrew=False,
    )
    defaults.update(overrides)

    # `feat_id`/`tool_proficiency` are NOT NULL FKs; get-or-create minimal
    # rows for them when the caller doesn't provide one, so `seed_background`
    # keeps working as a "just give me a background" factory.
    if defaults["feat_id"] is None:
        feat = await seed_feat(session)
        defaults["feat_id"] = feat.id
    if defaults["tool_proficiency"] is None:
        defaults["tool_proficiency"] = f"Tool-{uuid.uuid4().hex[:10]}"
    await _ensure_tool_proficiency_option(session, defaults["tool_proficiency"])

    obj = BackgroundDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_background_initial_equipment(
    session: AsyncSession, background: BackgroundDefinition, item: ItemDefinition, **overrides
) -> BackgroundInitialEquipment:
    defaults = dict(
        id=uuid.uuid4(),
        background_id=background.id,
        item_id=item.id,
        option="A",
        quantity=1,
    )
    defaults.update(overrides)
    obj = BackgroundInitialEquipment(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_class(session: AsyncSession, **overrides) -> ClassDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Class-{uuid.uuid4().hex[:10]}",
        description=None,
        hit_die=10,
        skill_choices=2,
        subclass_level=3,
        spell_ability=None,
        spellcasting_type=None,
        source="srd",
        is_homebrew=False,
    )
    defaults.update(overrides)
    obj = ClassDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_subclass(session: AsyncSession, class_def: ClassDefinition, **overrides) -> SubclassDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        class_id=class_def.id,
        name=f"Subclass-{uuid.uuid4().hex[:10]}",
        description=None,
        source="srd",
        is_homebrew=False,
    )
    defaults.update(overrides)
    obj = SubclassDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_item(session: AsyncSession, **overrides) -> ItemDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Item-{uuid.uuid4().hex[:10]}",
        item_type="weapon",
        subtype=None,
        rarity="common",
        requires_attunement=False,
        attunement_prerequisite=None,
        weight=1.0,
        cost_gp=1.0,
        description=None,
        properties={},
        source="srd",
        is_homebrew=False,
    )
    defaults.update(overrides)
    obj = ItemDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_campaign(session: AsyncSession, creator: User, **overrides) -> Campaign:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Campaign-{uuid.uuid4().hex[:10]}",
        description=None,
        created_by=creator.id,
        invite_code=uuid.uuid4().hex[:12],
        is_active=True,
        settings={},
    )
    defaults.update(overrides)
    obj = Campaign(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_campaign_member(session: AsyncSession, campaign: Campaign, user: User, **overrides) -> CampaignMember:
    defaults = dict(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        user_id=user.id,
        role="player",
    )
    defaults.update(overrides)
    obj = CampaignMember(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_character(session: AsyncSession, owner: User, **overrides) -> Character:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=owner.id,
        campaign_id=None,
        name="Test Character",
        experience_points=0,
        species_id=None,
        background_id=None,
        # Accepts either a dict (`{"STR": 10, ...}`, converted below into
        # `character_ability_scores` rows -- keeps the public factory interface
        # unchanged) or an explicit list of `CharacterAbilityScore` instances.
        ability_scores={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        current_hp=10,
        max_hp=10,
        temp_hp=0,
        death_saves={"successes": 0, "failures": 0},
        conditions=[],
        exhaustion_level=0,
        inspiration=False,
        choices={},
        spell_slots_remaining={},
        appearance={},
        notes=None,
        custom_data={},
        is_active=True,
    )
    defaults.update(overrides)

    ability_scores = defaults.pop("ability_scores")
    character_id = defaults["id"]

    obj = Character(**defaults)
    session.add(obj)

    if isinstance(ability_scores, dict):
        await _ensure_ability_score_options(session, ability_scores.keys())
        for name, value in ability_scores.items():
            session.add(CharacterAbilityScore(character_id=character_id, ability_score=name, value=value))
    else:
        for row in ability_scores:
            row.character_id = character_id
            await _ensure_ability_score_options(session, [row.ability_score])
            session.add(row)

    await session.flush()
    return obj


async def seed_character_class(
    session: AsyncSession, character: Character, class_def: ClassDefinition, **overrides
) -> CharacterClass:
    defaults = dict(
        id=uuid.uuid4(),
        character_id=character.id,
        class_id=class_def.id,
        level=1,
        subclass_id=None,
        hit_dice_used=0,
    )
    defaults.update(overrides)
    obj = CharacterClass(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_character_ability_score(
    session: AsyncSession, character: Character, **overrides
) -> CharacterAbilityScore:
    defaults = dict(
        id=uuid.uuid4(),
        character_id=character.id,
        ability_score="STR",
        value=10,
    )
    defaults.update(overrides)
    await _ensure_ability_score_options(session, [defaults["ability_score"]])
    obj = CharacterAbilityScore(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def _ensure_ability_score_options(session: AsyncSession, names) -> None:
    """Get-or-create `AbilityScoreOption` rows so FKs to `ability_score_options.name`
    (used by `SkillDefinition.ability_score` and `CharacterAbilityScore.ability_score`)
    can be safely inserted, even if no class has referenced that ability yet."""
    names = list(names)
    if not names:
        return
    existing = await session.execute(select(AbilityScoreOption).where(AbilityScoreOption.name.in_(names)))
    existing_names = {row.name for row in existing.scalars().all()}
    missing = set(names) - existing_names
    for name in missing:
        session.add(AbilityScoreOption(name=name))
    if missing:
        await session.flush()


async def seed_skill(session: AsyncSession, **overrides) -> SkillDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Skill-{uuid.uuid4().hex[:10]}",
        ability_score="STR",
    )
    defaults.update(overrides)

    # `ability_score` is a FK to `ability_score_options.name`; ensure the
    # lookup row exists (it is otherwise only lazily created when a class
    # references it as a primary/saving-throw ability).
    await _ensure_ability_score_options(session, [defaults["ability_score"]])

    obj = SkillDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_class_initial_equipment(
    session: AsyncSession, class_def: ClassDefinition, item: ItemDefinition, **overrides
) -> ClassInitialEquipment:
    defaults = dict(
        id=uuid.uuid4(),
        class_id=class_def.id,
        item_id=item.id,
        option="A",
        quantity=1,
    )
    defaults.update(overrides)
    obj = ClassInitialEquipment(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_inventory_entry(
    session: AsyncSession, character: Character, item: ItemDefinition, **overrides
) -> CharacterInventory:
    defaults = dict(
        id=uuid.uuid4(),
        character_id=character.id,
        item_id=item.id,
        quantity=1,
        equipped=False,
        attuned=False,
        custom_notes=None,
        added_by=None,
    )
    defaults.update(overrides)
    obj = CharacterInventory(**defaults)
    session.add(obj)
    await session.flush()
    return obj