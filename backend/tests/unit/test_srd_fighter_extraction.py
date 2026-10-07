"""The SRD Fighter/Champion extractor (scripts/extract_srd_fighter.py), fed only with
synthetic markdown written here: no test reads the SRD files."""
import pytest

from scripts.extract_srd_fighter import ClassExtractionError, Curated, parse_class, render_module

TRAITS = {
    "Primary Ability": "Strength or Dexterity",
    "Hit Point Die": "D10 per Fighter level",
    "Saving Throw Proficiencies": "Strength and Constitution",
    "Skill Proficiencies": "Choose 2: Athletics, History, or Acrobatics",
    "Weapon Proficiencies": "Simple and Martial weapons",
    "Armor Training": "Light, Medium, and Heavy armor and Shields",
    "Starting Equipment": "Choose A or B: (A) Chain Mail, 8 Javelins, and\n 4 GP; or (B) 155 GP",
}

ITEMS = {"Chain Mail": "Chain Mail", "Javelins": "Javelin", "GP": "Gold Piece"}


def traits_table(**overrides) -> str:
    traits = {**TRAITS, **overrides}
    rows = "".join(
        f"    <tr>\n      <td>{label}</td>\n      <td>{value}</td>\n    </tr>\n" for label, value in traits.items()
        if value is not None
    )
    return f"**Core Fighter Traits**\n\n<table>\n  <tbody>\n{rows}  </tbody>\n</table>\n\n"


def features_table(columns=("Second Wind",), rows=None) -> str:
    rows = rows or [
        (1, "Fighting Style, Second Wind", ("2",)),
        (2, "Action Surge (one use)", ("2",)),
        (3, "Fighter Subclass", ("2",)),
        (4, "Ability Score Improvement", ("3",)),
        (5, "Subclass feature", ("3",)),
        (6, "Ability Score Improvement", ("3",)),
        (7, "Action Surge (two uses)", ("4",)),
    ]
    head = "".join(f"<th>{c}</th>" for c in ("Level", "Proficiency Bonus", "Class Features", *columns))
    body = "".join(
        f"<tr><td>{level}</td><td>+2</td><td>{features}</td>{''.join(f'<td>{v}</td>' for v in values)}</tr>\n"
        for level, features, values in rows
    )
    return f"**Fighter Features**\n\n<table>\n<thead><tr>{head}</tr></thead>\n<tbody>\n{body}</tbody>\n</table>\n\n"


CLASS_FEATURES = (
    "#### Level 1: Fighting Style\n\nYou gain a Fighting Style feat.\n\n"
    "#### Level 1: Second Wind\n\nRegain Hit Points equal to 1d10 plus your Fighter level.\n\n"
    "You can use this feature twice.\n\n"
    "#### Level 2: Action Surge\n\nTake one additional action.\n\n"
    "#### Level 3: Fighter Subclass\n\nYou gain a Fighter subclass of your choice.\n\n"
    "#### Level 4: Ability Score Improvement\n\nYou gain the Ability Score Improvement feat. "
    "You gain this feature again at Fighter level 6.\n\n"
)
SUBCLASS = (
    "### Fighter Subclass: Champion\n\n_Pursue Excellence_\n\nA Champion focuses on prowess.\n\n"
    "#### Level 3: Improved Critical\n\nCritical Hit on a roll of 19 or 20.\n\n"
    "#### Level 5: Superior Critical\n\nCritical Hit on a roll of 18-20.\n\n"
)


def fighter_md(traits=None, table=None, features=CLASS_FEATURES, subclass=SUBCLASS) -> str:
    return (
        "## Druid\n\nNot this one.\n\n"
        "## Fighter\n\n" + (traits if traits is not None else traits_table())
        + "### Becoming a Fighter …\n\n#### As a Level 1 Character\n\n- Gain all the traits.\n\n"
        + "### Fighter Class Features\n\nAs a Fighter, you gain the following.\n\n"
        + (table if table is not None else features_table())
        + features + subclass + "## Monk\n\n#### Level 1: Martial Arts\n\nNot parsed.\n"
    )


def curated(**overrides) -> Curated:
    values = dict(
        structure={
            ("Fighter", "Second Wind"): dict(
                action_type_code="bonus_action",
                effects=[dict(operation_code="heal", target_code="hit_points", dice_count=1, die_size=10,
                              value_basis_code="class_level")],
                resources=[dict(name="Second Wind", recharges=[dict(recharge_type_code="short_rest", recovers=1)])],
            ),
            ("Fighter", "Action Surge"): dict(
                resources=[dict(name="Action Surge", recharges=[dict(recharge_type_code="short_rest")])],
            ),
            ("Champion", "Superior Critical"): dict(
                replaces="Improved Critical",
                effects=[dict(operation_code="set", target_code="critical_range", value=18)],
            ),
        },
        scaling_columns={"Second Wind": ("Second Wind", "resource", 0)},
        uses={"Action Surge": 0},
        items=ITEMS,
    )
    values.update(overrides)
    return Curated(**values)


def parse(md=None, **overrides) -> dict:
    return parse_class(fighter_md() if md is None else md, "Fighter", curated(**overrides))


def _features(owner: dict) -> list[tuple]:
    return [(f["level"], f["name"]) for f in owner["features"]]


# --- traits ---------------------------------------------------------------------

def test_core_traits():
    klass = parse()["class"]
    assert klass["name"] == "Fighter"
    assert klass["description"] is None
    assert klass["hit_die"] == 10
    assert klass["primary_ability"] == ("dex", "str")
    assert klass["skill_choices"] == 2
    assert klass["skills"] == ("acrobatics", "athletics", "history")
    assert klass["proficiency_grants"] == (
        {"saving_throw_ability_code": "str"}, {"saving_throw_ability_code": "con"},
        {"weapon_category_code": "simple"}, {"weapon_category_code": "martial"},
        {"armor_category_code": "light"}, {"armor_category_code": "medium"}, {"armor_category_code": "heavy"},
        {"armor_category_code": "shield"},
    )
    assert klass["spell_ability"] is None and klass["spellcasting_type"] is None


def test_starting_equipment_with_two_options_and_quantities():
    assert parse()["class"]["initial_equipment"] == (
        {"option": "A", "item": "Chain Mail", "quantity": 1},
        {"option": "A", "item": "Javelin", "quantity": 8},
        {"option": "A", "item": "Gold Piece", "quantity": 4},
        {"option": "B", "item": "Gold Piece", "quantity": 155},
    )


def test_equipment_item_without_map_raises():
    with pytest.raises(ClassExtractionError, match="Chain Mail"):
        parse(items={"Javelins": "Javelin", "GP": "Gold Piece"})


@pytest.mark.parametrize("label,value", [
    ("Hit Point Die", "Ten per level"),
    ("Primary Ability", "Strength or Luck"),
    ("Weapon Proficiencies", "Simple weapons and Martial weapons that have the Light property"),
    ("Armor Training", "Robes"),
])
def test_unrecognized_trait_value_raises(label, value):
    with pytest.raises(ClassExtractionError, match=label):
        parse(fighter_md(traits=traits_table(**{label: value})))


def test_unknown_trait_label_raises():
    table = traits_table().replace("<td>Armor Training</td>", "<td>Spell Slots</td>")
    with pytest.raises(ClassExtractionError, match="Spell Slots"):
        parse(fighter_md(traits=table))


def test_missing_trait_raises():
    with pytest.raises(ClassExtractionError, match="Hit Point Die"):
        parse(fighter_md(traits=traits_table(**{"Hit Point Die": None})))


# --- features ---------------------------------------------------------------------

def test_class_features_by_level_with_the_asi_expanded():
    klass = parse()["class"]
    assert _features(klass) == [
        (1, "Fighting Style"), (1, "Second Wind"), (2, "Action Surge"), (3, "Fighter Subclass"),
        (4, "Ability Score Improvement"), (6, "Ability Score Improvement"),
    ]
    asi = [f for f in klass["features"] if f["name"] == "Ability Score Improvement"]
    assert asi[0]["description"] == asi[1]["description"]
    assert klass["subclass_level"] == 3


def test_asi_expanded_to_three_levels():
    features = CLASS_FEATURES.replace("at Fighter level 6.", "at Fighter levels 6, 8, and 12.")
    rows = [(1, "Fighting Style, Second Wind", ("2",)), (2, "Action Surge (one use)", ("2",)),
            (3, "Fighter Subclass", ("2",))] + [(lv, "Ability Score Improvement", ("2",)) for lv in (4, 6, 8, 12)]
    klass = parse(fighter_md(features=features, table=features_table(rows=rows)))["class"]
    assert [f["level"] for f in klass["features"] if f["name"] == "Ability Score Improvement"] == [4, 6, 8, 12]


def test_feature_description_is_verbatim_without_the_heading():
    second_wind = next(f for f in parse()["class"]["features"] if f["name"] == "Second Wind")
    assert second_wind["description"] == (
        "Regain Hit Points equal to 1d10 plus your Fighter level.\n\nYou can use this feature twice."
    )


def test_curated_structure_is_applied():
    second_wind = next(f for f in parse()["class"]["features"] if f["name"] == "Second Wind")
    assert second_wind["action_type_code"] == "bonus_action"
    assert second_wind["effects"] == ({
        "operation_code": "heal", "target_code": "hit_points", "dice_count": 1, "die_size": 10,
        "value_basis_code": "class_level",
    },)
    fighting_style = next(f for f in parse()["class"]["features"] if f["name"] == "Fighting Style")
    assert fighting_style["effects"] == () and fighting_style["resources"] == ()


def test_scaling_column_gives_the_base_value_and_rows_only_where_it_changes():
    resource = next(f for f in parse()["class"]["features"] if f["name"] == "Second Wind")["resources"][0]
    assert resource["value"] == 2
    assert resource["scaling"] == ({"level": 4, "value": 3}, {"level": 7, "value": 4})


def test_choice_scaling_column():
    structure = {**curated().structure, ("Fighter", "Fighting Style"): dict(effects=[dict(
        operation_code="grant", choice=dict(pool_type_code="feat"))])}
    result = parse(structure=structure, scaling_columns={"Second Wind": ("Fighting Style", "choice", 0)})
    choice = next(f for f in result["class"]["features"] if f["name"] == "Fighting Style")["effects"][0]["choice"]
    assert choice["choose_count"] == 2
    assert choice["scaling"] == ({"level": 4, "value": 3}, {"level": 7, "value": 4})


def test_uses_in_the_class_features_column_become_scaling():
    resource = next(f for f in parse()["class"]["features"] if f["name"] == "Action Surge")["resources"][0]
    assert resource["value"] == 1
    assert resource["scaling"] == ({"level": 7, "value": 2},)
    assert resource["recharges"] == ({"recharge_type_code": "short_rest", "recovers": None},)


def test_scaling_column_without_link_raises():
    with pytest.raises(ClassExtractionError, match="Second Wind"):
        parse(scaling_columns={})


def test_uses_without_link_raises():
    with pytest.raises(ClassExtractionError, match="Action Surge"):
        parse(uses={})


def test_subclass_feature_of_the_table_is_not_a_feature():
    names = [f["name"] for f in parse()["class"]["features"]]
    assert "Subclass feature" not in names


def test_table_feature_without_heading_raises():
    rows = [(1, "Fighting Style, Second Wind, Weapon Mastery", ("2",)), (2, "Action Surge (one use)", ("2",)),
            (3, "Fighter Subclass", ("2",)), (4, "Ability Score Improvement", ("3",)),
            (6, "Ability Score Improvement", ("3",))]
    with pytest.raises(ClassExtractionError, match="Weapon Mastery"):
        parse(fighter_md(table=features_table(rows=rows)))


def test_subclass_section_changes_the_owner():
    result = parse()
    (champion,) = result["subclasses"]
    assert champion["name"] == "Champion"
    assert champion["class"] == "Fighter"
    assert _features(champion) == [(3, "Improved Critical"), (5, "Superior Critical")]
    assert not any(f["name"] == "Improved Critical" for f in result["class"]["features"])


def test_subclass_tagline_goes_to_the_description():
    (champion,) = parse()["subclasses"]
    assert champion["description"] == "_Pursue Excellence_\n\nA Champion focuses on prowess."


def test_replaces_points_to_name_and_level():
    (champion,) = parse()["subclasses"]
    superior = champion["features"][1]
    assert superior["replaces"] == ("Improved Critical", 3)
    assert champion["features"][0]["replaces"] is None


def test_replaces_a_feature_that_does_not_exist_or_is_not_lower_raises():
    structure = {("Champion", "Improved Critical"): dict(replaces="Superior Critical")}
    with pytest.raises(ClassExtractionError, match="Improved Critical"):
        parse(structure=structure)
    structure = {("Champion", "Superior Critical"): dict(replaces="Missing Feature")}
    with pytest.raises(ClassExtractionError, match="Missing Feature"):
        parse(structure=structure)


def test_invalid_feature_heading_raises():
    features = CLASS_FEATURES + "#### Bonus Feature\n\nNo level.\n\n"
    with pytest.raises(ClassExtractionError, match="Bonus Feature"):
        parse(fighter_md(features=features))


def test_curated_entry_without_feature_raises():
    structure = {("Fighter", "Indomitable"): dict(resources=[dict(name="x", recharges=[
        dict(recharge_type_code="long_rest")])])}
    with pytest.raises(ClassExtractionError, match="Indomitable"):
        parse(structure=structure)


def test_render_module_round_trips():
    result = parse()
    namespace: dict = {}
    exec(render_module(result), namespace)  # noqa: S102 - generated data module
    assert namespace["CLASS"] == result["class"]
    assert namespace["SUBCLASSES"] == result["subclasses"]
    assert "não editar à mão" in render_module(result)
