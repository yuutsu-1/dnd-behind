"""Extract the SRD 2024 spells from the SRD markdown into a versioned data module.

Development tool, run by hand from `backend/`:

    python -m scripts.extract_srd_spells

It reads `spells.md` of the SRD markdown (from "## Spell Descriptions" on) and writes
`app/db/seed/srd_spells.py`, which the squashed migration imports. The migration never
reads the markdown; the generated module only changes by running this script again.

Everything is parsed mechanically, except for the curated tables below (each entry
cites the line of the spell in `spells.md`):

- `MATERIAL_SPLITS`: the four material components that become more than one row;
- `CASTING_TIME_OVERRIDES`: Plant Growth, whose casting time has two forms;
- `AREAS`: the area each spell affects (text + shape). Whether a spell "affects an area"
  is a judgement call, so it is curated instead of parsed.

Any form that is not recognized raises `SpellExtractionError` (with the spell name and
the line): no spell is skipped.
"""
import re
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SOURCE = BACKEND_DIR.parent / "docs" / "dnd-5e-srd-markdown-master" / "spells.md"
TARGET = BACKEND_DIR / "app" / "db" / "seed" / "srd_spells.py"

SECTION_HEADING = "## Spell Descriptions"


class SpellExtractionError(Exception):
    pass


SCHOOLS = {
    name: name.lower() for name in (
        "Abjuration", "Conjuration", "Divination", "Enchantment", "Evocation", "Illusion", "Necromancy",
        "Transmutation",
    )
}
SPELL_LISTS = {
    name: name.lower() for name in ("Bard", "Cleric", "Druid", "Paladin", "Ranger", "Sorcerer", "Warlock", "Wizard")
}
AREA_SHAPES = frozenset({"cone", "cube", "cylinder", "emanation", "line", "sphere", "radius", "square"})

CASTING_TIMES = {
    "Action": "action",
    "Bonus Action": "bonus_action",
    "Reaction": "reaction",
    "1 minute": "1_minute",
    "10 minutes": "10_minutes",
    "1 hour": "1_hour",
    "8 hours": "8_hours",
    "12 hours": "12_hours",
    "24 hours": "24_hours",
}
# "<form>, which you take ...": a casting time with a condition. The condition has no
# column of its own: the original line goes to the end of the description.
CONDITIONAL_CASTING_TIMES = ("Reaction", "Bonus Action")
RITUAL_SUFFIX = " or Ritual"

HIGHER_LEVELS_LABEL = "_Using a Higher-Level Spell Slot._"
CANTRIP_UPGRADE_LABEL = "_Cantrip Upgrade._"

# --- curated tables -------------------------------------------------------------

# Material components split in more than one row (cost, consumption, "per target" or
# quantity differ). Each `description` must be an excerpt of the component text.
MATERIAL_SPLITS: dict[str, tuple[dict, ...]] = {
    # spells.md l. 600
    "Astral Projection": (
        dict(description="one jacinth worth 1,000+ GP", cost_gp="1000", consumed=True, per_target=True,
             quantity=1),
        dict(description="one silver bar worth 100+ GP", cost_gp="100", consumed=True, per_target=True,
             quantity=1),
    ),
    # spells.md l. 1011
    "Clone": (
        dict(description="a diamond worth 1,000+ GP, which the spell consumes", cost_gp="1000", consumed=True,
             per_target=False, quantity=1),
        dict(description="a sealable vessel worth 2,000+ GP that is large enough to hold the creature being cloned",
             cost_gp="2000", consumed=False, per_target=False, quantity=1),
    ),
    # spells.md l. 3453
    "Legend Lore": (
        dict(description="incense worth 250+ GP, which the spell consumes", cost_gp="250", consumed=True,
             per_target=False, quantity=1),
        dict(description="four ivory strips worth 50+ GP each", cost_gp="50", consumed=False, per_target=False,
             quantity=4),
    ),
    # spells.md l. 4800
    "Secret Chest": (
        dict(description="a chest, 3 feet by 2 feet by 2 feet, constructed from rare materials worth 5,000+ GP",
             cost_gp="5000", consumed=False, per_target=False, quantity=1),
        dict(description="a Tiny replica of the chest made from the same materials worth 50+ GP", cost_gp="50",
             consumed=False, per_target=False, quantity=1),
    ),
}

# Casting times with more than one form: the code used, and the original line goes to
# the end of the description (decision D4).
CASTING_TIME_OVERRIDES: dict[str, str] = {
    "Plant Growth": "action",  # spells.md l. 4124: "Action (Overgrowth) or 8 hours (Enrichment)"
}

# name -> (area_shape_code, area). Only areas the spell affects, stated in the text with
# a measure; one per spell (the first of the main description). Formats:
# sphere "{N}-foot-radius Sphere", cube "{N}-foot Cube", cone "{N}-foot Cone",
# cylinder "{R}-foot-radius, {H}-foot-high Cylinder", emanation "{N}-foot Emanation",
# line "{L}-foot Line, {W} feet wide", radius "{N}-foot radius", square "{N}-foot square";
# "up to N" uses the maximum.
AREAS: dict[str, tuple[str, str]] = {
    # sphere (28)
    "Acid Splash": ("sphere", "5-foot-radius Sphere"),  # l. 275
    "Calm Emotions": ("sphere", "20-foot-radius Sphere"),  # l. 901
    "Circle of Death": ("sphere", "60-foot-radius Sphere"),  # l. 983
    "Cloudkill": ("sphere", "20-foot-radius Sphere"),  # l. 1023
    "Confusion": ("sphere", "10-foot-radius Sphere"),  # l. 1148
    "Darkness": ("sphere", "15-foot-radius Sphere"),  # l. 1617
    "Daylight": ("sphere", "60-foot-radius Sphere"),  # l. 1643
    "Delayed Blast Fireball": ("sphere", "20-foot-radius Sphere"),  # l. 1671
    "Fireball": ("sphere", "20-foot-radius Sphere"),  # l. 2431
    "Fog Cloud": ("sphere", "20-foot-radius Sphere"),  # l. 2577
    "Freezing Sphere": ("sphere", "60-foot-radius Sphere"),  # l. 2652
    "Glyph of Warding": ("sphere", "20-foot-radius Sphere"),  # l. 2850
    "Incendiary Cloud": ("sphere", "20-foot-radius Sphere"),  # l. 3341
    "Insect Plague": ("sphere", "20-foot-radius Sphere"),  # l. 3368
    "Mass Cure Wounds": ("sphere", "30-foot-radius Sphere"),  # l. 3723
    "Meteor Swarm": ("sphere", "40-foot-radius Sphere"),  # l. 3830
    "Plant Growth": ("sphere", "100-foot-radius Sphere"),  # l. 4124 (Overgrowth)
    "Purify Food and Drink": ("sphere", "5-foot-radius Sphere"),  # l. 4460
    "Shatter": ("sphere", "10-foot-radius Sphere"),  # l. 4890
    "Silence": ("sphere", "20-foot-radius Sphere"),  # l. 4969
    "Sleep": ("sphere", "5-foot-radius Sphere"),  # l. 5011
    "Spike Growth": ("sphere", "20-foot-radius Sphere"),  # l. 5136
    "Stinking Cloud": ("sphere", "20-foot-radius Sphere"),  # l. 5192
    "Sunburst": ("sphere", "60-foot-radius Sphere"),  # l. 5360
    "Symbol": ("sphere", "60-foot-radius Sphere"),  # l. 5375
    "Vitriolic Sphere": ("sphere", "20-foot-radius Sphere"),  # l. 5772
    "Weird": ("sphere", "30-foot-radius Sphere"),  # l. 5927
    "Zone of Truth": ("sphere", "15-foot-radius Sphere"),  # l. 6014
    # cube (19)
    "Alarm": ("cube", "20-foot Cube"),  # l. 301
    "Control Water": ("cube", "100-foot Cube"),  # l. 1346
    "Create or Destroy Water": ("cube", "30-foot Cube"),  # l. 1510
    "Druidcraft": ("cube", "5-foot Cube"),  # l. 2006
    "Elementalism": ("cube", "5-foot Cube"),  # l. 2059
    "Faerie Fire": ("cube", "20-foot Cube"),  # l. 2213
    "Fire Storm": ("cube", "ten 10-foot Cubes"),  # l. 2474
    "Forcecage": ("cube", "20-foot Cube"),  # l. 2607
    "Hallucinatory Terrain": ("cube", "150-foot Cube"),  # l. 3048
    "Hypnotic Pattern": ("cube", "30-foot Cube"),  # l. 3246
    "Major Image": ("cube", "20-foot Cube"),  # l. 3706
    "Minor Illusion": ("cube", "5-foot Cube"),  # l. 3869
    "Phantasmal Force": ("cube", "10-foot Cube"),  # l. 4033
    "Private Sanctum": ("cube", "100-foot Cube"),  # l. 4353
    "Programmed Illusion": ("cube", "30-foot Cube"),  # l. 4392
    "Silent Image": ("cube", "15-foot Cube"),  # l. 4980
    "Slow": ("cube", "40-foot Cube"),  # l. 5037
    "Thunderwave": ("cube", "15-foot Cube"),  # l. 5566
    "Web": ("cube", "20-foot Cube"),  # l. 5908
    # cone (6)
    "Burning Hands": ("cone", "15-foot Cone"),  # l. 867
    "Color Spray": ("cone", "15-foot Cone"),  # l. 1040
    "Cone of Cold": ("cone", "60-foot Cone"),  # l. 1135
    "Dragon's Breath": ("cone", "15-foot Cone"),  # l. 1976
    "Fear": ("cone", "30-foot Cone"),  # l. 2256
    "Prismatic Spray": ("cone", "60-foot Cone"),  # l. 4239
    # cylinder (8)
    "Call Lightning": ("cylinder", "60-foot-radius, 10-foot-high Cylinder"),  # l. 882
    "Conjure Celestial": ("cylinder", "10-foot-radius, 40-foot-high Cylinder"),  # l. 1208
    "Flame Strike": ("cylinder", "10-foot-radius, 40-foot-high Cylinder"),  # l. 2504
    "Ice Storm": ("cylinder", "20-foot-radius, 40-foot-high Cylinder"),  # l. 3272
    "Magic Circle": ("cylinder", "10-foot-radius, 20-foot-high Cylinder"),  # l. 3602
    "Moonbeam": ("cylinder", "5-foot-radius, 40-foot-high Cylinder"),  # l. 3966
    "Reverse Gravity": ("cylinder", "50-foot-radius, 100-foot-high Cylinder"),  # l. 4650
    "Sleet Storm": ("cylinder", "20-foot-radius, 40-foot-high Cylinder"),  # l. 5024
    # emanation (11)
    "Antilife Shell": ("emanation", "10-foot Emanation"),  # l. 473
    "Antimagic Field": ("emanation", "10-foot Emanation"),  # l. 486
    "Aura of Life": ("emanation", "30-foot Emanation"),  # l. 663
    "Conjure Minor Elementals": ("emanation", "15-foot Emanation"),  # l. 1261
    "Conjure Woodland Beings": ("emanation", "10-foot Emanation"),  # l. 1276
    "Globe of Invulnerability": ("emanation", "10-foot Emanation"),  # l. 2835
    "Holy Aura": ("emanation", "30-foot Emanation"),  # l. 3220
    "Pass without Trace": ("emanation", "30-foot Emanation"),  # l. 4022
    "Speak with Plants": ("emanation", "30-foot Emanation"),  # l. 5106
    "Spirit Guardians": ("emanation", "15-foot Emanation"),  # l. 5149
    "Tiny Hut": ("emanation", "10-foot Emanation"),  # l. 5594
    # line (3)
    "Gust of Wind": ("line", "60-foot Line, 10 feet wide"),  # l. 2997
    "Lightning Bolt": ("line", "100-foot Line, 5 feet wide"),  # l. 3507
    "Sunbeam": ("line", "60-foot Line, 5 feet wide"),  # l. 5345
    # radius (10)
    "Continual Flame": ("radius", "20-foot radius"),  # l. 1335
    "Dancing Lights": ("radius", "10-foot radius"),  # l. 1605
    "Earthquake": ("radius", "100-foot radius"),  # l. 2025
    "Fire Shield": ("radius", "10-foot radius"),  # l. 2459
    "Flame Blade": ("radius", "10-foot radius"),  # l. 2487
    "Flaming Sphere": ("radius", "20-foot radius"),  # l. 2517
    "Hallow": ("radius", "60-foot radius"),  # l. 3014
    "Light": ("radius", "20-foot radius"),  # l. 3494
    "Produce Flame": ("radius", "20-foot radius"),  # l. 4377
    "Storm of Vengeance": ("radius", "300-foot radius"),  # l. 5227
    # square (6)
    "Black Tentacles": ("square", "20-foot square"),  # l. 772
    "Entangle": ("square", "20-foot square"),  # l. 2125
    "Grease": ("square", "10-foot square"),  # l. 2891
    "Guards and Wards": ("square", "50-foot square"),  # l. 2945
    "Mirage Arcane": ("square", "1-mile square"),  # l. 3886
    "Move Earth": ("square", "40-foot square"),  # l. 3980
}

# --- parsing --------------------------------------------------------------------

HEADING = re.compile(r"^(##|####) (.+)$")
LEVEL_HEADER = re.compile(r"^_Level ([1-9]) ([A-Za-z]+) \(([^()]+)\)_$")
CANTRIP_HEADER = re.compile(r"^_([A-Za-z]+) Cantrip \(([^()]+)\)_$")
# First line of a summon's stat block: "_Large Celestial, Fey, or Fiend (Your Choice), Neutral_".
STAT_BLOCK_HEADER = re.compile(r"^_(Tiny|Small|Medium|Large|Huge|Gargantuan)\b.*, [A-Za-z ]+_$")
STAT_BLOCK_SECTIONS = frozenset({"Traits", "Actions", "Bonus Actions", "Reactions"})
COMPONENTS_LINE = re.compile(r"^\*\*Components?:\*\* (.+)$")
COST = re.compile(r"([\d,]+)\+ (GP|SP|CP)\b")
COPPER_PIECES = re.compile(r"^(\d+) Copper Pieces?\b")
COIN_IN_GP = {"GP": Decimal("1"), "SP": Decimal("0.1"), "CP": Decimal("0.01")}
LEADING_QUANTITY = {"a pair of ": 2, "two ": 2, "three ": 3, "four ": 4, "five ": 5}
PER_TARGET_MARKERS = ("for each of the spell's targets", "for each corpse")


def _fail(name: str, line: int, message: str) -> SpellExtractionError:
    return SpellExtractionError(f"{name} (line {line}): {message}")


def _gp(amount: str, coin: str) -> str:
    return str(Decimal(amount.replace(",", "")) * COIN_IN_GP[coin])


def _material_rows(name: str, line: int, text: str, splits: dict) -> tuple[dict, ...]:
    if name in splits:
        for row in splits[name]:
            if row["description"] not in text:
                raise _fail(name, line, f"curated material {row['description']!r} is not in {text!r}")
        return tuple(dict(row) for row in splits[name])
    costs = COST.findall(text)
    copper = COPPER_PIECES.match(text)
    if len(costs) > 1:
        raise _fail(name, line, f"material with more than one cost needs a curated split: {text!r}")
    cost_gp, quantity = None, 1
    if copper:
        cost_gp, quantity = _gp("1", "CP"), int(copper.group(1))
    elif costs:
        cost_gp = _gp(*costs[0])
        quantity = next((n for prefix, n in LEADING_QUANTITY.items() if text.startswith(prefix)), 1)
    return (dict(
        description=text,
        cost_gp=cost_gp,
        consumed="the spell consumes" in text,
        per_target=any(marker in text for marker in PER_TARGET_MARKERS),
        quantity=quantity,
    ),)


def _components(name: str, line: int, value: str, splits: dict) -> dict:
    material = None
    head = value
    if value.startswith("M (") or ", M (" in value:
        head, _, rest = value.partition("M (")
        if not rest.endswith(")"):
            raise _fail(name, line, f"unrecognized components: {value!r}")
        material = rest[:-1]
    letters = [part for part in head.rstrip(", ").split(", ") if part]
    if letters not in ([], ["V"], ["S"], ["V", "S"]) or (not letters and material is None):
        raise _fail(name, line, f"unrecognized components: {value!r}")
    return dict(
        has_verbal="V" in letters,
        has_somatic="S" in letters,
        has_material=material is not None,
        materials=_material_rows(name, line, material, splits) if material is not None else (),
    )


def _casting_time(name: str, line: int, value: str, overrides: dict) -> tuple[str, bool, bool]:
    """(code, ritual, whether the original line goes to the description)."""
    ritual = value.endswith(RITUAL_SUFFIX)
    base = value[: -len(RITUAL_SUFFIX)] if ritual else value
    if base in CASTING_TIMES:
        return CASTING_TIMES[base], ritual, False
    for form in CONDITIONAL_CASTING_TIMES:
        if base.startswith(f"{form}, which you take "):
            return CASTING_TIMES[form], ritual, True
    if name in overrides:
        return overrides[name], False, True
    raise _fail(name, line, f"unrecognized casting time: {value!r}")


def _stat_line(name: str, lines: list[tuple[int, str]], index: int, prefix: str) -> str:
    if index >= len(lines) or not lines[index][1].startswith(prefix):
        number = lines[index][0] if index < len(lines) else lines[-1][0]
        raise _fail(name, number, f"expected a {prefix!r} line")
    return lines[index][1][len(prefix):]


def _paragraphs(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    current: list[str] = []
    start = 0
    for number, text in lines + [(0, "")]:
        # A labeled paragraph sometimes follows the previous one without a blank line.
        if current and text.startswith((HIGHER_LEVELS_LABEL, CANTRIP_UPGRADE_LABEL)):
            paragraphs.append((start, "\n".join(current).rstrip()))
            current = []
        if text.strip():
            if not current:
                start = number
            current.append(text)
        elif current:
            paragraphs.append((start, "\n".join(current).rstrip()))
            current = []
    return paragraphs


def _parse_spell(name: str, heading_line: int, header_line: int, level: int, school: str, classes: str,
                 body: list[tuple[int, str]], curated: dict) -> dict:
    if school not in SCHOOLS:
        raise _fail(name, header_line, f"unknown school {school!r}")
    lists = []
    for class_name in classes.split(", "):
        if class_name not in SPELL_LISTS:
            raise _fail(name, header_line, f"unknown class {class_name!r} in the header")
        lists.append(SPELL_LISTS[class_name])

    stat_lines = [entry for entry in body if entry[1].strip()][:4]
    casting = _stat_line(name, stat_lines, 0, "**Casting Time:** ")
    range_ = _stat_line(name, stat_lines, 1, "**Range:** ")
    components_line = stat_lines[2] if len(stat_lines) > 2 else (heading_line, "")
    match = COMPONENTS_LINE.match(components_line[1])
    if not match:
        raise _fail(name, components_line[0], f"unrecognized components line: {components_line[1]!r}")
    components = _components(name, components_line[0], match.group(1), curated["material_splits"])
    duration = _stat_line(name, stat_lines, 3, "**Duration:** ")
    code, ritual, keep_casting_line = _casting_time(
        name, stat_lines[0][0], casting, curated["casting_time_overrides"]
    )

    rest = [entry for entry in body if entry[0] > stat_lines[3][0]]
    description: list[str] = []
    higher_levels = cantrip_upgrade = None
    for number, paragraph in _paragraphs(rest):
        if paragraph.startswith(HIGHER_LEVELS_LABEL):
            if level == 0 or higher_levels is not None:
                raise _fail(name, number, f"unexpected {HIGHER_LEVELS_LABEL!r} paragraph")
            higher_levels = paragraph[len(HIGHER_LEVELS_LABEL):].strip()
        elif paragraph.startswith(CANTRIP_UPGRADE_LABEL):
            if level != 0 or cantrip_upgrade is not None:
                raise _fail(name, number, f"unexpected {CANTRIP_UPGRADE_LABEL!r} paragraph")
            cantrip_upgrade = paragraph[len(CANTRIP_UPGRADE_LABEL):].strip()
        else:
            description.append(paragraph)
    if keep_casting_line:
        description.append(f"Casting Time: {casting}")
    if not description:
        raise _fail(name, heading_line, "empty description")

    return dict(
        name=name,
        level=level,
        school_code=SCHOOLS[school],
        spell_lists=tuple(sorted(lists)),
        casting_time_code=code,
        ritual=ritual,
        concentration=duration.startswith("Concentration"),
        **components,
        range=range_,
        duration=duration,
        area=None,
        area_shape_code=None,
        description="\n\n".join(description),
        higher_levels=higher_levels,
        cantrip_upgrade=cantrip_upgrade,
    )


def parse_spells(
    markdown: str,
    *,
    areas: dict[str, tuple[str, str]] = AREAS,
    material_splits: dict[str, tuple[dict, ...]] = MATERIAL_SPLITS,
    casting_time_overrides: dict[str, str] = CASTING_TIME_OVERRIDES,
) -> list[dict]:
    """Every spell after "## Spell Descriptions", in the order of the text."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    try:
        start = lines.index(SECTION_HEADING)
    except ValueError:
        raise SpellExtractionError(f"missing {SECTION_HEADING!r}") from None
    numbered = [(index + 1, text) for index, text in enumerate(lines)][start + 1:]
    headings = [i for i, (_, text) in enumerate(numbered) if HEADING.match(text)]
    curated = dict(material_splits=material_splits, casting_time_overrides=casting_time_overrides)

    spells: list[dict] = []
    in_stat_block = False
    for position, index in enumerate(headings):
        number, text = numbered[index]
        title = HEADING.match(text).group(2)
        end = headings[position + 1] if position + 1 < len(headings) else len(numbered)
        block = numbered[index + 1:end]
        first = next(((n, t) for n, t in block if t.strip()), (number, ""))
        level_header = LEVEL_HEADER.match(first[1])
        cantrip_header = CANTRIP_HEADER.match(first[1])
        if level_header or cantrip_header:
            in_stat_block = False
            if level_header:
                level, school, classes = int(level_header.group(1)), level_header.group(2), level_header.group(3)
            else:
                level, school, classes = 0, cantrip_header.group(1), cantrip_header.group(2)
            body = [entry for entry in block if entry[0] > first[0]]
            spells.append(_parse_spell(title, number, first[0], level, school, classes, body, curated))
        elif STAT_BLOCK_HEADER.match(first[1]) and spells:
            in_stat_block = True  # a summon's stat block: dropped (monsters, phase 8)
        elif in_stat_block and title in STAT_BLOCK_SECTIONS:
            continue
        else:
            raise _fail(title, number, f"unrecognized header: {first[1]!r}")

    names = [spell["name"] for spell in spells]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise SpellExtractionError(f"duplicate spell names: {', '.join(duplicates)}")
    by_name = {spell["name"]: spell for spell in spells}
    for table in (areas, material_splits, casting_time_overrides):
        unknown = sorted(set(table) - set(by_name))
        if unknown:
            raise SpellExtractionError(f"curated entries without spell: {', '.join(unknown)}")
    for name, (shape, text) in areas.items():
        if shape not in AREA_SHAPES:
            raise SpellExtractionError(f"{name}: unknown area shape {shape!r}")
        by_name[name]["area"], by_name[name]["area_shape_code"] = text, shape
    return spells


# --- output ---------------------------------------------------------------------

MODULE_DOCSTRING = '''"""SRD 2024 spells, gerado por scripts/extract_srd_spells.py — não editar à mão.

Só dados (sem import de `app`): importado pela migration c1fcfd7fe014. Para mudar,
ajuste o extrator e rode `python -m scripts.extract_srd_spells` em backend/.
`cost_gp` é texto decimal em ouro, por unidade.
"""
'''


def _render_value(key: str, value) -> str:
    if key == "materials" and value:
        rows = "".join(f"            {row!r},\n" for row in value)
        return f"(\n{rows}        )"
    return repr(value)


def render_module(spells: list[dict]) -> str:
    out = [MODULE_DOCSTRING, "\nSPELLS = (\n"]
    for spell in spells:
        out.append("    {\n")
        for key, value in spell.items():
            out.append(f"        {key!r}: {_render_value(key, value)},\n")
        out.append("    },\n")
    out.append(")\n")
    return "".join(out)


def main() -> None:
    spells = parse_spells(SOURCE.read_text(encoding="utf-8"))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render_module(spells), encoding="utf-8", newline="\n")
    print(f"{len(spells)} spells -> {TARGET.relative_to(BACKEND_DIR)}")


if __name__ == "__main__":
    main()
