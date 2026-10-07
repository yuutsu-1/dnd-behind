"""Extract the SRD 2024 Fighter class and its Champion subclass, with their features,
from the SRD markdown into a versioned data module.

Development tool, run by hand from `backend/`:

    python -m scripts.extract_srd_fighter

It reads `classes.md` of the SRD markdown (from "## Fighter" to the next "## ") and
writes `app/db/seed/srd_fighter.py`, which the squashed migration imports. The
migration never reads the markdown; the generated module only changes by running this
script again.

Parsed mechanically:
- the "Core Fighter Traits" table (hit die, primary ability, saves, skills, weapons,
  armor, starting equipment; item names go through `ITEMS`);
- each `#### Level N: Name` of "### Fighter Class Features" (class) and of
  "### Fighter Subclass: X" (subclass) is a feature of level N; "You gain this feature
  again at Fighter levels 6, 8, ..." repeats the feature at those levels;
- the "Fighter Features" table: each extra column (Second Wind, Weapon Mastery) gives
  the base value of a resource/choice and one scaling row where the value changes;
  "(two uses)" in the Class Features column gives a scaling row of a resource.

`CURATED` (each entry citing the line of `classes.md`) gives the structure of each
feature (effects, choices, resources, recharges, kind, action type, replaced feature)
and the links table column -> resource/choice. Any form that is not recognized raises
`ClassExtractionError`: nothing is skipped.
"""
import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.srd_features import normalize_structure, render_data_module

BACKEND_DIR = Path(__file__).resolve().parents[1]
SOURCE = BACKEND_DIR.parent / "docs" / "dnd-5e-srd-markdown-master" / "classes.md"
TARGET = BACKEND_DIR / "app" / "db" / "seed" / "srd_fighter.py"

CLASS_NAME = "Fighter"


class ClassExtractionError(Exception):
    pass


ABILITIES = {
    "Strength": "str", "Dexterity": "dex", "Constitution": "con",
    "Intelligence": "int", "Wisdom": "wis", "Charisma": "cha",
}
SKILLS = {
    "Acrobatics": "acrobatics", "Animal Handling": "animal_handling", "Arcana": "arcana", "Athletics": "athletics",
    "Deception": "deception", "History": "history", "Insight": "insight", "Intimidation": "intimidation",
    "Investigation": "investigation", "Medicine": "medicine", "Nature": "nature", "Perception": "perception",
    "Performance": "performance", "Persuasion": "persuasion", "Religion": "religion",
    "Sleight of Hand": "sleight_of_hand", "Stealth": "stealth", "Survival": "survival",
}
WEAPON_CATEGORIES = {"Simple": "simple", "Martial": "martial"}
ARMOR_CATEGORIES = {"Light": "light", "Medium": "medium", "Heavy": "heavy"}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

TRAIT_LABELS = (
    "Primary Ability", "Hit Point Die", "Saving Throw Proficiencies", "Skill Proficiencies",
    "Weapon Proficiencies", "Armor Training", "Starting Equipment",
)
# Columns of the class table that never become scaling.
PLAIN_COLUMNS = ("Level", "Proficiency Bonus", "Class Features")
SUBCLASS_FEATURE = "Subclass feature"


@dataclass
class Curated:
    # (owner name, feature name) -> structure (same names as the API payload) plus
    # `feature_kind_code`, `action_type_code` and `replaces` (name of a lower feature).
    structure: dict[tuple[str, str], dict] = field(default_factory=dict)
    # Column of the class table -> (feature name, "resource" | "choice", index of the
    # resource / of the effect holding the choice).
    scaling_columns: dict[str, tuple[str, str, int]] = field(default_factory=dict)
    # Feature with "(N uses)" in the Class Features column -> index of its resource.
    uses: dict[str, int] = field(default_factory=dict)
    # Equipment name in the traits table -> SRD item name (singular).
    items: dict[str, str] = field(default_factory=dict)


STRUCTURE_KEYS = frozenset({"action_type_code", "feature_kind_code", "replaces", "effects", "resources"})


def _choose_feat(**choice) -> dict:
    return dict(effects=[dict(operation_code="grant", choice=dict(pool_type_code="feat", choose_count=1, **choice))])


_CRITICAL_CONDITION = "with weapons and Unarmed Strikes"

CURATED = Curated(
    structure={
        # l. 4790: "gain a Fighting Style feat of your choice"; l. 4792: "Whenever you gain a
        # Fighter level, you can replace the feat you chose with a different Fighting Style feat."
        ("Fighter", "Fighting Style"): dict(
            feature_kind_code="fighting_style",
            **_choose_feat(feat_category_code="fighting_style", swap_rule_code="on_class_level_up"),
        ),
        # l. 4796: "As a Bonus Action ... regain Hit Points equal to 1d10 plus your Fighter level."
        # l. 4798: "regain one expended use when you finish a Short Rest, and ... all expended
        # uses when you finish a Long Rest." (uses: Second Wind column)
        ("Fighter", "Second Wind"): dict(
            action_type_code="bonus_action",
            effects=[dict(operation_code="heal", target_code="hit_points", dice_count=1, die_size=10,
                          value_basis_code="class_level")],
            resources=[dict(name="Second Wind", recharges=[
                dict(recharge_type_code="short_rest", recovers=1),
                dict(recharge_type_code="long_rest", recovers=None),
            ])],
        ),
        # l. 4804: "mastery properties of three kinds of Simple or Martial weapons of your
        # choice. Whenever you finish a Long Rest, you can ... change one of those weapon
        # choices." (count: Weapon Mastery column; no filter: Simple or Martial is every weapon)
        ("Fighter", "Weapon Mastery"): dict(effects=[
            dict(operation_code="grant", choice=dict(pool_type_code="weapon", swap_rule_code="on_long_rest_one")),
        ]),
        # l. 4812: "can't do so again until you finish a Short or Long Rest" (uses: "(one use)",
        # "(two uses)" in the table).
        ("Fighter", "Action Surge"): dict(resources=[dict(name="Action Surge", recharges=[
            dict(recharge_type_code="short_rest", recovers=None),
            dict(recharge_type_code="long_rest", recovers=None),
        ])]),
        # l. 4824: "the Ability Score Improvement feat ... or another feat of your choice for
        # which you qualify" (no category filter: gate #2, H6).
        ("Fighter", "Ability Score Improvement"): _choose_feat(),
        # l. 4828: "attack twice instead of once".
        ("Fighter", "Extra Attack"): dict(effects=[
            dict(operation_code="set", target_code="attacks_per_action", value=2),
        ]),
        # l. 4836: "can't use this feature again until you finish a Long Rest" (uses: table).
        ("Fighter", "Indomitable"): dict(resources=[dict(name="Indomitable", recharges=[
            dict(recharge_type_code="long_rest", recovers=None),
        ])]),
        # l. 4846: "attack three times instead of once".
        ("Fighter", "Two Extra Attacks"): dict(replaces="Extra Attack", effects=[
            dict(operation_code="set", target_code="attacks_per_action", value=3),
        ]),
        # l. 4854: "an Epic Boon feat ... or another feat of your choice" (no filter: H6).
        ("Fighter", "Epic Boon"): _choose_feat(),
        # l. 4858: "attack four times instead of once".
        ("Fighter", "Three Extra Attacks"): dict(replaces="Two Extra Attacks", effects=[
            dict(operation_code="set", target_code="attacks_per_action", value=4),
        ]),
        # l. 4868: "with weapons and Unarmed Strikes can score a Critical Hit on a roll of 19 or 20".
        ("Champion", "Improved Critical"): dict(effects=[
            dict(operation_code="set", target_code="critical_range", value=19, condition_text=_CRITICAL_CONDITION),
        ]),
        # l. 4872: "Advantage on Initiative rolls and Strength (Athletics) checks".
        ("Champion", "Remarkable Athlete"): dict(effects=[
            dict(operation_code="advantage", target_code="initiative"),
            dict(operation_code="advantage", target_code="ability_check", skill_code="athletics"),
        ]),
        # l. 4878: "another Fighting Style feat of your choice".
        ("Champion", "Additional Fighting Style"): dict(
            feature_kind_code="fighting_style", **_choose_feat(feat_category_code="fighting_style"),
        ),
        # l. 4886: "on a roll of 18–20".
        ("Champion", "Superior Critical"): dict(replaces="Improved Critical", effects=[
            dict(operation_code="set", target_code="critical_range", value=18, condition_text=_CRITICAL_CONDITION),
        ]),
        # l. 4892: "_Defy Death._ You have Advantage on Death Saving Throws." (gate #2, H5; the
        # rest of Survivor stays in the text).
        ("Champion", "Survivor"): dict(effects=[
            dict(operation_code="advantage", target_code="death_saving_throw"),
        ]),
    },
    scaling_columns={
        "Second Wind": ("Second Wind", "resource", 0),
        "Weapon Mastery": ("Weapon Mastery", "choice", 0),
    },
    uses={"Action Surge": 0, "Indomitable": 0},
    # l. 4611-4613: Starting Equipment.
    items={
        "Chain Mail": "Chain Mail", "Greatsword": "Greatsword", "Flail": "Flail", "Javelins": "Javelin",
        "Dungeoneer's Pack": "Dungeoneer's Pack", "GP": "Gold Piece", "Studded Leather Armor": "Studded Leather Armor",
        "Scimitar": "Scimitar", "Shortsword": "Shortsword", "Longbow": "Longbow", "Arrows": "Arrow",
        "Quiver": "Quiver",
    },
)

HEADING = re.compile(r"^(#{2,4}) (.+)$")
FEATURE_HEADING = re.compile(r"^Level (\d+): (.+)$")
AGAIN = re.compile(r"You gain this feature again at \w+ levels? ([\d, and]+)\.")
TABLE = re.compile(r"<table>(.*?)</table>", re.DOTALL)
ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
CELL = re.compile(r"<t[dh]>(.*?)</t[dh]>", re.DOTALL)
USES = re.compile(r"^(.+?) \((\w+) uses?\)$")


def _fail(message: str) -> ClassExtractionError:
    return ClassExtractionError(message)


def _clean(text: str) -> str:
    return " ".join(text.split())


def _table_after(text: str, title: str) -> list[list[str]]:
    """Rows (cells, whitespace collapsed) of the first table after `**title**`."""
    start = text.find(f"**{title}**")
    if start < 0:
        raise _fail(f"missing table {title!r}")
    match = TABLE.search(text, start)
    if not match:
        raise _fail(f"missing table {title!r}")
    return [[_clean(cell) for cell in CELL.findall(row)] for row in ROW.findall(match.group(1))]


def _split_list(text: str) -> list[str]:
    """'A, B, and C' / 'A and B' / 'A, B, or C' -> ['A', 'B', 'C']."""
    parts = re.split(r", (?:and |or )?| and | or ", text)
    return [part.strip() for part in parts if part.strip()]


def _mapped(values: list[str], mapping: dict[str, str], label: str) -> list[str]:
    unknown = [value for value in values if value not in mapping]
    if unknown or not values:
        raise _fail(f"{label}: not recognized: {', '.join(unknown) or '(empty)'}")
    return [mapping[value] for value in values]


def _equipment(text: str, items: dict[str, str]) -> tuple[dict, ...]:
    label = "Starting Equipment"
    match = re.match(r"^Choose [A-Z](?:, [A-Z])*,? or [A-Z]: (.+)$", text)
    if not match:
        raise _fail(f"{label}: not recognized: {text!r}")
    options = re.findall(r"\(([A-Z])\) (.+?)(?=;(?: or)? \([A-Z]\)|$)", match.group(1))
    if not options:
        raise _fail(f"{label}: not recognized: {text!r}")
    rows = []
    for option, contents in options:
        for entry in _split_list(contents):
            quantity_match = re.match(r"^(\d+) (.+)$", entry)
            quantity, name = (int(quantity_match.group(1)), quantity_match.group(2)) if quantity_match else (1, entry)
            if name not in items:
                raise _fail(f"{label}: item without map: {name!r}")
            rows.append({"option": option, "item": items[name], "quantity": quantity})
    return tuple(rows)


def _traits(text: str, class_name: str, curated: Curated) -> dict:
    rows = _table_after(text, f"Core {class_name} Traits")
    traits: dict[str, str] = {}
    for row in rows:
        if len(row) != 2 or row[0] not in TRAIT_LABELS:
            raise _fail(f"unknown trait row: {row!r}")
        traits[row[0]] = row[1]
    missing = [label for label in TRAIT_LABELS if label not in traits]
    if missing:
        raise _fail(f"missing trait(s): {', '.join(missing)}")

    hit_die = re.match(rf"^D(\d+) per {class_name} level$", traits["Hit Point Die"])
    if not hit_die:
        raise _fail(f"Hit Point Die: not recognized: {traits['Hit Point Die']!r}")
    primary = sorted(_mapped(_split_list(traits["Primary Ability"]), ABILITIES, "Primary Ability"))
    saves = _mapped(_split_list(traits["Saving Throw Proficiencies"]), ABILITIES, "Saving Throw Proficiencies")
    skills_match = re.match(r"^Choose (\d+): (.+)$", traits["Skill Proficiencies"])
    if not skills_match:
        raise _fail(f"Skill Proficiencies: not recognized: {traits['Skill Proficiencies']!r}")
    skills = sorted(_mapped(_split_list(skills_match.group(2)), SKILLS, "Skill Proficiencies"))
    weapons_match = re.match(r"^(.+) weapons$", traits["Weapon Proficiencies"])
    weapons = _mapped(
        _split_list(weapons_match.group(1)) if weapons_match else [traits["Weapon Proficiencies"]],
        WEAPON_CATEGORIES, "Weapon Proficiencies",
    )
    armor_match = re.match(r"^(.+?) armor( and Shields)?$", traits["Armor Training"])
    if not armor_match:
        raise _fail(f"Armor Training: not recognized: {traits['Armor Training']!r}")
    armor = _mapped(_split_list(armor_match.group(1)), ARMOR_CATEGORIES, "Armor Training")
    if armor_match.group(2):
        armor.append("shield")

    grants = (
        [{"saving_throw_ability_code": code} for code in saves]
        + [{"weapon_category_code": code} for code in weapons]
        + [{"armor_category_code": code} for code in armor]
    )
    return dict(
        hit_die=int(hit_die.group(1)), primary_ability=tuple(primary), proficiency_grants=tuple(grants),
        skill_choices=int(skills_match.group(1)), skills=tuple(skills),
        initial_equipment=_equipment(traits["Starting Equipment"], curated.items),
    )


def _sections(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    """(heading marks, title, body lines) of every heading of the class text."""
    sections: list[tuple[str, str, list[str]]] = []
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            sections.append((heading.group(1), heading.group(2).strip(), []))
        elif sections:
            sections[-1][2].append(line)
    return sections


def _paragraphs(lines: list[str]) -> str:
    paragraphs, current = [], []
    for line in lines + [""]:
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    return "\n\n".join(paragraphs)


def _feature(name: str, level: int, description: str) -> dict:
    return dict(name=name, description=description, level=level, action_type_code=None, feature_kind_code=None,
                is_choice_option=False, replaces=None, effects=(), resources=())


def _features_of(body: list[tuple[str, str, list[str]]], owner: str) -> list[dict]:
    features = []
    for marks, title, lines in body:
        heading = FEATURE_HEADING.match(title)
        if marks != "####" or not heading:
            raise _fail(f"{owner}: feature heading outside the pattern 'Level N: Name': {title!r}")
        level, name = int(heading.group(1)), heading.group(2).strip()
        description = _paragraphs(lines)
        levels = [level]
        if again := AGAIN.search(description):
            levels += [int(value) for value in re.findall(r"\d+", again.group(1))]
        features.extend(_feature(name, lv, description) for lv in levels)
    return sorted(features, key=lambda f: f["level"])


def _apply_structure(owners: dict[str, list[dict]], curated: Curated) -> None:
    index = {(owner, f["name"]) for owner, features in owners.items() for f in features}
    orphans = sorted(f"{owner} / {name}" for owner, name in set(curated.structure) - index)
    if orphans:
        raise _fail(f"curated entries without feature: {', '.join(orphans)}")
    for owner, features in owners.items():
        for feature in features:
            entry = curated.structure.get((owner, feature["name"]))
            if entry is None:
                continue
            structure = normalize_structure(
                copy.deepcopy(entry), STRUCTURE_KEYS, f"{owner} / {feature['name']}", ClassExtractionError,
            )
            replaces = structure.pop("replaces", None)
            feature.update(structure)
            if replaces is not None:
                lower = [f["level"] for f in features if f["name"] == replaces and f["level"] < feature["level"]]
                if len(lower) != 1:
                    raise _fail(f"{owner} / {feature['name']}: replaces {replaces!r}, which is not one lower feature")
                feature["replaces"] = (replaces, lower[0])


def _target(features: list[dict], name: str, kind: str, position: int, label: str) -> dict:
    matches = [f for f in features if f["name"] == name]
    if len(matches) != 1:
        raise _fail(f"{label}: linked to {name!r}, which is not one class feature")
    feature = matches[0]
    try:
        if kind == "resource":
            return feature["resources"][position]
        return feature["effects"][position]["choice"]
    except (IndexError, KeyError):
        raise _fail(f"{label}: {name!r} has no {kind} #{position} in the curated structure") from None


def _set_series(target: dict, key: str, start: int, series: list[tuple[int, int]]) -> None:
    """Base value at `start` into `target[key]`; one scaling row at every later change."""
    base = next(value for level, value in series if level == start)
    target[key] = base
    rows, previous = [], base
    for level, value in series:
        if level > start and value != previous:
            rows.append({"level": level, "value": value})
            previous = value
    if rows:
        target["scaling"] = tuple(rows)


def _apply_table(rows: list[list[str]], features: list[dict], curated: Curated) -> None:
    header, data = rows[0], rows[1:]
    if list(header[:3]) != list(PLAIN_COLUMNS):
        raise _fail(f"unexpected class table header: {header!r}")
    levels = [int(row[0]) for row in data]
    for column in header[3:]:
        if column not in curated.scaling_columns:
            raise _fail(f"table column {column!r} without link to a resource/choice")
        name, kind, position = curated.scaling_columns[column]
        target = _target(features, name, kind, position, f"column {column!r}")
        position_in_row = header.index(column)
        series = [(level, int(row[position_in_row])) for level, row in zip(levels, data)]
        start = next(f["level"] for f in features if f["name"] == name)
        _set_series(target, "value" if kind == "resource" else "choose_count", start, series)

    # Every entry of the Class Features column is a feature heading of that level, except
    # "Subclass feature" and "(N uses)" of a feature gained at a lower level.
    uses: dict[str, list[tuple[int, int]]] = {}
    listed: set[tuple[str, int]] = set()
    headings = {(f["name"], f["level"]) for f in features}
    for level, row in zip(levels, data):
        for entry in _split_list(row[2]):
            if entry == SUBCLASS_FEATURE:
                continue
            name, match = entry, USES.match(entry)
            if match:
                name, word = match.group(1), match.group(2)
                if word not in NUMBER_WORDS:
                    raise _fail(f"table: unknown number {word!r} in {entry!r}")
                uses.setdefault(name, []).append((level, NUMBER_WORDS[word]))
            if (name, level) in headings:
                listed.add((name, level))
            elif not (match and any(n == name and lv < level for n, lv in headings)):
                raise _fail(f"table: {name!r} at level {level} has no feature heading")
    if missing := sorted(headings - listed, key=lambda key: key[1]):
        raise _fail(f"features not in the class table: {missing!r}")
    for name, series in uses.items():
        if name not in curated.uses:
            raise _fail(f"table: uses of {name!r} without link to a resource")
        target = _target(features, name, "resource", curated.uses[name], f"uses of {name!r}")
        start = next(f["level"] for f in features if f["name"] == name)
        _set_series(target, "value", start, series)


def parse_class(text: str, class_name: str = CLASS_NAME, curated: Curated | None = None) -> dict:
    """`{"class": {...}, "subclasses": (...)}` of `class_name` in `text` (classes.md)."""
    curated = CURATED if curated is None else curated
    lines = text.splitlines()
    try:
        start = lines.index(f"## {class_name}")
    except ValueError:
        raise _fail(f"missing '## {class_name}'") from None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    section_lines = lines[start:end]
    section_text = "\n".join(section_lines)

    traits = _traits(section_text, class_name, curated)
    sections = _sections(section_lines)
    class_features_title = f"{class_name} Class Features"
    subclass_prefix = f"{class_name} Subclass: "
    owners: dict[str, list[dict]] = {}
    subclass_descriptions: dict[str, str] = {}
    current: str | None = None
    grouped: dict[str, list] = {}
    for marks, title, body in sections:
        if marks == "###":
            if title == class_features_title:
                current = class_name
            elif title.startswith(subclass_prefix):
                current = title[len(subclass_prefix):]
                subclass_descriptions[current] = _paragraphs(body)
            else:
                current = None
            if current is not None:
                grouped[current] = []
            continue
        if marks == "##":
            continue
        if current is not None:
            grouped[current].append((marks, title, body))
    if class_name not in grouped:
        raise _fail(f"missing '### {class_features_title}'")
    for owner, body in grouped.items():
        owners[owner] = _features_of(body, owner)

    _apply_structure(owners, curated)
    class_features = owners[class_name]
    _apply_table(_table_after(section_text, f"{class_name} Features"), class_features, curated)

    subclass_feature = [f["level"] for f in class_features if f["name"] == f"{class_name} Subclass"]
    if len(subclass_feature) != 1:
        raise _fail(f"missing feature '{class_name} Subclass'")
    klass = dict(
        name=class_name, description=None, **traits, subclass_level=subclass_feature[0], spell_ability=None,
        spellcasting_type=None, features=tuple(class_features),
    )
    subclasses = tuple(
        dict(name=name, **{"class": class_name}, description=subclass_descriptions[name] or None,
             features=tuple(owners[name]))
        for name in grouped if name != class_name
    )
    return {"class": klass, "subclasses": subclasses}


# --- output ---------------------------------------------------------------------

MODULE_DOCSTRING = '''"""SRD 2024 Fighter + Champion, gerado por scripts/extract_srd_fighter.py — não editar à mão.

Só dados (sem import de `app`): importado pela migration c1fcfd7fe014. Para mudar,
ajuste o extrator e rode `python -m scripts.extract_srd_fighter` em backend/.
Itens por nome (uuid5 de SRD_ITEM_NAMESPACE na migration); `replaces` = (nome, nível)
de uma feature do mesmo dono. Estrutura das features: mesmos nomes do payload da API.
"""
'''


def render_module(result: dict) -> str:
    return render_data_module(MODULE_DOCSTRING, {"CLASS": result["class"], "SUBCLASSES": result["subclasses"]})


def main() -> None:
    result = parse_class(SOURCE.read_text(encoding="utf-8"))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render_module(result), encoding="utf-8", newline="\n")
    print(f"{CLASS_NAME}: {len(result['class']['features'])} features, "
          f"{len(result['subclasses'])} subclass(es) -> {TARGET.relative_to(BACKEND_DIR)}")


if __name__ == "__main__":
    main()
