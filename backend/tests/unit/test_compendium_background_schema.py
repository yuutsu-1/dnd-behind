import uuid

import pytest
from pydantic import ValidationError

from app.db.models.compendium import (
    AbilityScoreOption,
    BackgroundDefinition,
    BackgroundInitialEquipment,
    FeatDefinition,
    ItemDefinition,
    SkillDefinition,
)
from app.enums import AbilityScore
from app.schemas.compendium import (
    BackgroundCreate,
    BackgroundInitialEquipmentCreate,
    BackgroundOut,
    BackgroundUpdate,
    SkillCreate,
)


def _noble_kwargs(**overrides) -> dict:
    defaults = dict(
        name="Noble",
        ability_scores=[AbilityScore.STR, AbilityScore.INT, AbilityScore.CHA],
        feat_id=uuid.uuid4(),
        skills=[
            SkillCreate(name="History", ability_score=AbilityScore.INT),
            SkillCreate(name="Persuasion", ability_score=AbilityScore.CHA),
        ],
        tool_proficiency="Gaming Set",
        initial_equipment=[
            BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=1),
            BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=1),
            BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="B", quantity=1),
        ],
    )
    defaults.update(overrides)
    return defaults


class TestBackgroundCreateNobleCase:
    def test_full_noble_payload_validates(self):
        data = BackgroundCreate(**_noble_kwargs())
        assert len(data.ability_scores) == 3
        assert len(data.skills) == 2
        assert len(data.initial_equipment) == 3


class TestBackgroundCreateAbilityScoresCardinality:
    def test_two_ability_scores_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(ability_scores=[AbilityScore.STR, AbilityScore.INT]))

    def test_four_ability_scores_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(
                **_noble_kwargs(
                    ability_scores=[AbilityScore.STR, AbilityScore.INT, AbilityScore.CHA, AbilityScore.DEX]
                )
            )

    def test_duplicate_ability_score_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(
                **_noble_kwargs(ability_scores=[AbilityScore.STR, AbilityScore.STR, AbilityScore.CHA])
            )


class TestBackgroundCreateSkillsCardinality:
    def test_one_skill_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(
                **_noble_kwargs(skills=[SkillCreate(name="History", ability_score=AbilityScore.INT)])
            )

    def test_three_skills_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(
                **_noble_kwargs(
                    skills=[
                        SkillCreate(name="History", ability_score=AbilityScore.INT),
                        SkillCreate(name="Persuasion", ability_score=AbilityScore.CHA),
                        SkillCreate(name="Insight", ability_score=AbilityScore.WIS),
                    ]
                )
            )

    def test_duplicate_skill_name_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(
                **_noble_kwargs(
                    skills=[
                        SkillCreate(name="History", ability_score=AbilityScore.INT),
                        SkillCreate(name="History", ability_score=AbilityScore.INT),
                    ]
                )
            )


class TestBackgroundInitialEquipmentCreateQuantity:
    def test_quantity_must_be_at_least_one(self):
        with pytest.raises(ValidationError):
            BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=0)


class TestBackgroundUpdatePartial:
    def test_no_fields_provided_is_valid(self):
        data = BackgroundUpdate()
        assert data.ability_scores is None
        assert data.skills is None

    def test_partial_ability_scores_with_wrong_cardinality_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundUpdate(ability_scores=[AbilityScore.STR, AbilityScore.INT])

    def test_partial_skills_with_duplicate_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundUpdate(
                skills=[
                    SkillCreate(name="History", ability_score=AbilityScore.INT),
                    SkillCreate(name="History", ability_score=AbilityScore.INT),
                ]
            )

    def test_only_name_provided_is_valid(self):
        data = BackgroundUpdate(name="Renamed Noble")
        assert data.name == "Renamed Noble"
        assert data.tool_proficiency is None


class TestBackgroundOutSerialization:
    def test_populated_from_relationships(self):
        feat = FeatDefinition(id=uuid.uuid4(), name="Skilled", category="origin")
        item = ItemDefinition(id=uuid.uuid4(), name="Signet Ring", item_type="gear")
        background_id = uuid.uuid4()
        equipment_entry = BackgroundInitialEquipment(
            id=uuid.uuid4(), background_id=background_id, item_id=item.id, item=item, option="A", quantity=1
        )
        background = BackgroundDefinition(
            id=background_id,
            name="Noble",
            feat_id=feat.id,
            feat=feat,
            tool_proficiency="Gaming Set",
            ability_scores=[AbilityScoreOption(name="STR"), AbilityScoreOption(name="INT")],
            skills=[SkillDefinition(id=uuid.uuid4(), name="History", ability_score="INT")],
            initial_equipment=[equipment_entry],
            source="srd",
            is_homebrew=False,
        )

        out = BackgroundOut.model_validate(background, from_attributes=True)

        assert {a.value for a in out.ability_scores} == {"STR", "INT"}
        assert out.feat_id == feat.id
        assert out.feat_name == "Skilled"
        assert {s.name for s in out.skills} == {"History"}
        assert out.tool_proficiency == "Gaming Set"
        assert out.initial_equipment[0].item_name == "Signet Ring"
