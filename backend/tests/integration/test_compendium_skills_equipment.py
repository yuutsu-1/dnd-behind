import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.compendium import create_class, get_class, list_classes
from app.db.models.compendium import ClassDefinition
from app.db.models.reference import Ability, ArmorCategory, Skill, ToolProficiencyOption, WeaponCategory
from app.schemas.compendium import ClassCreate, ClassInitialEquipmentCreate, ClassOut
from tests.integration.conftest import (
    seed_campaign,
    seed_campaign_member,
    seed_item,
    seed_reference,
    seed_user,
)


def _minimal_class_kwargs(**overrides) -> dict:
    defaults = dict(
        name=f"Class-{uuid.uuid4().hex[:10]}",
        hit_die=8,
        primary_ability=["str"],
        saving_throw_proficiencies=["str"],
    )
    defaults.update(overrides)
    return defaults


async def _class_count(db_session, name: str) -> int:
    return (await db_session.execute(
        select(func.count()).select_from(ClassDefinition).where(ClassDefinition.name == name)
    )).scalar_one()


class TestClassCodes:
    async def test_create_with_srd_codes_echoes_the_codes(self, db_session):
        creator = await seed_user(db_session)
        data = ClassCreate(**_minimal_class_kwargs(
            name="Rogue",
            primary_ability=["dex"],
            saving_throw_proficiencies=["dex", "int"],
            armor_proficiencies=["light"],
            weapon_proficiencies=["simple", "martial"],
            tool_proficiencies=["thieves_tools"],
            skills=["stealth", "sleight_of_hand", "acrobatics"],
            spell_ability="cha",
        ))

        obj = await create_class(data, current_user=creator, db=db_session)
        out = ClassOut.model_validate(obj)

        assert out.primary_ability == ["dex"]
        assert sorted(out.saving_throw_proficiencies) == ["dex", "int"]
        assert out.armor_proficiencies == ["light"]
        assert sorted(out.weapon_proficiencies) == ["martial", "simple"]
        assert out.tool_proficiencies == ["thieves_tools"]
        assert out.spell_ability == "cha"
        skills = {s.code: s for s in out.skills}
        assert set(skills) == {"stealth", "sleight_of_hand", "acrobatics"}
        assert skills["stealth"].name == "Stealth"
        assert skills["stealth"].ability_code == "dex"
        assert out.skill_choices == 2  # unrelated field keeps its own meaning

    async def test_skill_pool_field_no_longer_part_of_the_schema(self):
        assert "skill_pool" not in ClassCreate.model_fields

    async def test_skills_are_plain_codes_not_inline_definitions(self):
        assert ClassCreate(**_minimal_class_kwargs(skills=["arcana"])).skills == ["arcana"]
        with pytest.raises(ValueError):
            ClassCreate(**_minimal_class_kwargs(skills=[{"name": "Arcana", "ability_score": "INT"}]))

    async def test_get_class_returns_codes(self, db_session):
        creator = await seed_user(db_session)
        data = ClassCreate(**_minimal_class_kwargs(skills=["arcana"]))
        obj = await create_class(data, current_user=creator, db=db_session)
        fetched = ClassOut.model_validate(await get_class(obj.id, db=db_session))
        assert fetched.primary_ability == ["str"]
        assert [s.code for s in fetched.skills] == ["arcana"]

    @pytest.mark.parametrize("field,value", [
        ("primary_ability", ["STR"]),
        ("primary_ability", ["luck"]),
        ("saving_throw_proficiencies", ["str", "nope"]),
        ("armor_proficiencies", ["Light"]),
        ("weapon_proficiencies", ["exotic"]),
        ("tool_proficiencies", ["lockpicks"]),
        ("skills", ["stealth", "psionics"]),
        ("spell_ability", "CHA"),
    ])
    async def test_unknown_code_is_400_and_writes_nothing(self, db_session, field, value):
        creator = await seed_user(db_session)
        await db_session.commit()
        name = f"Bad-{uuid.uuid4().hex[:8]}"
        data = ClassCreate(**_minimal_class_kwargs(name=name, **{field: value}))

        with pytest.raises(HTTPException) as exc_info:
            await create_class(data, current_user=creator, db=db_session)

        assert exc_info.value.status_code == 400
        assert await _class_count(db_session, name) == 0

    @pytest.mark.parametrize("model,field,extra", [
        (Skill, "skills", {"ability_code": "int"}),
        (Ability, "primary_ability", {}),
        (ArmorCategory, "armor_proficiencies", {}),
        (WeaponCategory, "weapon_proficiencies", {}),
        (ToolProficiencyOption, "tool_proficiencies", {}),
    ])
    async def test_invisible_homebrew_is_400_but_visible_homebrew_is_accepted(self, db_session, model, field, extra):
        author = await seed_user(db_session)
        outsider = await seed_user(db_session)
        entry = await seed_reference(db_session, model, author=author, **extra)
        await db_session.commit()
        code, author_id = entry.code, author.id

        name = f"Hidden-{uuid.uuid4().hex[:8]}"
        with pytest.raises(HTTPException) as exc_info:
            await create_class(
                ClassCreate(**_minimal_class_kwargs(name=name, **{field: [code]})), current_user=outsider, db=db_session
            )
        assert exc_info.value.status_code == 400
        assert await _class_count(db_session, name) == 0

        author = await db_session.get(type(author), author_id)
        obj = await create_class(
            ClassCreate(**_minimal_class_kwargs(**{field: [code]})), current_user=author, db=db_session
        )
        out = ClassOut.model_validate(obj)
        values = [s.code for s in out.skills] if field == "skills" else getattr(out, field)
        assert values == [code]

    async def test_homebrew_shared_with_my_campaign_is_accepted(self, db_session):
        author = await seed_user(db_session)
        player = await seed_user(db_session)
        campaign = await seed_campaign(db_session, creator=author)
        await seed_campaign_member(db_session, campaign, author, role="dm")
        await seed_campaign_member(db_session, campaign, player, role="player")
        skill = await seed_reference(db_session, Skill, author=author, ability_code="wis", campaigns=[campaign])

        obj = await create_class(
            ClassCreate(**_minimal_class_kwargs(skills=[skill.code])), current_user=player, db=db_session
        )
        assert [s.code for s in obj.skills] == [skill.code]


class TestClassSpellAbilityForeignKey:
    async def test_direct_insert_with_invalid_spell_ability_is_rejected_by_db(self, db_session):
        creator = await seed_user(db_session)
        with pytest.raises(IntegrityError):
            db_session.add(
                ClassDefinition(
                    id=uuid.uuid4(),
                    name=f"Invalid-{uuid.uuid4().hex[:10]}",
                    hit_die=8,
                    skill_choices=2,
                    subclass_level=3,
                    spell_ability="zzz",
                    is_homebrew=True,
                    created_by=creator.id,
                )
            )
            await db_session.flush()


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

    async def test_response_serializes_when_item_not_in_session(self, db_session):
        # Regression: in production the ItemDefinition is not held in the
        # session's identity map, so a lazy `item` load during response
        # serialization raised MissingGreenlet.
        creator = await seed_user(db_session)
        dagger = await seed_item(db_session, name="Dagger")
        dagger_id = dagger.id
        db_session.expunge(dagger)
        del dagger
        data = ClassCreate(
            **_minimal_class_kwargs(
                initial_equipment=[ClassInitialEquipmentCreate(item_id=dagger_id, option="A", quantity=2)],
            )
        )

        obj = await create_class(data, current_user=creator, db=db_session)
        out = ClassOut.model_validate(obj)
        assert out.initial_equipment[0].item_name == "Dagger"

        db_session.expunge_all()
        listed = await list_classes(db=db_session, search=data.name)
        assert ClassOut.model_validate(listed[0]).initial_equipment[0].item_name == "Dagger"

    async def test_referencing_missing_item_is_rejected(self, db_session):
        creator = await seed_user(db_session)
        await db_session.commit()
        data = ClassCreate(
            **_minimal_class_kwargs(
                initial_equipment=[ClassInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=1)]
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_class(data, current_user=creator, db=db_session)
        assert exc_info.value.status_code == 400
        assert await _class_count(db_session, data.name) == 0

    async def test_quantity_must_be_at_least_one(self):
        with pytest.raises(ValueError):
            ClassInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=0)
