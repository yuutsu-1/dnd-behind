"""Shape of the feature payloads (app/schemas/features.py): every shape rule is a 422
(`ValidationError`) before the endpoint looks at the database."""
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.features import EffectIn, FeatureIn, PrerequisiteIn, ResourceIn

# The example of the plan (B11): references inside the payload are positions.
FULL_FEATURES = [
    {"name": "Extra Attack", "level": 5,
     "effects": [{"operation_code": "set", "target_code": "attacks_per_action", "value": 2}]},
    {"name": "Two Extra Attacks", "level": 11, "replaces_index": 0,
     "effects": [{"operation_code": "set", "target_code": "attacks_per_action", "value": 3}]},
    {"name": "Second Wind", "level": 1, "action_type_code": "bonus_action",
     "effects": [{"operation_code": "heal", "target_code": "hit_points", "dice_count": 1, "die_size": 10,
                  "value_basis_code": "class_level", "resource_index": 0}],
     "resources": [{"name": "Second Wind", "value": 2,
                    "recharges": [{"recharge_type_code": "short_rest", "recovers": 1},
                                  {"recharge_type_code": "long_rest", "recovers": None}],
                    "scaling": [{"level": 4, "value": 3}, {"level": 10, "value": 4}]}]},
    {"name": "Weapon Mastery", "level": 1,
     "effects": [{"operation_code": "grant", "choice": {
         "pool_type_code": "weapon", "choose_count": 3, "swap_rule_code": "on_long_rest_one",
         "options": [{"item_id": str(uuid.uuid4())}, {"item_id": str(uuid.uuid4())}, {"item_id": str(uuid.uuid4())}],
         "scaling": [{"level": 4, "value": 4}]}}]},
]


def feature(**overrides) -> dict:
    return {"name": "Test Feature", **overrides}


def effect(**overrides) -> dict:
    return {"operation_code": "bonus", "target_code": "armor_class", "value": 1, **overrides}


def resource(**overrides) -> dict:
    return {"name": "Uses", "value": 1, "recharges": [{"recharge_type_code": "long_rest"}], **overrides}


def test_full_payload_validates():
    features = [FeatureIn.model_validate(f) for f in FULL_FEATURES]
    assert features[1].replaces_index == 0
    assert features[2].effects[0].resource_index == 0
    assert features[2].resources[0].recharges[1].recovers is None
    assert features[3].effects[0].choice.options[0].item_id is not None
    assert features[0].effects[0].value_multiplier == 1


# --- feature ----------------------------------------------------------------------

@pytest.mark.parametrize("level", [0, 21])
def test_level_out_of_range(level):
    with pytest.raises(ValidationError):
        FeatureIn.model_validate(feature(level=level))


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_name(name):
    with pytest.raises(ValidationError):
        FeatureIn.model_validate(feature(name=name))


@pytest.mark.parametrize("field,value", [
    ("id", str(uuid.uuid4())), ("source", "srd"), ("is_homebrew", False), ("created_by", str(uuid.uuid4())),
    ("class_id", str(uuid.uuid4())), ("subclass_id", str(uuid.uuid4())), ("feat_id", str(uuid.uuid4())),
    ("replaces_feature_id", str(uuid.uuid4())), ("sort_order", 3), ("effect_data", {}),
])
def test_forbidden_or_unknown_feature_fields(field, value):
    with pytest.raises(ValidationError):
        FeatureIn.model_validate(feature(**{field: value}))


def test_negative_replaces_index():
    with pytest.raises(ValidationError):
        FeatureIn.model_validate(feature(replaces_index=-1))


# --- effect -----------------------------------------------------------------------

def test_two_fixed_targets():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(skill_code="athletics", ability_code="str"))


def test_fixed_target_and_choice():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(operation_code="grant", target_code=None, skill_code="athletics",
                                       choice={"pool_type_code": "skill", "choose_count": 1}))


@pytest.mark.parametrize("dice", [{"dice_count": 1}, {"die_size": 6}])
def test_dice_go_together(dice):
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(**dice))


def test_die_size_must_be_a_real_die():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(dice_count=1, die_size=7))


def test_ability_modifier_needs_the_ability():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(value_basis_code="ability_modifier"))
    EffectIn.model_validate(effect(value_basis_code="ability_modifier", value_basis_ability_code="con"))


def test_basis_ability_needs_a_basis():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(value_basis_ability_code="con"))


def test_min_greater_than_max():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(min_value=5, max_value=4))


@pytest.mark.parametrize("field,value", [
    ("id", str(uuid.uuid4())), ("feature_id", str(uuid.uuid4())), ("resource_id", str(uuid.uuid4())),
    ("sort_order", 0), ("effect_type", "bonus"),
])
def test_forbidden_effect_fields(field, value):
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(**{field: value}))


def test_effect_scaling_with_duplicate_level():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(scaling=[{"level": 5, "value": 2}, {"level": 5, "value": 3}]))


@pytest.mark.parametrize("row", [{"level": 5}, {"level": 5, "dice_count": 2}, {"level": 0, "value": 1}])
def test_invalid_scaling_rows(row):
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(scaling=[row]))


def test_condition_text_must_not_be_blank():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(effect(condition_text="  "))


# --- choice and options -------------------------------------------------------------

def choice_effect(**choice) -> dict:
    return {"operation_code": "grant", "choice": {"pool_type_code": "skill", "choose_count": 1, **choice}}


def test_choose_count_at_least_one():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(choice_effect(choose_count=0))


@pytest.mark.parametrize("option", [{}, {"skill_code": "athletics", "ability_code": "str"}])
def test_option_needs_exactly_one_target(option):
    with pytest.raises(ValidationError):
        EffectIn.model_validate(choice_effect(options=[option]))


def test_duplicate_options():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(choice_effect(options=[{"skill_code": "athletics"}, {"skill_code": "athletics"}]))


def test_choose_more_than_the_options_without_repeat():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(choice_effect(choose_count=2, options=[{"skill_code": "athletics"}]))
    EffectIn.model_validate(choice_effect(choose_count=2, allow_repeat=True, options=[{"skill_code": "athletics"}]))
    EffectIn.model_validate(choice_effect(choose_count=2))  # no options: the whole pool


@pytest.mark.parametrize("level", [-1, 10])
def test_spell_level_range(level):
    with pytest.raises(ValidationError):
        EffectIn.model_validate(choice_effect(spell_level=level))


def test_choice_scaling_with_duplicate_level():
    with pytest.raises(ValidationError):
        EffectIn.model_validate(choice_effect(scaling=[{"level": 4, "value": 2}, {"level": 4, "value": 3}]))


@pytest.mark.parametrize("field", ["spell_list_from_choice_id", "effect_id", "id"])
def test_forbidden_choice_fields(field):
    with pytest.raises(ValidationError):
        EffectIn.model_validate(choice_effect(**{field: str(uuid.uuid4())}))


# --- resource and recharges ---------------------------------------------------------

def test_resource_needs_a_recharge():
    with pytest.raises(ValidationError):
        ResourceIn.model_validate(resource(recharges=[]))
    with pytest.raises(ValidationError):
        ResourceIn.model_validate({"name": "Uses", "value": 1})


def test_recovers_at_least_one():
    with pytest.raises(ValidationError):
        ResourceIn.model_validate(resource(recharges=[{"recharge_type_code": "long_rest", "recovers": 0}]))


def test_duplicate_recharge_type():
    with pytest.raises(ValidationError):
        ResourceIn.model_validate(resource(recharges=[{"recharge_type_code": "long_rest"},
                                                      {"recharge_type_code": "long_rest", "recovers": 1}]))


def test_resource_needs_uses():
    with pytest.raises(ValidationError):
        ResourceIn.model_validate(resource(value=None))
    ResourceIn.model_validate(resource(value=None, value_basis_code="proficiency_bonus"))


def test_resource_ability_modifier_needs_the_ability():
    with pytest.raises(ValidationError):
        ResourceIn.model_validate(resource(value=None, value_basis_code="ability_modifier"))


def test_resource_scaling_with_duplicate_level():
    with pytest.raises(ValidationError):
        ResourceIn.model_validate(resource(scaling=[{"level": 4, "value": 2}, {"level": 4, "value": 3}]))


def test_resource_name_is_required():
    with pytest.raises(ValidationError):
        ResourceIn.model_validate(resource(name=""))


# --- prerequisites ------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"or_group": 1},
    {"or_group": 1, "min_character_level": 4, "feature_kind_code": "fighting_style"},
    {"or_group": 1, "ability_code": "str"},
    {"or_group": 1, "min_score": 13},
    {"or_group": 1, "ability_code": "str", "min_score": 0},
    {"or_group": 1, "ability_code": "str", "min_score": 31},
    {"or_group": 1, "min_character_level": 21},
    {"or_group": 0, "min_character_level": 4},
    {"or_group": 1, "min_character_level": 4, "id": str(uuid.uuid4())},
])
def test_invalid_prerequisites(payload):
    with pytest.raises(ValidationError):
        PrerequisiteIn.model_validate(payload)


@pytest.mark.parametrize("payload", [
    {"or_group": 1, "min_character_level": 4},
    {"or_group": 2, "ability_code": "str", "min_score": 13},
    {"or_group": 1, "feature_kind_code": "spellcasting"},
])
def test_valid_prerequisites(payload):
    PrerequisiteIn.model_validate(payload)
