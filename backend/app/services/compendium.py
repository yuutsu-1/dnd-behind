from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.compendium import AbilityScoreOption, SkillDefinition
from app.schemas.compendium import SkillCreate


async def ensure_ability_score_options(db: AsyncSession, names: set[str]) -> None:
    """Get-or-create `AbilityScoreOption` rows so `SkillDefinition.ability_score`
    (a FK to `ability_score_options.name`) can be safely inserted, even if no
    class has referenced that ability score as a primary/saving-throw option yet."""
    if not names:
        return
    result = await db.execute(select(AbilityScoreOption).where(AbilityScoreOption.name.in_(names)))
    existing = {opt.name for opt in result.scalars().all()}
    missing = names - existing
    for name in missing:
        db.add(AbilityScoreOption(name=name))
    if missing:
        await db.flush()


async def resolve_skills(db: AsyncSession, skills: list[SkillCreate]) -> list[SkillDefinition]:
    """Get-or-create `SkillDefinition` rows for the given (name, ability_score) pairs.

    Unlike the simple lookup tables resolved by `_resolve_options` in
    `app/api/compendium.py` (unique by name alone), `SkillDefinition` is unique
    on the composite `(name, ability_score)`, so matching must consider both
    fields together.
    """
    if not skills:
        return []

    await ensure_ability_score_options(db, {s.ability_score.value for s in skills})

    names = [s.name for s in skills]
    result = await db.execute(select(SkillDefinition).where(SkillDefinition.name.in_(names)))
    existing_by_key = {(s.name, s.ability_score): s for s in result.scalars().all()}

    output: list[SkillDefinition] = []
    seen_keys: set[tuple[str, str]] = set()
    for skill in skills:
        key = (skill.name, skill.ability_score.value)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if key in existing_by_key:
            output.append(existing_by_key[key])
        else:
            new_skill = SkillDefinition(name=skill.name, ability_score=skill.ability_score.value)
            db.add(new_skill)
            await db.flush()
            existing_by_key[key] = new_skill
            output.append(new_skill)
    return output
