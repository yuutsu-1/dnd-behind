"""initial schema

Revision ID: c1fcfd7fe014
Revises: 
Create Date: 2026-10-04 13:45:36.399611

"""
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

# Transitional until phase 2 -- equipment.md "Tools": the 17 Artisan's Tools and
# the Other Tools (Gaming Set and Musical Instrument as generic entries).
TOOL_PROFICIENCY_OPTIONS = [
    ("alchemists_supplies", "Alchemist's Supplies"),
    ("brewers_supplies", "Brewer's Supplies"),
    ("calligraphers_supplies", "Calligrapher's Supplies"),
    ("carpenters_tools", "Carpenter's Tools"),
    ("cartographers_tools", "Cartographer's Tools"),
    ("cobblers_tools", "Cobbler's Tools"),
    ("cooks_utensils", "Cook's Utensils"),
    ("glassblowers_tools", "Glassblower's Tools"),
    ("jewelers_tools", "Jeweler's Tools"),
    ("leatherworkers_tools", "Leatherworker's Tools"),
    ("masons_tools", "Mason's Tools"),
    ("painters_supplies", "Painter's Supplies"),
    ("potters_tools", "Potter's Tools"),
    ("smiths_tools", "Smith's Tools"),
    ("tinkers_tools", "Tinker's Tools"),
    ("weavers_tools", "Weaver's Tools"),
    ("woodcarvers_tools", "Woodcarver's Tools"),
    ("disguise_kit", "Disguise Kit"),
    ("forgery_kit", "Forgery Kit"),
    ("gaming_set", "Gaming Set"),
    ("herbalism_kit", "Herbalism Kit"),
    ("musical_instrument", "Musical Instrument"),
    ("navigators_tools", "Navigator's Tools"),
    ("poisoners_kit", "Poisoner's Kit"),
    ("thieves_tools", "Thieves' Tools"),
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
        ("tool_proficiency_options", TOOL_PROFICIENCY_OPTIONS),
    ]:
        _insert_code_rows(name, rows)

    op.bulk_insert(
        _ref_table("skills", sa.column("ability_code", sa.String)),
        [{"code": c, "name": n, "ability_code": a, **_SRD} for c, n, a in SKILLS],
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
    op.create_table('item_definitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('item_type', sa.String(length=20), nullable=False),
    sa.Column('subtype', sa.String(length=30), nullable=True),
    sa.Column('rarity', sa.String(length=15), nullable=False),
    sa.Column('requires_attunement', sa.Boolean(), nullable=False),
    sa.Column('attunement_prerequisite', sa.Text(), nullable=True),
    sa.Column('weight', sa.Float(), nullable=True),
    sa.Column('cost_gp', sa.Float(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('is_homebrew', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
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
    op.create_table('tool_proficiency_options',
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
    sa.CheckConstraint("resource_table IN ('ability_scores', 'skills', 'damage_types', 'conditions', 'creature_types', 'sizes', 'alignments', 'languages', 'senses', 'movement_modes', 'weapon_categories', 'weapon_properties', 'weapon_masteries', 'armor_categories', 'tool_categories', 'spell_schools', 'recharge_types', 'action_types', 'character_levels', 'challenge_ratings', 'point_buy_costs', 'feat_categories', 'tool_proficiency_options')", name='ck_campaign_homebrew_rules_resource_table'),
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
    op.create_table('background_skills',
    sa.Column('background_id', sa.UUID(), nullable=False),
    sa.Column('skill_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['background_id'], ['background_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_code'], ['skills.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('background_id', 'skill_code')
    )
    op.create_table('background_tool_proficiencies',
    sa.Column('background_id', sa.UUID(), nullable=False),
    sa.Column('tool_proficiency_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['background_id'], ['background_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tool_proficiency_code'], ['tool_proficiency_options.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('background_id', 'tool_proficiency_code')
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
    op.create_table('class_armor_proficiencies',
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('armor_category_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['armor_category_code'], ['armor_categories.code'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('class_id', 'armor_category_code')
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
    op.create_table('class_saving_throws',
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
    op.create_table('class_tool_proficiencies',
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('tool_proficiency_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tool_proficiency_code'], ['tool_proficiency_options.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('class_id', 'tool_proficiency_code')
    )
    op.create_table('class_weapon_proficiencies',
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('weapon_category_code', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['class_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['weapon_category_code'], ['weapon_categories.code'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('class_id', 'weapon_category_code')
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
    op.drop_table('class_weapon_proficiencies')
    op.drop_table('class_tool_proficiencies')
    op.drop_table('class_skills')
    op.drop_table('class_saving_throws')
    op.drop_table('class_primary_abilities')
    op.drop_table('class_initial_equipment')
    op.drop_table('class_armor_proficiencies')
    op.drop_table('characters')
    op.drop_table('background_tool_proficiencies')
    op.drop_table('background_skills')
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
    op.drop_table('tool_proficiency_options')
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
