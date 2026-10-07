"""The SRD feat extractor (scripts/extract_srd_feats.py), fed only with synthetic
markdown written here: no test reads the SRD files."""
import pytest

from scripts.extract_srd_feats import FeatExtractionError, parse_feats, render_module

SECTION = "### Origin Feats\n\n"


def feat_md(name="Test Feat", category="_Origin Feat_", body="You gain a test benefit.") -> str:
    return f"#### {name}\n\n{category}\n\n{body}\n\n"


def parse(*feats: str, curated=None) -> list[dict]:
    text = "# Feats\n\n### Parts of a Feat\n\n_Category._ Ignored intro.\n\n" + SECTION + "".join(feats)
    return parse_feats(text, curated={} if curated is None else curated)


def one(*args, curated=None, **kwargs) -> dict:
    feats = parse(feat_md(*args, **kwargs), curated=curated)
    assert len(feats) == 1
    return feats[0]


def _prereqs(feat) -> list[tuple]:
    return [
        (p["or_group"], p["min_character_level"], p["ability_code"], p["min_score"], p["feature_kind_code"])
        for p in feat["prerequisites"]
    ]


# --- category and prerequisites -------------------------------------------------------

@pytest.mark.parametrize("line,code", [
    ("_Origin Feat_", "origin"),
    ("_General Feat (Prerequisite: Level 4+)_", "general"),
    ("_Fighting Style Feat (Prerequisite: Fighting Style Feature)_", "fighting_style"),
    ("_Epic Boon Feat (Prerequisite: Level 19+)_", "epic_boon"),
])
def test_category(line, code):
    assert one(category=line)["category_code"] == code


def test_feat_without_prerequisite():
    feat = one(category="_Origin Feat_")
    assert feat["prerequisites"] == ()


def test_level_prerequisite():
    feat = one(category="_General Feat (Prerequisite: Level 4+)_")
    assert _prereqs(feat) == [(1, 4, None, None, None)]


def test_level_and_ability_alternatives_are_two_groups_and_three_rows():
    feat = one(category="_General Feat (Prerequisite: Level 4+, Strength or Dexterity 13+)_")
    assert _prereqs(feat) == [(1, 4, None, None, None), (2, None, "str", 13, None), (2, None, "dex", 13, None)]


def test_feature_kind_prerequisite():
    feat = one(category="_Fighting Style Feat (Prerequisite: Fighting Style Feature)_")
    assert _prereqs(feat) == [(1, None, None, None, "fighting_style")]


def test_level_and_spellcasting_feature():
    feat = one(category="_Epic Boon Feat (Prerequisite: Level 19+, Spellcasting Feature)_")
    assert _prereqs(feat) == [(1, 19, None, None, None), (2, None, None, None, "spellcasting")]


@pytest.mark.parametrize("prerequisite", [
    "Level Four", "Strength 13", "Wizard Class", "Dancing Feature", "Charm or Luck 13+", "",
])
def test_prerequisite_outside_the_grammar_raises(prerequisite):
    with pytest.raises(FeatExtractionError, match="Test Feat"):
        one(category=f"_General Feat (Prerequisite: {prerequisite})_")


def test_unknown_category_raises():
    with pytest.raises(FeatExtractionError, match="Test Feat"):
        one(category="_Racial Feat_")


def test_missing_category_line_raises():
    with pytest.raises(FeatExtractionError, match="Test Feat"):
        one(category="You gain a benefit.")


# --- blocks and features ---------------------------------------------------------

def test_blocks_become_features_and_the_intro_is_the_description():
    feat = one(body=(
        "You gain the following benefits.\n\n"
        "_First Benefit._ The first text.\n\n"
        "_Second Benefit._ The second text."
    ))
    assert feat["description"] == "You gain the following benefits."
    assert [(f["name"], f["description"]) for f in feat["features"]] == [
        ("First Benefit", "The first text."), ("Second Benefit", "The second text."),
    ]
    assert feat["repeatable"] is False
    for feature in feat["features"]:
        assert feature["level"] is None
        assert feature["effects"] == () and feature["resources"] == ()
        assert feature["action_type_code"] is None


def test_feat_without_blocks_is_one_feature_with_the_feat_name_and_text():
    feat = one(name="Lone Feat", body="A single paragraph.\n\nA second paragraph.")
    assert feat["description"] == "A single paragraph.\n\nA second paragraph."
    assert [(f["name"], f["description"]) for f in feat["features"]] == [
        ("Lone Feat", "A single paragraph.\n\nA second paragraph."),
    ]


def test_repeatable_block_is_not_a_feature_and_goes_to_the_end_of_the_description():
    feat = one(body=(
        "You gain the following benefits.\n\n"
        "_Benefit._ The text.\n\n"
        "_Repeatable._ You can take this feat more than once, but differently each time."
    ))
    assert feat["repeatable"] is True
    assert [f["name"] for f in feat["features"]] == ["Benefit"]
    assert feat["description"] == (
        "You gain the following benefits.\n\nYou can take this feat more than once, but differently each time."
    )


def test_repeatable_feat_without_other_blocks():
    feat = one(name="Again", body="Gain something.\n\n_Repeatable._ You can take this feat more than once.")
    assert feat["repeatable"] is True
    assert feat["description"] == "Gain something.\n\nYou can take this feat more than once."
    assert [(f["name"], f["description"]) for f in feat["features"]] == [("Again", "Gain something.")]


def test_malformed_italic_block_raises():
    with pytest.raises(FeatExtractionError, match="Test Feat"):
        one(body="_Broken block without period_ text.")


def test_duplicate_feat_name_raises():
    with pytest.raises(FeatExtractionError, match="Twin"):
        parse(feat_md(name="Twin"), feat_md(name="Twin"))


def test_category_sections_are_skipped():
    feats = parse(feat_md(name="A"), "### General Feats\n\n", feat_md(name="B", category="_General Feat_"))
    assert [(f["name"], f["category_code"]) for f in feats] == [("A", "origin"), ("B", "general")]


def test_text_before_the_origin_section_is_ignored():
    text = "# Feats\n\n#### Not A Feat\n\nStuff.\n\n" + SECTION + feat_md(name="Real")
    assert [f["name"] for f in parse_feats(text, curated={})] == ["Real"]


# --- curated structure -------------------------------------------------------------

def test_curated_entry_is_applied_to_its_feature():
    curated = {
        ("Test Feat", "Benefit"): dict(
            action_type_code="bonus_action",
            effects=[dict(operation_code="bonus", target_code="armor_class", value=1)],
            resources=[dict(name="Uses", value=1, recharges=[dict(recharge_type_code="long_rest", recovers=None)])],
        ),
    }
    feat = one(body="Intro.\n\n_Benefit._ Text.\n\n_Other._ More.", curated=curated)
    benefit, other = feat["features"]
    assert benefit["action_type_code"] == "bonus_action"
    assert benefit["effects"] == ({"operation_code": "bonus", "target_code": "armor_class", "value": 1},)
    assert benefit["resources"][0]["name"] == "Uses"
    assert benefit["resources"][0]["recharges"] == ({"recharge_type_code": "long_rest", "recovers": None},)
    assert other["effects"] == () and other["resources"] == ()


def test_curated_entry_without_feature_raises():
    curated = {("Test Feat", "Missing"): dict(effects=[dict(operation_code="bonus", target_code="initiative")])}
    with pytest.raises(FeatExtractionError, match="Missing"):
        one(body="Intro.\n\n_Benefit._ Text.", curated=curated)


def test_curated_entry_with_unknown_key_raises():
    curated = {("Test Feat", "Benefit"): dict(effects=[dict(operation_code="bonus", effect_data={})])}
    with pytest.raises(FeatExtractionError, match="effect_data"):
        one(body="Intro.\n\n_Benefit._ Text.", curated=curated)


# --- output ---------------------------------------------------------------------

def test_render_module_round_trips():
    feats = parse(feat_md(name="Alpha", category="_General Feat (Prerequisite: Level 4+)_"))
    namespace: dict = {}
    exec(render_module(feats), namespace)  # noqa: S102 - generated data module
    assert namespace["FEATS"] == tuple(feats)
    assert "não editar à mão" in render_module(feats)
