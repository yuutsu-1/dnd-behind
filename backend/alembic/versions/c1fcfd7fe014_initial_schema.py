"""initial schema

Revision ID: c1fcfd7fe014
Revises: 
Create Date: 2026-10-04 13:45:36.399611

"""
import uuid
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c1fcfd7fe014'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- SRD 2024 seed -----------------------------------------------------------
# Every row is `source="srd"`, `is_homebrew=False`, `created_by=NULL`.

ABILITY_SCORES = [
    ("str", "Strength"), ("dex", "Dexterity"), ("con", "Constitution"),
    ("int", "Intelligence"), ("wis", "Wisdom"), ("cha", "Charisma"),
]

# (code, name, ability_code)
SKILLS = [
    ("acrobatics", "Acrobatics", "dex"),
    ("animal_handling", "Animal Handling", "wis"),
    ("arcana", "Arcana", "int"),
    ("athletics", "Athletics", "str"),
    ("deception", "Deception", "cha"),
    ("history", "History", "int"),
    ("insight", "Insight", "wis"),
    ("intimidation", "Intimidation", "cha"),
    ("investigation", "Investigation", "int"),
    ("medicine", "Medicine", "wis"),
    ("nature", "Nature", "int"),
    ("perception", "Perception", "wis"),
    ("performance", "Performance", "cha"),
    ("persuasion", "Persuasion", "cha"),
    ("religion", "Religion", "int"),
    ("sleight_of_hand", "Sleight of Hand", "dex"),
    ("stealth", "Stealth", "dex"),
    ("survival", "Survival", "wis"),
]

DAMAGE_TYPES = [
    ("acid", "Acid"), ("bludgeoning", "Bludgeoning"), ("cold", "Cold"), ("fire", "Fire"),
    ("force", "Force"), ("lightning", "Lightning"), ("necrotic", "Necrotic"), ("piercing", "Piercing"),
    ("poison", "Poison"), ("psychic", "Psychic"), ("radiant", "Radiant"), ("slashing", "Slashing"),
    ("thunder", "Thunder"),
]

CONDITIONS = [
    ("blinded", "Blinded"), ("charmed", "Charmed"), ("deafened", "Deafened"), ("exhaustion", "Exhaustion"),
    ("frightened", "Frightened"), ("grappled", "Grappled"), ("incapacitated", "Incapacitated"),
    ("invisible", "Invisible"), ("paralyzed", "Paralyzed"), ("petrified", "Petrified"),
    ("poisoned", "Poisoned"), ("prone", "Prone"), ("restrained", "Restrained"), ("stunned", "Stunned"),
    ("unconscious", "Unconscious"),
]

# (condition_code, implied_condition_code) -- rules-glossary.md condition entries.
CONDITION_IMPLICATIONS = [
    ("paralyzed", "incapacitated"),
    ("petrified", "incapacitated"),
    ("stunned", "incapacitated"),
    ("unconscious", "incapacitated"),
    ("unconscious", "prone"),
]

CREATURE_TYPES = [
    ("aberration", "Aberration"), ("beast", "Beast"), ("celestial", "Celestial"), ("construct", "Construct"),
    ("dragon", "Dragon"), ("elemental", "Elemental"), ("fey", "Fey"), ("fiend", "Fiend"), ("giant", "Giant"),
    ("humanoid", "Humanoid"), ("monstrosity", "Monstrosity"), ("ooze", "Ooze"), ("plant", "Plant"),
    ("undead", "Undead"),
]

# (code, name, hit_die, carry_multiplier, sort_order) -- monsters.md "Hit Dice by
# Size" and rules-glossary.md "Carrying Capacity".
SIZES = [
    ("tiny", "Tiny", 4, "7.5", 1),
    ("small", "Small", 6, "15", 2),
    ("medium", "Medium", 8, "15", 3),
    ("large", "Large", 10, "30", 4),
    ("huge", "Huge", 12, "60", 5),
    ("gargantuan", "Gargantuan", 20, "120", 6),
]

ALIGNMENTS = [
    ("lawful_good", "Lawful Good"), ("neutral_good", "Neutral Good"), ("chaotic_good", "Chaotic Good"),
    ("lawful_neutral", "Lawful Neutral"), ("neutral", "Neutral"), ("chaotic_neutral", "Chaotic Neutral"),
    ("lawful_evil", "Lawful Evil"), ("neutral_evil", "Neutral Evil"), ("chaotic_evil", "Chaotic Evil"),
    ("unaligned", "Unaligned"),
]

# (code, name, rarity) -- character-creation.md Standard/Rare Languages.
LANGUAGES = [
    ("common", "Common", "standard"),
    ("common_sign_language", "Common Sign Language", "standard"),
    ("draconic", "Draconic", "standard"),
    ("dwarvish", "Dwarvish", "standard"),
    ("elvish", "Elvish", "standard"),
    ("giant", "Giant", "standard"),
    ("gnomish", "Gnomish", "standard"),
    ("goblin", "Goblin", "standard"),
    ("halfling", "Halfling", "standard"),
    ("orc", "Orc", "standard"),
    ("abyssal", "Abyssal", "rare"),
    ("celestial", "Celestial", "rare"),
    ("deep_speech", "Deep Speech", "rare"),
    ("druidic", "Druidic", "rare"),
    ("infernal", "Infernal", "rare"),
    ("primordial", "Primordial", "rare"),
    ("sylvan", "Sylvan", "rare"),
    ("thieves_cant", "Thieves' Cant", "rare"),
    ("undercommon", "Undercommon", "rare"),
]

SENSES = [
    ("blindsight", "Blindsight"), ("darkvision", "Darkvision"),
    ("tremorsense", "Tremorsense"), ("truesight", "Truesight"),
]

MOVEMENT_MODES = [
    ("walk", "Walk"), ("burrow", "Burrow"), ("climb", "Climb"), ("fly", "Fly"), ("swim", "Swim"),
]

WEAPON_CATEGORIES = [("simple", "Simple"), ("martial", "Martial")]

WEAPON_PROPERTIES = [
    ("ammunition", "Ammunition"), ("finesse", "Finesse"), ("heavy", "Heavy"), ("light", "Light"),
    ("loading", "Loading"), ("range", "Range"), ("reach", "Reach"), ("thrown", "Thrown"),
    ("two_handed", "Two-Handed"), ("versatile", "Versatile"),
]

WEAPON_MASTERIES = [
    ("cleave", "Cleave"), ("graze", "Graze"), ("nick", "Nick"), ("push", "Push"),
    ("sap", "Sap"), ("slow", "Slow"), ("topple", "Topple"), ("vex", "Vex"),
]

ARMOR_CATEGORIES = [
    ("light", "Light Armor"), ("medium", "Medium Armor"), ("heavy", "Heavy Armor"), ("shield", "Shield"),
]

TOOL_CATEGORIES = [
    ("artisans_tools", "Artisan's Tools"), ("gaming_set", "Gaming Set"), ("musical_instrument", "Musical Instrument"),
]

SPELL_SCHOOLS = [
    ("abjuration", "Abjuration"), ("conjuration", "Conjuration"), ("divination", "Divination"),
    ("enchantment", "Enchantment"), ("evocation", "Evocation"), ("illusion", "Illusion"),
    ("necromancy", "Necromancy"), ("transmutation", "Transmutation"),
]

RECHARGE_TYPES = [
    ("short_rest", "Short Rest"), ("long_rest", "Long Rest"), ("dawn", "Dawn"),
    ("initiative", "Initiative"), ("turn", "Turn"),
]

ACTION_TYPES = [("action", "Action"), ("bonus_action", "Bonus Action"), ("reaction", "Reaction")]

FEAT_CATEGORIES = [
    ("origin", "Origin"), ("general", "General"), ("fighting_style", "Fighting Style"), ("epic_boon", "Epic Boon"),
]

# (level, min_xp, proficiency_bonus) -- character-creation.md "Character Advancement".
CHARACTER_LEVELS = [
    (1, 0, 2), (2, 300, 2), (3, 900, 2), (4, 2700, 2),
    (5, 6500, 3), (6, 14000, 3), (7, 23000, 3), (8, 34000, 3),
    (9, 48000, 4), (10, 64000, 4), (11, 85000, 4), (12, 100000, 4),
    (13, 120000, 5), (14, 140000, 5), (15, 165000, 5), (16, 195000, 5),
    (17, 225000, 6), (18, 265000, 6), (19, 305000, 6), (20, 355000, 6),
]


def _cr_proficiency_bonus(value: float) -> int:
    # monsters.md "Proficiency Bonus by Challenge Rating": 0-4 +2, 5-8 +3, ... 29-30 +9.
    if value <= 4:
        return 2
    return 2 + (int(value) - 1) // 4


# (code, name, numeric_value) -- monsters.md "Experience Points by Challenge Rating".
CHALLENGE_RATINGS = [("0", "0", "0"), ("1_8", "1/8", "0.125"), ("1_4", "1/4", "0.25"), ("1_2", "1/2", "0.5")] + [
    (str(n), str(n), str(n)) for n in range(1, 31)
]

# (score, cost) -- character-creation.md "Ability Score Point Costs".
POINT_BUY_COSTS = [(8, 0), (9, 1), (10, 2), (11, 3), (12, 4), (13, 5), (14, 7), (15, 9)]

# equipment.md "Weapons", "Armor", "Tools" and "Adventuring Gear".
ITEM_TYPES = [
    ("weapon", "Weapon"), ("armor", "Armor"), ("tool", "Tool"), ("ammunition", "Ammunition"),
    ("adventuring_gear", "Adventuring Gear"), ("pack", "Pack"), ("currency", "Currency"),
]

# (code, name, category_code, ability_code, cost_gp, weight_lb) -- equipment.md "Tools".
# Each variant is its own tool type (the SRD requires a separate proficiency for each);
# the physical item of the same name points to it. Gaming Sets weigh "—" (0).
TOOLS = [
    ("alchemists_supplies", "Alchemist's Supplies", "artisans_tools", "int", "50", "8"),
    ("brewers_supplies", "Brewer's Supplies", "artisans_tools", "int", "20", "9"),
    ("calligraphers_supplies", "Calligrapher's Supplies", "artisans_tools", "dex", "10", "5"),
    ("carpenters_tools", "Carpenter's Tools", "artisans_tools", "str", "8", "6"),
    ("cartographers_tools", "Cartographer's Tools", "artisans_tools", "wis", "15", "6"),
    ("cobblers_tools", "Cobbler's Tools", "artisans_tools", "dex", "5", "5"),
    ("cooks_utensils", "Cook's Utensils", "artisans_tools", "wis", "1", "8"),
    ("glassblowers_tools", "Glassblower's Tools", "artisans_tools", "int", "30", "5"),
    ("jewelers_tools", "Jeweler's Tools", "artisans_tools", "int", "25", "2"),
    ("leatherworkers_tools", "Leatherworker's Tools", "artisans_tools", "dex", "5", "5"),
    ("masons_tools", "Mason's Tools", "artisans_tools", "str", "10", "8"),
    ("painters_supplies", "Painter's Supplies", "artisans_tools", "wis", "10", "5"),
    ("potters_tools", "Potter's Tools", "artisans_tools", "int", "10", "3"),
    ("smiths_tools", "Smith's Tools", "artisans_tools", "str", "20", "8"),
    ("tinkers_tools", "Tinker's Tools", "artisans_tools", "dex", "50", "10"),
    ("weavers_tools", "Weaver's Tools", "artisans_tools", "dex", "1", "5"),
    ("woodcarvers_tools", "Woodcarver's Tools", "artisans_tools", "dex", "1", "5"),
    ("disguise_kit", "Disguise Kit", None, "cha", "25", "3"),
    ("forgery_kit", "Forgery Kit", None, "dex", "15", "5"),
    ("herbalism_kit", "Herbalism Kit", None, "int", "5", "3"),
    ("navigators_tools", "Navigator's Tools", None, "wis", "25", "2"),
    ("poisoners_kit", "Poisoner's Kit", None, "int", "50", "2"),
    ("thieves_tools", "Thieves' Tools", None, "dex", "25", "1"),
    ("dice_set", "Dice Set", "gaming_set", "wis", "0.1", "0"),
    ("dragonchess_set", "Dragonchess Set", "gaming_set", "wis", "1", "0"),
    ("playing_card_set", "Playing Card Set", "gaming_set", "wis", "0.5", "0"),
    ("three_dragon_ante_set", "Three-Dragon Ante Set", "gaming_set", "wis", "1", "0"),
    ("bagpipes", "Bagpipes", "musical_instrument", "cha", "30", "6"),
    ("drum", "Drum", "musical_instrument", "cha", "6", "3"),
    ("dulcimer", "Dulcimer", "musical_instrument", "cha", "25", "10"),
    ("flute", "Flute", "musical_instrument", "cha", "2", "1"),
    ("horn", "Horn", "musical_instrument", "cha", "3", "2"),
    ("lute", "Lute", "musical_instrument", "cha", "35", "2"),
    ("lyre", "Lyre", "musical_instrument", "cha", "30", "2"),
    ("pan_flute", "Pan Flute", "musical_instrument", "cha", "12", "2"),
    ("shawm", "Shawm", "musical_instrument", "cha", "2", "1"),
    ("viol", "Viol", "musical_instrument", "cha", "30", "1"),
]

# --- SRD 2024 equipment (equipment.md) -----------------------------------------
# One item = one unit. Prices are in GP (1 SP = 0.1, 1 CP = 0.01) and weights in lb;
# a weight of "—" is 0. Ammunition is priced per piece (pack price / pack size).
# Ids are uuid5(SRD_ITEM_NAMESPACE, name): stable across rebuilds, so the sub-rows
# below (ammunition of a weapon, pack contents) are wired by name without lookups.
SRD_ITEM_NAMESPACE = uuid.UUID("5d0f3b8e-2c4a-4f6e-9b1d-7a3c5e8f0b24")

# (name, cost_gp) -- "Coins": fifty coins weigh a pound.
COINS = [
    ("Copper Piece", "0.01"), ("Silver Piece", "0.1"), ("Electrum Piece", "0.5"),
    ("Gold Piece", "1"), ("Platinum Piece", "10"),
]
COIN_WEIGHT_LB = "0.02"

# (name, cost_gp, weight_lb) -- "Ammunition": Arrows 20 for 1 GP/1 lb, Bolts 20 for
# 1 GP/1½ lb, Firearm Bullets 10 for 3 GP/2 lb, Sling Bullets 20 for 4 CP/1½ lb,
# Needles 50 for 1 GP/1 lb.
AMMUNITION = [
    ("Arrow", "0.05", "0.05"),
    ("Bolt", "0.05", "0.075"),
    ("Bullet, Firearm", "0.3", "0.2"),
    ("Bullet, Sling", "0.002", "0.075"),
    ("Needle", "0.02", "0.02"),
]

# (name, category, is_ranged, damage ("XdY" or a flat number), damage type, mastery,
#  properties, cost_gp, weight_lb). A property is a code, ("range", normal, long),
# ("versatile", die size) or ("ammunition", ammunition item name). "Thrown (Range
# 20/60)" is `thrown` + `range`; "Ammunition (Range 80/320; Bolt)" is `ammunition` + `range`.
WEAPONS = [
    ("Club", "simple", False, "1d4", "bludgeoning", "slow", ["light"], "0.1", "2"),
    ("Dagger", "simple", False, "1d4", "piercing", "nick", ["finesse", "light", "thrown", ("range", 20, 60)], "2", "1"),
    ("Greatclub", "simple", False, "1d8", "bludgeoning", "push", ["two_handed"], "0.2", "10"),
    ("Handaxe", "simple", False, "1d6", "slashing", "vex", ["light", "thrown", ("range", 20, 60)], "5", "2"),
    ("Javelin", "simple", False, "1d6", "piercing", "slow", ["thrown", ("range", 30, 120)], "0.5", "2"),
    ("Light Hammer", "simple", False, "1d4", "bludgeoning", "nick", ["light", "thrown", ("range", 20, 60)], "2", "2"),
    ("Mace", "simple", False, "1d6", "bludgeoning", "sap", [], "5", "4"),
    ("Quarterstaff", "simple", False, "1d6", "bludgeoning", "topple", [("versatile", 8)], "0.2", "4"),
    ("Sickle", "simple", False, "1d4", "slashing", "nick", ["light"], "1", "2"),
    ("Spear", "simple", False, "1d6", "piercing", "sap", ["thrown", ("range", 20, 60), ("versatile", 8)], "1", "3"),
    ("Dart", "simple", True, "1d4", "piercing", "vex", ["finesse", "thrown", ("range", 20, 60)], "0.05", "0.25"),
    ("Light Crossbow", "simple", True, "1d8", "piercing", "slow",
     [("ammunition", "Bolt"), ("range", 80, 320), "loading", "two_handed"], "25", "5"),
    ("Shortbow", "simple", True, "1d6", "piercing", "vex",
     [("ammunition", "Arrow"), ("range", 80, 320), "two_handed"], "25", "2"),
    ("Sling", "simple", True, "1d4", "bludgeoning", "slow",
     [("ammunition", "Bullet, Sling"), ("range", 30, 120)], "0.1", "0"),
    ("Battleaxe", "martial", False, "1d8", "slashing", "topple", [("versatile", 10)], "10", "4"),
    ("Flail", "martial", False, "1d8", "bludgeoning", "sap", [], "10", "2"),
    ("Glaive", "martial", False, "1d10", "slashing", "graze", ["heavy", "reach", "two_handed"], "20", "6"),
    ("Greataxe", "martial", False, "1d12", "slashing", "cleave", ["heavy", "two_handed"], "30", "7"),
    ("Greatsword", "martial", False, "2d6", "slashing", "graze", ["heavy", "two_handed"], "50", "6"),
    ("Halberd", "martial", False, "1d10", "slashing", "cleave", ["heavy", "reach", "two_handed"], "20", "6"),
    # "Two-Handed (unless mounted)": stored as `two_handed`, the exception goes in the description.
    ("Lance", "martial", False, "1d10", "piercing", "topple", ["heavy", "reach", "two_handed"], "10", "6"),
    ("Longsword", "martial", False, "1d8", "slashing", "sap", [("versatile", 10)], "15", "3"),
    ("Maul", "martial", False, "2d6", "bludgeoning", "topple", ["heavy", "two_handed"], "10", "10"),
    ("Morningstar", "martial", False, "1d8", "piercing", "sap", [], "15", "4"),
    ("Pike", "martial", False, "1d10", "piercing", "push", ["heavy", "reach", "two_handed"], "5", "18"),
    ("Rapier", "martial", False, "1d8", "piercing", "vex", ["finesse"], "25", "2"),
    ("Scimitar", "martial", False, "1d6", "slashing", "nick", ["finesse", "light"], "25", "3"),
    ("Shortsword", "martial", False, "1d6", "piercing", "vex", ["finesse", "light"], "10", "2"),
    ("Trident", "martial", False, "1d8", "piercing", "topple",
     ["thrown", ("range", 20, 60), ("versatile", 10)], "5", "4"),
    ("Warhammer", "martial", False, "1d8", "bludgeoning", "push", [("versatile", 10)], "15", "5"),
    ("War Pick", "martial", False, "1d8", "piercing", "sap", [("versatile", 10)], "5", "2"),
    ("Whip", "martial", False, "1d4", "slashing", "slow", ["finesse", "reach"], "2", "3"),
    ("Blowgun", "martial", True, "1", "piercing", "vex",
     [("ammunition", "Needle"), ("range", 25, 100), "loading"], "10", "1"),
    ("Hand Crossbow", "martial", True, "1d6", "piercing", "vex",
     [("ammunition", "Bolt"), ("range", 30, 120), "light", "loading"], "75", "3"),
    ("Heavy Crossbow", "martial", True, "1d10", "piercing", "push",
     [("ammunition", "Bolt"), ("range", 100, 400), "heavy", "loading", "two_handed"], "50", "18"),
    ("Longbow", "martial", True, "1d8", "piercing", "slow",
     [("ammunition", "Arrow"), ("range", 150, 600), "heavy", "two_handed"], "50", "2"),
    ("Musket", "martial", True, "1d12", "piercing", "slow",
     [("ammunition", "Bullet, Firearm"), ("range", 40, 120), "loading", "two_handed"], "500", "10"),
    ("Pistol", "martial", True, "1d10", "piercing", "vex",
     [("ammunition", "Bullet, Firearm"), ("range", 30, 90), "loading"], "250", "3"),
]
WEAPON_DESCRIPTIONS = {"Lance": "Two-Handed (unless mounted)."}

# (name, category, base_ac, adds_dex_modifier, max_dex_modifier, strength_requirement,
#  stealth_disadvantage, cost_gp, weight_lb). For the Shield, `base_ac` is the +2 bonus.
ARMORS = [
    ("Padded Armor", "light", 11, True, None, None, True, "5", "8"),
    ("Leather Armor", "light", 11, True, None, None, False, "10", "10"),
    ("Studded Leather Armor", "light", 12, True, None, None, False, "45", "13"),
    ("Hide Armor", "medium", 12, True, 2, None, False, "10", "12"),
    ("Chain Shirt", "medium", 13, True, 2, None, False, "50", "20"),
    ("Scale Mail", "medium", 14, True, 2, None, True, "50", "45"),
    ("Breastplate", "medium", 14, True, 2, None, False, "400", "20"),
    ("Half Plate Armor", "medium", 15, True, 2, None, True, "750", "40"),
    ("Ring Mail", "heavy", 14, False, None, None, True, "30", "40"),
    ("Chain Mail", "heavy", 16, False, None, 13, True, "75", "55"),
    ("Splint Armor", "heavy", 17, False, None, 15, True, "200", "60"),
    ("Plate Armor", "heavy", 18, False, None, 15, True, "1500", "65"),
    ("Shield", "shield", 2, False, None, None, False, "10", "6"),
]

# (name, cost_gp, weight_lb) -- the "Adventuring Gear" table without the "Varies" rows
# (Ammunition, Arcane Focus, Druidic Focus, Holy Symbol) and the packs (PACKS below).
ADVENTURING_GEAR = [
    ("Acid", "25", "1"), ("Alchemist's Fire", "50", "1"), ("Antitoxin", "50", "0"),
    ("Backpack", "2", "5"), ("Ball Bearings", "1", "2"), ("Barrel", "2", "70"), ("Basket", "0.4", "2"),
    ("Bedroll", "1", "7"), ("Bell", "1", "0"), ("Blanket", "0.5", "3"), ("Block and Tackle", "1", "5"),
    ("Book", "25", "5"), ("Bottle, Glass", "2", "2"), ("Bucket", "0.05", "2"), ("Caltrops", "1", "2"),
    ("Candle", "0.01", "0"), ("Case, Crossbow Bolt", "1", "1"), ("Case, Map or Scroll", "1", "1"),
    ("Chain", "5", "10"), ("Chest", "5", "25"), ("Climber's Kit", "25", "12"), ("Clothes, Fine", "15", "6"),
    ("Clothes, Traveler's", "2", "4"), ("Component Pouch", "25", "2"), ("Costume", "5", "4"),
    ("Crowbar", "2", "5"), ("Flask", "0.02", "1"), ("Grappling Hook", "2", "4"), ("Healer's Kit", "5", "3"),
    ("Holy Water", "25", "1"), ("Hunting Trap", "5", "25"), ("Ink", "10", "0"), ("Ink Pen", "0.02", "0"),
    ("Jug", "0.02", "4"), ("Ladder", "0.1", "25"), ("Lamp", "0.5", "1"), ("Lantern, Bullseye", "10", "2"),
    ("Lantern, Hooded", "5", "2"), ("Lock", "10", "1"), ("Magnifying Glass", "100", "0"),
    ("Manacles", "2", "6"), ("Map", "1", "0"), ("Mirror", "5", "0.5"), ("Net", "1", "3"), ("Oil", "0.1", "1"),
    ("Paper", "0.2", "0"), ("Parchment", "0.1", "0"), ("Perfume", "5", "0"), ("Poison, Basic", "100", "0"),
    ("Pole", "0.05", "7"), ("Pot, Iron", "2", "10"), ("Potion of Healing", "50", "0.5"), ("Pouch", "0.5", "1"),
    ("Quiver", "1", "1"), ("Ram, Portable", "4", "35"), ("Rations", "0.5", "2"), ("Robe", "1", "4"),
    ("Rope", "1", "5"), ("Sack", "0.01", "0.5"), ("Shovel", "2", "5"), ("Signal Whistle", "0.05", "0"),
    ("Spell Scroll (Cantrip)", "30", "0"), ("Spell Scroll (Level 1)", "50", "0"), ("Spikes, Iron", "1", "5"),
    ("Spyglass", "1000", "1"), ("String", "0.1", "0"), ("Tent", "2", "20"), ("Tinderbox", "0.5", "1"),
    ("Torch", "0.01", "1"), ("Vial", "1", "0"), ("Waterskin", "0.2", "5"),
]

# (name, cost_gp, weight_lb, description) -- "Arcane Focuses", "Druidic Focuses" and
# "Holy Symbols": one adventuring-gear item per form; the table notes go to `description`.
FOCUSES = [
    ("Arcane Focus (Crystal)", "10", "1", None),
    ("Arcane Focus (Orb)", "20", "3", None),
    ("Arcane Focus (Rod)", "10", "2", None),
    ("Arcane Focus (Staff)", "5", "4", "Also a Quarterstaff."),
    ("Arcane Focus (Wand)", "10", "1", None),
    ("Druidic Focus (Sprig of Mistletoe)", "1", "0", None),
    ("Druidic Focus (Wooden Staff)", "5", "4", "Also a Quarterstaff."),
    ("Druidic Focus (Yew Wand)", "10", "1", None),
    ("Holy Symbol (Amulet)", "5", "1", "Worn or held."),
    ("Holy Symbol (Emblem)", "5", "0", "Borne on fabric or a Shield."),
    ("Holy Symbol (Reliquary)", "5", "2", "Held."),
]

# Capacity in pounds (Backpack, Basket, Pouch and Sack descriptions).
CONTAINERS = {"Backpack": "30", "Basket": "40", "Pouch": "6", "Sack": "30"}

# (name, cost_gp, weight_lb, [(content item name, quantity)]) -- the pack descriptions.
PACKS = [
    ("Burglar's Pack", "16", "42", [
        ("Backpack", 1), ("Ball Bearings", 1), ("Bell", 1), ("Candle", 10), ("Crowbar", 1),
        ("Lantern, Hooded", 1), ("Oil", 7), ("Rations", 5), ("Rope", 1), ("Tinderbox", 1), ("Waterskin", 1),
    ]),
    ("Diplomat's Pack", "39", "39", [
        ("Chest", 1), ("Clothes, Fine", 1), ("Ink", 1), ("Ink Pen", 5), ("Lamp", 1), ("Case, Map or Scroll", 2),
        ("Oil", 4), ("Paper", 5), ("Parchment", 5), ("Perfume", 1), ("Tinderbox", 1),
    ]),
    ("Dungeoneer's Pack", "12", "55", [
        ("Backpack", 1), ("Caltrops", 1), ("Crowbar", 1), ("Oil", 2), ("Rations", 10), ("Rope", 1),
        ("Tinderbox", 1), ("Torch", 10), ("Waterskin", 1),
    ]),
    ("Entertainer's Pack", "40", "58.5", [
        ("Backpack", 1), ("Bedroll", 1), ("Bell", 1), ("Lantern, Bullseye", 1), ("Costume", 3), ("Mirror", 1),
        ("Oil", 8), ("Rations", 9), ("Tinderbox", 1), ("Waterskin", 1),
    ]),
    ("Explorer's Pack", "10", "55", [
        ("Backpack", 1), ("Bedroll", 1), ("Oil", 2), ("Rations", 10), ("Rope", 1), ("Tinderbox", 1),
        ("Torch", 10), ("Waterskin", 1),
    ]),
    ("Priest's Pack", "33", "29", [
        ("Backpack", 1), ("Blanket", 1), ("Holy Water", 1), ("Lamp", 1), ("Rations", 7), ("Robe", 1),
        ("Tinderbox", 1),
    ]),
    ("Scholar's Pack", "40", "22", [
        ("Backpack", 1), ("Book", 1), ("Ink", 1), ("Ink Pen", 1), ("Lamp", 1), ("Oil", 10), ("Parchment", 10),
        ("Tinderbox", 1),
    ]),
]

_SRD = {"source": "srd", "is_homebrew": False, "created_by": None}


def _ref_table(name: str, *extra: sa.Column) -> sa.sql.TableClause:
    return sa.table(
        name,
        sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("source", sa.String), sa.column("is_homebrew", sa.Boolean), sa.column("created_by", sa.UUID),
        *extra,
    )


def _insert_code_rows(name: str, rows: list[tuple[str, str]]) -> None:
    op.bulk_insert(_ref_table(name), [{"code": code, "name": label, **_SRD} for code, label in rows])


def _seed() -> None:
    for name, rows in [
        ("ability_scores", ABILITY_SCORES),
        ("damage_types", DAMAGE_TYPES),
        ("conditions", CONDITIONS),
        ("creature_types", CREATURE_TYPES),
        ("alignments", ALIGNMENTS),
        ("senses", SENSES),
        ("movement_modes", MOVEMENT_MODES),
        ("weapon_categories", WEAPON_CATEGORIES),
        ("weapon_properties", WEAPON_PROPERTIES),
        ("weapon_masteries", WEAPON_MASTERIES),
        ("armor_categories", ARMOR_CATEGORIES),
        ("tool_categories", TOOL_CATEGORIES),
        ("spell_schools", SPELL_SCHOOLS),
        ("recharge_types", RECHARGE_TYPES),
        ("action_types", ACTION_TYPES),
        ("feat_categories", FEAT_CATEGORIES),
        ("item_types", ITEM_TYPES),
    ]:
        _insert_code_rows(name, rows)

    op.bulk_insert(
        _ref_table("skills", sa.column("ability_code", sa.String)),
        [{"code": c, "name": n, "ability_code": a, **_SRD} for c, n, a in SKILLS],
    )
    op.bulk_insert(
        _ref_table("tool_types", sa.column("category_code", sa.String), sa.column("ability_code", sa.String)),
        [
            {"code": c, "name": n, "category_code": cat, "ability_code": a, **_SRD}
            for c, n, cat, a, _cost, _weight in TOOLS
        ],
    )
    op.bulk_insert(
        sa.table("condition_implications",
                 sa.column("condition_code", sa.String), sa.column("implied_condition_code", sa.String)),
        [{"condition_code": c, "implied_condition_code": i} for c, i in CONDITION_IMPLICATIONS],
    )
    op.bulk_insert(
        _ref_table("sizes", sa.column("hit_die", sa.Integer), sa.column("carry_multiplier", sa.Numeric),
                   sa.column("sort_order", sa.Integer)),
        [
            {"code": c, "name": n, "hit_die": hd, "carry_multiplier": Decimal(cm), "sort_order": so, **_SRD}
            for c, n, hd, cm, so in SIZES
        ],
    )
    op.bulk_insert(
        _ref_table("languages", sa.column("rarity", sa.String)),
        [{"code": c, "name": n, "rarity": r, **_SRD} for c, n, r in LANGUAGES],
    )
    op.bulk_insert(
        _ref_table("challenge_ratings", sa.column("numeric_value", sa.Numeric),
                   sa.column("proficiency_bonus", sa.Integer)),
        [
            {"code": c, "name": n, "numeric_value": Decimal(v),
             "proficiency_bonus": _cr_proficiency_bonus(float(v)), **_SRD}
            for c, n, v in CHALLENGE_RATINGS
        ],
    )
    op.bulk_insert(
        sa.table("character_levels",
                 sa.column("level", sa.Integer), sa.column("min_xp", sa.Integer),
                 sa.column("proficiency_bonus", sa.Integer),
                 sa.column("source", sa.String), sa.column("is_homebrew", sa.Boolean),
                 sa.column("created_by", sa.UUID)),
        [{"level": lv, "min_xp": xp, "proficiency_bonus": pb, **_SRD} for lv, xp, pb in CHARACTER_LEVELS],
    )
    op.bulk_insert(
        sa.table("point_buy_costs",
                 sa.column("score", sa.Integer), sa.column("cost", sa.Integer),
                 sa.column("source", sa.String), sa.column("is_homebrew", sa.Boolean),
                 sa.column("created_by", sa.UUID)),
        [{"score": score, "cost": cost, **_SRD} for score, cost in POINT_BUY_COSTS],
    )
    _seed_items()


def _srd_item_id(name: str) -> uuid.UUID:
    return uuid.uuid5(SRD_ITEM_NAMESPACE, name)


def _weapon_damage(damage: str) -> dict:
    if "d" in damage:
        count, size = damage.split("d")
        return {"damage_dice_count": int(count), "damage_die_size": int(size), "damage_flat": 0}
    return {"damage_dice_count": None, "damage_die_size": None, "damage_flat": int(damage)}


def _property_link(item_id: uuid.UUID, prop) -> dict:
    link = {
        "weapon_item_id": item_id, "range_normal_ft": None, "range_long_ft": None,
        "versatile_die_size": None, "ammunition_item_id": None,
    }
    if isinstance(prop, str):
        return {**link, "property_code": prop}
    code, *params = prop
    if code == "range":
        return {**link, "property_code": code, "range_normal_ft": params[0], "range_long_ft": params[1]}
    if code == "versatile":
        return {**link, "property_code": code, "versatile_die_size": params[0]}
    return {**link, "property_code": code, "ammunition_item_id": _srd_item_id(params[0])}


def _seed_items() -> None:
    items: list[dict] = []
    weapons: list[dict] = []
    links: list[dict] = []
    armors: list[dict] = []
    tools: list[dict] = []
    containers: list[dict] = []
    contents: list[dict] = []

    def add(name: str, item_type: str, cost: str, weight: str, description: str | None = None) -> uuid.UUID:
        item_id = _srd_item_id(name)
        items.append({
            "id": item_id, "name": name, "item_type_code": item_type,
            "cost_gp": Decimal(cost), "weight_lb": Decimal(weight), "description": description, **_SRD,
        })
        return item_id

    for name, cost in COINS:
        add(name, "currency", cost, COIN_WEIGHT_LB)
    for name, cost, weight in AMMUNITION:
        add(name, "ammunition", cost, weight)
    for name, category, is_ranged, damage, damage_type, mastery, props, cost, weight in WEAPONS:
        item_id = add(name, "weapon", cost, weight, WEAPON_DESCRIPTIONS.get(name))
        weapons.append({
            "item_id": item_id, "category_code": category, "is_ranged": is_ranged,
            "damage_type_code": damage_type, "mastery_code": mastery, **_weapon_damage(damage),
        })
        links.extend(_property_link(item_id, prop) for prop in props)
    for name, category, base_ac, adds_dex, max_dex, strength, stealth, cost, weight in ARMORS:
        armors.append({
            "item_id": add(name, "armor", cost, weight), "category_code": category, "base_ac": base_ac,
            "adds_dex_modifier": adds_dex, "max_dex_modifier": max_dex, "strength_requirement": strength,
            "stealth_disadvantage": stealth,
        })
    for code, name, _category, _ability, cost, weight in TOOLS:
        tools.append({"item_id": add(name, "tool", cost, weight), "tool_type_code": code})
    for name, cost, weight in ADVENTURING_GEAR:
        item_id = add(name, "adventuring_gear", cost, weight)
        if name in CONTAINERS:
            containers.append({"item_id": item_id, "capacity_weight_lb": Decimal(CONTAINERS[name])})
    for name, cost, weight, description in FOCUSES:
        add(name, "adventuring_gear", cost, weight, description)
    for name, cost, weight, pack_contents in PACKS:
        pack_id = add(name, "pack", cost, weight)
        contents.extend(
            {"pack_item_id": pack_id, "item_id": _srd_item_id(content), "quantity": quantity}
            for content, quantity in pack_contents
        )

    uid, string, integer, boolean, numeric = sa.UUID, sa.String, sa.Integer, sa.Boolean, sa.Numeric
    op.bulk_insert(sa.table(
        "item_definitions", sa.column("id", uid), sa.column("name", string), sa.column("item_type_code", string),
        sa.column("cost_gp", numeric), sa.column("weight_lb", numeric), sa.column("description", sa.Text),
        sa.column("source", string), sa.column("is_homebrew", boolean), sa.column("created_by", uid),
    ), items)
    op.bulk_insert(sa.table(
        "weapons", sa.column("item_id", uid), sa.column("category_code", string), sa.column("is_ranged", boolean),
        sa.column("damage_dice_count", integer), sa.column("damage_die_size", integer),
        sa.column("damage_flat", integer), sa.column("damage_type_code", string), sa.column("mastery_code", string),
    ), weapons)
    op.bulk_insert(sa.table(
        "weapon_property_links", sa.column("weapon_item_id", uid), sa.column("property_code", string),
        sa.column("range_normal_ft", integer), sa.column("range_long_ft", integer),
        sa.column("versatile_die_size", integer), sa.column("ammunition_item_id", uid),
    ), links)
    op.bulk_insert(sa.table(
        "armors", sa.column("item_id", uid), sa.column("category_code", string), sa.column("base_ac", integer),
        sa.column("adds_dex_modifier", boolean), sa.column("max_dex_modifier", integer),
        sa.column("strength_requirement", integer), sa.column("stealth_disadvantage", boolean),
    ), armors)
    op.bulk_insert(sa.table("tools", sa.column("item_id", uid), sa.column("tool_type_code", string)), tools)
    op.bulk_insert(
        sa.table("containers", sa.column("item_id", uid), sa.column("capacity_weight_lb", numeric)), containers
    )
    op.bulk_insert(sa.table(
        "item_contents", sa.column("pack_item_id", uid), sa.column("item_id", uid), sa.column("quantity", integer),
    ), contents)


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('feature_grants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_type', sa.String(length=30), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('effect_type', sa.String(length=30), nullable=False),
    sa.Column('effect_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('level_requirement', sa.Integer(), nullable=False),
    sa.Column('is_optional', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feature_grants_source_id'), 'feature_grants', ['source_id'], unique=False)
    op.create_index(op.f('ix_feature_grants_source_type'), 'feature_grants', ['source_type'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('ability_scores',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('action_types',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('alignments',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('armor_categories',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('campaigns',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('invite_code', sa.String(length=12), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_campaigns_invite_code'), 'campaigns', ['invite_code'], unique=True)
    op.create_table('challenge_ratings',
    sa.Column('numeric_value', sa.Numeric(), nullable=False),
    sa.Column('proficiency_bonus', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.CheckConstraint('proficiency_bonus >= 0', name='ck_challenge_ratings_proficiency_bonus'),
    sa.CheckConstraint('numeric_value >= 0', name='ck_challenge_ratings_numeric_value'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code'),
    sa.UniqueConstraint('numeric_value')
    )
    op.create_table('character_levels',
    sa.Column('level', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('min_xp', sa.Integer(), nullable=False),
    sa.Column('proficiency_bonus', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.CheckConstraint('level >= 1', name='ck_character_levels_level'),
    sa.CheckConstraint('min_xp >= 0', name='ck_character_levels_min_xp'),
    sa.CheckConstraint('proficiency_bonus >= 0', name='ck_character_levels_proficiency_bonus'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('level')
    )
    op.create_table('conditions',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('creature_types',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('damage_types',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('feat_categories',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('feat_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('level_prerequisite', sa.Integer(), nullable=False),
    sa.Column('prerequisite_description', sa.Text(), nullable=True),
    sa.Column('repeatable', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('languages',
    sa.Column('rarity', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.CheckConstraint("rarity IN ('standard', 'rare')", name='ck_languages_rarity'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('movement_modes',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('point_buy_costs',
    sa.Column('score', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('cost', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.CheckConstraint('cost >= 0', name='ck_point_buy_costs_cost'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('score')
    )
    op.create_table('recharge_types',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('refresh_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
    op.create_table('senses',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('sizes',
    sa.Column('hit_die', sa.Integer(), nullable=False),
    sa.Column('carry_multiplier', sa.Numeric(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.CheckConstraint('carry_multiplier > 0', name='ck_sizes_carry_multiplier_positive'),
    sa.CheckConstraint('hit_die > 0', name='ck_sizes_hit_die_positive'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code'),
    sa.UniqueConstraint('sort_order')
    )
    op.create_table('spell_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('school', sa.String(length=20), nullable=False),
    sa.Column('casting_time', sa.String(length=50), nullable=False),
    sa.Column('range', sa.String(length=50), nullable=False),
    sa.Column('components', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('material_component', sa.Text(), nullable=True),
    sa.Column('duration', sa.String(length=50), nullable=False),
    sa.Column('concentration', sa.Boolean(), nullable=False),
    sa.Column('ritual', sa.Boolean(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('higher_levels', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('spell_schools',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('tool_categories',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('weapon_categories',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('weapon_masteries',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('weapon_properties',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('item_types',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('tool_types',
    sa.Column('category_code', sa.String(length=50), nullable=True),
    sa.Column('ability_code', sa.String(length=50), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['ability_code'], ['ability_scores.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['category_code'], ['tool_categories.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('item_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('item_type_code', sa.String(length=50), nullable=False),
    sa.Column('cost_gp', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('weight_lb', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['item_type_code'], ['item_types.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('weapons',
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('category_code', sa.String(length=50), nullable=False),
    sa.Column('is_ranged', sa.Boolean(), nullable=False),
    sa.Column('damage_dice_count', sa.Integer(), nullable=True),
    sa.Column('damage_die_size', sa.Integer(), nullable=True),
    sa.Column('damage_flat', sa.Integer(), nullable=False),
    sa.Column('damage_type_code', sa.String(length=50), nullable=False),
    sa.Column('mastery_code', sa.String(length=50), nullable=True),
    sa.CheckConstraint('(damage_dice_count IS NULL) = (damage_die_size IS NULL)', name='ck_weapons_damage_dice_pair'),
    sa.CheckConstraint('damage_dice_count IS NOT NULL OR damage_flat >= 1', name='ck_weapons_damage_flat_without_dice'),
    sa.CheckConstraint('damage_dice_count >= 1', name='ck_weapons_damage_dice_count'),
    sa.CheckConstraint('damage_die_size IN (4, 6, 8, 10, 12, 20)', name='ck_weapons_damage_die_size'),
    sa.ForeignKeyConstraint(['category_code'], ['weapon_categories.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['damage_type_code'], ['damage_types.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['mastery_code'], ['weapon_masteries.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('item_id')
    )
    op.create_table('weapon_property_links',
    sa.Column('weapon_item_id', sa.UUID(), nullable=False),
    sa.Column('property_code', sa.String(length=50), nullable=False),
    sa.Column('range_normal_ft', sa.Integer(), nullable=True),
    sa.Column('range_long_ft', sa.Integer(), nullable=True),
    sa.Column('versatile_die_size', sa.Integer(), nullable=True),
    sa.Column('ammunition_item_id', sa.UUID(), nullable=True),
    sa.CheckConstraint('range_normal_ft > 0', name='ck_weapon_property_links_range_normal'),
    sa.CheckConstraint('range_long_ft >= range_normal_ft', name='ck_weapon_property_links_range_long'),
    sa.CheckConstraint('versatile_die_size IN (4, 6, 8, 10, 12, 20)', name='ck_weapon_property_links_versatile_die_size'),
    sa.ForeignKeyConstraint(['ammunition_item_id'], ['item_definitions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['property_code'], ['weapon_properties.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['weapon_item_id'], ['weapons.item_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('weapon_item_id', 'property_code')
    )
    op.create_table('armors',
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('category_code', sa.String(length=50), nullable=False),
    sa.Column('base_ac', sa.Integer(), nullable=False),
    sa.Column('adds_dex_modifier', sa.Boolean(), nullable=False),
    sa.Column('max_dex_modifier', sa.Integer(), nullable=True),
    sa.Column('strength_requirement', sa.Integer(), nullable=True),
    sa.Column('stealth_disadvantage', sa.Boolean(), nullable=False),
    sa.CheckConstraint('base_ac >= 0', name='ck_armors_base_ac'),
    sa.CheckConstraint('max_dex_modifier >= 0', name='ck_armors_max_dex_modifier'),
    sa.CheckConstraint('strength_requirement >= 1', name='ck_armors_strength_requirement'),
    sa.ForeignKeyConstraint(['category_code'], ['armor_categories.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id')
    )
    op.create_table('tools',
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('tool_type_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tool_type_code'], ['tool_types.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('item_id')
    )
    op.create_table('containers',
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('capacity_weight_lb', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.CheckConstraint('capacity_weight_lb > 0', name='ck_containers_capacity_weight_lb'),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id')
    )
    op.create_table('item_contents',
    sa.Column('pack_item_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity >= 1', name='ck_item_contents_quantity'),
    sa.CheckConstraint('pack_item_id <> item_id', name='ck_item_contents_not_self'),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['pack_item_id'], ['item_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('pack_item_id', 'item_id')
    )
    op.create_table('background_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('feat_id', sa.UUID(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['feat_id'], ['feat_definitions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('campaign_homebrew_rules',
    sa.Column('resource_table', sa.String(length=50), nullable=False),
    sa.Column('resource_key', sa.String(length=50), nullable=False),
    sa.Column('campaign_id', sa.UUID(), nullable=False),
    sa.CheckConstraint("resource_table IN ('ability_scores', 'skills', 'damage_types', 'conditions', 'creature_types', 'sizes', 'alignments', 'languages', 'senses', 'movement_modes', 'weapon_categories', 'weapon_properties', 'weapon_masteries', 'armor_categories', 'tool_categories', 'spell_schools', 'recharge_types', 'action_types', 'character_levels', 'challenge_ratings', 'point_buy_costs', 'feat_categories', 'item_types', 'tool_types')", name='ck_campaign_homebrew_rules_resource_table'),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('resource_table', 'resource_key', 'campaign_id')
    )
    op.create_index('ix_campaign_homebrew_rules_campaign_id', 'campaign_homebrew_rules', ['campaign_id'], unique=False)
    op.create_table('campaign_members',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('campaign_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('class_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('hit_die', sa.Integer(), nullable=False),
    sa.Column('skill_choices', sa.Integer(), nullable=False),
    sa.Column('subclass_level', sa.Integer(), nullable=False),
    sa.Column('spell_ability', sa.String(length=50), nullable=True),
    sa.Column('spellcasting_type', sa.String(length=10), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['spell_ability'], ['ability_scores.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('condition_implications',
    sa.Column('condition_code', sa.String(length=50), nullable=False),
    sa.Column('implied_condition_code', sa.String(length=50), nullable=False),
    sa.CheckConstraint('condition_code <> implied_condition_code', name='ck_condition_implications_not_self'),
    sa.ForeignKeyConstraint(['condition_code'], ['conditions.code'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['implied_condition_code'], ['conditions.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('condition_code', 'implied_condition_code')
    )
    op.create_table('skills',
    sa.Column('ability_code', sa.String(length=50), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['ability_code'], ['ability_scores.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('species_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('creature_type', sa.String(length=30), nullable=False),
    sa.Column('size_code', sa.String(length=50), nullable=False),
    sa.Column('base_speed', sa.Integer(), nullable=False),
    sa.Column('special_traits', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['size_code'], ['sizes.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('proficiency_grants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('weapon_category_code', sa.String(length=50), nullable=True),
    sa.Column('required_weapon_property_code', sa.String(length=50), nullable=True),
    sa.Column('armor_category_code', sa.String(length=50), nullable=True),
    sa.Column('tool_type_code', sa.String(length=50), nullable=True),
    sa.Column('tool_category_code', sa.String(length=50), nullable=True),
    sa.Column('skill_code', sa.String(length=50), nullable=True),
    sa.Column('saving_throw_ability_code', sa.String(length=50), nullable=True),
    sa.Column('language_code', sa.String(length=50), nullable=True),
    sa.CheckConstraint('num_nonnulls(weapon_category_code, armor_category_code, tool_type_code, tool_category_code, skill_code, saving_throw_ability_code, language_code) = 1', name='ck_proficiency_grants_single_target'),
    sa.CheckConstraint('required_weapon_property_code IS NULL OR weapon_category_code IS NOT NULL', name='ck_proficiency_grants_required_property'),
    sa.ForeignKeyConstraint(['armor_category_code'], ['armor_categories.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['language_code'], ['languages.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['required_weapon_property_code'], ['weapon_properties.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['saving_throw_ability_code'], ['ability_scores.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['skill_code'], ['skills.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tool_category_code'], ['tool_categories.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tool_type_code'], ['tool_types.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['weapon_category_code'], ['weapon_categories.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('weapon_category_code', 'armor_category_code', 'tool_type_code', 'tool_category_code', 'skill_code', 'saving_throw_ability_code', 'language_code', 'required_weapon_property_code', name='uq_proficiency_grants_target', postgresql_nulls_not_distinct=True)
    )
    op.create_table('background_proficiency_grants',
    sa.Column('background_id', sa.UUID(), nullable=False),
    sa.Column('grant_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['background_id'], ['background_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['grant_id'], ['proficiency_grants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('background_id', 'grant_id')
    )
    op.create_table('class_proficiency_grants',
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('grant_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['grant_id'], ['proficiency_grants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('class_id', 'grant_id')
    )
    op.create_table('background_ability_scores',
    sa.Column('background_id', sa.UUID(), nullable=False),
    sa.Column('ability_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['ability_code'], ['ability_scores.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['background_id'], ['background_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('background_id', 'ability_code')
    )
    op.create_table('background_initial_equipment',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('background_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('option', sa.String(length=10), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity >= 1', name='ck_background_initial_equipment_quantity_positive'),
    sa.ForeignKeyConstraint(['background_id'], ['background_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('characters',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('campaign_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('experience_points', sa.Integer(), nullable=False),
    sa.Column('species_id', sa.UUID(), nullable=True),
    sa.Column('background_id', sa.UUID(), nullable=True),
    sa.Column('current_hp', sa.Integer(), nullable=False),
    sa.Column('max_hp', sa.Integer(), nullable=False),
    sa.Column('temp_hp', sa.Integer(), nullable=False),
    sa.Column('death_saves', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('exhaustion_level', sa.Integer(), nullable=False),
    sa.Column('inspiration', sa.Boolean(), nullable=False),
    sa.Column('choices', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('spell_slots_remaining', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('appearance', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('custom_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['background_id'], ['background_definitions.id'], ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['species_id'], ['species_definitions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('class_initial_equipment',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('option', sa.String(length=10), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity >= 1', name='ck_class_initial_equipment_quantity_positive'),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('class_primary_abilities',
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('ability_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['ability_code'], ['ability_scores.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('class_id', 'ability_code')
    )
    op.create_table('class_skills',
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('skill_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_code'], ['skills.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('class_id', 'skill_code')
    )
    op.create_table('spell_class_lists',
    sa.Column('spell_id', sa.UUID(), nullable=False),
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['spell_id'], ['spell_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('spell_id', 'class_id')
    )
    op.create_table('subclass_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('character_ability_scores',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('ability_code', sa.String(length=50), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.CheckConstraint('value >= 1 AND value <= 30', name='ck_character_ability_scores_value_bounds'),
    sa.ForeignKeyConstraint(['ability_code'], ['ability_scores.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('character_id', 'ability_code')
    )
    op.create_table('character_classes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('subclass_id', sa.UUID(), nullable=True),
    sa.Column('hit_dice_used', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ),
    sa.ForeignKeyConstraint(['subclass_id'], ['subclass_definitions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('character_id', 'class_id')
    )
    op.create_table('character_feats',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('feat_id', sa.UUID(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('choices', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['feat_id'], ['feat_definitions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('character_inventory',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('equipped', sa.Boolean(), nullable=False),
    sa.Column('attuned', sa.Boolean(), nullable=False),
    sa.Column('custom_notes', sa.Text(), nullable=True),
    sa.Column('added_by', sa.UUID(), nullable=True),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['added_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['item_id'], ['item_definitions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('character_resources',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('resource_name', sa.String(length=50), nullable=False),
    sa.Column('max_uses', sa.Integer(), nullable=False),
    sa.Column('remaining_uses', sa.Integer(), nullable=False),
    sa.Column('reset_on', sa.String(length=15), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('character_skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('skill_code', sa.String(length=50), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('expertise', sa.Boolean(), server_default='false', nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_code'], ['skills.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('character_id', 'skill_code')
    )
    op.create_table('character_spell_slots',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('spell_level', sa.Integer(), nullable=False),
    sa.Column('remaining_slots', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('character_spells',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('character_id', sa.UUID(), nullable=False),
    sa.Column('spell_id', sa.UUID(), nullable=False),
    sa.Column('is_prepared', sa.Boolean(), nullable=False),
    sa.Column('is_always_prepared', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['spell_id'], ['spell_definitions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
    _seed()


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('class_proficiency_grants')
    op.drop_table('background_proficiency_grants')
    op.drop_table('proficiency_grants')
    op.drop_table('item_contents')
    op.drop_table('containers')
    op.drop_table('tools')
    op.drop_table('armors')
    op.drop_table('weapon_property_links')
    op.drop_table('weapons')
    op.drop_table('character_spells')
    op.drop_table('character_spell_slots')
    op.drop_table('character_skills')
    op.drop_table('character_resources')
    op.drop_table('character_inventory')
    op.drop_table('character_feats')
    op.drop_table('character_classes')
    op.drop_table('character_ability_scores')
    op.drop_table('subclass_definitions')
    op.drop_table('spell_class_lists')
    op.drop_table('class_skills')
    op.drop_table('class_primary_abilities')
    op.drop_table('class_initial_equipment')
    op.drop_table('characters')
    op.drop_table('background_initial_equipment')
    op.drop_table('background_ability_scores')
    op.drop_table('species_definitions')
    op.drop_table('skills')
    op.drop_table('condition_implications')
    op.drop_table('class_definitions')
    op.drop_table('campaign_members')
    op.drop_index('ix_campaign_homebrew_rules_campaign_id', table_name='campaign_homebrew_rules')
    op.drop_table('campaign_homebrew_rules')
    op.drop_table('background_definitions')
    op.drop_table('weapon_properties')
    op.drop_table('weapon_masteries')
    op.drop_table('weapon_categories')
    op.drop_table('tool_types')
    op.drop_table('tool_categories')
    op.drop_table('spell_schools')
    op.drop_table('spell_definitions')
    op.drop_table('sizes')
    op.drop_table('senses')
    op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_table('recharge_types')
    op.drop_table('point_buy_costs')
    op.drop_table('movement_modes')
    op.drop_table('languages')
    op.drop_table('item_definitions')
    op.drop_table('item_types')
    op.drop_table('feat_definitions')
    op.drop_table('feat_categories')
    op.drop_table('damage_types')
    op.drop_table('creature_types')
    op.drop_table('conditions')
    op.drop_table('character_levels')
    op.drop_table('challenge_ratings')
    op.drop_index(op.f('ix_campaigns_invite_code'), table_name='campaigns')
    op.drop_table('campaigns')
    op.drop_table('armor_categories')
    op.drop_table('alignments')
    op.drop_table('action_types')
    op.drop_table('ability_scores')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_feature_grants_source_type'), table_name='feature_grants')
    op.drop_index(op.f('ix_feature_grants_source_id'), table_name='feature_grants')
    op.drop_table('feature_grants')
    # ### end Alembic commands ###
