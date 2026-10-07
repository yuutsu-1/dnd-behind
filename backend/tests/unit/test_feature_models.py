"""Metadata of the phase 4 tables: feats, prerequisites, features, effects, choices,
resources, recharges and scaling (no database needed)."""
import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

import app.db.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base


def _table(name):
    assert name in Base.metadata.tables, f"table {name} not registered"
    return Base.metadata.tables[name]


def _fk(table_name, column_name):
    fks = list(_table(table_name).c[column_name].foreign_keys)
    assert len(fks) == 1, f"{table_name}.{column_name} should have exactly one FK"
    return fks[0]


def _checks(table_name) -> dict[str, str]:
    return {
        c.name: str(c.sqltext) for c in _table(table_name).constraints if isinstance(c, CheckConstraint)
    }


def _uniques(table_name) -> dict[str, UniqueConstraint]:
    return {c.name: c for c in _table(table_name).constraints if isinstance(c, UniqueConstraint)}


# --- step 2: feats and prerequisites ------------------------------------------------

def test_feat_definitions_columns():
    table = _table("feat_definitions")
    for removed in ("category", "level_prerequisite", "prerequisite_description"):
        assert removed not in table.c
    assert {"id", "name", "description", "category_code", "repeatable", "source", "is_homebrew",
            "created_by", "created_at"} <= set(table.c.keys())
    assert table.c.name.unique is not True
    assert not any(
        {c.name for c in uc.columns} == {"name"} for uc in _uniques("feat_definitions").values()
    )
    assert table.c.category_code.nullable is False
    fk = _fk("feat_definitions", "category_code")
    assert fk.target_fullname == "feat_categories.code"
    assert fk.ondelete == "RESTRICT"


def test_feat_prerequisites_columns_and_foreign_keys():
    table = _table("feat_prerequisites")
    assert set(table.c.keys()) == {
        "id", "feat_id", "or_group", "min_character_level", "ability_code", "min_score", "feature_kind_code",
    }
    assert table.c.or_group.nullable is False
    assert table.c.feat_id.nullable is False
    assert _fk("feat_prerequisites", "feat_id").target_fullname == "feat_definitions.id"
    assert _fk("feat_prerequisites", "feat_id").ondelete == "CASCADE"
    assert _fk("feat_prerequisites", "ability_code").target_fullname == "ability_scores.code"
    assert _fk("feat_prerequisites", "ability_code").ondelete == "RESTRICT"
    assert _fk("feat_prerequisites", "feature_kind_code").target_fullname == "feature_kinds.code"
    assert _fk("feat_prerequisites", "feature_kind_code").ondelete == "RESTRICT"


def test_feat_prerequisites_checks():
    checks = _checks("feat_prerequisites")
    assert "num_nonnulls(min_character_level, ability_code, feature_kind_code) = 1" in checks[
        "ck_feat_prerequisites_single_target"
    ]
    assert "(ability_code IS NULL) = (min_score IS NULL)" in checks["ck_feat_prerequisites_ability_pair"]
    assert "min_character_level BETWEEN 1 AND 20" in checks["ck_feat_prerequisites_min_character_level"]
    assert "min_score BETWEEN 1 AND 30" in checks["ck_feat_prerequisites_min_score"]


def test_feat_model_exposes_prerequisites_and_category():
    from app.db.models.compendium import FeatDefinition

    assert {"prerequisites", "category"} <= set(FeatDefinition.__mapper__.relationships.keys())


# --- step 3: feature_definitions ----------------------------------------------------

def test_feature_grants_is_gone():
    import app.db.models as models
    import app.db.models.compendium as compendium

    assert "feature_grants" not in Base.metadata.tables
    assert not hasattr(compendium, "FeatureGrant")
    assert not hasattr(models, "FeatureGrant")


def test_feature_definitions_columns():
    table = _table("feature_definitions")
    assert set(table.c.keys()) == {
        "id", "name", "description", "sort_order", "class_id", "subclass_id", "feat_id", "level",
        "action_type_code", "feature_kind_code", "replaces_feature_id", "is_choice_option",
        "source", "is_homebrew", "created_by", "created_at",
    }
    assert table.c.name.nullable is False
    assert table.c.sort_order.nullable is False
    assert table.c.is_choice_option.nullable is False
    for owner, target in (("class_id", "class_definitions.id"), ("subclass_id", "subclass_definitions.id"),
                          ("feat_id", "feat_definitions.id")):
        fk = _fk("feature_definitions", owner)
        assert fk.target_fullname == target
        assert fk.ondelete == "CASCADE"
        assert table.c[owner].nullable is True
    for column, target in (("action_type_code", "action_types.code"), ("feature_kind_code", "feature_kinds.code")):
        fk = _fk("feature_definitions", column)
        assert fk.target_fullname == target
        assert fk.ondelete == "RESTRICT"


def test_replaces_feature_id_is_no_action():
    """NO ACTION (checked at the end of the statement): the cascade of the owner deletes a
    whole chain Extra -> Two -> Three Extra Attacks in one statement (risk R4)."""
    fk = _fk("feature_definitions", "replaces_feature_id")
    assert fk.target_fullname == "feature_definitions.id"
    assert fk.ondelete is None


def test_feature_definitions_checks():
    checks = _checks("feature_definitions")
    assert "num_nonnulls(class_id, subclass_id, feat_id) = 1" in checks["ck_feature_definitions_single_owner"]
    assert "(level IS NULL) = (feat_id IS NOT NULL)" in checks["ck_feature_definitions_level_by_owner"]
    assert "level BETWEEN 1 AND 20" in checks["ck_feature_definitions_level"]
    assert "replaces_feature_id <> id" in checks["ck_feature_definitions_not_self_replacing"]


def test_owners_expose_their_features():
    from app.db.models.compendium import ClassDefinition, FeatDefinition, SubclassDefinition

    for model in (ClassDefinition, SubclassDefinition, FeatDefinition):
        assert "features" in model.__mapper__.relationships.keys()


# --- step 4: feature_effects, feature_choices, feature_choice_options -------------------

EFFECT_CODE_TARGETS = {
    "skill_code": "skills.code", "ability_code": "ability_scores.code", "damage_type_code": "damage_types.code",
    "condition_code": "conditions.code", "sense_code": "senses.code", "movement_mode_code": "movement_modes.code",
}
EFFECT_ENTITY_TARGETS = {
    "feat_id": "feat_definitions.id", "spell_id": "spell_definitions.id",
    "granted_feature_id": "feature_definitions.id", "proficiency_grant_id": "proficiency_grants.id",
    "item_id": "item_definitions.id",
}


def test_feature_effects_columns():
    table = _table("feature_effects")
    assert set(table.c.keys()) == {
        "id", "feature_id", "sort_order", "operation_code", "target_code",
        *EFFECT_CODE_TARGETS, *EFFECT_ENTITY_TARGETS,
        "value", "dice_count", "die_size", "value_basis_code", "value_basis_ability_code", "value_multiplier",
        "min_value", "max_value", "spell_ability_code", "always_prepared", "resource_id", "condition_text",
    }
    assert table.c.operation_code.nullable is False
    assert table.c.value_multiplier.nullable is False
    assert table.c.value_multiplier.default.arg == 1
    assert table.c.always_prepared.nullable is False


def test_feature_effects_foreign_keys():
    fk = _fk("feature_effects", "feature_id")
    assert (fk.target_fullname, fk.ondelete) == ("feature_definitions.id", "CASCADE")
    codes = {
        **EFFECT_CODE_TARGETS, "operation_code": "effect_operations.code", "target_code": "effect_targets.code",
        "value_basis_code": "value_bases.code", "value_basis_ability_code": "ability_scores.code",
        "spell_ability_code": "ability_scores.code",
    }
    for column, target in codes.items():
        fk = _fk("feature_effects", column)
        assert (fk.target_fullname, fk.ondelete) == (target, "RESTRICT"), column
    # Entity targets block the delete of the target (409), checked at the end of the statement.
    for column, target in {**EFFECT_ENTITY_TARGETS, "resource_id": "feature_resources.id"}.items():
        fk = _fk("feature_effects", column)
        assert (fk.target_fullname, fk.ondelete) == (target, None), column


def test_feature_effects_checks():
    checks = _checks("feature_effects")
    single = checks["ck_feature_effects_single_target"]
    assert "num_nonnulls(" in single and ") <= 1" in single
    for column in (*EFFECT_CODE_TARGETS, *EFFECT_ENTITY_TARGETS):
        assert column in single
    assert "(dice_count IS NULL) = (die_size IS NULL)" in checks["ck_feature_effects_dice_pair"]
    assert "die_size IN (4, 6, 8, 10, 12, 20)" in checks["ck_feature_effects_die_size"]
    assert "dice_count >= 1" in checks["ck_feature_effects_dice_count"]
    assert "value_basis_ability_code IS NULL OR value_basis_code IS NOT NULL" in checks[
        "ck_feature_effects_basis_ability"
    ]
    assert "min_value <= max_value" in checks["ck_feature_effects_min_max"]
    assert {"feature_id", "sort_order"} == {c.name for c in _uniques("feature_effects")[
        "uq_feature_effects_sort_order"
    ].columns}


def test_feature_choices_columns_and_constraints():
    table = _table("feature_choices")
    assert set(table.c.keys()) == {
        "id", "effect_id", "choose_count", "allow_repeat", "pool_type_code", "feat_category_code",
        "spell_list_code", "spell_level", "weapon_category_code", "tool_category_code",
        "spell_list_from_choice_id", "swap_rule_code",
    }
    fk = _fk("feature_choices", "effect_id")
    assert (fk.target_fullname, fk.ondelete) == ("feature_effects.id", "CASCADE")
    assert table.c.effect_id.nullable is False
    assert {c.name for c in _uniques("feature_choices")["uq_feature_choices_effect_id"].columns} == {"effect_id"}
    for column, target in {
        "pool_type_code": "choice_pool_types.code", "feat_category_code": "feat_categories.code",
        "spell_list_code": "spell_lists.code", "weapon_category_code": "weapon_categories.code",
        "tool_category_code": "tool_categories.code", "swap_rule_code": "choice_swap_rules.code",
    }.items():
        fk = _fk("feature_choices", column)
        assert (fk.target_fullname, fk.ondelete) == (target, "RESTRICT"), column
    fk = _fk("feature_choices", "spell_list_from_choice_id")
    assert (fk.target_fullname, fk.ondelete) == ("feature_choices.id", None)
    checks = _checks("feature_choices")
    assert "choose_count >= 1" in checks["ck_feature_choices_choose_count"]
    assert "spell_level BETWEEN 0 AND 9" in checks["ck_feature_choices_spell_level"]
    assert "spell_list_from_choice_id <> id" in checks["ck_feature_choices_not_self_spell_list"]


OPTION_TARGETS = {
    "feat_id": ("feat_definitions.id", None), "spell_id": ("spell_definitions.id", None),
    "skill_code": ("skills.code", "RESTRICT"), "tool_type_code": ("tool_types.code", "RESTRICT"),
    "ability_code": ("ability_scores.code", "RESTRICT"), "item_id": ("item_definitions.id", None),
    "spell_list_code": ("spell_lists.code", "RESTRICT"), "feature_id": ("feature_definitions.id", None),
}


def test_feature_choice_options_columns_and_constraints():
    table = _table("feature_choice_options")
    assert set(table.c.keys()) == {"id", "choice_id", *OPTION_TARGETS}
    fk = _fk("feature_choice_options", "choice_id")
    assert (fk.target_fullname, fk.ondelete) == ("feature_choices.id", "CASCADE")
    for column, expected in OPTION_TARGETS.items():
        fk = _fk("feature_choice_options", column)
        assert (fk.target_fullname, fk.ondelete) == expected, column
    single = _checks("feature_choice_options")["ck_feature_choice_options_single_target"]
    assert "num_nonnulls(" in single and ") = 1" in single
    for column in OPTION_TARGETS:
        assert column in single
    unique = _uniques("feature_choice_options")["uq_feature_choice_options_target"]
    assert {c.name for c in unique.columns} == {"choice_id", *OPTION_TARGETS}
    assert unique.dialect_options["postgresql"]["nulls_not_distinct"] is True


# --- step 5: feature_resources, feature_resource_recharges, feature_scaling -------------

def test_feature_resources_columns_and_constraints():
    table = _table("feature_resources")
    assert set(table.c.keys()) == {
        "id", "feature_id", "sort_order", "name", "value", "value_basis_code", "value_basis_ability_code",
        "value_multiplier", "min_value",
    }
    assert table.c.name.nullable is False
    assert table.c.value_multiplier.nullable is False
    fk = _fk("feature_resources", "feature_id")
    assert (fk.target_fullname, fk.ondelete) == ("feature_definitions.id", "CASCADE")
    for column, target in (("value_basis_code", "value_bases.code"), ("value_basis_ability_code", "ability_scores.code")):
        fk = _fk("feature_resources", column)
        assert (fk.target_fullname, fk.ondelete) == (target, "RESTRICT")
    checks = _checks("feature_resources")
    assert "value IS NOT NULL OR value_basis_code IS NOT NULL" in checks["ck_feature_resources_has_uses"]
    assert "value_basis_ability_code IS NULL OR value_basis_code IS NOT NULL" in checks[
        "ck_feature_resources_basis_ability"
    ]
    assert {c.name for c in _uniques("feature_resources")["uq_feature_resources_sort_order"].columns} == {
        "feature_id", "sort_order",
    }


def test_feature_resource_recharges_columns_and_constraints():
    table = _table("feature_resource_recharges")
    assert set(table.c.keys()) == {"id", "resource_id", "recharge_type_code", "recovers"}
    assert table.c.recovers.nullable is True
    fk = _fk("feature_resource_recharges", "resource_id")
    assert (fk.target_fullname, fk.ondelete) == ("feature_resources.id", "CASCADE")
    fk = _fk("feature_resource_recharges", "recharge_type_code")
    assert (fk.target_fullname, fk.ondelete) == ("recharge_types.code", "RESTRICT")
    assert "recovers >= 1" in _checks("feature_resource_recharges")["ck_feature_resource_recharges_recovers"]
    unique = _uniques("feature_resource_recharges")["uq_feature_resource_recharges_type"]
    assert {c.name for c in unique.columns} == {"resource_id", "recharge_type_code"}


def test_feature_scaling_columns_and_constraints():
    table = _table("feature_scaling")
    assert set(table.c.keys()) == {"id", "effect_id", "choice_id", "resource_id", "level", "value", "dice_count",
                                   "die_size"}
    for column, target in (("effect_id", "feature_effects.id"), ("choice_id", "feature_choices.id"),
                           ("resource_id", "feature_resources.id")):
        fk = _fk("feature_scaling", column)
        assert (fk.target_fullname, fk.ondelete) == (target, "CASCADE")
    assert table.c.level.nullable is False
    checks = _checks("feature_scaling")
    assert "num_nonnulls(effect_id, choice_id, resource_id) = 1" in checks["ck_feature_scaling_single_target"]
    assert "level BETWEEN 1 AND 20" in checks["ck_feature_scaling_level"]
    assert "(dice_count IS NULL) = (die_size IS NULL)" in checks["ck_feature_scaling_dice_pair"]
    assert "die_size IN (4, 6, 8, 10, 12, 20)" in checks["ck_feature_scaling_die_size"]
    assert "value IS NOT NULL OR dice_count IS NOT NULL" in checks["ck_feature_scaling_has_value"]
    unique = _uniques("feature_scaling")["uq_feature_scaling_level"]
    assert {c.name for c in unique.columns} == {"effect_id", "choice_id", "resource_id", "level"}
    assert unique.dialect_options["postgresql"]["nulls_not_distinct"] is True


PHASE4_TABLES = (
    "feat_prerequisites", "feature_definitions", "feature_effects", "feature_choices", "feature_choice_options",
    "feature_resources", "feature_resource_recharges", "feature_scaling",
)


@pytest.mark.parametrize("name", PHASE4_TABLES)
def test_no_phase4_table_uses_jsonb(name):
    assert not any(isinstance(column.type, JSONB) for column in _table(name).columns)


def test_phase4_models_are_exported():
    import app.db.models as models

    for name in ("FeatPrerequisite", "FeatureDefinition", "FeatureEffect", "FeatureChoice", "FeatureChoiceOption",
                 "FeatureResource", "FeatureResourceRecharge", "FeatureScaling"):
        assert hasattr(models, name), name


def test_children_relationships_exist():
    from app.db.models.features import FeatureChoice, FeatureDefinition, FeatureEffect, FeatureResource

    assert {"effects", "resources"} <= set(FeatureDefinition.__mapper__.relationships.keys())
    assert {"choice", "scaling"} <= set(FeatureEffect.__mapper__.relationships.keys())
    assert {"options", "scaling"} <= set(FeatureChoice.__mapper__.relationships.keys())
    assert {"recharges", "scaling"} <= set(FeatureResource.__mapper__.relationships.keys())
