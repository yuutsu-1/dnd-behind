import uuid

import pytest
from pydantic import ValidationError

from app.db.models.compendium import (
    BackgroundDefinition,
    BackgroundInitialEquipment,
    FeatDefinition,
    ItemDefinition,
    ProficiencyGrant,
)
from app.db.models.reference import Ability, Skill, ToolCategory
from app.schemas.compendium import (
    BackgroundCreate,
    BackgroundInitialEquipmentCreate,
    BackgroundOut,
    BackgroundUpdate,
)


def _grants(skills=("history", "persuasion"), tools=({"tool_category_code": "gaming_set"},)) -> list[dict]:
    return [{"skill_code": code} for code in skills] + list(tools)


def _noble_kwargs(**overrides) -> dict:
    defaults = dict(
        name="Noble",
        ability_scores=["str", "int", "cha"],
        feat_id=uuid.uuid4(),
        proficiency_grants=_grants(),
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
        assert [g.kind for g in data.proficiency_grants] == ["skill", "skill", "tool_category"]
        assert len(data.initial_equipment) == 3

    def test_old_proficiency_fields_are_gone(self):
        for model in (BackgroundCreate, BackgroundUpdate):
            assert "skills" not in model.model_fields
            assert "tool_proficiencies" not in model.model_fields
            assert "proficiency_grants" in model.model_fields


class TestBackgroundCreateAbilityScoresCardinality:
    def test_two_ability_scores_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(ability_scores=["str", "int"]))

    def test_four_ability_scores_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(ability_scores=["str", "int", "cha", "dex"]))

    def test_duplicate_ability_score_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(ability_scores=["str", "str", "cha"]))


class TestBackgroundCreateSkillGrants:
    def test_one_skill_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants(skills=["history"])))

    def test_three_skills_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants(skills=["history", "persuasion", "insight"])))

    def test_duplicate_skill_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants(skills=["history", "history"])))

    def test_inline_skill_definitions_are_not_descriptors(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(proficiency_grants=[
                {"name": "History", "ability_score": "INT"}, {"skill_code": "persuasion"},
                {"tool_category_code": "gaming_set"},
            ]))


class TestBackgroundCreateToolGrants:
    def test_fixed_tool_is_accepted(self):
        data = BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants(tools=[{"tool_type_code": "thieves_tools"}])))
        assert data.proficiency_grants[-1].kind == "tool"

    def test_several_tool_grants_are_all_accepted(self):
        tools = [{"tool_type_code": "thieves_tools"}, {"tool_category_code": "musical_instrument"}]
        data = BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants(tools=tools)))
        assert [g.kind for g in data.proficiency_grants] == ["skill", "skill", "tool", "tool_category"]

    def test_no_tool_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants(tools=[])))

    def test_duplicate_tool_rejected(self):
        tools = [{"tool_category_code": "gaming_set"}, {"tool_category_code": "gaming_set"}]
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants(tools=tools)))

    @pytest.mark.parametrize("other", [
        {"armor_category_code": "light"},
        {"weapon_category_code": "simple"},
        {"saving_throw_ability_code": "str"},
        {"language_code": "elvish"},
    ])
    def test_other_kinds_rejected(self, other):
        with pytest.raises(ValidationError):
            BackgroundCreate(**_noble_kwargs(proficiency_grants=_grants() + [other]))

    def test_missing_field_rejected(self):
        kwargs = _noble_kwargs()
        del kwargs["proficiency_grants"]
        with pytest.raises(ValidationError):
            BackgroundCreate(**kwargs)


class TestBackgroundInitialEquipmentCreateQuantity:
    def test_quantity_must_be_at_least_one(self):
        with pytest.raises(ValidationError):
            BackgroundInitialEquipmentCreate(item_id=uuid.uuid4(), option="A", quantity=0)


class TestBackgroundUpdatePartial:
    def test_no_fields_provided_is_valid(self):
        data = BackgroundUpdate()
        assert data.ability_scores is None
        assert data.proficiency_grants is None

    def test_partial_ability_scores_with_wrong_cardinality_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundUpdate(ability_scores=["str", "int"])

    def test_grants_follow_the_same_rules(self):
        with pytest.raises(ValidationError):
            BackgroundUpdate(proficiency_grants=_grants(skills=["history", "history"]))
        with pytest.raises(ValidationError):
            BackgroundUpdate(proficiency_grants=_grants(tools=[]))
        with pytest.raises(ValidationError):
            BackgroundUpdate(proficiency_grants=_grants() + [{"armor_category_code": "light"}])

    def test_empty_grants_rejected(self):
        with pytest.raises(ValidationError):
            BackgroundUpdate(proficiency_grants=[])

    def test_valid_grants(self):
        assert len(BackgroundUpdate(proficiency_grants=_grants()).proficiency_grants) == 3

    def test_only_name_provided_is_valid(self):
        data = BackgroundUpdate(name="Renamed Noble")
        assert data.name == "Renamed Noble"
        assert data.proficiency_grants is None


class TestBackgroundOutSerialization:
    def test_populated_from_relationships(self):
        feat = FeatDefinition(id=uuid.uuid4(), name="Skilled", category="origin")
        item = ItemDefinition(id=uuid.uuid4(), name="Signet Ring", item_type_code="adventuring_gear")
        background_id = uuid.uuid4()
        equipment_entry = BackgroundInitialEquipment(
            id=uuid.uuid4(), background_id=background_id, item_id=item.id, item=item, option="A", quantity=1
        )
        persuasion = Skill(code="persuasion", name="Persuasion", ability_code="cha")
        history = Skill(code="history", name="History", ability_code="int")
        background = BackgroundDefinition(
            id=background_id,
            name="Noble",
            feat_id=feat.id,
            feat=feat,
            proficiency_grants=[
                ProficiencyGrant(id=uuid.uuid4(), skill_code="persuasion", skill=persuasion),
                ProficiencyGrant(id=uuid.uuid4(), tool_category_code="gaming_set",
                                 tool_category=ToolCategory(code="gaming_set", name="Gaming Set")),
                ProficiencyGrant(id=uuid.uuid4(), skill_code="history", skill=history),
            ],
            ability_scores=[Ability(code="str", name="Strength"), Ability(code="int", name="Intelligence")],
            initial_equipment=[equipment_entry],
            source="srd",
            is_homebrew=False,
        )

        out = BackgroundOut.model_validate(background, from_attributes=True)

        assert set(out.ability_scores) == {"str", "int"}
        assert out.feat_id == feat.id
        assert out.feat_name == "Skilled"
        # Derived from the `skill` grants, sorted by name.
        assert [(s.code, s.name, s.ability_code) for s in out.skills] == [
            ("history", "History", "int"), ("persuasion", "Persuasion", "cha"),
        ]
        assert [(g.kind, g.target_name) for g in out.proficiency_grants] == [
            ("skill", "Persuasion"), ("tool_category", "Gaming Set"), ("skill", "History"),
        ]
        assert "tool_proficiencies" not in BackgroundOut.model_fields
        assert out.initial_equipment[0].item_name == "Signet Ring"
