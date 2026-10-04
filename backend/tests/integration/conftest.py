import os
import uuid
from contextlib import contextmanager
from decimal import Decimal

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
    CharacterSkill,
)
from app.db.models.compendium import (  # noqa: E402
    BackgroundDefinition,
    BackgroundInitialEquipment,
    ClassDefinition,
    ClassInitialEquipment,
    FeatDefinition,
    ItemDefinition,
    ProficiencyGrant,
    SpeciesDefinition,
    SubclassDefinition,
    background_proficiency_grants,
    class_proficiency_grants,
)
from app.db.models.items import Armor, ItemContent, Tool, Weapon, WeaponPropertyLink  # noqa: E402
from app.db.models.reference import CampaignHomebrewRule, Skill  # noqa: E402
from app.db.models.user import User  # noqa: E402

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


@pytest.fixture
async def api_client(db_session):
    """HTTP client (httpx + ASGITransport, no real server) whose requests share the
    test's `db_session` (so everything is rolled back at the end of the test)."""
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_db
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def auth_headers(user: User) -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def no_redis(monkeypatch):
    """Replace the Redis publisher used by `_broadcast` with a recorder (no real Redis in tests).
    Returns the list of (channel, parsed_message) published."""
    import json

    published: list[tuple[str, dict]] = []

    async def fake_publish(channel, message):
        published.append((channel, json.loads(message)))

    monkeypatch.setattr("app.api.characters.publish", fake_publish)
    return published


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
        size_code="medium",
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


async def seed_background(session: AsyncSession, **overrides) -> BackgroundDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Background-{uuid.uuid4().hex[:10]}",
        description=None,
        feat_id=None,
        source="srd",
        is_homebrew=False,
    )
    defaults.update(overrides)

    # `feat_id` is a NOT NULL FK; create a minimal feat when the caller
    # doesn't provide one, so `seed_background` keeps working as a
    # "just give me a background" factory.
    if defaults["feat_id"] is None:
        feat = await seed_feat(session)
        defaults["feat_id"] = feat.id

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


async def seed_item(session: AsyncSession, author: User | None = None, **overrides) -> ItemDefinition:
    """A base item with no sub-row (default type `adventuring_gear`, which needs none).
    With `author` it is homebrew of that user; otherwise it looks like an SRD row."""
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Item-{uuid.uuid4().hex[:10]}",
        item_type_code="adventuring_gear",
        cost_gp=Decimal("1"),
        weight_lb=Decimal("1"),
        description=None,
        source="srd",
        is_homebrew=False,
        created_by=None,
    )
    if author is not None:
        defaults.update(source="homebrew", is_homebrew=True, created_by=author.id)
    defaults.update(overrides)
    obj = ItemDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def srd_item(session: AsyncSession, name: str) -> ItemDefinition:
    """The seeded SRD item called `name` (seed names are unique)."""
    result = await session.execute(
        select(ItemDefinition).where(ItemDefinition.name == name, ItemDefinition.source == "srd")
    )
    return result.scalar_one()


async def seed_weapon(
    session: AsyncSession, author: User | None = None, properties: list[dict] = (), **weapon_overrides
) -> ItemDefinition:
    """A `weapon` item plus its `weapons` row (simple melee 1d6 slashing by default) and
    the given `weapon_property_links` rows (dicts of link columns)."""
    item = await seed_item(session, author=author, item_type_code="weapon")
    weapon = dict(
        category_code="simple", is_ranged=False, damage_dice_count=1, damage_die_size=6, damage_flat=0,
        damage_type_code="slashing", mastery_code=None,
    )
    weapon.update(weapon_overrides)
    session.add(Weapon(item_id=item.id, **weapon))
    await session.flush()
    for link in properties:
        session.add(WeaponPropertyLink(weapon_item_id=item.id, **link))
    await session.flush()
    return item


async def seed_armor(session: AsyncSession, author: User | None = None, **armor_overrides) -> ItemDefinition:
    item = await seed_item(session, author=author, item_type_code="armor")
    armor = dict(
        category_code="light", base_ac=11, adds_dex_modifier=True, max_dex_modifier=None,
        strength_requirement=None, stealth_disadvantage=False,
    )
    armor.update(armor_overrides)
    session.add(Armor(item_id=item.id, **armor))
    await session.flush()
    return item


async def seed_tool(
    session: AsyncSession, author: User | None = None, tool_type_code: str = "thieves_tools"
) -> ItemDefinition:
    item = await seed_item(session, author=author, item_type_code="tool")
    session.add(Tool(item_id=item.id, tool_type_code=tool_type_code))
    await session.flush()
    return item


async def seed_pack(
    session: AsyncSession, author: User | None = None, contents: list[tuple[ItemDefinition, int]] = ()
) -> ItemDefinition:
    """A `pack` item holding `contents` (item, quantity); one Torch by default."""
    item = await seed_item(session, author=author, item_type_code="pack")
    contents = list(contents) or [(await srd_item(session, "Torch"), 1)]
    for content, quantity in contents:
        session.add(ItemContent(pack_item_id=item.id, item_id=content.id, quantity=quantity))
    await session.flush()
    return item


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
        # Accepts either a dict (`{"str": 10, ...}`, converted below into
        # `character_ability_scores` rows) or an explicit list of
        # `CharacterAbilityScore` instances. Codes must exist in `ability_scores`
        # (the SRD seed provides the six standard ones).
        ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
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
        for code, value in ability_scores.items():
            session.add(CharacterAbilityScore(character_id=character_id, ability_code=code, value=value))
    else:
        for row in ability_scores:
            row.character_id = character_id
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
        ability_code="str",
        value=10,
    )
    defaults.update(overrides)
    obj = CharacterAbilityScore(**defaults)
    session.add(obj)
    await session.flush()
    return obj


def random_code(prefix: str = "hb") -> str:
    """A fresh code valid for `^[a-z0-9]+(_[a-z0-9]+)*$`."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def seed_skill(session: AsyncSession, **overrides) -> Skill:
    """A homebrew-free skill row in the `skills` reference table (random code,
    `ability_code` defaults to the SRD `str`)."""
    defaults = dict(
        code=random_code("skill"),
        name=f"Skill-{uuid.uuid4().hex[:10]}",
        ability_code="str",
        description=None,
        source="srd",
        is_homebrew=False,
        created_by=None,
    )
    defaults.update(overrides)
    obj = Skill(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_reference(
    session: AsyncSession,
    model,
    author: User | None = None,
    campaigns=(),
    **overrides,
):
    """Create a reference row of `model` (any `app.db.models.reference` model).

    With `author`, the row is homebrew (`source="homebrew"`, `is_homebrew=True`,
    `created_by=author.id`); without it, it looks like an SRD row. `campaigns`
    adds `campaign_homebrew_rules` shares. Code-keyed models get a random code and
    name unless overridden; numeric-keyed models need their key in `overrides`."""
    defaults: dict = {}
    if "code" in model.__table__.c:
        defaults.update(code=random_code(), name=f"Ref-{uuid.uuid4().hex[:8]}")
    if "ability_code" in model.__table__.c:
        # `skills` and `tool_types` need an ability; the SRD `str` by default.
        defaults.update(ability_code="str")
    if author is not None:
        defaults.update(source="homebrew", is_homebrew=True, created_by=author.id)
    else:
        defaults.update(source="srd", is_homebrew=False, created_by=None)
    defaults.update(overrides)
    obj = model(**defaults)
    session.add(obj)
    await session.flush()

    key_column = next(iter(model.__table__.primary_key.columns)).name
    for campaign in campaigns:
        session.add(CampaignHomebrewRule(
            resource_table=model.__tablename__,
            resource_key=str(getattr(obj, key_column)),
            campaign_id=campaign.id,
        ))
    if campaigns:
        await session.flush()
    return obj


async def seed_character_skill(
    session: AsyncSession, character: Character, skill: Skill, **overrides
) -> CharacterSkill:
    defaults = dict(
        id=uuid.uuid4(),
        character_id=character.id,
        skill_code=skill.code,
        source="other",
        expertise=False,
    )
    defaults.update(overrides)
    obj = CharacterSkill(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_class_skill(session: AsyncSession, class_def: ClassDefinition, *skills: Skill) -> None:
    """Link skills to a class's `class_skills` pool (raw association insert, no lazy load)."""
    from app.db.models.compendium import class_skills
    for skill in skills:
        await session.execute(class_skills.insert().values(class_id=class_def.id, skill_code=skill.code))
    session.expire(class_def, ["skills"])


async def seed_grant(session: AsyncSession, **target) -> ProficiencyGrant:
    """The proficiency grant for `target` (target columns, e.g. `skill_code="stealth"`),
    reused if it already exists -- the same target is always the same grant."""
    columns = {column: target.get(column) for column in (
        "weapon_category_code", "required_weapon_property_code", "armor_category_code", "tool_type_code",
        "tool_category_code", "skill_code", "saving_throw_ability_code", "language_code",
    )}
    unknown = set(target) - set(columns)
    assert not unknown, f"unknown grant columns: {unknown}"
    query = select(ProficiencyGrant).where(
        *(getattr(ProficiencyGrant, column).is_not_distinct_from(value) for column, value in columns.items())
    )
    grant = (await session.execute(query)).scalar_one_or_none()
    if grant is None:
        grant = ProficiencyGrant(**columns)
        session.add(grant)
        await session.flush()
    return grant


async def seed_class_grant(session: AsyncSession, class_def: ClassDefinition, **target) -> ProficiencyGrant:
    """Link the grant for `target` to the class (raw link insert)."""
    grant = await seed_grant(session, **target)
    await session.execute(class_proficiency_grants.insert().values(class_id=class_def.id, grant_id=grant.id))
    session.expire(class_def, ["proficiency_grants"])
    return grant


async def seed_background_grant(
    session: AsyncSession, background: BackgroundDefinition, **target
) -> ProficiencyGrant:
    """Link the grant for `target` to the background (raw link insert)."""
    grant = await seed_grant(session, **target)
    await session.execute(
        background_proficiency_grants.insert().values(background_id=background.id, grant_id=grant.id)
    )
    session.expire(background, ["proficiency_grants"])
    return grant


async def seed_background_skill(
    session: AsyncSession, background: BackgroundDefinition, *skills: Skill
) -> None:
    """Give the background fixed proficiency in `skills` (one `skill` grant each)."""
    for skill in skills:
        await seed_background_grant(session, background, skill_code=skill.code)


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