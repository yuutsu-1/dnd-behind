"""Shared by the SRD feature extractors (scripts/extract_srd_feats.py and
scripts/extract_srd_fighter.py): the shape of the curated structure of a feature and
the rendering of the generated data modules.

A curated feature structure is written with the same names as the API payload
(`FeatureIn` in app/schemas/features.py): effects (with an optional `choice`, which has
`options` and `scaling`), `resources` (with `recharges` and `scaling`). Only the keys
that matter are written (sparse); the migration fills the defaults. Any unknown key is
an error: nothing is silently ignored.
"""
import pprint

EFFECT_KEYS = frozenset({
    "operation_code", "target_code",
    "feat_id", "spell_id", "granted_feature_id", "proficiency_grant_id", "skill_code", "ability_code",
    "damage_type_code", "condition_code", "sense_code", "movement_mode_code", "item_id",
    "value", "dice_count", "die_size", "value_basis_code", "value_basis_ability_code", "value_multiplier",
    "min_value", "max_value", "spell_ability_code", "always_prepared", "resource_index", "condition_text",
    "choice", "scaling",
})
CHOICE_KEYS = frozenset({
    "choose_count", "allow_repeat", "pool_type_code", "feat_category_code", "spell_list_code", "spell_level",
    "weapon_category_code", "tool_category_code", "spell_list_from_effect_index", "swap_rule_code", "options",
    "scaling",
})
OPTION_KEYS = frozenset({
    "feat_id", "spell_id", "skill_code", "tool_type_code", "ability_code", "item_id", "spell_list_code", "feature_id",
})
RESOURCE_KEYS = frozenset({
    "name", "value", "value_basis_code", "value_basis_ability_code", "value_multiplier", "min_value", "recharges",
    "scaling",
})
RECHARGE_KEYS = frozenset({"recharge_type_code", "recovers"})
SCALING_KEYS = frozenset({"level", "value", "dice_count", "die_size"})


def _check_keys(entry: dict, allowed: frozenset, where: str, error: type[Exception]) -> None:
    unknown = sorted(set(entry) - allowed)
    if unknown:
        raise error(f"{where}: unknown key(s) {', '.join(unknown)}")


def _scaling(rows, where: str, error) -> tuple:
    out = []
    for row in rows:
        _check_keys(row, SCALING_KEYS, f"{where} scaling", error)
        out.append(dict(row))
    return tuple(out)


def normalize_choice(choice: dict, where: str, error) -> dict:
    _check_keys(choice, CHOICE_KEYS, f"{where} choice", error)
    out = {key: value for key, value in choice.items() if key not in ("options", "scaling")}
    if "options" in choice:
        options = []
        for option in choice["options"]:
            _check_keys(option, OPTION_KEYS, f"{where} option", error)
            if len(option) != 1:
                raise error(f"{where}: an option has exactly one target")
            options.append(dict(option))
        out["options"] = tuple(options)
    if "scaling" in choice:
        out["scaling"] = _scaling(choice["scaling"], f"{where} choice", error)
    return out


def normalize_effect(effect: dict, where: str, error) -> dict:
    _check_keys(effect, EFFECT_KEYS, f"{where} effect", error)
    if "operation_code" not in effect:
        raise error(f"{where}: an effect needs an operation_code")
    out = {key: value for key, value in effect.items() if key not in ("choice", "scaling")}
    if "choice" in effect:
        out["choice"] = normalize_choice(effect["choice"], where, error)
    if "scaling" in effect:
        out["scaling"] = _scaling(effect["scaling"], f"{where} effect", error)
    return out


def normalize_resource(resource: dict, where: str, error) -> dict:
    _check_keys(resource, RESOURCE_KEYS, f"{where} resource", error)
    if not resource.get("name") or not resource.get("recharges"):
        raise error(f"{where}: a resource needs a name and at least one recharge")
    out = {key: value for key, value in resource.items() if key not in ("recharges", "scaling")}
    recharges = []
    for recharge in resource["recharges"]:
        _check_keys(recharge, RECHARGE_KEYS, f"{where} recharge", error)
        recharges.append({"recharge_type_code": recharge["recharge_type_code"], "recovers": recharge.get("recovers")})
    out["recharges"] = tuple(recharges)
    if "scaling" in resource:
        out["scaling"] = _scaling(resource["scaling"], f"{where} resource", error)
    return out


def normalize_structure(entry: dict, allowed: frozenset, where: str, error) -> dict:
    """The curated `entry` of one feature with every nested list turned into a tuple."""
    _check_keys(entry, allowed, where, error)
    out = {key: value for key, value in entry.items() if key not in ("effects", "resources")}
    out["effects"] = tuple(normalize_effect(effect, where, error) for effect in entry.get("effects", ()))
    out["resources"] = tuple(normalize_resource(res, where, error) for res in entry.get("resources", ()))
    return out


def render_data_module(docstring: str, assignments: dict[str, object]) -> str:
    """A Python module with `docstring` and one `NAME = <literal>` per assignment."""
    out = [docstring]
    for name, value in assignments.items():
        out.append(f"\n{name} = {pprint.pformat(value, indent=1, width=120, sort_dicts=False)}\n")
    return "".join(out)
