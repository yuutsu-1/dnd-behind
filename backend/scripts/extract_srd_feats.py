"""Extract the SRD 2024 feats from the SRD markdown into a versioned data module.

Development tool, run by hand from `backend/`:

    python -m scripts.extract_srd_feats

It reads `feats.md` of the SRD markdown (from "### Origin Feats" on) and writes
`app/db/seed/srd_feats.py`, which the squashed migration imports. The migration never
reads the markdown; the generated module only changes by running this script again.

Parsed mechanically:
- `#### Name` starts a feat; the italic line under it gives the category and the
  prerequisites ("(Prerequisite: Level 4+, Strength or Dexterity 13+)": a comma starts a
  new AND group, "A or B 13+" are alternatives in the same group);
- the text before the first italic block is the feat's description;
- each italic block (`_Name._ text`) is one feature; a feat without blocks is one
  feature with the feat's name and text;
- the `_Repeatable._` block only sets `repeatable` (its text goes to the end of the
  feat's description).

`FEATURE_STRUCTURE` (curated, each entry citing the line of `feats.md`) gives what is
structured in each feature: effects, choices, options, resources, recharges, action
type. Features without an entry are text only. Any form that is not recognized raises
`FeatExtractionError` (with the feat name and the line): nothing is skipped.
"""
import re
from pathlib import Path

from scripts.srd_features import normalize_structure, render_data_module

BACKEND_DIR = Path(__file__).resolve().parents[1]
SOURCE = BACKEND_DIR.parent / "docs" / "dnd-5e-srd-markdown-master" / "feats.md"
TARGET = BACKEND_DIR / "app" / "db" / "seed" / "srd_feats.py"

START_HEADING = "### Origin Feats"


class FeatExtractionError(Exception):
    pass


CATEGORIES = {
    "Origin": "origin",
    "General": "general",
    "Fighting Style": "fighting_style",
    "Epic Boon": "epic_boon",
}
ABILITIES = {
    "Strength": "str", "Dexterity": "dex", "Constitution": "con",
    "Intelligence": "int", "Wisdom": "wis", "Charisma": "cha",
}
# "<X> Feature" prerequisites -> feature_kinds code.
FEATURE_KINDS = {"Fighting Style": "fighting_style", "Spellcasting": "spellcasting"}

REPEATABLE = "Repeatable"

HEADING = re.compile(r"^(#{1,4}) (.+)$")
CATEGORY_LINE = re.compile(r"^_(.+?) Feat(?: \(Prerequisite: (.*)\))?_$")
BLOCK = re.compile(r"^_([^_]+?)\._ (.+)$", re.DOTALL)
LEVEL = re.compile(r"^Level (\d+)\+$")
ABILITY_SCORE = re.compile(r"^(.+?) (\d+)\+$")
FEATURE_KIND = re.compile(r"^(.+) Feature$")

# --- curated structure ------------------------------------------------------------

# feats.md l. 173: "Resistance to all damage except Psychic and Radiant" (the 13 SRD damage
# types minus those two).
_ALL_DAMAGE_BUT_PSYCHIC_AND_RADIANT = (
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison", "slashing",
    "thunder",
)


def _boon_asi(*abilities: str) -> dict:
    """'Increase one ability score of your choice (or one of `abilities`) by 1, to a maximum of 30.'"""
    choice = dict(pool_type_code="ability_score", choose_count=1)
    if abilities:
        choice["options"] = [dict(ability_code=code) for code in abilities]
    return dict(effects=[dict(operation_code="ability_score_increase", value=1, max_value=30, choice=choice)])


FEATURE_STRUCTURE: dict[tuple[str, str], dict] = {
    # l. 27: "add your Proficiency Bonus to the roll" (Initiative).
    ("Alert", "Initiative Proficiency"): dict(effects=[
        dict(operation_code="bonus", target_code="initiative", value_basis_code="proficiency_bonus"),
    ]),
    # l. 55: "proficiency in any combination of three skills or tools of your choice".
    ("Skilled", "Skilled"): dict(effects=[
        dict(operation_code="grant", choice=dict(pool_type_code="skill_or_tool", choose_count=3)),
    ]),
    # l. 65: "increase one ability score by 2, or two ability scores by 1 ... can't increase
    # an ability score above 20" = two picks of +1, repeat allowed.
    ("Ability Score Improvement", "Ability Score Improvement"): dict(effects=[
        dict(operation_code="ability_score_increase", value=1, max_value=20,
             choice=dict(pool_type_code="ability_score", choose_count=2, allow_repeat=True)),
    ]),
    # l. 75: "Increase your Strength or Dexterity score by 1, to a maximum of 20."
    ("Grappler", "Ability Score Increase"): dict(effects=[
        dict(operation_code="ability_score_increase", value=1, max_value=20,
             choice=dict(pool_type_code="ability_score", choose_count=1,
                         options=[dict(ability_code="str"), dict(ability_code="dex")])),
    ]),
    # l. 79: "Advantage on attack rolls against a creature Grappled by you."
    ("Grappler", "Attack Advantage"): dict(effects=[
        dict(operation_code="advantage", target_code="attack_roll",
             condition_text="against a creature Grappled by you"),
    ]),
    # l. 89: "+2 bonus to attack rolls you make with Ranged weapons".
    ("Archery", "Archery"): dict(effects=[
        dict(operation_code="bonus", target_code="attack_roll", value=2, condition_text="with Ranged weapons"),
    ]),
    # l. 95: "While you're wearing Light, Medium, or Heavy armor, you gain a +1 bonus to Armor Class."
    ("Defense", "Defense"): dict(effects=[
        dict(operation_code="bonus", target_code="armor_class", value=1,
             condition_text="while wearing Light, Medium, or Heavy armor"),
    ]),
    ("Boon of Combat Prowess", "Ability Score Increase"): _boon_asi(),  # l. 117
    ("Boon of Dimensional Travel", "Ability Score Increase"): _boon_asi(),  # l. 127
    ("Boon of Fate", "Ability Score Increase"): _boon_asi(),  # l. 137
    # l. 139: "can't use it again until you roll Initiative or finish a Short or Long Rest".
    ("Boon of Fate", "Improve Fate"): dict(resources=[
        dict(name="Improve Fate", value=1, recharges=[
            dict(recharge_type_code="initiative", recovers=None),
            dict(recharge_type_code="short_rest", recovers=None),
            dict(recharge_type_code="long_rest", recovers=None),
        ]),
    ]),
    ("Boon of Irresistible Offense", "Ability Score Increase"): _boon_asi("str", "dex"),  # l. 147
    ("Boon of Spell Recall", "Ability Score Increase"): _boon_asi("int", "wis", "cha"),  # l. 159
    ("Boon of the Night Spirit", "Ability Score Increase"): _boon_asi(),  # l. 169
    # l. 171: "as a Bonus Action".
    ("Boon of the Night Spirit", "Merge with Shadows"): dict(action_type_code="bonus_action"),
    # l. 173: "While within Dim Light or Darkness, you have Resistance to all damage except
    # Psychic and Radiant."
    ("Boon of the Night Spirit", "Shadowy Form"): dict(effects=[
        dict(operation_code="damage_resistance", damage_type_code=code,
             condition_text="while within Dim Light or Darkness")
        for code in _ALL_DAMAGE_BUT_PSYCHIC_AND_RADIANT
    ]),
    ("Boon of Truesight", "Ability Score Increase"): _boon_asi(),  # l. 181
    # l. 183: "Truesight with a range of 60 feet".
    ("Boon of Truesight", "Truesight"): dict(effects=[
        dict(operation_code="grant", sense_code="truesight", value=60),
    ]),
}
STRUCTURE_KEYS = frozenset({"action_type_code", "effects", "resources"})


# --- parsing ----------------------------------------------------------------------

def _fail(name: str, line: int, message: str) -> FeatExtractionError:
    return FeatExtractionError(f"{name} (line {line}): {message}")


def _parse_prerequisites(name: str, line: int, text: str) -> tuple[dict, ...]:
    rows: list[dict] = []
    for group, part in enumerate(text.split(", "), start=1):
        base = dict(or_group=group, min_character_level=None, ability_code=None, min_score=None,
                    feature_kind_code=None)
        if match := LEVEL.match(part):
            rows.append({**base, "min_character_level": int(match.group(1))})
        elif (match := FEATURE_KIND.match(part)) and match.group(1) in FEATURE_KINDS:
            rows.append({**base, "feature_kind_code": FEATURE_KINDS[match.group(1)]})
        elif match := ABILITY_SCORE.match(part):
            names = match.group(1).split(" or ")
            if any(ability not in ABILITIES for ability in names):
                raise _fail(name, line, f"unknown ability in prerequisite {part!r}")
            rows.extend({**base, "ability_code": ABILITIES[ability], "min_score": int(match.group(2))}
                        for ability in names)
        else:
            raise _fail(name, line, f"prerequisite outside the grammar: {part!r}")
    return tuple(rows)


def _paragraphs(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """(first line number, text) of each blank-line separated paragraph."""
    paragraphs: list[tuple[int, str]] = []
    current: list[tuple[int, str]] = []
    for number, text in lines + [(0, "")]:
        if text.strip():
            current.append((number, text.strip()))
        elif current:
            paragraphs.append((current[0][0], " ".join(t for _, t in current)))
            current = []
    return paragraphs


def _feature(name: str, description: str) -> dict:
    return dict(name=name, description=description, level=None, action_type_code=None, feature_kind_code=None,
                is_choice_option=False, replaces=None, effects=(), resources=())


def _parse_feat(name: str, number: int, body: list[tuple[int, str]]) -> dict:
    paragraphs = _paragraphs(body)
    if not paragraphs:
        raise _fail(name, number, "missing category line")
    category_line, rest = paragraphs[0], paragraphs[1:]
    match = CATEGORY_LINE.match(category_line[1])
    if not match:
        raise _fail(name, category_line[0], f"missing category line: {category_line[1]!r}")
    category, prerequisite = match.group(1), match.group(2)
    if category not in CATEGORIES:
        raise _fail(name, category_line[0], f"unknown category {category!r}")
    prerequisites = (
        _parse_prerequisites(name, category_line[0], prerequisite) if prerequisite is not None else ()
    )

    intro: list[str] = []
    blocks: list[list] = []  # [name, [texts]]
    repeatable_text: str | None = None
    for line, text in rest:
        if text.startswith("_"):
            block = BLOCK.match(text)
            if not block:
                raise _fail(name, line, f"malformed italic block: {text[:40]!r}")
            label, block_text = block.group(1), block.group(2)
            if label == REPEATABLE:
                repeatable_text = block_text
            else:
                blocks.append([label, [block_text]])
        elif blocks:
            blocks[-1][1].append(text)
        else:
            intro.append(text)

    body_text = "\n\n".join(intro)
    if blocks:
        features = [_feature(label, "\n\n".join(texts)) for label, texts in blocks]
    else:
        features = [_feature(name, body_text)]
    description = "\n\n".join(part for part in (body_text, repeatable_text) if part)
    return dict(
        name=name, category_code=CATEGORIES[category], description=description or None,
        repeatable=repeatable_text is not None, prerequisites=prerequisites, features=tuple(features),
    )


def parse_feats(text: str, curated: dict[tuple[str, str], dict] | None = None) -> list[dict]:
    """Every feat of `text` (from "### Origin Feats" on), with `curated` structure applied."""
    curated = FEATURE_STRUCTURE if curated is None else curated
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == START_HEADING)
    except StopIteration:
        raise FeatExtractionError(f"missing {START_HEADING!r}") from None
    numbered = [(i + 1, line) for i, line in enumerate(lines)][start:]

    # Split into sections at every heading; only `####` sections are feats.
    sections: list[tuple[str, str, int, list[tuple[int, str]]]] = []
    for number, line in numbered:
        heading = HEADING.match(line)
        if heading is not None:
            sections.append((heading.group(1), heading.group(2).strip(), number, []))
        elif sections:
            sections[-1][3].append((number, line))
    feats = [_parse_feat(title, number, body) for level, title, number, body in sections if level == "####"]

    names = [feat["name"] for feat in feats]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise FeatExtractionError(f"duplicate feat names: {', '.join(duplicates)}")

    features = {(feat["name"], feature["name"]): feature for feat in feats for feature in feat["features"]}
    orphans = sorted(f"{feat} / {feature}" for feat, feature in set(curated) - set(features))
    if orphans:
        raise FeatExtractionError(f"curated entries without feature: {', '.join(orphans)}")
    for key, entry in curated.items():
        structure = normalize_structure(entry, STRUCTURE_KEYS, " / ".join(key), FeatExtractionError)
        features[key].update(structure)
    return feats


# --- output ---------------------------------------------------------------------

MODULE_DOCSTRING = '''"""SRD 2024 feats, gerado por scripts/extract_srd_feats.py — não editar à mão.

Só dados (sem import de `app`): importado pela migration c1fcfd7fe014. Para mudar,
ajuste o extrator e rode `python -m scripts.extract_srd_feats` em backend/.
Estrutura das features: mesmos nomes do payload da API (efeitos esparsos; a
migration completa os defaults).
"""
'''


def render_module(feats: list[dict]) -> str:
    return render_data_module(MODULE_DOCSTRING, {"FEATS": tuple(feats)})


def main() -> None:
    feats = parse_feats(SOURCE.read_text(encoding="utf-8"))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render_module(feats), encoding="utf-8", newline="\n")
    print(f"{len(feats)} feats -> {TARGET.relative_to(BACKEND_DIR)}")


if __name__ == "__main__":
    main()
