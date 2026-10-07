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
    CharacterSpell,
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
    SpellDefinition,
    SubclassDefinition,
    background_proficiency_grants,
    class_proficiency_grants,
)
from app.db.models.items import Armor, ItemContent, Tool, Weapon, WeaponPropertyLink  # noqa: E402
from app.db.models.reference import CampaignHomebrewRule, Skill  # noqa: E402
from app.db.models.spells import SpellMaterial, spell_list_spells  # noqa: E402
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


async def seed_feat(session: AsyncSession, author: User | None = None, **overrides) -> FeatDefinition:
    """A feat without prerequisites or features (category `origin` by default). With
    `author` it is homebrew of that user; otherwise it looks like an SRD row."""
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Feat-{uuid.uuid4().hex[:10]}",
        description=None,
        category_code="origin",
        repeatable=False,
        source="srd",
        is_homebrew=False,
    )
    if author is not None:
        defaults.update(source="homebrew", is_homebrew=True, created_by=author.id)
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


async def seed_class(session: AsyncSession, author: User | None = None, **overrides) -> ClassDefinition:
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
    if author is not None:
        defaults.update(source="homebrew", is_homebrew=True, created_by=author.id)
    defaults.update(overrides)
    obj = ClassDefinition(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def seed_subclass(
    session: AsyncSession, class_def: ClassDefinition, author: User | None = None, **overrides
) -> SubclassDefinition:
    defaults = dict(
        id=uuid.uuid4(),
        class_id=class_def.id,
        name=f"Subclass-{uuid.uuid4().hex[:10]}",
        description=None,
        source="srd",
        is_homebrew=False,
    )
    if author is not None:
        defaults.update(source="homebrew", is_homebrew=True, created_by=author.id)
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


def squash_namespace(name: str) -> uuid.UUID:
    """A uuid5 namespace constant (`SRD_*_NAMESPACE`) of the squash (alembic/versions is
    not importable as a package)."""
    import re

    backend = os.path.dirname(os.path.dirname(_INTEGRATION_DIR))
    path = os.path.join(backend, "alembic", "versions", "c1fcfd7fe014_initial_schema.py")
    with open(path, encoding="utf-8") as handle:
        match = re.search(rf'{name} = uuid\.UUID\("([0-9a-f-]+)"\)', handle.read())
    return uuid.UUID(match.group(1))


def _srd_spell_namespace() -> uuid.UUID:
    return squash_namespace("SRD_SPELL_NAMESPACE")


def srd_spell_id(name: str) -> uuid.UUID:
    """Id of the seeded SRD spell `name` (uuid5 of the name)."""
    return uuid.uuid5(_srd_spell_namespace(), name)


async def srd_spell(session: AsyncSession, name: str) -> SpellDefinition:
    """The seeded SRD spell called `name` (seed names are unique)."""
    result = await session.execute(select(SpellDefinition).where(SpellDefinition.id == srd_spell_id(name)))
    return result.scalar_one()


async def seed_spell(
    session: AsyncSession,
    author: User | None = None,
    materials: list[dict] = (),
    spell_lists: list[str] = (),
    **overrides,
) -> SpellDefinition:
    """A coherent spell (level 1 evocation, V, action, Self, Instantaneous by default).
    With `author` it is homebrew of that user; otherwise it looks like an SRD row.
    `materials` are dicts of `spell_materials` columns (sort_order = position) and set
    `has_material`; `spell_lists` are list codes linked to the spell."""
    defaults = dict(
        id=uuid.uuid4(),
        name=f"Spell-{uuid.uuid4().hex[:10]}",
        level=1,
        school_code="evocation",
        has_verbal=True,
        has_somatic=False,
        has_material=bool(materials),
        casting_time_code="action",
        ritual=False,
        concentration=False,
        range="Self",
        duration="Instantaneous",
        area=None,
        area_shape_code=None,
        description="A test spell.",
        higher_levels=None,
        cantrip_upgrade=None,
        source="srd",
        is_homebrew=False,
        created_by=None,
    )
    if author is not None:
        defaults.update(source="homebrew", is_homebrew=True, created_by=author.id)
    defaults.update(overrides)
    spell = SpellDefinition(**defaults)
    session.add(spell)
    await session.flush()
    for sort_order, material in enumerate(materials):
        session.add(SpellMaterial(spell_id=spell.id, sort_order=sort_order, **material))
    for code in spell_lists:
        await session.execute(spell_list_spells.insert().values(spell_list_code=code, spell_id=spell.id))
    await session.flush()
    return spell


async def seed_character_spell(
    session: AsyncSession, character: Character, spell: SpellDefinition, **overrides
) -> CharacterSpell:
    defaults = dict(
        id=uuid.uuid4(),
        character_id=character.id,
        spell_id=spell.id,
        is_prepared=False,
        is_always_prepared=False,
        source="class",
    )
    defaults.update(overrides)
    obj = CharacterSpell(**defaults)
    session.add(obj)
    await session.flush()
    return obj


# --- features (phase 4) -------------------------------------------------------------

async def _seed_scaling(session: AsyncSession, column: str, target_id: uuid.UUID, rows) -> None:
    from app.db.models.features import FeatureScaling

    for row in rows:
        session.add(FeatureScaling(**{column: target_id}, **row))


async def seed_feature(
    session: AsyncSession,
    *,
    class_def: ClassDefinition | None = None,
    subclass: SubclassDefinition | None = None,
    feat: FeatDefinition | None = None,
    effects: list[dict] = (),
    resources: list[dict] = (),
    **overrides,
):
    """A feature of exactly one owner (provenance copied from it) with its children,
    written directly in the database. `effects`/`resources` take the shape of the API
    payload: an effect may have a `choice` (with `options` and `scaling`), `scaling` and
    `resource_index`; a resource has `recharges` and may have `scaling`. Class/subclass
    features get level 1 unless `level` is given; `sort_order` is the next position."""
    from sqlalchemy import func

    from app.db.models.features import (
        FeatureChoice,
        FeatureChoiceOption,
        FeatureDefinition,
        FeatureEffect,
        FeatureResource,
        FeatureResourceRecharge,
    )

    owner = class_def or subclass or feat
    owner_column = "class_id" if class_def else "subclass_id" if subclass else "feat_id"
    owner_filter = getattr(FeatureDefinition, owner_column) == owner.id
    position = await session.scalar(select(func.count()).select_from(FeatureDefinition).where(owner_filter))
    defaults = dict(
        id=uuid.uuid4(), name=f"Feature-{uuid.uuid4().hex[:10]}", description=None, sort_order=position,
        level=None if feat is not None else 1, source=owner.source, is_homebrew=owner.is_homebrew,
        created_by=owner.created_by, **{owner_column: owner.id},
    )
    defaults.update(overrides)
    feature = FeatureDefinition(**defaults)
    session.add(feature)
    await session.flush()

    resource_ids = []
    for index, resource in enumerate(resources):
        row = FeatureResource(
            id=uuid.uuid4(), feature_id=feature.id, sort_order=index,
            **{k: v for k, v in resource.items() if k not in ("recharges", "scaling")},
        )
        session.add(row)
        await session.flush()
        resource_ids.append(row.id)
        for recharge in resource.get("recharges", ()):
            session.add(FeatureResourceRecharge(resource_id=row.id, **recharge))
        await _seed_scaling(session, "resource_id", row.id, resource.get("scaling", ()))
    for index, effect in enumerate(effects):
        values = {k: v for k, v in effect.items() if k not in ("choice", "scaling", "resource_index")}
        if "resource_index" in effect:
            values["resource_id"] = resource_ids[effect["resource_index"]]
        row = FeatureEffect(id=uuid.uuid4(), feature_id=feature.id, sort_order=index, **values)
        session.add(row)
        await session.flush()
        await _seed_scaling(session, "effect_id", row.id, effect.get("scaling", ()))
        choice = effect.get("choice")
        if choice is not None:
            choice_row = FeatureChoice(
                id=uuid.uuid4(), effect_id=row.id,
                **{k: v for k, v in choice.items() if k not in ("options", "scaling")},
            )
            session.add(choice_row)
            await session.flush()
            for option in choice.get("options", ()):
                session.add(FeatureChoiceOption(choice_id=choice_row.id, **option))
            await _seed_scaling(session, "choice_id", choice_row.id, choice.get("scaling", ()))
    await session.flush()
    return feature


def srd_feat_id(name: str) -> uuid.UUID:
    return uuid.uuid5(squash_namespace("SRD_FEAT_NAMESPACE"), name)


def srd_class_id(name: str = "Fighter") -> uuid.UUID:
    return uuid.uuid5(squash_namespace("SRD_CLASS_NAMESPACE"), name)


def srd_subclass_id(name: str = "Champion") -> uuid.UUID:
    return uuid.uuid5(squash_namespace("SRD_SUBCLASS_NAMESPACE"), name)


def srd_feature_id(key: str) -> uuid.UUID:
    """Id of a seeded feature by its path, e.g. "class:Fighter/1/Second Wind" or
    "feat:Alert/-/Initiative Proficiency"."""
    return uuid.uuid5(squash_namespace("SRD_FEATURE_NAMESPACE"), key)


async def srd_feat(session: AsyncSession, name: str) -> FeatDefinition:
    return (await session.execute(select(FeatDefinition).where(FeatDefinition.id == srd_feat_id(name)))).scalar_one()


async def srd_class(session: AsyncSession, name: str = "Fighter") -> ClassDefinition:
    return (await session.execute(
        select(ClassDefinition).where(ClassDefinition.id == srd_class_id(name))
    )).scalar_one()


async def srd_subclass(session: AsyncSession, name: str = "Champion") -> SubclassDefinition:
    return (await session.execute(
        select(SubclassDefinition).where(SubclassDefinition.id == srd_subclass_id(name))
    )).scalar_one()


async def srd_feature(session: AsyncSession, key: str):
    from app.db.models.features import FeatureDefinition

    return (await session.execute(
        select(FeatureDefinition).where(FeatureDefinition.id == srd_feature_id(key))
    )).unique().scalar_one()
