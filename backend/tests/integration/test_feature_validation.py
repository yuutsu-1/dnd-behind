"""Coherence of the features embedded in an owner (app/services/features.py): one test
per rule, through the owner's POST. Order: 422 of shape (schema) -> 400 (unknown or
invisible codes, missing ids) -> 422 of coherence. On every error nothing is written."""
import uuid

import pytest
from sqlalchemy import inspect, text

from app.core.security import create_access_token

from app.db.models.reference import ChoicePoolType, EffectOperation, EffectTarget
from tests.integration.conftest import (
    seed_class,
    seed_feat,
    seed_feature,
    seed_item,
    seed_reference,
    seed_user,
    seed_weapon,
    srd_feature_id,
    srd_item,
)


COUNTED_TABLES = (
    "feat_definitions", "class_definitions", "subclass_definitions", "feat_prerequisites", "feature_definitions",
    "feature_effects", "feature_choices", "feature_choice_options", "feature_resources",
    "feature_resource_recharges", "feature_scaling",
)


@pytest.fixture
async def user(db_session):
    user = await seed_user(db_session)
    await db_session.commit()
    return user


@pytest.fixture
async def submit(api_client, db_session):
    """POST `features` embedded in a new owner of kind `owner` as `user`; returns 200 when
    the owner is created, else the error status (asserting that nothing was written)."""
    parent_id = (await seed_class(db_session)).id

    async def run(user, features: list[dict], owner: str = "feat") -> int:
        await db_session.commit()  # what the test seeded survives the handler's rollback
        before = await _counts(db_session)
        if owner == "feat":
            url, payload = "/api/compendium/feats", {"name": "Validated", "category_code": "origin"}
        elif owner == "class":
            url, payload = "/api/compendium/classes", {
                "name": f"Validated-{uuid.uuid4().hex[:8]}", "hit_die": 8, "primary_ability": ["str"]}
        else:
            url, payload = "/api/compendium/subclasses", {"name": "Validated", "class_id": str(parent_id)}
        # The identity key never triggers a load (a previous rollback expired the instance).
        user_id = inspect(user).identity[0]
        headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}
        response = await api_client.post(url, json={**payload, "features": features}, headers=headers)
        if response.status_code == 201:
            return 200
        assert await _counts(db_session) == before, response.text
        return response.status_code

    return run


async def _counts(db_session) -> dict[str, int]:
    return {t: (await db_session.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one() for t in COUNTED_TABLES}


def feat_feature(*effects, **overrides) -> dict:
    return {"name": "Feature", "effects": list(effects), **overrides}


def class_feature(*effects, level=1, **overrides) -> dict:
    return {"name": "Feature", "level": level, "effects": list(effects), **overrides}


@pytest.fixture
def expect(submit):
    async def run(user, status, *effects, owner="feat"):
        feature = feat_feature(*effects) if owner == "feat" else class_feature(*effects)
        assert await submit(user, [feature], owner) == status

    return run


# --- valid payloads ------------------------------------------------------------------

async def test_srd_like_payloads_are_valid(db_session, user, submit):
    features = [
        class_feature({"operation_code": "set", "target_code": "attacks_per_action", "value": 2}, level=5),
        class_feature({"operation_code": "set", "target_code": "attacks_per_action", "value": 3}, level=11,
                      replaces_index=0),
        class_feature({"operation_code": "heal", "target_code": "hit_points", "dice_count": 1, "die_size": 10,
                       "value_basis_code": "class_level", "resource_index": 0}, resources=[
            {"name": "Second Wind", "value": 2, "recharges": [{"recharge_type_code": "short_rest", "recovers": 1}],
             "scaling": [{"level": 4, "value": 3}]}]),
        class_feature({"operation_code": "grant", "choice": {
            "pool_type_code": "feat", "choose_count": 1, "feat_category_code": "fighting_style",
            "swap_rule_code": "on_class_level_up"}}, feature_kind_code="fighting_style"),
        class_feature({"operation_code": "advantage", "target_code": "ability_check", "skill_code": "athletics"},
                      {"operation_code": "advantage", "target_code": "initiative"}, level=3),
    ]
    assert await submit(user, features, "class") == 200


# --- owner and level -----------------------------------------------------------------

async def test_class_feature_without_level_is_422(db_session, user, submit):
    assert await submit(user, [feat_feature()], "class") == 422
    assert await submit(user, [feat_feature()], "subclass") == 422


async def test_feat_feature_with_level_is_422(db_session, user, submit):
    assert await submit(user, [class_feature()], "feat") == 422


# --- 400: codes and ids ------------------------------------------------------------

@pytest.mark.parametrize("feature", [
    feat_feature(action_type_code="no_such_action"),
    feat_feature(feature_kind_code="no_such_kind"),
    feat_feature({"operation_code": "no_such_op"}),
    feat_feature({"operation_code": "bonus", "target_code": "no_such_target", "value": 1}),
    feat_feature({"operation_code": "expertise", "skill_code": "no_such_skill"}),
    feat_feature({"operation_code": "damage_resistance", "damage_type_code": "no_such_damage"}),
    feat_feature({"operation_code": "condition_immunity", "condition_code": "no_such_condition"}),
    feat_feature({"operation_code": "grant", "sense_code": "no_such_sense", "value": 60}),
    feat_feature({"operation_code": "grant", "movement_mode_code": "no_such_mode", "value": 30}),
    feat_feature({"operation_code": "bonus", "target_code": "initiative", "value_basis_code": "no_such_basis"}),
    feat_feature({"operation_code": "grant", "choice": {"pool_type_code": "no_such_pool", "choose_count": 1}}),
    feat_feature({"operation_code": "grant", "choice": {"pool_type_code": "feat", "choose_count": 1,
                                                        "feat_category_code": "no_such_category"}}),
    feat_feature({"operation_code": "grant", "choice": {"pool_type_code": "weapon", "choose_count": 1,
                                                        "swap_rule_code": "no_such_rule"}}),
    feat_feature({"operation_code": "grant", "choice": {"pool_type_code": "skill", "choose_count": 1,
                                                        "options": [{"skill_code": "no_such_skill"}]}}),
    feat_feature(resources=[{"name": "Uses", "value": 1, "recharges": [{"recharge_type_code": "no_such_rest"}]}]),
])
async def test_unknown_code_is_400(db_session, user, feature, submit):
    assert await submit(user, [feature]) == 400


async def test_invisible_homebrew_operation_is_400(db_session, user, submit, expect):
    other = await seed_user(db_session)
    code = (await seed_reference(db_session, EffectOperation, author=other)).code
    await expect(user, 400, {"operation_code": code})
    # The author sees it, and a homebrew operation only needs "at most one typed target".
    assert await submit(other, [feat_feature({"operation_code": code, "skill_code": "stealth"})]) == 200


@pytest.mark.parametrize("field", ["feat_id", "spell_id", "granted_feature_id", "proficiency_grant_id", "item_id"])
async def test_missing_entity_is_400(db_session, user, field, expect):
    await expect(user, 400, {"operation_code": "grant", field: str(uuid.uuid4())})


@pytest.mark.parametrize("pool,field", [("feat", "feat_id"), ("spell", "spell_id"), ("weapon", "item_id"),
                                        ("feature", "feature_id")])
async def test_missing_option_entity_is_400(db_session, user, pool, field, expect):
    await expect(user, 400, {"operation_code": "grant", "choice": {
        "pool_type_code": pool, "choose_count": 1, "options": [{field: str(uuid.uuid4())}]}})


async def test_weapon_option_that_is_not_a_weapon_is_400(db_session, user, expect):
    torch_id = (await srd_item(db_session, "Torch")).id
    weapon_id = (await seed_weapon(db_session, author=user)).id
    await expect(user, 400, {"operation_code": "grant", "choice": {
        "pool_type_code": "weapon", "choose_count": 1, "options": [{"item_id": str(torch_id)}]}})
    await expect(user, 200, {"operation_code": "grant", "choice": {
        "pool_type_code": "weapon", "choose_count": 1, "options": [{"item_id": str(weapon_id)}]}})


async def test_existing_entities_are_valid(db_session, user, expect):
    feat = await seed_feat(db_session, author=user)
    item = await seed_item(db_session, author=user)
    await expect(user, 200, {"operation_code": "grant", "feat_id": str(feat.id)})
    await expect(user, 200, {"operation_code": "grant", "granted_feature_id": str(
        srd_feature_id("class:Fighter/1/Second Wind"))})
    # An item is a valid target for a homebrew operation (only "at most one target").
    op = await seed_reference(db_session, EffectOperation, author=user)
    await expect(user, 200, {"operation_code": op.code, "item_id": str(item.id)})


# --- 422: operation x target (B13) ---------------------------------------------------

@pytest.mark.parametrize("effect", [
    {"operation_code": "bonus", "ability_code": "str", "value": 1},  # bonus needs target_code
    {"operation_code": "bonus", "target_code": "armor_class"},  # no value or formula
    {"operation_code": "bonus", "target_code": "armor_class", "value": 1, "skill_code": "stealth"},
    {"operation_code": "set", "target_code": "critical_range"},  # set needs value
    {"operation_code": "set", "target_code": "critical_range", "value": 19, "dice_count": 1, "die_size": 4},
    {"operation_code": "set", "value": 2},
    {"operation_code": "heal", "target_code": "armor_class", "value": 5},
    {"operation_code": "heal", "target_code": "hit_points"},
    {"operation_code": "grant", "target_code": "speed", "sense_code": "darkvision", "value": 60},
    {"operation_code": "grant"},  # grant needs a target or a choice
    {"operation_code": "grant", "skill_code": "stealth"},  # skills are granted through a choice/grant id
    {"operation_code": "grant", "sense_code": "darkvision"},  # sense without range
    {"operation_code": "grant", "choice": {"pool_type_code": "ability_score", "choose_count": 1}},
    {"operation_code": "expertise", "ability_code": "str"},
    {"operation_code": "expertise"},
    {"operation_code": "expertise", "choice": {"pool_type_code": "feat", "choose_count": 1}},
    {"operation_code": "ability_score_increase", "ability_code": "str"},  # needs value
    {"operation_code": "ability_score_increase", "skill_code": "stealth", "value": 1},
    {"operation_code": "ability_score_increase", "value": 1, "choice": {"pool_type_code": "skill",
                                                                         "choose_count": 1}},
    {"operation_code": "damage_resistance", "condition_code": "charmed"},
    {"operation_code": "damage_resistance"},
    {"operation_code": "damage_immunity", "target_code": "armor_class", "damage_type_code": "fire"},
    {"operation_code": "condition_immunity", "damage_type_code": "fire"},
    {"operation_code": "advantage", "skill_code": "athletics"},  # needs target_code
    {"operation_code": "advantage", "target_code": "armor_class", "skill_code": "athletics"},
    {"operation_code": "advantage", "target_code": "attack_roll", "ability_code": "str"},
    {"operation_code": "advantage", "target_code": "saving_throw", "damage_type_code": "fire"},
    {"operation_code": "spellcasting_ability", "choice": {"pool_type_code": "ability_score", "choose_count": 1}},
    {"operation_code": "spellcasting_ability", "ability_code": "int"},
    {"operation_code": "spell_list", "choice": {"pool_type_code": "spell_list", "choose_count": 1}},
])
async def test_incoherent_operation_and_target_is_422(db_session, user, effect, expect):
    await expect(user, 422, effect)


@pytest.mark.parametrize("effect", [
    {"operation_code": "grant", "sense_code": "truesight", "value": 60},
    {"operation_code": "grant", "movement_mode_code": "fly", "value": 30},
    {"operation_code": "grant", "choice": {"pool_type_code": "skill_or_tool", "choose_count": 3}},
    {"operation_code": "expertise", "skill_code": "stealth"},
    {"operation_code": "expertise", "choice": {"pool_type_code": "skill", "choose_count": 2}},
    {"operation_code": "ability_score_increase", "value": 1, "max_value": 30,
     "choice": {"pool_type_code": "ability_score", "choose_count": 1}},
    {"operation_code": "damage_immunity", "damage_type_code": "poison"},
    {"operation_code": "condition_immunity", "condition_code": "charmed"},
    {"operation_code": "advantage", "target_code": "saving_throw", "ability_code": "dex"},
    {"operation_code": "advantage", "target_code": "death_saving_throw"},
    {"operation_code": "bonus", "target_code": "initiative", "value_basis_code": "proficiency_bonus"},
    {"operation_code": "spellcasting_ability", "choice": {"pool_type_code": "ability_score", "choose_count": 1,
                                                          "options": [{"ability_code": "int"}]}},
    {"operation_code": "spell_list", "choice": {"pool_type_code": "spell_list", "choose_count": 1,
                                                "options": [{"spell_list_code": "cleric"}]}},
])
async def test_coherent_operation_and_target(db_session, user, effect, expect):
    await expect(user, 200, effect)


async def test_homebrew_target_code_is_only_checked_for_shape(db_session, user, expect):
    target = await seed_reference(db_session, EffectTarget, author=user)
    await expect(user, 200, {"operation_code": "advantage", "target_code": target.code,
                                         "skill_code": "athletics"})


# --- 422: choices (B14) ------------------------------------------------------------

def choice(pool: str, **extra) -> dict:
    return {"operation_code": "grant", "choice": {"pool_type_code": pool, "choose_count": 1, **extra}}


@pytest.mark.parametrize("effect", [
    choice("skill", options=[{"ability_code": "str"}]),
    choice("skill_or_tool", options=[{"spell_list_code": "wizard"}]),
    choice("skill", feat_category_code="origin"),
    choice("feat", spell_list_code="wizard"),
    choice("feat", spell_level=1),
    choice("skill", weapon_category_code="simple"),
    choice("feat", tool_category_code="gaming_set"),
    choice("spell", spell_list_from_effect_index=5),
])
async def test_incoherent_choice_is_422(db_session, user, effect, expect):
    await expect(user, 422, effect)


async def test_spell_list_from_must_point_to_a_spell_list_choice(db_session, user, submit):
    spell_list = {"operation_code": "spell_list", "choice": {"pool_type_code": "spell_list", "choose_count": 1,
                                                             "options": [{"spell_list_code": "cleric"},
                                                                         {"spell_list_code": "wizard"}]}}
    from_it = choice("spell", spell_level=0, spell_list_from_effect_index=0)
    assert await submit(user, [feat_feature(spell_list, from_it)]) == 200
    from_skill = choice("spell", spell_list_from_effect_index=0)
    assert await submit(user, [feat_feature(choice("skill"), from_skill)]) == 422
    itself = choice("spell", spell_list_from_effect_index=0)
    assert await submit(user, [feat_feature(itself)]) == 422


async def test_homebrew_pool_accepts_any_option(db_session, user, expect):
    pool = await seed_reference(db_session, ChoicePoolType, author=user)
    await expect(user, 200, {"operation_code": "grant", "choice": {
        "pool_type_code": pool.code, "choose_count": 1, "options": [{"skill_code": "stealth"}]}})


async def test_feature_option_pool(db_session, user, expect):
    target = await seed_feature(db_session, feat=await seed_feat(db_session, author=user), is_choice_option=True)
    await expect(user, 200, choice("feature", options=[{"feature_id": str(target.id)}]))


# --- 422: resources, scaling and replacement -----------------------------------------

async def test_resource_index_out_of_range_is_422(db_session, user, expect):
    await expect(user, 422, {"operation_code": "bonus", "target_code": "initiative", "value": 1,
                                         "resource_index": 0})


async def test_scaling_below_the_feature_level_is_422(db_session, user, submit):
    feature = class_feature({"operation_code": "bonus", "target_code": "armor_class", "value": 1,
                             "scaling": [{"level": 3, "value": 2}]}, level=5)
    assert await submit(user, [feature], "class") == 422
    feature["effects"][0]["scaling"] = [{"level": 5, "value": 2}]
    assert await submit(user, [feature], "class") == 200
    resource = class_feature(level=5, resources=[{"name": "Uses", "value": 1, "recharges": [
        {"recharge_type_code": "long_rest"}], "scaling": [{"level": 2, "value": 2}]}])
    assert await submit(user, [resource], "class") == 422
    chooser = class_feature(choice("skill", scaling=[{"level": 4, "value": 2}]), level=5)
    assert await submit(user, [chooser], "class") == 422


async def test_feat_scaling_from_level_one(db_session, user, submit):
    feature = feat_feature({"operation_code": "bonus", "target_code": "armor_class", "value": 1,
                            "scaling": [{"level": 1, "value": 2}]})
    assert await submit(user, [feature]) == 200


@pytest.mark.parametrize("features", [
    [class_feature(level=5), class_feature(level=11, replaces_index=2)],  # out of range
    [class_feature(level=5, replaces_index=0)],  # itself
    [class_feature(level=5), class_feature(level=5, replaces_index=0)],  # same level
    [class_feature(level=11), class_feature(level=5, replaces_index=0)],  # higher level
    # QA cycle 1: the replaced feature has no level (checked before comparing levels).
    [class_feature(level=5, replaces_index=1), feat_feature()],
    [feat_feature(), class_feature(level=5, replaces_index=0)],
])
@pytest.mark.parametrize("owner", ["class", "subclass"])
async def test_invalid_replacement_is_422(db_session, user, features, owner, submit):
    assert await submit(user, features, owner) == 422


async def test_feat_features_cannot_replace(db_session, user, submit):
    assert await submit(user, [feat_feature(), feat_feature(replaces_index=0)]) == 422
