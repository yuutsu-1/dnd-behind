"""Features (phase 4): read, validation and writing of the features embedded in their
owner (class, subclass or feat). There is no write route of its own for a feature.

Features are global (every user sees every feature). Every child level is loaded
explicitly, in a fixed number of queries (no lazy load, no N+1)."""
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import case, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.compendium import (
    ClassDefinition,
    FeatDefinition,
    ItemDefinition,
    ProficiencyGrant,
    SpellDefinition,
    SubclassDefinition,
)
from app.db.models.features import (
    EFFECT_TARGET_COLUMNS,
    FeatureChoice,
    FeatureChoiceOption,
    FeatureDefinition,
    FeatureEffect,
    FeatureResource,
    FeatureResourceRecharge,
    FeatureScaling,
)
from app.db.models.reference import (
    Ability,
    ActionType,
    ChoicePoolType,
    ChoiceSwapRule,
    Condition,
    DamageType,
    EffectOperation,
    EffectTarget,
    FeatCategory,
    FeatureKind,
    MovementMode,
    RechargeType,
    Sense,
    Skill,
    SpellList,
    ToolCategory,
    ToolType,
    ValueBasis,
    WeaponCategory,
)
from app.db.models.user import User
from app.schemas.features import EffectIn, FeatureIn
from app.services.reference import resolve_codes


def feature_children(base=None) -> list:
    """Loader options for every child of a feature. `base`: the loader of the features
    themselves when they are loaded through their owner (e.g. `selectinload(Owner.features)`)."""
    def chain(*path):
        loader = base.selectinload(path[0]) if base is not None else selectinload(path[0])
        for attribute in path[1:]:
            loader = loader.selectinload(attribute)
        return loader

    # Entity targets are listed explicitly: under an owner (feat -> features -> effects ->
    # feat/feature) the mapper repeats in the path and the default eager load would stop.
    effect_entities = (FeatureEffect.feat, FeatureEffect.spell, FeatureEffect.granted_feature,
                       FeatureEffect.proficiency_grant, FeatureEffect.item)
    option_entities = (FeatureChoiceOption.feat, FeatureChoiceOption.spell, FeatureChoiceOption.item,
                       FeatureChoiceOption.feature)
    return [
        *(chain(FeatureDefinition.effects, entity) for entity in effect_entities),
        *(chain(FeatureDefinition.effects, FeatureEffect.choice, FeatureChoice.options, entity)
          for entity in option_entities),
        chain(FeatureDefinition.effects, FeatureEffect.choice, FeatureChoice.scaling),
        chain(FeatureDefinition.effects, FeatureEffect.scaling),
        chain(FeatureDefinition.resources, FeatureResource.recharges),
        chain(FeatureDefinition.resources, FeatureResource.scaling),
    ]


def owner_features(owner_attribute) -> list:
    """Loader options for `owner.features` with every child."""
    return feature_children(selectinload(owner_attribute))


async def list_features(
    db: AsyncSession,
    *,
    class_id: uuid.UUID | None = None,
    subclass_id: uuid.UUID | None = None,
    feat_id: uuid.UUID | None = None,
    level: int | None = None,
    kind: str | None = None,
) -> list[FeatureDefinition]:
    """Ordered by owner (classes, then subclasses, then feats; by owner name and id), then
    level (NULL first), sort order, name, id. Unknown ids/codes just match nothing."""
    query = (
        select(FeatureDefinition)
        .outerjoin(ClassDefinition, ClassDefinition.id == FeatureDefinition.class_id)
        .outerjoin(SubclassDefinition, SubclassDefinition.id == FeatureDefinition.subclass_id)
        .outerjoin(FeatDefinition, FeatDefinition.id == FeatureDefinition.feat_id)
    )
    if class_id is not None:
        query = query.where(FeatureDefinition.class_id == class_id)
    if subclass_id is not None:
        query = query.where(FeatureDefinition.subclass_id == subclass_id)
    if feat_id is not None:
        query = query.where(FeatureDefinition.feat_id == feat_id)
    if level is not None:
        query = query.where(FeatureDefinition.level == level)
    if kind:
        query = query.where(FeatureDefinition.feature_kind_code == kind)
    owner_kind = case(
        (FeatureDefinition.class_id.is_not(None), 0), (FeatureDefinition.subclass_id.is_not(None), 1), else_=2,
    )
    query = query.options(*feature_children()).order_by(
        owner_kind,
        func.coalesce(ClassDefinition.name, SubclassDefinition.name, FeatDefinition.name),
        func.coalesce(FeatureDefinition.class_id, FeatureDefinition.subclass_id, FeatureDefinition.feat_id),
        FeatureDefinition.level.asc().nulls_first(),
        FeatureDefinition.sort_order,
        FeatureDefinition.name,
        FeatureDefinition.id,
    )
    return list((await db.execute(query)).unique().scalars().all())


async def get_feature(db: AsyncSession, feature_id: uuid.UUID) -> FeatureDefinition | None:
    query = (
        select(FeatureDefinition).where(FeatureDefinition.id == feature_id)
        .options(*feature_children()).execution_options(populate_existing=True)
    )
    return (await db.execute(query)).unique().scalar_one_or_none()


# --- validation ------------------------------------------------------------------------

OWNER_KINDS = ("class", "subclass", "feat")


@dataclass(frozen=True)
class OperationRule:
    """What an SRD operation expects (matrix B13 of the phase 4 plan)."""

    target_code: str  # "forbidden" | "required"
    fixed: frozenset[str] = frozenset()  # typed targets accepted
    pools: frozenset[str] = frozenset()  # choice pools accepted
    needs_target: bool = True  # a fixed target or a choice is required
    needs_amount: bool = False  # value, dice or formula
    needs_value: bool = False  # a plain `value`
    no_dice: bool = False
    needs_options: bool = False  # the choice must list its options
    only_target_code: str | None = None


_GRANT_FIXED = frozenset({
    "feat_id", "spell_id", "granted_feature_id", "proficiency_grant_id", "sense_code", "movement_mode_code",
})
OPERATION_RULES: dict[str, OperationRule] = {
    "grant": OperationRule(
        "forbidden", _GRANT_FIXED,
        frozenset({"feat", "spell", "skill", "tool_type", "skill_or_tool", "weapon", "feature"}),
    ),
    "expertise": OperationRule("forbidden", frozenset({"skill_code"}), frozenset({"skill"})),
    "ability_score_increase": OperationRule(
        "forbidden", frozenset({"ability_code"}), frozenset({"ability_score"}), needs_value=True,
    ),
    "damage_resistance": OperationRule("forbidden", frozenset({"damage_type_code"})),
    "damage_immunity": OperationRule("forbidden", frozenset({"damage_type_code"})),
    "condition_immunity": OperationRule("forbidden", frozenset({"condition_code"})),
    "bonus": OperationRule("required", needs_target=False, needs_amount=True),
    "set": OperationRule("required", needs_target=False, needs_value=True, no_dice=True),
    "advantage": OperationRule("required", frozenset({"skill_code", "ability_code"}), needs_target=False),
    "heal": OperationRule("required", needs_target=False, needs_amount=True, only_target_code="hit_points"),
    "spellcasting_ability": OperationRule(
        "forbidden", pools=frozenset({"ability_score"}), needs_options=True,
    ),
    "spell_list": OperationRule("forbidden", pools=frozenset({"spell_list"}), needs_options=True),
}
# Fixed targets that also need a `value` (the range/speed in feet).
_TARGETS_WITH_VALUE = frozenset({"sense_code", "movement_mode_code"})
# Typed target of `advantage` -> SRD target codes it fits.
_ADVANTAGE_TARGETS = {"skill_code": {"ability_check"}, "ability_code": {"ability_check", "saving_throw"}}

POOL_OPTIONS: dict[str, frozenset[str]] = {
    "feat": frozenset({"feat_id"}), "spell": frozenset({"spell_id"}), "skill": frozenset({"skill_code"}),
    "tool_type": frozenset({"tool_type_code"}), "skill_or_tool": frozenset({"skill_code", "tool_type_code"}),
    "ability_score": frozenset({"ability_code"}), "weapon": frozenset({"item_id"}),
    "spell_list": frozenset({"spell_list_code"}), "feature": frozenset({"feature_id"}),
}
POOL_FILTERS: dict[str, frozenset[str]] = {
    "feat_category_code": frozenset({"feat"}),
    "spell_list_code": frozenset({"spell"}),
    "spell_level": frozenset({"spell"}),
    "spell_list_from_effect_index": frozenset({"spell"}),
    "weapon_category_code": frozenset({"weapon"}),
    "tool_category_code": frozenset({"tool_type", "skill_or_tool"}),
}

# Model of each code field (where it appears) and the label of the 400 message.
_FEATURE_CODES = {"action_type_code": (ActionType, "action type"), "feature_kind_code": (FeatureKind, "feature kind")}
_EFFECT_CODES = {
    "operation_code": (EffectOperation, "effect operation"), "target_code": (EffectTarget, "effect target"),
    "skill_code": (Skill, "skill"), "ability_code": (Ability, "ability score"),
    "damage_type_code": (DamageType, "damage type"), "condition_code": (Condition, "condition"),
    "sense_code": (Sense, "sense"), "movement_mode_code": (MovementMode, "movement mode"),
    "value_basis_code": (ValueBasis, "value basis"), "value_basis_ability_code": (Ability, "ability score"),
    "spell_ability_code": (Ability, "ability score"),
}
_CHOICE_CODES = {
    "pool_type_code": (ChoicePoolType, "choice pool type"), "feat_category_code": (FeatCategory, "feat category"),
    "spell_list_code": (SpellList, "spell list"), "weapon_category_code": (WeaponCategory, "weapon category"),
    "tool_category_code": (ToolCategory, "tool category"), "swap_rule_code": (ChoiceSwapRule, "choice swap rule"),
}
_OPTION_CODES = {
    "skill_code": (Skill, "skill"), "tool_type_code": (ToolType, "tool type"), "ability_code": (Ability, "ability score"),
    "spell_list_code": (SpellList, "spell list"),
}
_RESOURCE_CODES = {
    "value_basis_code": (ValueBasis, "value basis"), "value_basis_ability_code": (Ability, "ability score"),
}
# Entity id fields (effects and options) -> model and label.
_ENTITIES = {
    "feat_id": (FeatDefinition, "feat"), "spell_id": (SpellDefinition, "spell"), "item_id": (ItemDefinition, "item"),
    "granted_feature_id": (FeatureDefinition, "feature"), "feature_id": (FeatureDefinition, "feature"),
    "proficiency_grant_id": (ProficiencyGrant, "proficiency grant"),
}


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _walk(features: Sequence[FeatureIn]):
    """(where, kind, row) of every row of the payload that may hold codes or ids."""
    for i, feature in enumerate(features):
        yield f"features[{i}]", "feature", feature
        for j, resource in enumerate(feature.resources):
            yield f"features[{i}].resources[{j}]", "resource", resource
            for k, recharge in enumerate(resource.recharges):
                yield f"features[{i}].resources[{j}].recharges[{k}]", "recharge", recharge
        for j, effect in enumerate(feature.effects):
            yield f"features[{i}].effects[{j}]", "effect", effect
            if effect.choice is not None:
                yield f"features[{i}].effects[{j}].choice", "choice", effect.choice
                for k, option in enumerate(effect.choice.options):
                    yield f"features[{i}].effects[{j}].choice.options[{k}]", "option", option


_CODES_BY_KIND = {
    "feature": _FEATURE_CODES, "effect": _EFFECT_CODES, "choice": _CHOICE_CODES, "option": _OPTION_CODES,
    "resource": _RESOURCE_CODES, "recharge": {"recharge_type_code": (RechargeType, "recharge type")},
}


async def _resolve_codes(db: AsyncSession, features: Sequence[FeatureIn], user: User) -> dict[tuple, object]:
    """400 for any code that does not exist or is not visible (same message either way).
    Returns `{(model, code): row}` (the row tells whether the code is SRD or homebrew)."""
    wanted: dict[tuple, list[str]] = {}
    for _, kind, row in _walk(features):
        for field, (model, label) in _CODES_BY_KIND[kind].items():
            code = getattr(row, field)
            if code is not None:
                wanted.setdefault((model, label), []).append(code)
    resolved: dict[tuple, object] = {}
    for (model, label), codes in wanted.items():
        unique = list(dict.fromkeys(codes))
        for code, row in zip(unique, await resolve_codes(db, model, unique, user, label=label)):
            resolved[(model, code)] = row
    return resolved


async def _check_entities(db: AsyncSession, features: Sequence[FeatureIn]) -> None:
    """400 for any referenced feat/spell/item/feature/grant that does not exist; 400 for a
    `weapon` option that is not a weapon."""
    wanted: dict[str, set[uuid.UUID]] = {}
    weapon_options: list[uuid.UUID] = []
    for _, kind, row in _walk(features):
        if kind not in ("effect", "option"):
            continue
        for field in _ENTITIES:
            value = getattr(row, field, None)
            if value is not None:
                wanted.setdefault(field, set()).add(value)
    for feature in features:
        for effect in feature.effects:
            if effect.choice is not None and effect.choice.pool_type_code == "weapon":
                weapon_options += [option.item_id for option in effect.choice.options if option.item_id is not None]
    item_types: dict[uuid.UUID, str] = {}
    for field, ids in wanted.items():
        model, label = _ENTITIES[field]
        if model is ItemDefinition:
            rows = await db.execute(select(ItemDefinition.id, ItemDefinition.item_type_code).where(
                ItemDefinition.id.in_(ids)))
            item_types = dict(rows.all())
            found = set(item_types)
        else:
            found = set((await db.execute(select(model.id).where(model.id.in_(ids)))).scalars())
        if missing := sorted(str(value) for value in ids - found):
            raise _bad_request(f"Unknown {label} id(s): {', '.join(missing)}")
    for item_id in weapon_options:
        if item_types.get(item_id) != "weapon":
            raise _bad_request(f"Item {item_id} is not a weapon")


def _is_srd(resolved: dict, model, code: str | None) -> bool:
    row = resolved.get((model, code)) if code is not None else None
    return row is not None and not row.is_homebrew


def _check_effect(where: str, index: int, effect: EffectIn, feature: FeatureIn, resolved: dict) -> None:
    if effect.resource_index is not None and effect.resource_index >= len(feature.resources):
        raise _unprocessable(f"{where}: resource_index {effect.resource_index} is not a resource of the feature")
    rule = OPERATION_RULES.get(effect.operation_code) if _is_srd(resolved, EffectOperation, effect.operation_code) \
        else None
    if rule is None:
        return  # homebrew operation: only "at most one typed target" (schema)
    op = effect.operation_code
    targets = effect.targets
    if rule.target_code == "forbidden" and effect.target_code is not None:
        raise _unprocessable(f"{where}: operation '{op}' takes no target_code")
    if rule.target_code == "required" and effect.target_code is None:
        raise _unprocessable(f"{where}: operation '{op}' needs a target_code")
    if rule.only_target_code and effect.target_code != rule.only_target_code \
            and _is_srd(resolved, EffectTarget, effect.target_code):
        raise _unprocessable(f"{where}: operation '{op}' only targets '{rule.only_target_code}'")
    if extra := [target for target in targets if target not in rule.fixed]:
        raise _unprocessable(f"{where}: operation '{op}' does not take {', '.join(extra)}")
    if effect.choice is not None and not rule.pools:
        raise _unprocessable(f"{where}: operation '{op}' takes no choice")
    choice = effect.choice
    if choice is not None and _is_srd(resolved, ChoicePoolType, choice.pool_type_code) \
            and choice.pool_type_code not in rule.pools:
        raise _unprocessable(f"{where}: operation '{op}' does not choose from pool '{choice.pool_type_code}'")
    if rule.needs_target and not targets and choice is None:
        raise _unprocessable(f"{where}: operation '{op}' needs a fixed target or a choice")
    if rule.needs_options and (choice is None or not choice.options):
        raise _unprocessable(f"{where}: operation '{op}' needs a choice with its options")
    if rule.needs_amount and not effect.has_amount:
        raise _unprocessable(f"{where}: operation '{op}' needs a value, dice or a formula")
    if rule.needs_value and effect.value is None:
        raise _unprocessable(f"{where}: operation '{op}' needs a value")
    if rule.no_dice and effect.dice_count is not None:
        raise _unprocessable(f"{where}: operation '{op}' takes no dice")
    for target in targets:
        if target in _TARGETS_WITH_VALUE and effect.value is None:
            raise _unprocessable(f"{where}: {target} needs a value (in feet)")
        fits = _ADVANTAGE_TARGETS.get(target)
        if op == "advantage" and fits and _is_srd(resolved, EffectTarget, effect.target_code) \
                and effect.target_code not in fits:
            raise _unprocessable(f"{where}: {target} does not fit target_code '{effect.target_code}'")


def _check_choice(where: str, index: int, effect: EffectIn, feature: FeatureIn, resolved: dict) -> None:
    choice = effect.choice
    source = choice.spell_list_from_effect_index
    if source is not None:
        target = feature.effects[source] if source < len(feature.effects) and source != index else None
        if target is None or target.choice is None or target.choice.pool_type_code != "spell_list":
            raise _unprocessable(f"{where}: spell_list_from_effect_index must point to another effect of the "
                                 "feature whose choice has pool 'spell_list'")
    if not _is_srd(resolved, ChoicePoolType, choice.pool_type_code):
        return  # homebrew pool: any option and filter
    pool = choice.pool_type_code
    allowed = POOL_OPTIONS.get(pool, frozenset())
    for option in choice.options:
        if extra := [target for target in option.targets if target not in allowed]:
            raise _unprocessable(f"{where}: option {', '.join(extra)} does not fit pool '{pool}'")
    for field, pools in POOL_FILTERS.items():
        if getattr(choice, field) is not None and pool not in pools:
            raise _unprocessable(f"{where}: filter {field} does not fit pool '{pool}'")


def _scaling_rows(feature: FeatureIn):
    for effect in feature.effects:
        yield from effect.scaling
        if effect.choice is not None:
            yield from effect.choice.scaling
    for resource in feature.resources:
        yield from resource.scaling


def _check_level(i: int, feature: FeatureIn, owner: str) -> None:
    where = f"features[{i}]"
    if owner == "feat" and feature.level is not None:
        raise _unprocessable(f"{where}: a feat feature has no level")
    if owner != "feat" and feature.level is None:
        raise _unprocessable(f"{where}: a {owner} feature needs a level (1..20)")


def _check_feature(i: int, feature: FeatureIn, features: Sequence[FeatureIn], owner: str, resolved: dict) -> None:
    """Coherence of one feature; every level was already checked (`_check_level`)."""
    where = f"features[{i}]"
    if feature.replaces_index is not None:
        target = feature.replaces_index
        if owner == "feat":
            raise _unprocessable(f"{where}: a feat feature cannot replace another feature")
        if target >= len(features) or target == i:
            raise _unprocessable(f"{where}: replaces_index {target} is not another feature of the owner")
        if features[target].level >= feature.level:
            raise _unprocessable(f"{where}: the replaced feature must have a lower level")
    minimum = feature.level or 1
    if any(row.level < minimum for row in _scaling_rows(feature)):
        raise _unprocessable(f"{where}: scaling levels must be >= the feature level ({minimum})")
    for j, effect in enumerate(feature.effects):
        _check_effect(f"{where}.effects[{j}]", j, effect, feature, resolved)
        if effect.choice is not None:
            _check_choice(f"{where}.effects[{j}].choice", j, effect, feature, resolved)


_OWNER_COLUMNS = {"class": "class_id", "subclass": "subclass_id", "feat": "feat_id"}


async def _check_owner_references(
    db: AsyncSession, features: Sequence[FeatureIn], owner: str, owner_id: uuid.UUID,
) -> None:
    """On a replacement (PATCH), the new features may not point to a CURRENT feature of
    the owner (it is deleted by the replacement), and a feat may not point to itself."""
    column = getattr(FeatureDefinition, _OWNER_COLUMNS[owner])
    current = set((await db.execute(select(FeatureDefinition.id).where(column == owner_id))).scalars())
    for where, kind, row in _walk(features):
        if kind not in ("effect", "option"):
            continue
        target = row.granted_feature_id if kind == "effect" else row.feature_id
        if target is not None and target in current:
            raise _unprocessable(
                f"{where}: points to a current feature of this {owner}, which the replacement deletes"
            )
        if owner == "feat" and row.feat_id == owner_id:
            raise _unprocessable(f"{where}: a feat cannot reference itself")


async def validate_features(
    db: AsyncSession, features: Sequence[FeatureIn], owner: str, user: User, owner_id: uuid.UUID | None = None,
) -> None:
    """Every feature of an owner of kind `owner` ("class", "subclass" or "feat"), in its
    final state: 400 (codes and ids) first, then 422 (coherence). `owner_id` (PATCH): the
    owner being changed. Writes nothing."""
    assert owner in OWNER_KINDS
    resolved = await _resolve_codes(db, features, user)
    await _check_entities(db, features)
    if owner_id is not None:
        await _check_owner_references(db, features, owner, owner_id)
    for i, feature in enumerate(features):
        _check_level(i, feature, owner)
    for i, feature in enumerate(features):
        _check_feature(i, feature, features, owner, resolved)


# --- writing ----------------------------------------------------------------------------

_EFFECT_COLUMNS = (
    "operation_code", "target_code", *EFFECT_TARGET_COLUMNS, "value", "dice_count", "die_size", "value_basis_code",
    "value_basis_ability_code", "value_multiplier", "min_value", "max_value", "spell_ability_code", "always_prepared",
    "condition_text",
)
_CHOICE_COLUMNS = (
    "choose_count", "allow_repeat", "pool_type_code", "feat_category_code", "spell_list_code", "spell_level",
    "weapon_category_code", "tool_category_code", "swap_rule_code",
)
_RESOURCE_COLUMNS = ("name", "value", "value_basis_code", "value_basis_ability_code", "value_multiplier", "min_value")


def _scaling_inserts(column: str, target_id: uuid.UUID, rows) -> list[dict]:
    return [
        {"id": uuid.uuid4(), "effect_id": None, "choice_id": None, "resource_id": None, column: target_id,
         "level": row.level, "value": row.value, "dice_count": row.dice_count, "die_size": row.die_size}
        for row in rows
    ]


async def insert_features(
    db: AsyncSession, owner_column: str, owner_id: uuid.UUID, features: Sequence[FeatureIn], provenance: dict,
) -> None:
    """Write `features` (already validated) for the owner; `provenance` (`source`,
    `is_homebrew`, `created_by`) is copied from the owner. Positions become ids."""
    feature_ids = [uuid.uuid4() for _ in features]
    rows: dict[type, list[dict]] = {model: [] for model in (
        FeatureDefinition, FeatureResource, FeatureResourceRecharge, FeatureEffect, FeatureChoice,
        FeatureChoiceOption, FeatureScaling,
    )}
    replaces: list[tuple[uuid.UUID, uuid.UUID]] = []
    spell_list_sources: list[tuple[uuid.UUID, uuid.UUID]] = []
    for position, (feature_id, feature) in enumerate(zip(feature_ids, features)):
        rows[FeatureDefinition].append({
            "id": feature_id, "name": feature.name, "description": feature.description, "sort_order": position,
            "class_id": None, "subclass_id": None, "feat_id": None, owner_column: owner_id, "level": feature.level,
            "action_type_code": feature.action_type_code, "feature_kind_code": feature.feature_kind_code,
            "replaces_feature_id": None, "is_choice_option": feature.is_choice_option, **provenance,
        })
        if feature.replaces_index is not None:
            replaces.append((feature_id, feature_ids[feature.replaces_index]))
        resource_ids = [uuid.uuid4() for _ in feature.resources]
        for index, (resource_id, resource) in enumerate(zip(resource_ids, feature.resources)):
            rows[FeatureResource].append({
                "id": resource_id, "feature_id": feature_id, "sort_order": index,
                **{column: getattr(resource, column) for column in _RESOURCE_COLUMNS},
            })
            rows[FeatureResourceRecharge].extend(
                {"id": uuid.uuid4(), "resource_id": resource_id, "recharge_type_code": recharge.recharge_type_code,
                 "recovers": recharge.recovers}
                for recharge in resource.recharges
            )
            rows[FeatureScaling].extend(_scaling_inserts("resource_id", resource_id, resource.scaling))
        effect_ids = [uuid.uuid4() for _ in feature.effects]
        choice_ids = [uuid.uuid4() if effect.choice is not None else None for effect in feature.effects]
        for index, (effect_id, effect) in enumerate(zip(effect_ids, feature.effects)):
            rows[FeatureEffect].append({
                "id": effect_id, "feature_id": feature_id, "sort_order": index,
                **{column: getattr(effect, column) for column in _EFFECT_COLUMNS},
                "resource_id": resource_ids[effect.resource_index] if effect.resource_index is not None else None,
            })
            rows[FeatureScaling].extend(_scaling_inserts("effect_id", effect_id, effect.scaling))
            choice = effect.choice
            if choice is None:
                continue
            choice_id = choice_ids[index]
            rows[FeatureChoice].append({
                "id": choice_id, "effect_id": effect_id, "spell_list_from_choice_id": None,
                **{column: getattr(choice, column) for column in _CHOICE_COLUMNS},
            })
            if choice.spell_list_from_effect_index is not None:
                spell_list_sources.append((choice_id, choice_ids[choice.spell_list_from_effect_index]))
            rows[FeatureChoiceOption].extend(
                {"id": uuid.uuid4(), "choice_id": choice_id, **option.model_dump()} for option in choice.options
            )
            rows[FeatureScaling].extend(_scaling_inserts("choice_id", choice_id, choice.scaling))

    for model, values in rows.items():
        if values:
            await db.execute(insert(model), values)
    for feature_id, replaced_id in replaces:
        await db.execute(
            update(FeatureDefinition).where(FeatureDefinition.id == feature_id)
            .values(replaces_feature_id=replaced_id)
        )
    for choice_id, source_id in spell_list_sources:
        await db.execute(
            update(FeatureChoice).where(FeatureChoice.id == choice_id).values(spell_list_from_choice_id=source_id)
        )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def replace_features(
    db: AsyncSession, owner_column: str, owner_id: uuid.UUID, features: Sequence[FeatureIn], provenance: dict,
) -> None:
    """Delete the owner's features (children cascade) and write `features`. A current
    feature referenced from outside the owner (another effect or option) blocks it: 409."""
    try:
        async with db.begin_nested():
            await db.execute(delete(FeatureDefinition).where(getattr(FeatureDefinition, owner_column) == owner_id))
    except IntegrityError:
        raise _conflict("A feature of this owner is still referenced and cannot be replaced") from None
    await insert_features(db, owner_column, owner_id, features, provenance)
