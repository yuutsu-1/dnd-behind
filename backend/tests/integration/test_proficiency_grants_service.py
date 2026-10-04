"""Resolution of proficiency-grant descriptors: validate codes (exist + visible, 400),
reuse the grant with the same target or create it inside the caller's transaction."""
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.models.compendium import ProficiencyGrant
from app.db.models.reference import Skill, ToolType, WeaponProperty
from app.schemas.proficiency_grants import ProficiencyGrantDescriptor as D
from app.schemas.proficiency_grants import ProficiencyGrantOut
from app.services.proficiency_grants import resolve_grants
from tests.integration.conftest import (
    seed_campaign,
    seed_campaign_member,
    seed_reference,
    seed_user,
)


async def _grant_count(db_session) -> int:
    return await db_session.scalar(select(func.count()).select_from(ProficiencyGrant))


@pytest.fixture
async def people(db_session):
    a = await seed_user(db_session)
    b = await seed_user(db_session)
    p = await seed_user(db_session)
    c = await seed_campaign(db_session, creator=b)
    await seed_campaign_member(db_session, c, b, role="dm")
    await seed_campaign_member(db_session, c, p, role="player")
    await db_session.commit()
    return dict(a=a, b=b, p=p, c=c)


async def test_same_descriptor_twice_is_the_same_grant(db_session, people):
    before = await _grant_count(db_session)
    [first] = await resolve_grants(db_session, [D(skill_code="stealth")], people["a"])
    [second] = await resolve_grants(db_session, [D(skill_code="stealth")], people["a"])
    assert first.id == second.id
    assert await _grant_count(db_session) == before + 1


async def test_existing_grant_is_reused(db_session, people):
    [created] = await resolve_grants(db_session, [D(armor_category_code="shield")], people["a"])
    await db_session.commit()
    db_session.expunge_all()
    [again] = await resolve_grants(db_session, [D(armor_category_code="shield")], people["b"])
    assert again.id == created.id


async def test_category_with_and_without_property_are_distinct(db_session, people):
    grants = await resolve_grants(db_session, [
        D(weapon_category_code="martial"),
        D(weapon_category_code="martial", required_weapon_property_code="light"),
    ], people["a"])
    assert len({g.id for g in grants}) == 2
    assert [g.required_weapon_property_code for g in grants] == [None, "light"]


async def test_order_follows_the_descriptors(db_session, people):
    descriptors = [D(saving_throw_ability_code="str"), D(tool_type_code="herbalism_kit"), D(language_code="elvish")]
    grants = await resolve_grants(db_session, descriptors, people["a"])
    assert [g.kind for g in grants] == ["saving_throw", "tool", "language"]


async def test_output_data_is_available_for_new_and_existing_grants(db_session, people):
    [old] = await resolve_grants(db_session, [D(tool_category_code="gaming_set")], people["a"])
    await db_session.commit()
    grants = await resolve_grants(db_session, [
        D(tool_category_code="gaming_set"),
        D(weapon_category_code="martial", required_weapon_property_code="finesse"),
        D(tool_type_code="thieves_tools"),
    ], people["a"])
    outs = [ProficiencyGrantOut.model_validate(g) for g in grants]
    assert outs[0].id == old.id
    assert [(o.kind, o.target_name) for o in outs] == [
        ("tool_category", "Gaming Set"), ("weapon_category", "Martial"), ("tool", "Thieves' Tools"),
    ]
    assert outs[1].required_weapon_property_name == "Finesse"


@pytest.mark.parametrize("descriptor", [
    D(skill_code="no_such_skill"),
    D(weapon_category_code="exotic"),
    D(weapon_category_code="martial", required_weapon_property_code="no_such_property"),
    D(armor_category_code="no_such_armor"),
    D(tool_type_code="no_such_tool"),
    D(tool_category_code="no_such_category"),
    D(saving_throw_ability_code="luck"),
    D(language_code="klingon"),
])
async def test_unknown_code_is_400_and_nothing_is_kept(db_session, people, descriptor):
    before = await _grant_count(db_session)
    with pytest.raises(HTTPException) as exc:
        await resolve_grants(db_session, [D(skill_code="arcana"), descriptor], people["a"])
    assert exc.value.status_code == 400
    await db_session.rollback()
    assert await _grant_count(db_session) == before


async def test_invisible_homebrew_is_400_with_the_same_message_as_unknown(db_session, people):
    await seed_reference(db_session, Skill, author=people["b"], code="hidden_skill", name="Hidden")
    await db_session.commit()
    with pytest.raises(HTTPException) as invisible:
        await resolve_grants(db_session, [D(skill_code="hidden_skill")], people["a"])
    with pytest.raises(HTTPException) as unknown:
        await resolve_grants(db_session, [D(skill_code="other_skill")], people["a"])
    assert invisible.value.status_code == unknown.value.status_code == 400
    assert invisible.value.detail.replace("hidden_skill", "X") == unknown.value.detail.replace("other_skill", "X")


async def test_own_and_shared_homebrew_are_accepted(db_session, people):
    own = await seed_reference(db_session, ToolType, author=people["a"], ability_code="dex")
    shared = await seed_reference(
        db_session, WeaponProperty, author=people["b"], campaigns=[people["c"]], code="spiky", name="Spiky",
    )
    await db_session.commit()
    grants = await resolve_grants(db_session, [D(tool_type_code=own.code)], people["a"])
    assert grants[0].tool_type_code == own.code
    grants = await resolve_grants(
        db_session, [D(weapon_category_code="simple", required_weapon_property_code=shared.code)], people["p"],
    )
    assert grants[0].required_weapon_property_code == "spiky"


async def test_unique_target_holds_with_nulls(db_session):
    await db_session.execute(text("INSERT INTO proficiency_grants (id, skill_code) VALUES (gen_random_uuid(), 'insight')"))
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text("INSERT INTO proficiency_grants (id, skill_code) VALUES (gen_random_uuid(), 'insight')")
            )


async def test_single_target_check_holds_in_the_database(db_session):
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(text(
                "INSERT INTO proficiency_grants (id, skill_code, language_code) "
                "VALUES (gen_random_uuid(), 'insight', 'elvish')"
            ))
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(text(
                "INSERT INTO proficiency_grants (id, armor_category_code, required_weapon_property_code) "
                "VALUES (gen_random_uuid(), 'light', 'light')"
            ))
