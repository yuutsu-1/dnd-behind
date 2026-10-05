"""The SRD spell extractor (scripts/extract_srd_spells.py), fed only with synthetic
markdown written here: no test reads the SRD files."""
from decimal import Decimal

import pytest

from scripts.extract_srd_spells import (
    CASTING_TIME_OVERRIDES,
    MATERIAL_SPLITS,
    SpellExtractionError,
    parse_spells,
    render_module,
)

SECTION = "## Spell Descriptions\n\n"


def spell_md(
    name="Test Bolt",
    header="_Level 1 Evocation (Wizard)_",
    casting="Action",
    range_="90 feet",
    components="**Components:** V, S",
    duration="Instantaneous",
    body="A bolt of test energy.",
) -> str:
    return (
        f"#### {name}\n\n{header}\n\n"
        f"**Casting Time:** {casting}\n**Range:** {range_}\n{components}\n**Duration:** {duration}\n\n"
        f"{body}\n\n"
    )


def parse(*spells: str, **curated) -> list[dict]:
    curated.setdefault("areas", {})
    curated.setdefault("material_splits", {})
    curated.setdefault("casting_time_overrides", {})
    return parse_spells("# Spells\n\nIntro text.\n\n" + SECTION + "".join(spells), **curated)


def one(*args, **kwargs) -> dict:
    spells = parse(spell_md(*args, **kwargs))
    assert len(spells) == 1
    return spells[0]


# --- header ----------------------------------------------------------------------

def test_level_header():
    spell = one(header="_Level 2 Evocation (Wizard)_")
    assert spell["name"] == "Test Bolt"
    assert spell["level"] == 2
    assert spell["school_code"] == "evocation"
    assert spell["spell_lists"] == ("wizard",)


def test_cantrip_header_and_lists_sorted_by_code():
    spell = one(header="_Evocation Cantrip (Wizard, Sorcerer)_")
    assert spell["level"] == 0
    assert spell["school_code"] == "evocation"
    assert spell["spell_lists"] == ("sorcerer", "wizard")


@pytest.mark.parametrize("header", [
    "_Level 2 Evocation_",                 # no classes
    "_Level 10 Evocation (Wizard)_",       # level out of range
    "_Evocation (Wizard)_",                # neither level nor cantrip
    "Level 2 Evocation (Wizard)",          # not italic
])
def test_unrecognized_header_raises_with_name_and_line(header):
    with pytest.raises(SpellExtractionError, match=r"Test Bolt.*line \d+"):
        parse(spell_md(header=header))


def test_unknown_school_raises():
    with pytest.raises(SpellExtractionError, match="school"):
        parse(spell_md(header="_Level 1 Pyromancy (Wizard)_"))


def test_unknown_class_raises():
    with pytest.raises(SpellExtractionError, match="Artificer"):
        parse(spell_md(header="_Level 1 Evocation (Wizard, Artificer)_"))


def test_duplicate_name_raises():
    with pytest.raises(SpellExtractionError, match="duplicate"):
        parse(spell_md(), spell_md())


def test_missing_section_raises():
    with pytest.raises(SpellExtractionError, match="Spell Descriptions"):
        parse_spells(spell_md(), areas={}, material_splits={}, casting_time_overrides={})


def test_unrecognized_heading_block_is_not_skipped_silently():
    """A heading that is neither a spell nor a stat block fails instead of being dropped."""
    text = spell_md() + "#### Broken Spell\n\nSome text without header.\n\n" + spell_md(name="Other")
    with pytest.raises(SpellExtractionError, match="Broken Spell"):
        parse(text)


# --- casting time ----------------------------------------------------------------

@pytest.mark.parametrize("casting,code,ritual", [
    ("Action", "action", False),
    ("Action or Ritual", "action", True),
    ("Bonus Action", "bonus_action", False),
    ("1 minute", "1_minute", False),
    ("1 minute or Ritual", "1_minute", True),
    ("10 minutes", "10_minutes", False),
    ("10 minutes or Ritual", "10_minutes", True),
    ("1 hour", "1_hour", False),
    ("1 hour or Ritual", "1_hour", True),
    ("8 hours", "8_hours", False),
    ("12 hours", "12_hours", False),
    ("24 hours", "24_hours", False),
])
def test_casting_time_codes(casting, code, ritual):
    spell = one(casting=casting)
    assert spell["casting_time_code"] == code
    assert spell["ritual"] is ritual
    assert spell["description"] == "A bolt of test energy."


def test_reaction_with_condition_appends_the_casting_time_line_to_description():
    casting = "Reaction, which you take when you see a creature within 60 feet of yourself casting a spell"
    spell = one(casting=casting)
    assert spell["casting_time_code"] == "reaction"
    assert spell["ritual"] is False
    assert spell["description"] == f"A bolt of test energy.\n\nCasting Time: {casting}"
    assert "casting_trigger" not in spell


def test_bonus_action_with_condition_appends_the_casting_time_line_to_description():
    casting = "Bonus Action, which you take immediately after hitting a target with a Melee weapon"
    spell = one(casting=casting)
    assert spell["casting_time_code"] == "bonus_action"
    assert spell["description"].endswith(f"\n\nCasting Time: {casting}")


def test_casting_time_override_keeps_the_original_line_in_description():
    casting = "Action (Overgrowth) or 8 hours (Enrichment)"
    [spell] = parse(spell_md(name="Plant Growth", casting=casting), casting_time_overrides={"Plant Growth": "action"})
    assert spell["casting_time_code"] == "action"
    assert spell["description"].endswith("Casting Time: Action (Overgrowth) or 8 hours (Enrichment)")


def test_real_override_table_is_plant_growth_only():
    assert CASTING_TIME_OVERRIDES == {"Plant Growth": "action"}


@pytest.mark.parametrize("casting", ["2 rounds", "Action (Overgrowth) or 8 hours (Enrichment)", "Free"])
def test_unrecognized_casting_time_raises(casting):
    with pytest.raises(SpellExtractionError, match="casting time"):
        parse(spell_md(casting=casting))


# --- range / duration ------------------------------------------------------------

@pytest.mark.parametrize("range_", ["90 feet", "Self", "Touch", "1 mile", "500 miles", "Sight", "Unlimited"])
def test_range_is_verbatim(range_):
    assert one(range_=range_)["range"] == range_


@pytest.mark.parametrize("duration,concentration", [
    ("Concentration, up to 6 rounds", True),
    ("Concentration, up to 1 minute", True),
    ("Up to 8 hours", False),
    ("Instantaneous", False),
    ("Until dispelled or triggered", False),
    ("Special", False),
])
def test_duration_is_verbatim_and_sets_concentration(duration, concentration):
    spell = one(duration=duration)
    assert spell["duration"] == duration
    assert spell["concentration"] is concentration


def test_missing_stat_line_raises():
    text = "#### Test Bolt\n\n_Level 1 Evocation (Wizard)_\n\n**Casting Time:** Action\n**Range:** Self\n\nBody.\n\n"
    with pytest.raises(SpellExtractionError, match="Test Bolt"):
        parse(text)


# --- components ------------------------------------------------------------------

@pytest.mark.parametrize("line,v,s,m", [
    ("**Components:** V, S", True, True, False),
    ("**Components:** V", True, False, False),
    ("**Components:** S", False, True, False),
    ("**Component:** V", True, False, False),
    ("**Component:** V, S", True, True, False),
    ("**Components:** V, S, M (a feather)", True, True, True),
    ("**Components:** V, M (a feather)", True, False, True),
    ("**Components:** S, M (a feather)", False, True, True),
])
def test_components(line, v, s, m):
    spell = one(components=line)
    assert (spell["has_verbal"], spell["has_somatic"], spell["has_material"]) == (v, s, m)
    assert bool(spell["materials"]) is m


@pytest.mark.parametrize("line", [
    "**Components:** V, S, X", "**Components:** M", "**Components:** V, S, M (unclosed", "**Components:**",
    "**Components:** S, V",
])
def test_unrecognized_components_raise(line):
    with pytest.raises(SpellExtractionError, match="components"):
        parse(spell_md(components=line))


def material(text: str, name="Test Bolt", **curated) -> tuple[dict, ...]:
    [spell] = parse(spell_md(name=name, components=f"**Components:** V, S, M ({text})"), **curated)
    return spell["materials"]


def row(description, cost_gp=None, consumed=False, per_target=False, quantity=1) -> dict:
    return dict(description=description, cost_gp=cost_gp, consumed=consumed, per_target=per_target,
                quantity=quantity)


def test_material_without_cost_is_one_row_with_the_whole_text():
    assert material("powdered rhubarb leaf") == (row("powdered rhubarb leaf"),)


def test_material_numeral_without_cost_stays_in_the_text():
    """B6: no cost -> quantity 1, the numeral only in the text."""
    assert material("three silver pins") == (row("three silver pins"),)


def test_material_with_cost_and_consumed():
    assert material("gold dust worth 25+ GP, which the spell consumes") == (
        row("gold dust worth 25+ GP, which the spell consumes", cost_gp="25", consumed=True),
    )


def test_material_cost_with_thousands_separator():
    assert material("a diamond worth 5,000+ GP")[0]["cost_gp"] == "5000"


def test_material_per_corpse():
    """Create Undead."""
    assert material("one 150+ GP black onyx stone for each corpse") == (
        row("one 150+ GP black onyx stone for each corpse", cost_gp="150", per_target=True),
    )


def test_material_pair_each():
    """Warding Bond."""
    text = "a pair of platinum rings worth 50+ GP each, which you and the target must wear for the duration"
    assert material(text) == (row(text, cost_gp="50", quantity=2),)


def test_material_copper_pieces_consumed():
    """Gentle Repose."""
    assert material("2 Copper Pieces, which the spell consumes") == (
        row("2 Copper Pieces, which the spell consumes", cost_gp="0.01", consumed=True, quantity=2),
    )


def test_material_one_copper_piece():
    """Detect Thoughts."""
    assert material("1 Copper Piece") == (row("1 Copper Piece", cost_gp="0.01"),)


def test_material_cost_in_copper():
    """True Strike."""
    text = "a weapon with which you have proficiency and that is worth 1+ CP"
    assert material(text) == (row(text, cost_gp="0.01"),)


def test_material_with_two_costs_needs_a_curated_split():
    with pytest.raises(SpellExtractionError, match="curated"):
        material("a gem worth 10+ GP and a rod worth 20+ GP")


CLONE = (
    "a diamond worth 1,000+ GP, which the spell consumes, and a sealable vessel worth 2,000+ GP "
    "that is large enough to hold the creature being cloned"
)
LEGEND_LORE = "incense worth 250+ GP, which the spell consumes, and four ivory strips worth 50+ GP each"
ASTRAL = (
    "for each of the spell's targets, one jacinth worth 1,000+ GP and one silver bar worth 100+ GP, "
    "all of which the spell consumes"
)
SECRET_CHEST = (
    "a chest, 3 feet by 2 feet by 2 feet, constructed from rare materials worth 5,000+ GP, and a Tiny "
    "replica of the chest made from the same materials worth 50+ GP"
)


def _curated(name):
    return {"material_splits": {name: MATERIAL_SPLITS[name]}}


def test_clone_split():
    rows = material(CLONE, name="Clone", **_curated("Clone"))
    assert [(r["cost_gp"], r["consumed"], r["per_target"], r["quantity"]) for r in rows] == [
        ("1000", True, False, 1), ("2000", False, False, 1),
    ]
    assert "diamond" in rows[0]["description"] and "vessel" in rows[1]["description"]


def test_legend_lore_split():
    rows = material(LEGEND_LORE, name="Legend Lore", **_curated("Legend Lore"))
    assert [(r["cost_gp"], r["consumed"], r["per_target"], r["quantity"]) for r in rows] == [
        ("250", True, False, 1), ("50", False, False, 4),
    ]
    assert "incense" in rows[0]["description"] and "ivory" in rows[1]["description"]


def test_astral_projection_split():
    rows = material(ASTRAL, name="Astral Projection", **_curated("Astral Projection"))
    assert [(r["cost_gp"], r["consumed"], r["per_target"], r["quantity"]) for r in rows] == [
        ("1000", True, True, 1), ("100", True, True, 1),
    ]
    assert "jacinth" in rows[0]["description"] and "silver bar" in rows[1]["description"]


def test_secret_chest_split():
    rows = material(SECRET_CHEST, name="Secret Chest", **_curated("Secret Chest"))
    assert [r["cost_gp"] for r in rows] == ["5000", "50"]


def test_real_split_table_covers_exactly_four_spells():
    assert set(MATERIAL_SPLITS) == {"Astral Projection", "Clone", "Legend Lore", "Secret Chest"}


def test_curated_split_whose_excerpt_is_not_in_the_text_raises():
    with pytest.raises(SpellExtractionError, match="Clone"):
        material("a diamond worth 1,000+ GP", name="Clone", **_curated("Clone"))


def test_material_costs_are_valid_decimals():
    for rows in MATERIAL_SPLITS.values():
        for r in rows:
            assert Decimal(r["cost_gp"]) >= 0


# --- body ------------------------------------------------------------------------

def test_higher_levels_paragraph_leaves_description():
    body = "First paragraph.\n\n_Using a Higher-Level Spell Slot._ The damage increases by 1d4."
    spell = one(body=body)
    assert spell["description"] == "First paragraph."
    assert spell["higher_levels"] == "The damage increases by 1d4."
    assert spell["cantrip_upgrade"] is None


def test_cantrip_upgrade_paragraph_leaves_description():
    body = "Bubble.\n\n_Cantrip Upgrade._ The damage increases by 1d6 when you reach level 5."
    spell = one(header="_Evocation Cantrip (Wizard)_", body=body)
    assert spell["description"] == "Bubble."
    assert spell["cantrip_upgrade"] == "The damage increases by 1d6 when you reach level 5."
    assert spell["higher_levels"] is None


@pytest.mark.parametrize("header,label,field", [
    ("_Level 4 Conjuration (Druid)_", "_Using a Higher-Level Spell Slot._", "higher_levels"),
    ("_Evocation Cantrip (Wizard)_", "_Cantrip Upgrade._", "cantrip_upgrade"),
])
def test_labeled_line_right_after_a_paragraph_without_blank_line(header, label, field):
    body = f"First paragraph.\nSecond line of it.\n{label} Use the level."
    spell = one(header=header, body=body)
    assert spell["description"] == "First paragraph.\nSecond line of it."
    assert spell[field] == "Use the level."


def test_higher_levels_in_a_cantrip_raises():
    body = "Bubble.\n\n_Using a Higher-Level Spell Slot._ More."
    with pytest.raises(SpellExtractionError, match="Higher-Level"):
        parse(spell_md(header="_Evocation Cantrip (Wizard)_", body=body))


def test_cantrip_upgrade_in_a_leveled_spell_raises():
    body = "Bolt.\n\n_Cantrip Upgrade._ More."
    with pytest.raises(SpellExtractionError, match="Cantrip Upgrade"):
        parse(spell_md(body=body))


def test_line_break_inside_a_paragraph_is_preserved():
    body = "A Medium or smaller target counts as\none object.\n\n**Bold.** Second paragraph."
    assert one(body=body)["description"] == body


def test_extra_blank_lines_collapse_to_one_paragraph_break():
    assert one(body="One.\n\n\n\nTwo.")["description"] == "One.\n\nTwo."


STAT_BLOCK_H2 = (
    "## Otherworldly Thing\n\n_Large Celestial, Fey, or Fiend (Your Choice), Neutral_\n\n"
    "**AC** 10 + 1 per spell level\n**HP** 5\n\n<table>\n  <tr><td>STR</td></tr>\n</table>\n\n"
    "#### Traits\n\n**_Life Bond._** Something.\n\n#### Actions\n\n**_Slam._** Hit.\n\n"
)
STAT_BLOCK_H4 = (
    "#### Animated Thing\n\n_Huge or Smaller Construct, Unaligned_\n\n**AC** 15\n\n"
    "#### Actions\n\n_Slam._ Hit.\n\n"
)


@pytest.mark.parametrize("stat_block", [STAT_BLOCK_H2, STAT_BLOCK_H4])
def test_summon_stat_block_leaves_the_spell(stat_block):
    body = "Summon it. It uses the **Otherworldly Thing** stat block.\n\n_Using a Higher-Level Spell Slot._ Bigger."
    spells = parse(spell_md(name="Find Thing", body=body) + stat_block + spell_md(name="Next Spell"))
    assert [s["name"] for s in spells] == ["Find Thing", "Next Spell"]
    find, following = spells
    assert find["description"] == "Summon it. It uses the **Otherworldly Thing** stat block."
    assert find["higher_levels"] == "Bigger."
    assert "**AC**" not in find["description"] and "#### Actions" not in find["description"]
    assert following["description"] == "A bolt of test energy."


def test_stat_block_before_any_spell_raises():
    with pytest.raises(SpellExtractionError):
        parse(STAT_BLOCK_H4 + spell_md())


# --- curated areas ---------------------------------------------------------------

def test_area_comes_from_the_curated_table():
    spells = parse(
        spell_md(name="Boom"), spell_md(name="Quiet"),
        areas={"Boom": ("sphere", "20-foot-radius Sphere")},
    )
    by_name = {s["name"]: s for s in spells}
    assert (by_name["Boom"]["area"], by_name["Boom"]["area_shape_code"]) == ("20-foot-radius Sphere", "sphere")
    assert (by_name["Quiet"]["area"], by_name["Quiet"]["area_shape_code"]) == (None, None)


@pytest.mark.parametrize("curated", [
    {"areas": {"Nowhere": ("cube", "5-foot Cube")}},
    {"material_splits": {"Nowhere": MATERIAL_SPLITS["Clone"]}},
    {"casting_time_overrides": {"Nowhere": "action"}},
])
def test_curated_entry_without_spell_raises(curated):
    with pytest.raises(SpellExtractionError, match="Nowhere"):
        parse(spell_md(), **curated)


def test_curated_area_with_unknown_shape_raises():
    with pytest.raises(SpellExtractionError, match="shape"):
        parse(spell_md(), areas={"Test Bolt": ("hexagon", "5-foot Hexagon")})


# --- generated module ------------------------------------------------------------

def test_render_module_round_trips_and_is_deterministic():
    spells = parse(
        spell_md(components="**Components:** V, S, M (gold dust worth 25+ GP, which the spell consumes)",
                 body='Quotes " and \' and\nnewline.'),
        spell_md(name="Other", header="_Abjuration Cantrip (Cleric)_"),
    )
    source = render_module(spells)
    assert source == render_module(spells)
    assert "scripts/extract_srd_spells.py" in source
    assert "import app" not in source and "from app" not in source
    namespace: dict = {}
    exec(compile(source, "srd_spells.py", "exec"), namespace)
    assert namespace["SPELLS"] == tuple(spells)
