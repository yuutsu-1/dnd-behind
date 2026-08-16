import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.compendium import create_background, get_background, update_background
from app.db.models.compendium import (
    BackgroundInitialEquipment,
    background_ability_scores,
    background_skills,
)
from app.enums import AbilityScore
from app.schemas.compendium import (
    BackgroundCreate,
    BackgroundInitialEquipmentCreate,
    BackgroundUpdate,
    SkillCreate,
)
from tests.integration.conftest import (
    seed_background,
    seed_background_initial_equipment,
    seed_feat,
    seed_item,
    seed_user,
)


def _noble_kwargs(feat_id: uuid.UUID, item_ids: list[uuid.UUID], **overrides) -> dict:
    defaults = dict(
        name=f"Noble-{uuid.uuid4().hex[:10]}",
        description="Born to a family of wealth and influence.",
        ability_scores=[AbilityScore.STR, AbilityScore.INT, AbilityScore.CHA],
        feat_id=feat_id,
        skills=[
            SkillCreate(name="History", ability_score=AbilityScore.INT),
            SkillCreate(name="Persuasion", ability_score=AbilityScore.CHA),
        ],
        tool_proficiency="Gaming Set",
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
        feat = await seed_feat(db_session, name="Skilled", category="origin")
        fine_clothes = await seed_item(db_session, name="Fine Clothes")
        signet_ring = await seed_item(db_session, name="Signet Ring")
        purse = await seed_item(db_session, name="Purse")

        data = BackgroundCreate(
            **_noble_kwargs(feat.id, [fine_clothes.id, signet_ring.id, purse.id])
        )

        obj = await create_background(data, current_user=creator, db=db_session)

        assert {a.name for a in obj.ability_scores} == {"STR", "INT", "CHA"}
        assert obj.feat_id == feat.id
        assert obj.feat_name == "Skilled"
        assert {s.name for s in obj.skills} == {"History", "Persuasion"}
        assert obj.tool_proficiency == "Gaming Set"
        assert len(obj.initial_equipment) == 3
        assert {e.item_name for e in obj.initial_equipment} == {"Fine Clothes", "Signet Ring", "Purse"}


class TestCreateBackgroundValidation:
    async def test_ability_scores_cardinality_rejected_by_schema(self):
        with pytest.raises(ValueError):
            BackgroundCreate(
                name="Bad",
                ability_scores=[AbilityScore.STR, AbilityScore.INT],
                feat_id=uuid.uuid4(),
                skills=[
                    SkillCreate(name="History", ability_score=AbilityScore.INT),
                    SkillCreate(name="Persuasion", ability_score=AbilityScore.CHA),
                ],
                tool_proficiency="Gaming Set",
            )

    async def test_skills_duplicate_rejected_by_schema(self):
        with pytest.raises(ValueError):
            BackgroundCreate(
                name="Bad",
                ability_scores=[AbilityScore.STR, AbilityScore.INT, AbilityScore.CHA],
                feat_id=uuid.uuid4(),
                skills=[
                    SkillCreate(name="History", ability_score=AbilityScore.INT),
                    SkillCreate(name="History", ability_score=AbilityScore.INT),
                ],
                tool_proficiency="Gaming Set",
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

        skill_link_result = await db_session.execute(
            select(background_skills).where(background_skills.c.background_id == background_id)
        )
        assert skill_link_result.first() is None


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
    async def test_partial_update_of_tool_proficiency(self, db_session):
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
            obj.id, BackgroundUpdate(tool_proficiency="Musical Instrument"), current_user=creator, db=db_session
        )

        assert updated.tool_proficiency == "Musical Instrument"
        # Unrelated fields untouched.
        assert {a.name for a in updated.ability_scores} == {"STR", "INT", "CHA"}

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
            BackgroundUpdate(ability_scores=[AbilityScore.DEX, AbilityScore.WIS, AbilityScore.CON]),
            current_user=creator,
            db=db_session,
        )

        assert {a.name for a in updated.ability_scores} == {"DEX", "WIS", "CON"}

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
