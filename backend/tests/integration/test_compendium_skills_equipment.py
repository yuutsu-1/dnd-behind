import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.compendium import create_class, create_skill, list_skills
from app.db.models.compendium import SkillDefinition
from app.enums import AbilityScore
from app.schemas.compendium import ClassCreate, ClassInitialEquipmentCreate, SkillCreate
from tests.integration.conftest import seed_item, seed_skill, seed_user


def _minimal_class_kwargs(**overrides) -> dict:
    defaults = dict(
        name=f"Class-{uuid.uuid4().hex[:10]}",
        hit_die=8,
        primary_ability=[AbilityScore.STR],
        saving_throw_proficiencies=[AbilityScore.STR],
    )
    defaults.update(overrides)
    return defaults


class TestClassSkillsM2M:
    async def test_class_created_with_skills_via_m2m(self, db_session):
        creator = await seed_user(db_session)
        data = ClassCreate(
            **_minimal_class_kwargs(
                name="Rogue",
                skills=[
                    SkillCreate(name="Stealth", ability_score=AbilityScore.DEX),
                    SkillCreate(name="Sleight of Hand", ability_score=AbilityScore.DEX),
                ],
            )
        )

        obj = await create_class(data, current_user=creator, db=db_session)

        assert {s.name for s in obj.skills} == {"Stealth", "Sleight of Hand"}
        assert obj.skill_choices == 2  # unrelated field keeps its own meaning

    async def test_skill_pool_field_no_longer_part_of_the_schema(self):
        assert "skill_pool" not in type(ClassCreate(**_minimal_class_kwargs())).model_fields

    async def test_resolving_same_skill_twice_across_classes_reuses_row(self, db_session):
        creator = await seed_user(db_session)
        data_a = ClassCreate(**_minimal_class_kwargs(name="Fighter", skills=[SkillCreate(name="Athletics", ability_score=AbilityScore.STR)]))
        data_b = ClassCreate(**_minimal_class_kwargs(name="Barbarian", skills=[SkillCreate(name="Athletics", ability_score=AbilityScore.STR)]))

        await create_class(data_a, current_user=creator, db=db_session)
        await create_class(data_b, current_user=creator, db=db_session)

        result = await db_session.execute(
            select(SkillDefinition).where(SkillDefinition.name == "Athletics", SkillDefinition.ability_score == "STR")
        )
        rows = result.scalars().all()
        assert len(rows) == 1

    async def test_same_name_different_ability_score_creates_distinct_skills(self, db_session):
        creator = await seed_user(db_session)
        data = ClassCreate(
            **_minimal_class_kwargs(
                skills=[
                    SkillCreate(name="Insight", ability_score=AbilityScore.WIS),
                ]
            )
        )
        await create_class(data, current_user=creator, db=db_session)

        # A differently-keyed "Insight" (different ability score) must not collide.
        other = await seed_skill(db_session, name="Insight", ability_score="INT")
        result = await db_session.execute(select(SkillDefinition).where(SkillDefinition.name == "Insight"))
        rows = result.scalars().all()
        assert len(rows) == 2
        assert {r.ability_score for r in rows} == {"WIS", "INT"}


class TestSkillDefinitionUniqueConstraint:
    async def test_duplicate_name_and_ability_score_rejected_by_db(self, db_session):
        await seed_skill(db_session, name="Perception", ability_score="WIS")
        db_session.add(SkillDefinition(id=uuid.uuid4(), name="Perception", ability_score="WIS"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_create_skill_endpoint_and_list_skills(self, db_session):
        creator = await seed_user(db_session)
        skill = await create_skill(SkillCreate(name="Arcana", ability_score=AbilityScore.INT), current_user=creator, db=db_session)
        assert skill.name == "Arcana"
        assert skill.ability_score == "INT"

        skills = await list_skills(db=db_session, search="Arcana")
        assert any(s.name == "Arcana" for s in skills)


class TestClassInitialEquipment:
    async def test_created_and_grouped_by_option(self, db_session):
        creator = await seed_user(db_session)
        dagger = await seed_item(db_session, name="Dagger")
        shortsword = await seed_item(db_session, name="Shortsword")
        data = ClassCreate(
            **_minimal_class_kwargs(
                name="Rogue Equipment Test",
                initial_equipment=[
                    ClassInitialEquipmentCreate(item_id=dagger.id, option="A", quantity=2),
                    ClassInitialEquipmentCreate(item_id=shortsword.id, option="B", quantity=1),
                ],
            )
        )

        obj = await create_class(data, current_user=creator, db=db_session)

        by_option = {e.option: e for e in obj.initial_equipment}
        assert by_option["A"].item_name == "Dagger"
        assert by_option["A"].quantity == 2
        assert by_option["B"].item_name == "Shortsword"
        assert by_option["B"].quantity == 1

    async def test_referencing_missing_item_is_rejected(self, db_session):
        creator = await seed_user(db_session)
        data = ClassCreate(
            **_minimal_class_kwargs(
                initial_equipment=[ClassInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=1)]
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_class(data, current_user=creator, db=db_session)
        assert exc_info.value.status_code == 400

    async def test_quantity_must_be_at_least_one(self):
        with pytest.raises(ValueError):
            ClassInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=0)
