"""DELETE of a homebrew reference entry still referenced by a FK gives 409 and keeps
everything (entry and shares) in place; outgoing implications and shares go with it."""
import pytest
from sqlalchemy import func, select

from app.db.models.compendium import class_primary_abilities
from app.db.models.reference import (
    Ability,
    CampaignHomebrewRule,
    Condition,
    ConditionImplication,
    Size,
    Skill,
)
from tests.integration.conftest import (
    auth_headers,
    seed_campaign,
    seed_campaign_member,
    seed_character,
    seed_character_ability_score,
    seed_character_skill,
    seed_class,
    seed_class_skill,
    seed_reference,
    seed_species,
    seed_user,
)

API = "/api/compendium"


@pytest.fixture
async def author(db_session):
    user = await seed_user(db_session)
    campaign = await seed_campaign(db_session, creator=user)
    await seed_campaign_member(db_session, campaign, user, role="dm")
    return dict(user=user, campaign=campaign, headers=auth_headers(user))


async def _exists(db_session, model, code) -> bool:
    count = (await db_session.execute(
        select(func.count()).select_from(model).where(model.code == code)
    )).scalar_one()
    return count == 1


async def _shares(db_session, table, key) -> int:
    return (await db_session.execute(
        select(func.count()).select_from(CampaignHomebrewRule).where(
            CampaignHomebrewRule.resource_table == table, CampaignHomebrewRule.resource_key == key,
        )
    )).scalar_one()


async def test_ability_referenced_by_skill_is_409(api_client, db_session, author):
    await seed_reference(db_session, Ability, author=author["user"], code="luck", name="Luck",
                         campaigns=[author["campaign"]])
    await seed_reference(db_session, Skill, author=author["user"], code="gambling", ability_code="luck")
    await db_session.commit()

    response = await api_client.delete(f"{API}/ability-scores/luck", headers=author["headers"])
    assert response.status_code == 409
    assert await _exists(db_session, Ability, "luck")
    assert await _shares(db_session, "ability_scores", "luck") == 1


async def test_ability_referenced_by_class_association_is_409(api_client, db_session, author):
    await seed_reference(db_session, Ability, author=author["user"], code="luck", name="Luck")
    klass = await seed_class(db_session)
    await db_session.execute(class_primary_abilities.insert().values(class_id=klass.id, ability_code="luck"))
    await db_session.commit()
    assert (await api_client.delete(f"{API}/ability-scores/luck", headers=author["headers"])).status_code == 409


async def test_ability_referenced_by_class_spell_ability_is_409(api_client, db_session, author):
    await seed_reference(db_session, Ability, author=author["user"], code="luck", name="Luck")
    await seed_class(db_session, spell_ability="luck")
    await db_session.commit()
    assert (await api_client.delete(f"{API}/ability-scores/luck", headers=author["headers"])).status_code == 409


async def test_ability_referenced_by_character_is_409(api_client, db_session, author):
    await seed_reference(db_session, Ability, author=author["user"], code="luck", name="Luck")
    character = await seed_character(db_session, owner=author["user"])
    await seed_character_ability_score(db_session, character, ability_code="luck", value=12)
    await db_session.commit()
    assert (await api_client.delete(f"{API}/ability-scores/luck", headers=author["headers"])).status_code == 409


async def test_condition_target_of_implication_is_409(api_client, db_session, author):
    await seed_reference(db_session, Condition, author=author["user"], code="dazed")
    db_session.add(ConditionImplication(condition_code="stunned", implied_condition_code="dazed"))
    await db_session.commit()

    assert (await api_client.delete(f"{API}/conditions/dazed", headers=author["headers"])).status_code == 409
    assert await _exists(db_session, Condition, "dazed")


async def test_condition_with_only_outgoing_implications_is_deleted(api_client, db_session, author):
    await seed_reference(db_session, Condition, author=author["user"], code="dazed",
                         campaigns=[author["campaign"]])
    db_session.add(ConditionImplication(condition_code="dazed", implied_condition_code="incapacitated"))
    await db_session.commit()

    assert (await api_client.delete(f"{API}/conditions/dazed", headers=author["headers"])).status_code == 204
    remaining = (await db_session.execute(
        select(func.count()).select_from(ConditionImplication).where(ConditionImplication.condition_code == "dazed")
    )).scalar_one()
    assert remaining == 0
    assert not await _exists(db_session, Condition, "dazed")
    assert await _shares(db_session, "conditions", "dazed") == 0


async def test_skill_used_by_character_is_409(api_client, db_session, author):
    skill = await seed_reference(db_session, Skill, author=author["user"], code="gambling", ability_code="cha")
    character = await seed_character(db_session, owner=author["user"])
    await seed_character_skill(db_session, character, skill)
    await db_session.commit()
    assert (await api_client.delete(f"{API}/skills/gambling", headers=author["headers"])).status_code == 409
    assert await _exists(db_session, Skill, "gambling")


async def test_skill_in_class_list_is_409(api_client, db_session, author):
    skill = await seed_reference(db_session, Skill, author=author["user"], code="gambling", ability_code="cha")
    klass = await seed_class(db_session)
    await seed_class_skill(db_session, klass, skill)
    await db_session.commit()
    assert (await api_client.delete(f"{API}/skills/gambling", headers=author["headers"])).status_code == 409


async def test_size_used_by_species_is_409(api_client, db_session, author):
    await seed_reference(db_session, Size, author=author["user"], code="colossal", hit_die=30,
                         carry_multiplier=240, sort_order=7)
    await seed_species(db_session, size_code="colossal")
    await db_session.commit()
    assert (await api_client.delete(f"{API}/sizes/colossal", headers=author["headers"])).status_code == 409
