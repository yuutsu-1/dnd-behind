import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.compendium import create_background, get_background, update_background
from app.db.models.compendium import (
    BackgroundInitialEquipment,
    ProficiencyGrant,
    background_ability_scores,
    background_proficiency_grants,
)
from app.db.models.compendium import BackgroundDefinition
from app.db.models.reference import Skill
from app.schemas.compendium import (
    BackgroundCreate,
    BackgroundInitialEquipmentCreate,
    BackgroundOut,
    BackgroundUpdate,
)
from tests.integration.conftest import (
    seed_background,
    seed_background_initial_equipment,
    seed_feat,
    seed_item,
    seed_reference,
    seed_user,
)


def _grants(skills=("history", "persuasion"), tools=({"tool_category_code": "gaming_set"},)) -> list[dict]:
    return [{"skill_code": code} for code in skills] + list(tools)


async def _grant_count(db_session) -> int:
    return await db_session.scalar(select(func.count()).select_from(ProficiencyGrant))


def _tool_grants(out: BackgroundOut) -> list[tuple[str, str]]:
    return sorted(
        (g.kind, g.tool_type_code or g.tool_category_code)
        for g in out.proficiency_grants if g.kind in ("tool", "tool_category")
    )


def _noble_kwargs(feat_id: uuid.UUID, item_ids: list[uuid.UUID], **overrides) -> dict:
    defaults = dict(
        name=f"Noble-{uuid.uuid4().hex[:10]}",
        description="Born to a family of wealth and influence.",
        ability_scores=["str", "int", "cha"],
        feat_id=feat_id,
        proficiency_grants=_grants(),
        initial_equipment=[
            BackgroundInitialEquipmentCreate(item_id=item_ids[0], option="A", quantity=1),
            BackgroundInitialEquipmentCreate(item_id=item_ids[1], option="A", quantity=1),
            BackgroundInitialEquipmentCreate(item_id=item_ids[2], option="B", quantity=1),
        ],
    )
    defaults.update(overrides)
    return defaults


class TestCreateBackgroundNobleCase:
    async def test_full_noble_payload_echoes_all_five_mechanical_components(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session, name="Skilled", category_code="origin")
        fine_clothes = await seed_item(db_session, name="Fine Clothes")
        signet_ring = await seed_item(db_session, name="Signet Ring")
        purse = await seed_item(db_session, name="Purse")

        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )

        obj = await create_background(data, current_user=creator, db=db_session)

        out = BackgroundOut.model_validate(obj)
        assert set(out.ability_scores) == {"str", "int", "cha"}
        assert obj.feat_id == feat.id
        assert obj.feat_name == "Skilled"
        assert [(s.code, s.ability_code) for s in out.skills] == [("history", "int"), ("persuasion", "cha")]
        assert _tool_grants(out) == [("tool_category", "gaming_set")]
        assert len(obj.initial_equipment) == 3
        assert {e.item_name for e in obj.initial_equipment} == {"Fine Clothes", "Signet Ring", "Purse"}


    async def test_tool_choice_is_a_single_tool_category_grant(self, db_session):
        # Phase 2: "choose one" is expressed by a `tool_category` grant; several tool
        # grants are all fixed (the old "several tools = choose one" rule is gone).
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        items = [await seed_item(db_session) for _ in range(3)]

        choice = BackgroundCreate(**_noble_kwargs(
            feat.id, [i.id for i in items], proficiency_grants=_grants(tools=[{"tool_category_code": "musical_instrument"}]),
        ))
        out = BackgroundOut.model_validate(await create_background(choice, current_user=creator, db=db_session))
        assert _tool_grants(out) == [("tool_category", "musical_instrument")]

        fixed = BackgroundCreate(**_noble_kwargs(
            feat.id, [i.id for i in items],
            proficiency_grants=_grants(tools=[{"tool_type_code": "herbalism_kit"}, {"tool_type_code": "thieves_tools"}]),
        ))
        out = BackgroundOut.model_validate(await create_background(fixed, current_user=creator, db=db_session))
        assert _tool_grants(out) == [("tool", "herbalism_kit"), ("tool", "thieves_tools")]

    async def test_response_serializes_when_items_not_in_session(self, db_session):
        # Regression: lazy `item` load during response serialization raised
        # MissingGreenlet when the ItemDefinition was not in the identity map.
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        items = [await seed_item(db_session, name=f"Item {n}") for n in range(3)]
        item_ids = [i.id for i in items]
        for i in items:
            db_session.expunge(i)
        del items, i

        data = BackgroundCreate(**_noble_kwargs(feat.id, item_ids))
        obj = await create_background(data, current_user=creator, db=db_session)
        out = BackgroundOut.model_validate(obj)
        assert {e.item_name for e in out.initial_equipment} == {"Item 0", "Item 1", "Item 2"}

        db_session.expunge_all()
        fetched = await get_background(obj.id, db=db_session)
        assert {e.item_name for e in BackgroundOut.model_validate(fetched).initial_equipment} == {"Item 0", "Item 1", "Item 2"}


class TestCreateBackgroundValidation:
    async def test_ability_scores_cardinality_rejected_by_schema(self):
        with pytest.raises(ValueError):
            BackgroundCreate(
                name="Bad",
                ability_scores=["str", "int"],
                feat_id=uuid.uuid4(),
                proficiency_grants=_grants(),
            )

    async def test_skills_duplicate_rejected_by_schema(self):
        with pytest.raises(ValueError):
            BackgroundCreate(
                name="Bad",
                ability_scores=["str", "int", "cha"],
                feat_id=uuid.uuid4(),
                proficiency_grants=_grants(skills=["history", "history"]),
            )

    async def test_nonexistent_feat_id_is_rejected_with_400(self, db_session):
        creator = await seed_user(db_session)
        fine_clothes = await seed_item(db_session)
        signet_ring = await seed_item(db_session)
        purse = await seed_item(db_session)

        data = BackgroundCreate(
            **_noble_kwargs(uuid.uuid4(), [fine_clothes.id, signet_ring.id, purse.id])
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_background(data, current_user=creator, db=db_session)
        assert exc_info.value.status_code == 400

    async def test_nonexistent_item_id_in_initial_equipment_is_rejected_with_400(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)

        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()])
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_background(data, current_user=creator, db=db_session)
        assert exc_info.value.status_code == 400

    async def test_initial_equipment_quantity_must_be_at_least_one(self):
        with pytest.raises(ValueError):
            BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=0)


class TestBackgroundCascadeDelete:
    async def test_deleting_background_cascades_to_related_rows(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        fine_clothes = await seed_item(db_session)
        signet_ring = await seed_item(db_session)
        purse = await seed_item(db_session)
        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )
        background = await create_background(data, current_user=creator, db=db_session)
        background_id = background.id

        await db_session.delete(background)
        await db_session.flush()

        equipment_result = await db_session.execute(
            select(BackgroundInitialEquipment).where(BackgroundInitialEquipment.background_id == background_id)
        )
        assert equipment_result.scalar_one_or_none() is None

        ability_link_result = await db_session.execute(
            select(background_ability_scores).where(background_ability_scores.c.background_id == background_id)
        )
        assert ability_link_result.first() is None

        grant_ids = [g.id for g in background.proficiency_grants]
        grant_link_result = await db_session.execute(
            select(background_proficiency_grants).where(background_proficiency_grants.c.background_id == background_id)
        )
        assert grant_link_result.first() is None
        # The grants themselves are shared and never deleted with an owner.
        remaining = await db_session.scalar(
            select(func.count()).select_from(ProficiencyGrant).where(ProficiencyGrant.id.in_(grant_ids))
        )
        assert remaining == 3


class TestSeedBackgroundInitialEquipmentHelper:
    async def test_helper_creates_row_linked_to_background_and_item(self, db_session):
        feat = await seed_feat(db_session)
        item = await seed_item(db_session, name="Traveler's Clothes")
        background = await seed_background(db_session, feat_id=feat.id)

        entry = await seed_background_initial_equipment(db_session, background, item, option="A", quantity=2)

        assert entry.background_id == background.id
        assert entry.item_id == item.id
        assert entry.item_name == "Traveler's Clothes"
        assert entry.quantity == 2


class TestGetBackground:
    async def test_returns_background_by_id(self, db_session):
        feat = await seed_feat(db_session)
        background = await seed_background(db_session, name="Sage", feat_id=feat.id)

        obj = await get_background(background.id, db=db_session)

        assert obj.id == background.id
        assert obj.name == "Sage"

    async def test_missing_background_raises_404(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            await get_background(uuid.uuid4(), db=db_session)
        assert exc_info.value.status_code == 404


class TestUpdateBackground:
    async def test_partial_update_replaces_the_grants(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        fine_clothes = await seed_item(db_session)
        signet_ring = await seed_item(db_session)
        purse = await seed_item(db_session)
        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )
        obj = await create_background(data, current_user=creator, db=db_session)

        old_grant_ids = {g.id for g in obj.proficiency_grants}
        updated = await update_background(
            obj.id,
            BackgroundUpdate(proficiency_grants=_grants(
                skills=["insight", "persuasion"], tools=[{"tool_category_code": "musical_instrument"}],
            )),
            current_user=creator, db=db_session,
        )

        out = BackgroundOut.model_validate(updated)
        assert _tool_grants(out) == [("tool_category", "musical_instrument")]
        assert [s.code for s in out.skills] == ["insight", "persuasion"]
        # Old grants left the background but stay in the database.
        assert await db_session.scalar(
            select(func.count()).select_from(ProficiencyGrant).where(ProficiencyGrant.id.in_(old_grant_ids))
        ) == 3
        # Unrelated fields untouched.
        assert {a.code for a in updated.ability_scores} == {"str", "int", "cha"}

    async def test_partial_update_of_ability_scores(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        fine_clothes = await seed_item(db_session)
        signet_ring = await seed_item(db_session)
        purse = await seed_item(db_session)
        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )
        obj = await create_background(data, current_user=creator, db=db_session)

        updated = await update_background(
            obj.id,
            BackgroundUpdate(ability_scores=["dex", "wis", "con"]),
            current_user=creator,
            db=db_session,
        )

        assert {a.code for a in updated.ability_scores} == {"dex", "wis", "con"}

    async def test_missing_background_raises_404(self, db_session):
        creator = await seed_user(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await update_background(
                uuid.uuid4(), BackgroundUpdate(name="New name"), current_user=creator, db=db_session
            )
        assert exc_info.value.status_code == 404

    async def test_nonexistent_feat_id_on_update_is_rejected_with_400(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        fine_clothes = await seed_item(db_session)
        signet_ring = await seed_item(db_session)
        purse = await seed_item(db_session)
        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )
        obj = await create_background(data, current_user=creator, db=db_session)

        with pytest.raises(HTTPException) as exc_info:
            await update_background(
                obj.id, BackgroundUpdate(feat_id=uuid.uuid4()), current_user=creator, db=db_session
            )
        assert exc_info.value.status_code == 400

    async def test_nonexistent_item_id_in_initial_equipment_on_update_is_rejected_with_400(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        fine_clothes = await seed_item(db_session)
        signet_ring = await seed_item(db_session)
        purse = await seed_item(db_session)
        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )
        obj = await create_background(data, current_user=creator, db=db_session)

        with pytest.raises(HTTPException) as exc_info:
            await update_background(
                obj.id,
                BackgroundUpdate(
                    initial_equipment=[
                        BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=1)
                    ]
                ),
                current_user=creator,
                db=db_session,
            )
        assert exc_info.value.status_code == 400

    async def test_full_replacement_of_initial_equipment_reflects_exactly_the_new_list(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        fine_clothes = await seed_item(db_session, name="Fine Clothes")
        signet_ring = await seed_item(db_session, name="Signet Ring")
        purse = await seed_item(db_session, name="Purse")
        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )
        obj = await create_background(data, current_user=creator, db=db_session)
        assert len(obj.initial_equipment) == 3

        dagger = await seed_item(db_session, name="Dagger")
        pouch = await seed_item(db_session, name="Pouch")

        updated = await update_background(
            obj.id,
            BackgroundUpdate(
                initial_equipment=[
                    BackgroundInitialEquipmentCreate(item_id=dagger.id, option="A", quantity=2),
                    BackgroundInitialEquipmentCreate(item_id=pouch.id, option="B", quantity=5),
                ]
            ),
            current_user=creator,
            db=db_session,
        )

        assert len(updated.initial_equipment) == 2
        by_item_id = {e.item_id: e for e in updated.initial_equipment}
        assert set(by_item_id.keys()) == {dagger.id, pouch.id}
        assert by_item_id[dagger.id].quantity == 2
        assert by_item_id[dagger.id].option == "A"
        assert by_item_id[pouch.id].quantity == 5
        assert by_item_id[pouch.id].option == "B"
        # The original three items must be gone, not merged.
        assert fine_clothes.id not in by_item_id
        assert signet_ring.id not in by_item_id
        assert purse.id not in by_item_id


async def _background_count(db_session, name: str) -> int:
    from sqlalchemy import func
    return (await db_session.execute(
        select(func.count()).select_from(BackgroundDefinition).where(BackgroundDefinition.name == name)
    )).scalar_one()


class TestBackgroundCodes:
    @pytest.mark.parametrize("field,value", [
        ("ability_scores", ["STR", "int", "cha"]),
        ("ability_scores", ["str", "int", "luck"]),
        ("proficiency_grants", _grants(skills=["history", "psionics"])),
        ("proficiency_grants", _grants(tools=[{"tool_type_code": "lockpicks"}])),
        ("proficiency_grants", _grants(tools=[{"tool_category_code": "dice_set"}])),
    ])
    async def test_create_with_unknown_code_is_400_and_writes_nothing(self, db_session, field, value):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        items = [await seed_item(db_session) for _ in range(3)]
        await db_session.commit()
        data = BackgroundCreate(**_noble_kwargs(feat.id, [i.id for i in items], **{field: value}))
        grants_before = await _grant_count(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await create_background(data, current_user=creator, db=db_session)

        assert exc_info.value.status_code == 400
        assert await _background_count(db_session, data.name) == 0
        assert await _grant_count(db_session) == grants_before

    async def test_invisible_homebrew_skill_is_400(self, db_session):
        author = await seed_user(db_session)
        outsider = await seed_user(db_session)
        hidden = await seed_reference(db_session, Skill, author=author, ability_code="int")
        feat = await seed_feat(db_session)
        items = [await seed_item(db_session) for _ in range(3)]
        data = BackgroundCreate(**_noble_kwargs(
            feat.id, [i.id for i in items], proficiency_grants=_grants(skills=["history", hidden.code]),
        ))
        await db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await create_background(data, current_user=outsider, db=db_session)
        assert exc_info.value.status_code == 400

    async def test_own_homebrew_skill_is_accepted(self, db_session):
        author = await seed_user(db_session)
        mine = await seed_reference(db_session, Skill, author=author, ability_code="int")
        feat = await seed_feat(db_session)
        items = [await seed_item(db_session) for _ in range(3)]
        data = BackgroundCreate(**_noble_kwargs(
            feat.id, [i.id for i in items], proficiency_grants=_grants(skills=["history", mine.code]),
        ))

        obj = await create_background(data, current_user=author, db=db_session)
        assert {s.code for s in obj.skills} == {"history", mine.code}

    @pytest.mark.parametrize("update", [
        BackgroundUpdate(ability_scores=["dex", "wis", "luck"]),
        BackgroundUpdate(proficiency_grants=_grants(skills=["history", "psionics"])),
        BackgroundUpdate(proficiency_grants=_grants(tools=[{"tool_type_code": "dice"}])),
        BackgroundUpdate(name="Renamed", proficiency_grants=_grants(skills=["nope", "history"])),
    ])
    async def test_update_with_unknown_code_is_400_and_changes_nothing(self, db_session, update):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        items = [await seed_item(db_session) for _ in range(3)]
        obj = await create_background(
            BackgroundCreate(**_noble_kwargs(feat.id, [i.id for i in items])), current_user=creator, db=db_session
        )
        background_id, original_name = obj.id, obj.name

        with pytest.raises(HTTPException) as exc_info:
            await update_background(background_id, update, current_user=creator, db=db_session)
        assert exc_info.value.status_code == 400

        fetched = BackgroundOut.model_validate(await get_background(background_id, db=db_session))
        assert fetched.name == original_name
        assert set(fetched.ability_scores) == {"str", "int", "cha"}
        assert {s.code for s in fetched.skills} == {"history", "persuasion"}
        assert _tool_grants(fetched) == [("tool_category", "gaming_set")]

    async def test_update_with_valid_codes(self, db_session):
        creator = await seed_user(db_session)
        feat = await seed_feat(db_session)
        items = [await seed_item(db_session) for _ in range(3)]
        obj = await create_background(
            BackgroundCreate(**_noble_kwargs(feat.id, [i.id for i in items])), current_user=creator, db=db_session
        )
        updated = await update_background(
            obj.id, BackgroundUpdate(proficiency_grants=_grants(skills=["insight", "religion"])),
            current_user=creator, db=db_session,
        )
        assert {s.code for s in BackgroundOut.model_validate(updated).skills} == {"insight", "religion"}
