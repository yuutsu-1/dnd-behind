"""The generated SRD spell module (app/db/seed/srd_spells.py), checked against the fixed
numbers and values of the phase 3 plan. Nothing here reads the SRD markdown."""
from collections import Counter

import pytest

from app.db.seed.srd_spells import SPELLS

BY_NAME = {spell["name"]: spell for spell in SPELLS}


def spell(name: str) -> dict:
    return BY_NAME[name]


def materials(name: str) -> list[tuple]:
    return [
        (m["cost_gp"], m["consumed"], m["per_target"], m["quantity"]) for m in spell(name)["materials"]
    ]


# --- general counts ---------------------------------------------------------------

def test_339_spells_with_unique_names():
    assert len(SPELLS) == 339
    assert len(BY_NAME) == 339


def test_27_cantrips():
    assert sum(1 for s in SPELLS if s["level"] == 0) == 27


def test_29_rituals():
    assert sum(1 for s in SPELLS if s["ritual"]) == 29


def test_133_concentration_and_it_matches_the_duration_text():
    assert sum(1 for s in SPELLS if s["concentration"]) == 133
    for s in SPELLS:
        assert s["concentration"] is s["duration"].startswith("Concentration"), s["name"]


def test_124_with_higher_levels_or_cantrip_upgrade():
    assert sum(1 for s in SPELLS if s["higher_levels"]) == 109
    assert sum(1 for s in SPELLS if s["cantrip_upgrade"]) == 15
    assert sum(1 for s in SPELLS if s["higher_levels"] or s["cantrip_upgrade"]) == 124


def test_texts_are_coherent_with_the_level():
    for s in SPELLS:
        if s["level"] == 0:
            assert s["higher_levels"] is None, s["name"]
        else:
            assert s["cantrip_upgrade"] is None, s["name"]


def test_189_with_material_and_193_material_rows():
    assert sum(1 for s in SPELLS if s["has_material"]) == 189
    assert sum(len(s["materials"]) for s in SPELLS) == 193
    assert sorted(s["name"] for s in SPELLS if len(s["materials"]) > 1) == [
        "Astral Projection", "Clone", "Legend Lore", "Secret Chest",
    ]


def test_has_material_iff_materials():
    for s in SPELLS:
        assert s["has_material"] is bool(s["materials"]), s["name"]


def test_every_spell_has_a_component():
    for s in SPELLS:
        assert s["has_verbal"] or s["has_somatic"] or s["has_material"], s["name"]


def test_879_list_links_and_every_spell_has_a_list():
    assert sum(len(s["spell_lists"]) for s in SPELLS) == 879
    assert all(s["spell_lists"] for s in SPELLS)


def test_casting_time_distribution():
    assert Counter(s["casting_time_code"] for s in SPELLS) == {
        "action": 257, "bonus_action": 23, "reaction": 4, "1_minute": 28, "10_minutes": 13,
        "1_hour": 11, "8_hours": 1, "12_hours": 1, "24_hours": 1,
    }


def test_reactions():
    reactions = sorted(s["name"] for s in SPELLS if s["casting_time_code"] == "reaction")
    assert reactions == ["Counterspell", "Feather Fall", "Hellish Rebuke", "Shield"]


def test_casting_time_line_is_appended_to_8_conditional_spells_and_plant_growth():
    with_line = sorted(s["name"] for s in SPELLS if "\n\nCasting Time: " in s["description"])
    assert with_line == sorted([
        "Counterspell", "Feather Fall", "Hellish Rebuke", "Shield",
        "Divine Smite", "Ensnaring Strike", "Searing Smite", "Shining Smite",
        "Plant Growth",
    ])
    conditional_bonus = [
        s for s in SPELLS
        if s["casting_time_code"] == "bonus_action" and "\n\nCasting Time: Bonus Action, which you take " in s["description"]
    ]
    assert len(conditional_bonus) == 4


def test_no_trigger_field():
    assert all("casting_trigger" not in s for s in SPELLS)


def test_list_sizes():
    counts = Counter(code for s in SPELLS for code in s["spell_lists"])
    assert counts == {
        "bard": 130, "cleric": 109, "druid": 124, "paladin": 38, "ranger": 48,
        "sorcerer": 140, "warlock": 72, "wizard": 218,
    }


def test_lists_follow_the_spell_headers():
    assert spell("Phantasmal Force")["spell_lists"] == ("bard", "sorcerer", "wizard")
    assert spell("Mind Spike")["spell_lists"] == ("sorcerer", "warlock", "wizard")


def test_area_distribution():
    assert sum(1 for s in SPELLS if s["area"]) == 91
    assert Counter(s["area_shape_code"] for s in SPELLS if s["area_shape_code"]) == {
        "sphere": 28, "cube": 19, "cone": 6, "cylinder": 8, "emanation": 11, "line": 3, "radius": 10, "square": 6,
    }


def test_area_and_shape_go_together():
    for s in SPELLS:
        assert (s["area"] is None) is (s["area_shape_code"] is None), s["name"]


def test_schools_are_srd_codes():
    assert {s["school_code"] for s in SPELLS} == {
        "abjuration", "conjuration", "divination", "enchantment", "evocation", "illusion", "necromancy",
        "transmutation",
    }


# --- fixed values ----------------------------------------------------------------

def test_acid_arrow():
    s = spell("Acid Arrow")
    assert (s["level"], s["school_code"], s["casting_time_code"], s["range"]) == (2, "evocation", "action", "90 feet")
    assert (s["has_verbal"], s["has_somatic"], s["has_material"]) == (True, True, True)
    assert s["materials"] == ({
        "description": "powdered rhubarb leaf", "cost_gp": None, "consumed": False, "per_target": False,
        "quantity": 1,
    },)
    assert s["duration"] == "Instantaneous"
    assert s["higher_levels"]
    assert s["area"] is None and s["area_shape_code"] is None
    assert s["spell_lists"] == ("wizard",)


def test_acid_splash():
    s = spell("Acid Splash")
    assert s["level"] == 0 and s["cantrip_upgrade"] and not s["has_material"] and s["materials"] == ()
    assert (s["area"], s["area_shape_code"]) == ("5-foot-radius Sphere", "sphere")


def test_alarm():
    s = spell("Alarm")
    assert (s["casting_time_code"], s["ritual"], s["duration"]) == ("1_minute", True, "8 hours")
    assert (s["area"], s["area_shape_code"]) == ("20-foot Cube", "cube")


def test_alter_self():
    s = spell("Alter Self")
    assert (s["range"], s["concentration"], s["duration"]) == ("Self", True, "Concentration, up to 1 hour")


def test_counterspell():
    s = spell("Counterspell")
    assert s["casting_time_code"] == "reaction"
    assert s["description"].endswith(
        "\n\nCasting Time: Reaction, which you take when you see a creature within 60 feet of yourself "
        "casting a spell with Verbal, Somatic, or Material components"
    )


def test_etherealness():
    s = spell("Etherealness")
    assert (s["duration"], s["concentration"]) == ("Up to 8 hours", False)


def test_tsunami():
    s = spell("Tsunami")
    assert (s["duration"], s["range"]) == ("Concentration, up to 6 rounds", "1 mile")


def test_project_image():
    assert spell("Project Image")["range"] == "500 miles"


def test_mirage_arcane():
    s = spell("Mirage Arcane")
    assert s["range"] == "Sight"
    assert (s["area"], s["area_shape_code"]) == ("1-mile square", "square")


@pytest.mark.parametrize("name,area,shape", [
    ("Ice Storm", "20-foot-radius, 40-foot-high Cylinder", "cylinder"),
    ("Lightning Bolt", "100-foot Line, 5 feet wide", "line"),
    ("Light", "20-foot radius", "radius"),
    ("Fire Storm", "ten 10-foot Cubes", "cube"),
    ("Teleportation Circle", None, None),
])
def test_areas(name, area, shape):
    assert (spell(name)["area"], spell(name)["area_shape_code"]) == (area, shape)


def test_plant_growth():
    s = spell("Plant Growth")
    assert s["casting_time_code"] == "action"
    assert s["description"].endswith("\n\nCasting Time: Action (Overgrowth) or 8 hours (Enrichment)")
    assert (s["area"], s["area_shape_code"]) == ("100-foot-radius Sphere", "sphere")


@pytest.mark.parametrize("name,code", [("Awaken", "8_hours"), ("Simulacrum", "12_hours"), ("Hallow", "24_hours")])
def test_long_casting_times(name, code):
    assert spell(name)["casting_time_code"] == code


# The bodies of Find Steed and Summon Dragon name their stat block ("uses the
# **Otherworldly Steed** stat block"), so the check is on the stat block itself.
@pytest.mark.parametrize("name,heading", [
    ("Animate Objects", "#### Animated Object"),
    ("Find Steed", "## Otherworldly Steed"),
    ("Giant Insect", "## Giant Insect"),
    ("Summon Dragon", "## Draconic Spirit"),
])
def test_summon_stat_blocks_are_not_in_the_description(name, heading):
    s = spell(name)
    assert heading not in s["description"]
    for marker in ("**AC**", "**HP**", "<table>", "#### Actions", "#### Traits"):
        assert marker not in s["description"], marker
    assert s["higher_levels"]
    assert "**AC**" not in s["higher_levels"]


def test_no_description_contains_a_stat_block():
    for s in SPELLS:
        for marker in ("## Otherworldly Steed", "## Draconic Spirit", "#### Animated Object", "## Giant Insect"):
            assert marker not in s["description"], (s["name"], marker)


def test_animate_objects_keeps_the_line_break_of_the_text():
    assert "counts as\none object" in spell("Animate Objects")["description"]


def test_clone():
    assert materials("Clone") == [("1000", True, False, 1), ("2000", False, False, 1)]


def test_legend_lore():
    assert materials("Legend Lore") == [("250", True, False, 1), ("50", False, False, 4)]


def test_astral_projection():
    assert materials("Astral Projection") == [("1000", True, True, 1), ("100", True, True, 1)]


def test_create_undead():
    assert materials("Create Undead") == [("150", False, True, 1)]


def test_warding_bond():
    assert materials("Warding Bond") == [("50", False, False, 2)]


def test_gentle_repose():
    assert materials("Gentle Repose") == [("0.01", True, False, 2)]
    assert "Copper Piece" in spell("Gentle Repose")["materials"][0]["description"]


def test_true_strike():
    assert materials("True Strike") == [("0.01", False, False, 1)]


def test_detect_thoughts():
    assert spell("Detect Thoughts")["materials"] == ({
        "description": "1 Copper Piece", "cost_gp": "0.01", "consumed": False, "per_target": False, "quantity": 1,
    },)


def test_secret_chest():
    assert [m["cost_gp"] for m in spell("Secret Chest")["materials"]] == ["5000", "50"]


def test_chain_lightning():
    assert materials("Chain Lightning") == [(None, False, False, 1)]
    assert spell("Chain Lightning")["materials"][0]["description"] == "three silver pins"
