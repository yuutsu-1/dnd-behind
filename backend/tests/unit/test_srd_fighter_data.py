"""The generated SRD Fighter/Champion data (app/db/seed/srd_fighter.py), checked
against fixed numbers taken from classes.md by hand (no test reads the SRD files).
Gate #2: H5 (Survivor's "Defy Death" is an advantage on death saving throws) and H6
(no category filter on the Fighter's Ability Score Improvement / Epic Boon)."""
from collections import Counter

import pytest

from app.db.seed.srd_fighter import CLASS, SUBCLASSES

(CHAMPION,) = SUBCLASSES
OWNERS = {"Fighter": CLASS, "Champion": CHAMPION}

# Every SRD item name used by the class equipment (all seeded by the squash).
SRD_ITEM_NAMES = {
    "Chain Mail", "Greatsword", "Flail", "Javelin", "Dungeoneer's Pack", "Gold Piece", "Studded Leather Armor",
    "Scimitar", "Shortsword", "Longbow", "Arrow", "Quiver",
}


def _all_features():
    return list(CLASS["features"]) + list(CHAMPION["features"])


def _effects(features=None):
    return [effect for feature in (features or _all_features()) for effect in feature["effects"]]


def _choices():
    return [effect["choice"] for effect in _effects() if "choice" in effect]


def _resources():
    return [resource for feature in _all_features() for resource in feature["resources"]]


def _one(owner: str, name: str) -> dict:
    (feature,) = [f for f in OWNERS[owner]["features"] if f["name"] == name]
    return feature


# --- class traits -------------------------------------------------------------------

def test_fighter_traits():
    assert CLASS["name"] == "Fighter"
    assert CLASS["description"] is None
    assert CLASS["hit_die"] == 10
    assert CLASS["primary_ability"] == ("dex", "str")
    assert CLASS["skill_choices"] == 2
    assert CLASS["skills"] == (
        "acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "perception",
        "persuasion", "survival",
    )
    assert CLASS["subclass_level"] == 3
    assert CLASS["spell_ability"] is None and CLASS["spellcasting_type"] is None


def test_fighter_8_grants():
    assert CLASS["proficiency_grants"] == (
        {"saving_throw_ability_code": "str"}, {"saving_throw_ability_code": "con"},
        {"weapon_category_code": "simple"}, {"weapon_category_code": "martial"},
        {"armor_category_code": "light"}, {"armor_category_code": "medium"}, {"armor_category_code": "heavy"},
        {"armor_category_code": "shield"},
    )


def test_fighter_15_equipment_rows():
    rows = [(e["option"], e["item"], e["quantity"]) for e in CLASS["initial_equipment"]]
    assert rows == [
        ("A", "Chain Mail", 1), ("A", "Greatsword", 1), ("A", "Flail", 1), ("A", "Javelin", 8),
        ("A", "Dungeoneer's Pack", 1), ("A", "Gold Piece", 4),
        ("B", "Studded Leather Armor", 1), ("B", "Scimitar", 1), ("B", "Shortsword", 1), ("B", "Longbow", 1),
        ("B", "Arrow", 20), ("B", "Quiver", 1), ("B", "Dungeoneer's Pack", 1), ("B", "Gold Piece", 11),
        ("C", "Gold Piece", 155),
    ]
    assert {e["item"] for e in CLASS["initial_equipment"]} <= SRD_ITEM_NAMES


# --- features -----------------------------------------------------------------------

def test_20_fighter_features_by_level():
    assert Counter(f["level"] for f in CLASS["features"]) == {
        1: 3, 2: 2, 3: 1, 4: 1, 5: 2, 6: 1, 8: 1, 9: 2, 11: 1, 12: 1, 13: 1, 14: 1, 16: 1, 19: 1, 20: 1,
    }
    assert len(CLASS["features"]) == 20
    assert [f["level"] for f in CLASS["features"] if f["name"] == "Ability Score Improvement"] == [
        4, 6, 8, 12, 14, 16,
    ]


def test_fighter_feature_names():
    assert [(f["level"], f["name"]) for f in CLASS["features"]] == [
        (1, "Fighting Style"), (1, "Second Wind"), (1, "Weapon Mastery"), (2, "Action Surge"),
        (2, "Tactical Mind"), (3, "Fighter Subclass"), (4, "Ability Score Improvement"), (5, "Extra Attack"),
        (5, "Tactical Shift"), (6, "Ability Score Improvement"), (8, "Ability Score Improvement"),
        (9, "Indomitable"), (9, "Tactical Master"), (11, "Two Extra Attacks"), (12, "Ability Score Improvement"),
        (13, "Studied Attacks"), (14, "Ability Score Improvement"), (16, "Ability Score Improvement"),
        (19, "Epic Boon"), (20, "Three Extra Attacks"),
    ]


def test_6_champion_features():
    assert CHAMPION["name"] == "Champion"
    assert CHAMPION["class"] == "Fighter"
    assert [(f["level"], f["name"]) for f in CHAMPION["features"]] == [
        (3, "Improved Critical"), (3, "Remarkable Athlete"), (7, "Additional Fighting Style"), (10, "Heroic Warrior"),
        (15, "Superior Critical"), (18, "Survivor"),
    ]
    assert CHAMPION["description"].startswith("_Pursue Physical Excellence in Combat_\n\nA Champion focuses")


def test_totals():
    assert len(_effects(CLASS["features"])) == 13
    assert len(_effects(CHAMPION["features"])) == 6
    assert len(_effects()) == 19
    assert len(_choices()) == 10
    assert sum(len(choice.get("options", ())) for choice in _choices()) == 0
    assert len(_resources()) == 3
    assert sum(len(resource["recharges"]) for resource in _resources()) == 5
    scaling = sum(len(r.get("scaling", ())) for r in _resources()) + sum(len(c.get("scaling", ())) for c in _choices())
    scaling += sum(len(e.get("scaling", ())) for e in _effects())
    assert scaling == 8
    assert sum(1 for f in _all_features() if f["replaces"]) == 3
    assert sorted(f["name"] for f in _all_features() if f["feature_kind_code"] == "fighting_style") == [
        "Additional Fighting Style", "Fighting Style",
    ]
    assert [(f["name"], f["action_type_code"]) for f in _all_features() if f["action_type_code"]] == [
        ("Second Wind", "bonus_action"),
    ]


def test_text_only_features():
    text_only = sorted(f["name"] for f in _all_features() if not f["effects"] and not f["resources"])
    assert text_only == sorted([
        "Tactical Mind", "Fighter Subclass", "Tactical Shift", "Tactical Master", "Studied Attacks",
        "Heroic Warrior",
    ])


def test_every_feature_has_a_level_and_replaces_a_lower_one_of_the_same_owner():
    for owner in OWNERS.values():
        keys = {(f["name"], f["level"]) for f in owner["features"]}
        for feature in owner["features"]:
            assert 1 <= feature["level"] <= 20
            if feature["replaces"]:
                assert feature["replaces"] in keys
                assert feature["replaces"][1] < feature["level"]


def test_fighting_style():
    feature = _one("Fighter", "Fighting Style")
    assert feature["feature_kind_code"] == "fighting_style"
    assert feature["effects"] == ({"operation_code": "grant", "choice": {
        "pool_type_code": "feat", "choose_count": 1, "feat_category_code": "fighting_style",
        "swap_rule_code": "on_class_level_up",
    }},)


def test_second_wind():
    feature = _one("Fighter", "Second Wind")
    assert feature["action_type_code"] == "bonus_action"
    assert feature["effects"] == ({
        "operation_code": "heal", "target_code": "hit_points", "dice_count": 1, "die_size": 10,
        "value_basis_code": "class_level",
    },)
    (resource,) = feature["resources"]
    assert resource["name"] == "Second Wind"
    assert resource["value"] == 2
    assert resource["recharges"] == (
        {"recharge_type_code": "short_rest", "recovers": 1}, {"recharge_type_code": "long_rest", "recovers": None},
    )
    assert resource["scaling"] == ({"level": 4, "value": 3}, {"level": 10, "value": 4})


def test_weapon_mastery():
    (effect,) = _one("Fighter", "Weapon Mastery")["effects"]
    assert effect["operation_code"] == "grant"
    assert effect["choice"] == {
        "pool_type_code": "weapon", "swap_rule_code": "on_long_rest_one", "choose_count": 3,
        "scaling": ({"level": 4, "value": 4}, {"level": 10, "value": 5}, {"level": 16, "value": 6}),
    }


def test_action_surge():
    feature = _one("Fighter", "Action Surge")
    assert feature["effects"] == ()
    (resource,) = feature["resources"]
    assert resource["value"] == 1
    assert resource["recharges"] == (
        {"recharge_type_code": "short_rest", "recovers": None}, {"recharge_type_code": "long_rest", "recovers": None},
    )
    assert resource["scaling"] == ({"level": 17, "value": 2},)


def test_indomitable():
    (resource,) = _one("Fighter", "Indomitable")["resources"]
    assert resource["value"] == 1
    assert resource["recharges"] == ({"recharge_type_code": "long_rest", "recovers": None},)
    assert resource["scaling"] == ({"level": 13, "value": 2}, {"level": 17, "value": 3})


@pytest.mark.parametrize("level", [4, 6, 8, 12, 14, 16])
def test_ability_score_improvement_is_a_feat_choice_without_filter(level):
    (feature,) = [f for f in CLASS["features"] if f["name"] == "Ability Score Improvement" and f["level"] == level]
    assert feature["effects"] == ({"operation_code": "grant", "choice": {"pool_type_code": "feat", "choose_count": 1}},)


def test_asi_descriptions_are_the_same():
    descriptions = {f["description"] for f in CLASS["features"] if f["name"] == "Ability Score Improvement"}
    assert len(descriptions) == 1


def test_epic_boon():
    assert _one("Fighter", "Epic Boon")["effects"] == (
        {"operation_code": "grant", "choice": {"pool_type_code": "feat", "choose_count": 1}},
    )


@pytest.mark.parametrize("name,attacks,replaces", [
    ("Extra Attack", 2, None), ("Two Extra Attacks", 3, ("Extra Attack", 5)),
    ("Three Extra Attacks", 4, ("Two Extra Attacks", 11)),
])
def test_extra_attacks(name, attacks, replaces):
    feature = _one("Fighter", name)
    assert feature["effects"] == ({"operation_code": "set", "target_code": "attacks_per_action", "value": attacks},)
    assert feature["replaces"] == replaces


@pytest.mark.parametrize("name,critical,replaces", [
    ("Improved Critical", 19, None), ("Superior Critical", 18, ("Improved Critical", 3)),
])
def test_critical(name, critical, replaces):
    feature = _one("Champion", name)
    assert feature["effects"] == ({
        "operation_code": "set", "target_code": "critical_range", "value": critical,
        "condition_text": "with weapons and Unarmed Strikes",
    },)
    assert feature["replaces"] == replaces


def test_remarkable_athlete():
    assert _one("Champion", "Remarkable Athlete")["effects"] == (
        {"operation_code": "advantage", "target_code": "initiative"},
        {"operation_code": "advantage", "target_code": "ability_check", "skill_code": "athletics"},
    )


def test_additional_fighting_style():
    feature = _one("Champion", "Additional Fighting Style")
    assert feature["feature_kind_code"] == "fighting_style"
    assert feature["effects"] == ({"operation_code": "grant", "choice": {
        "pool_type_code": "feat", "choose_count": 1, "feat_category_code": "fighting_style",
    }},)


def test_survivor_defy_death_is_structured_and_the_text_keeps_both_blocks():
    feature = _one("Champion", "Survivor")
    assert feature["effects"] == ({"operation_code": "advantage", "target_code": "death_saving_throw"},)
    assert feature["resources"] == ()
    assert "_Defy Death._" in feature["description"] and "_Heroic Rally._" in feature["description"]


def test_feature_descriptions_have_no_heading():
    for feature in _all_features():
        assert feature["description"]
        assert not feature["description"].startswith("Level ")
        assert "####" not in feature["description"]
