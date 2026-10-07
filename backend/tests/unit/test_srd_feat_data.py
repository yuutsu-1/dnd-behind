"""The generated SRD feat data (app/db/seed/srd_feats.py), checked against fixed
numbers taken from feats.md by hand (no test reads the SRD files)."""
from collections import Counter

import pytest

from app.db.seed.srd_feats import FEATS

BY_NAME = {feat["name"]: feat for feat in FEATS}


def _features():
    return [feature for feat in FEATS for feature in feat["features"]]


def _effects():
    return [effect for feature in _features() for effect in feature["effects"]]


def _choices():
    return [effect["choice"] for effect in _effects() if "choice" in effect]


def _resources():
    return [resource for feature in _features() for resource in feature["resources"]]


def _feature(feat: str, name: str) -> dict:
    (feature,) = [f for f in BY_NAME[feat]["features"] if f["name"] == name]
    return feature


def _prereqs(feat: str) -> list[tuple]:
    return [
        (p["or_group"], p["min_character_level"], p["ability_code"], p["min_score"], p["feature_kind_code"])
        for p in BY_NAME[feat]["prerequisites"]
    ]


def test_17_feats_with_unique_names():
    assert len(FEATS) == 17
    assert len(BY_NAME) == 17


def test_categories():
    assert Counter(feat["category_code"] for feat in FEATS) == {
        "origin": 4, "general": 2, "fighting_style": 4, "epic_boon": 7,
    }


def test_3_repeatable():
    assert sorted(feat["name"] for feat in FEATS if feat["repeatable"]) == [
        "Ability Score Improvement", "Magic Initiate", "Skilled",
    ]


def test_13_feats_with_prerequisites_and_16_rows():
    assert sum(1 for feat in FEATS if feat["prerequisites"]) == 13
    assert sum(len(feat["prerequisites"]) for feat in FEATS) == 16


def test_totals():
    assert len(_features()) == 32
    assert len(_effects()) == 26
    assert len(_choices()) == 10
    assert sum(len(choice.get("options", ())) for choice in _choices()) == 7
    assert len(_resources()) == 1
    assert sum(len(resource["recharges"]) for resource in _resources()) == 3
    scaling = sum(len(e.get("scaling", ())) for e in _effects()) + sum(len(c.get("scaling", ())) for c in _choices())
    scaling += sum(len(r.get("scaling", ())) for r in _resources())
    assert scaling == 0
    assert [(f["name"], f["action_type_code"]) for f in _features() if f["action_type_code"]] == [
        ("Merge with Shadows", "bonus_action"),
    ]


def test_feat_features_have_no_level_and_replace_nothing():
    for feature in _features():
        assert feature["level"] is None
        assert feature["replaces"] is None
        assert feature["feature_kind_code"] is None
        assert feature["is_choice_option"] is False


@pytest.mark.parametrize("feat,count", [
    ("Alert", 2), ("Magic Initiate", 3), ("Savage Attacker", 1), ("Skilled", 1), ("Ability Score Improvement", 1),
    ("Grappler", 4), ("Archery", 1), ("Defense", 1), ("Great Weapon Fighting", 1), ("Two-Weapon Fighting", 1),
    ("Boon of Combat Prowess", 2), ("Boon of Dimensional Travel", 2), ("Boon of Fate", 2),
    ("Boon of Irresistible Offense", 3), ("Boon of Spell Recall", 2), ("Boon of the Night Spirit", 3),
    ("Boon of Truesight", 2),
])
def test_features_per_feat(feat, count):
    assert len(BY_NAME[feat]["features"]) == count


def test_alert():
    assert [f["name"] for f in BY_NAME["Alert"]["features"]] == ["Initiative Proficiency", "Initiative Swap"]
    assert _feature("Alert", "Initiative Proficiency")["effects"] == ({
        "operation_code": "bonus", "target_code": "initiative", "value_basis_code": "proficiency_bonus",
    },)
    assert _feature("Alert", "Initiative Swap")["effects"] == ()
    assert BY_NAME["Alert"]["description"] == "You gain the following benefits."
    assert _feature("Alert", "Initiative Proficiency")["description"].startswith("When you roll Initiative")


def test_grappler():
    assert _prereqs("Grappler") == [(1, 4, None, None, None), (2, None, "str", 13, None), (2, None, "dex", 13, None)]
    assert [f["name"] for f in BY_NAME["Grappler"]["features"]] == [
        "Ability Score Increase", "Punch and Grab", "Attack Advantage", "Fast Wrestler",
    ]
    (asi,) = _feature("Grappler", "Ability Score Increase")["effects"]
    assert asi["operation_code"] == "ability_score_increase"
    assert (asi["value"], asi["max_value"]) == (1, 20)
    assert asi["choice"]["pool_type_code"] == "ability_score"
    assert asi["choice"]["choose_count"] == 1
    assert sorted(o["ability_code"] for o in asi["choice"]["options"]) == ["dex", "str"]
    assert _feature("Grappler", "Attack Advantage")["effects"] == ({
        "operation_code": "advantage", "target_code": "attack_roll",
        "condition_text": "against a creature Grappled by you",
    },)
    assert _feature("Grappler", "Punch and Grab")["effects"] == ()
    assert _feature("Grappler", "Fast Wrestler")["effects"] == ()


def test_archery():
    assert _prereqs("Archery") == [(1, None, None, None, "fighting_style")]
    assert _feature("Archery", "Archery")["effects"] == ({
        "operation_code": "bonus", "target_code": "attack_roll", "value": 2, "condition_text": "with Ranged weapons",
    },)


def test_defense():
    assert _feature("Defense", "Defense")["effects"] == ({
        "operation_code": "bonus", "target_code": "armor_class", "value": 1,
        "condition_text": "while wearing Light, Medium, or Heavy armor",
    },)


@pytest.mark.parametrize("feat", ["Great Weapon Fighting", "Two-Weapon Fighting", "Savage Attacker"])
def test_text_only_single_feature_feats(feat):
    (feature,) = BY_NAME[feat]["features"]
    assert feature["name"] == feat
    assert feature["effects"] == () and feature["resources"] == ()
    assert feature["description"] == BY_NAME[feat]["description"]


def test_savage_attacker_text():
    assert BY_NAME["Savage Attacker"]["description"].startswith("You've trained to deal particularly damaging strikes.")


def test_four_fighting_styles_require_the_feature_kind():
    styles = [feat for feat in FEATS if feat["category_code"] == "fighting_style"]
    assert len(styles) == 4
    for feat in styles:
        assert _prereqs(feat["name"]) == [(1, None, None, None, "fighting_style")]


def test_ability_score_improvement():
    feat = BY_NAME["Ability Score Improvement"]
    assert feat["repeatable"] is True
    assert _prereqs("Ability Score Improvement") == [(1, 4, None, None, None)]
    (effect,) = _feature("Ability Score Improvement", "Ability Score Improvement")["effects"]
    assert effect["operation_code"] == "ability_score_increase"
    assert (effect["value"], effect["max_value"]) == (1, 20)
    assert effect["choice"] == {"pool_type_code": "ability_score", "choose_count": 2, "allow_repeat": True}


def test_skilled():
    assert BY_NAME["Skilled"]["repeatable"] is True
    (effect,) = _feature("Skilled", "Skilled")["effects"]
    assert effect == {"operation_code": "grant", "choice": {"pool_type_code": "skill_or_tool", "choose_count": 3}}
    assert BY_NAME["Skilled"]["description"].endswith("You can take this feat more than once.")


def test_seven_boons_require_level_19_and_have_an_asi_capped_at_30():
    boons = [feat for feat in FEATS if feat["category_code"] == "epic_boon"]
    assert len(boons) == 7
    for feat in boons:
        assert _prereqs(feat["name"])[0] == (1, 19, None, None, None)
        (effect,) = _feature(feat["name"], "Ability Score Increase")["effects"]
        assert effect["operation_code"] == "ability_score_increase"
        assert (effect["value"], effect["max_value"]) == (1, 30)
        assert effect["choice"]["choose_count"] == 1


def test_boon_of_truesight():
    (asi,) = _feature("Boon of Truesight", "Ability Score Increase")["effects"]
    assert "options" not in asi["choice"]
    assert _feature("Boon of Truesight", "Truesight")["effects"] == ({
        "operation_code": "grant", "sense_code": "truesight", "value": 60,
    },)


def test_boon_of_fate():
    improve = _feature("Boon of Fate", "Improve Fate")
    assert improve["effects"] == ()
    (resource,) = improve["resources"]
    assert resource["name"] == "Improve Fate"
    assert resource["value"] == 1
    assert resource["recharges"] == (
        {"recharge_type_code": "initiative", "recovers": None},
        {"recharge_type_code": "short_rest", "recovers": None},
        {"recharge_type_code": "long_rest", "recovers": None},
    )


def test_boon_of_spell_recall():
    assert _prereqs("Boon of Spell Recall") == [(1, 19, None, None, None), (2, None, None, None, "spellcasting")]
    (asi,) = _feature("Boon of Spell Recall", "Ability Score Increase")["effects"]
    assert sorted(o["ability_code"] for o in asi["choice"]["options"]) == ["cha", "int", "wis"]


def test_boon_of_irresistible_offense_options():
    (asi,) = _feature("Boon of Irresistible Offense", "Ability Score Increase")["effects"]
    assert sorted(o["ability_code"] for o in asi["choice"]["options"]) == ["dex", "str"]


def test_boon_of_the_night_spirit():
    shadowy = _feature("Boon of the Night Spirit", "Shadowy Form")["effects"]
    assert len(shadowy) == 11
    assert {e["operation_code"] for e in shadowy} == {"damage_resistance"}
    assert {e["condition_text"] for e in shadowy} == {"while within Dim Light or Darkness"}
    assert sorted(e["damage_type_code"] for e in shadowy) == [
        "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison", "slashing",
        "thunder",
    ]
    merge = _feature("Boon of the Night Spirit", "Merge with Shadows")
    assert merge["action_type_code"] == "bonus_action"
    assert merge["effects"] == ()


def test_magic_initiate_is_text_only():
    feat = BY_NAME["Magic Initiate"]
    assert [f["name"] for f in feat["features"]] == ["Two Cantrips", "Level 1 Spell", "Spell Change"]
    for feature in feat["features"]:
        assert feature["effects"] == () and feature["resources"] == ()
    assert feat["description"].endswith("you must choose a different spell list each time.")
