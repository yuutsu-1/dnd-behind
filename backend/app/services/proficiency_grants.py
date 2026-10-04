"""Turn proficiency-grant descriptors into `ProficiencyGrant` rows.

- Every code must exist and be visible to the caller (rule 6f, `resolve_codes`): 400
  otherwise, with the same message whether the code is unknown or invisible.
- The grant with the same target (every identifying column equal, NULLs included) is
  reused; missing ones are created in the caller's transaction -- nothing is committed
  here, so a rollback by the caller discards them.
- Orphan grants are never deleted.
"""
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.compendium import GRANT_KEY_COLUMNS, ProficiencyGrant
from app.db.models.reference import (
    Ability,
    ArmorCategory,
    Language,
    Skill,
    ToolCategory,
    ToolType,
    WeaponCategory,
    WeaponProperty,
)
from app.schemas.proficiency_grants import ProficiencyGrantDescriptor
from app.services.reference import Viewer, resolve_codes

# column -> (reference model, label used in the 400 message, relationship on the grant)
_REFERENCES = {
    "weapon_category_code": (WeaponCategory, "weapon category", "weapon_category"),
    "required_weapon_property_code": (WeaponProperty, "weapon property", "required_weapon_property"),
    "armor_category_code": (ArmorCategory, "armor category", "armor_category"),
    "tool_type_code": (ToolType, "tool type", "tool_type"),
    "tool_category_code": (ToolCategory, "tool category", "tool_category"),
    "skill_code": (Skill, "skill", "skill"),
    "saving_throw_ability_code": (Ability, "ability score", "saving_throw_ability"),
    "language_code": (Language, "language", "language"),
}


async def _resolve_references(
    db: AsyncSession, descriptors: Sequence[ProficiencyGrantDescriptor], viewer: Viewer
) -> dict[str, dict[str, object]]:
    """`{column: {code: reference row}}` for every code used; 400 on unknown/invisible."""
    rows: dict[str, dict[str, object]] = {}
    for column, (model, label, _) in _REFERENCES.items():
        codes = list(dict.fromkeys(getattr(d, column) for d in descriptors if getattr(d, column) is not None))
        if codes:
            resolved = await resolve_codes(db, model, codes, viewer, label=label)
            rows[column] = dict(zip(codes, resolved))
    return rows


async def _find(db: AsyncSession, descriptor: ProficiencyGrantDescriptor) -> ProficiencyGrant | None:
    query = select(ProficiencyGrant).where(*(
        getattr(ProficiencyGrant, column).is_not_distinct_from(getattr(descriptor, column))
        for column in GRANT_KEY_COLUMNS
    ))
    return (await db.execute(query)).unique().scalar_one_or_none()


async def _create(
    db: AsyncSession, descriptor: ProficiencyGrantDescriptor, references: dict[str, dict[str, object]]
) -> ProficiencyGrant:
    values: dict[str, object] = {}
    for column, (_, _, relationship_name) in _REFERENCES.items():
        code = getattr(descriptor, column)
        if code is not None:
            # The target row is set too, so `target_name` works without a lazy load.
            values[column] = code
            values[relationship_name] = references[column][code]
    grant = ProficiencyGrant(**values)
    try:
        async with db.begin_nested():
            db.add(grant)
            await db.flush()
    except IntegrityError:
        # A concurrent request created the same grant first: use theirs.
        existing = await _find(db, descriptor)
        if existing is None:
            raise
        return existing
    return grant


def _list_order(grant: ProficiencyGrant) -> tuple:
    required = grant.required_weapon_property_code
    return (grant.kind, grant.target_code, required is not None, required or "", str(grant.id))


async def list_grants(db: AsyncSession) -> list[ProficiencyGrant]:
    """Every grant (grants are global), ordered by kind, target code, required weapon
    property (none first) and id."""
    grants = (await db.execute(select(ProficiencyGrant))).unique().scalars().all()
    return sorted(grants, key=_list_order)


async def get_grant(db: AsyncSession, grant_id) -> ProficiencyGrant | None:
    return (await db.execute(
        select(ProficiencyGrant).where(ProficiencyGrant.id == grant_id)
    )).unique().scalar_one_or_none()


async def resolve_grants(
    db: AsyncSession, descriptors: Sequence[ProficiencyGrantDescriptor], viewer: Viewer
) -> list[ProficiencyGrant]:
    """The grants for `descriptors`, in the same order (existing ones reused, missing
    ones created). Validates every code before writing anything."""
    references = await _resolve_references(db, descriptors, viewer)
    grants = []
    for descriptor in descriptors:
        grant = await _find(db, descriptor)
        if grant is None:
            grant = await _create(db, descriptor, references)
        grants.append(grant)
    return grants
