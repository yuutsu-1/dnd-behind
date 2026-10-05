"""DELETE of a homebrew reference entry still referenced by a FK gives 409 and keeps
everything (entry and shares) in place; outgoing implications and shares go with it."""
import pytest
from sqlalchemy import func, select

from app.db.models.compendium import class_primary_abilities
from app.db.models.reference import (
    Ability,
    ArmorCategory,
    CampaignHomebrewRule,
    Condition,
    ConditionImplication,
    DamageType,
    ItemType,
    Language,
    Size,
    Skill,
    ToolCategory,
    ToolType,
    WeaponCategory,
    WeaponMastery,
    WeaponProperty,
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
    seed_armor,
    seed_background,
    seed_background_skill,
    seed_class_grant,
    seed_grant,
    seed_item,
    seed_reference,
    seed_species,
    seed_tool,
    seed_user,
    seed_weapon,
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


# --- phase 2: references used by items, tool types and proficiency grants ---------------

async def _delete(api_client, author, slug, code):
    return await api_client.delete(f"{API}/{slug}/{code}", headers=author["headers"])


async def test_weapon_mastery_used_by_a_weapon_is_409(api_client, db_session, author):
    await seed_reference(db_session, WeaponMastery, author=author["user"], code="shove")
    await seed_weapon(db_session, author=author["user"], mastery_code="shove")
    await db_session.commit()
    assert (await _delete(api_client, author, "weapon-masteries", "shove")).status_code == 409
    assert await _exists(db_session, WeaponMastery, "shove")


@pytest.mark.parametrize("model,slug,weapon_column", [
    (WeaponCategory, "weapon-categories", "category_code"),
    (DamageType, "damage-types", "damage_type_code"),
])
async def test_weapon_category_and_damage_type_used_by_a_weapon_are_409(
    api_client, db_session, author, model, slug, weapon_column
):
    entry = await seed_reference(db_session, model, author=author["user"])
    await seed_weapon(db_session, author=author["user"], **{weapon_column: entry.code})
    await db_session.commit()
    code = entry.code
    assert (await _delete(api_client, author, slug, code)).status_code == 409
    assert await _exists(db_session, model, code)


async def test_weapon_property_used_by_a_weapon_link_is_409(api_client, db_session, author):
    await seed_reference(db_session, WeaponProperty, author=author["user"], code="spiky")
    await seed_weapon(db_session, author=author["user"], properties=[{"property_code": "spiky"}])
    await db_session.commit()
    assert (await _delete(api_client, author, "weapon-properties", "spiky")).status_code == 409


async def test_armor_category_used_by_an_armor_is_409(api_client, db_session, author):
    await seed_reference(db_session, ArmorCategory, author=author["user"], code="mithral")
    await seed_armor(db_session, author=author["user"], category_code="mithral")
    await db_session.commit()
    assert (await _delete(api_client, author, "armor-categories", "mithral")).status_code == 409


async def test_item_type_used_by_an_item_is_409(api_client, db_session, author):
    await seed_reference(db_session, ItemType, author=author["user"], code="relic")
    await seed_item(db_session, author=author["user"], item_type_code="relic")
    await db_session.commit()
    assert (await _delete(api_client, author, "item-types", "relic")).status_code == 409
    assert await _exists(db_session, ItemType, "relic")


async def test_weapon_property_used_as_required_property_of_a_grant_is_409(api_client, db_session, author):
    await seed_reference(db_session, WeaponProperty, author=author["user"], code="spiky")
    await seed_grant(db_session, weapon_category_code="martial", required_weapon_property_code="spiky")
    await db_session.commit()
    assert (await _delete(api_client, author, "weapon-properties", "spiky")).status_code == 409
    assert await _exists(db_session, WeaponProperty, "spiky")


async def test_skill_used_by_a_background_grant_is_409(api_client, db_session, author):
    skill = await seed_reference(db_session, Skill, author=author["user"], code="gambling", ability_code="cha")
    await seed_background_skill(db_session, await seed_background(db_session), skill)
    await db_session.commit()
    assert (await _delete(api_client, author, "skills", "gambling")).status_code == 409
    assert await _exists(db_session, Skill, "gambling")


async def test_language_used_by_a_grant_is_409(api_client, db_session, author):
    await seed_reference(db_session, Language, author=author["user"], code="aquan", rarity="rare")
    await seed_grant(db_session, language_code="aquan")
    await db_session.commit()
    assert (await _delete(api_client, author, "languages", "aquan")).status_code == 409


async def test_tool_type_used_by_a_tool_item_is_409(api_client, db_session, author):
    await seed_reference(db_session, ToolType, author=author["user"], code="harp", ability_code="cha")
    await seed_tool(db_session, author=author["user"], tool_type_code="harp")
    await db_session.commit()
    assert (await _delete(api_client, author, "tool-types", "harp")).status_code == 409
    assert await _exists(db_session, ToolType, "harp")


async def test_tool_type_used_by_a_grant_is_409(api_client, db_session, author):
    await seed_reference(db_session, ToolType, author=author["user"], code="harp", ability_code="cha")
    await seed_grant(db_session, tool_type_code="harp")
    await db_session.commit()
    assert (await _delete(api_client, author, "tool-types", "harp")).status_code == 409


async def test_unused_tool_type_is_deleted(api_client, db_session, author):
    await seed_reference(db_session, ToolType, author=author["user"], code="harp", ability_code="cha",
                         campaigns=[author["campaign"]])
    await db_session.commit()
    assert (await _delete(api_client, author, "tool-types", "harp")).status_code == 204
    assert not await _exists(db_session, ToolType, "harp")
    assert await _shares(db_session, "tool_types", "harp") == 0


async def test_tool_category_used_by_a_tool_type_is_409(api_client, db_session, author):
    await seed_reference(db_session, ToolCategory, author=author["user"], code="weird_kits")
    await seed_reference(db_session, ToolType, author=author["user"], code="odd_kit", category_code="weird_kits")
    await db_session.commit()
    assert (await _delete(api_client, author, "tool-categories", "weird_kits")).status_code == 409


async def test_tool_category_used_by_a_grant_is_409(api_client, db_session, author):
    await seed_reference(db_session, ToolCategory, author=author["user"], code="weird_kits")
    await seed_grant(db_session, tool_category_code="weird_kits")
    await db_session.commit()
    assert (await _delete(api_client, author, "tool-categories", "weird_kits")).status_code == 409


async def test_ability_used_by_a_tool_type_is_409(api_client, db_session, author):
    await seed_reference(db_session, Ability, author=author["user"], code="luck", name="Luck")
    await seed_reference(db_session, ToolType, author=author["user"], code="dice_of_fate", ability_code="luck")
    await db_session.commit()
    assert (await _delete(api_client, author, "ability-scores", "luck")).status_code == 409


async def test_ability_used_as_saving_throw_grant_is_409(api_client, db_session, author):
    await seed_reference(db_session, Ability, author=author["user"], code="luck", name="Luck")
    await seed_class_grant(db_session, await seed_class(db_session), saving_throw_ability_code="luck")
    await db_session.commit()
    assert (await _delete(api_client, author, "ability-scores", "luck")).status_code == 409


@pytest.mark.parametrize("model,slug,column", [
    (WeaponCategory, "weapon-categories", "weapon_category_code"),
    (ArmorCategory, "armor-categories", "armor_category_code"),
])
async def test_categories_used_by_a_grant_are_409(api_client, db_session, author, model, slug, column):
    entry = await seed_reference(db_session, model, author=author["user"])
    await seed_grant(db_session, **{column: entry.code})
    await db_session.commit()
    code = entry.code
    assert (await _delete(api_client, author, slug, code)).status_code == 409


# --- phase 3: references used by spells --------------------------------------------

@pytest.mark.parametrize("slug,model,spell_field", [
    ("casting-times", "CastingTime", "casting_time_code"),
    ("area-shapes", "AreaShape", "area_shape_code"),
    ("spell-schools", "SpellSchool", "school_code"),
])
async def test_reference_used_by_a_spell_is_409(api_client, db_session, author, slug, model, spell_field):
    import app.db.models.reference as reference
    from tests.integration.conftest import seed_spell

    model = getattr(reference, model)
    await seed_reference(db_session, model, author=author["user"], code="hb_used", name="Used",
                         campaigns=[author["campaign"]])
    overrides = {spell_field: "hb_used"}
    if spell_field == "area_shape_code":
        overrides["area"] = "Some area"
    await seed_spell(db_session, author=author["user"], **overrides)
    await db_session.commit()

    response = await api_client.delete(f"{API}/{slug}/hb_used", headers=author["headers"])
    assert response.status_code == 409
    assert await _exists(db_session, model, "hb_used")
    assert await _shares(db_session, model.__tablename__, "hb_used") == 1


async def test_spell_list_used_by_a_link_is_409(api_client, db_session, author):
    from app.db.models.reference import SpellList
    from tests.integration.conftest import seed_spell

    await seed_reference(db_session, SpellList, author=author["user"], code="hb_list", name="Homebrew List",
                         campaigns=[author["campaign"]])
    await seed_spell(db_session, author=author["user"], spell_lists=["hb_list"])
    await db_session.commit()

    response = await api_client.delete(f"{API}/spell-lists/hb_list", headers=author["headers"])
    assert response.status_code == 409
    assert await _exists(db_session, SpellList, "hb_list")
    assert await _shares(db_session, "spell_lists", "hb_list") == 1


async def test_spell_list_without_links_can_be_deleted(api_client, db_session, author):
    from app.db.models.reference import SpellList

    await seed_reference(db_session, SpellList, author=author["user"], code="hb_free", name="Free List",
                         campaigns=[author["campaign"]])
    await db_session.commit()

    response = await api_client.delete(f"{API}/spell-lists/hb_free", headers=author["headers"])
    assert response.status_code == 204
    assert not await _exists(db_session, SpellList, "hb_free")
    assert await _shares(db_session, "spell_lists", "hb_free") == 0
