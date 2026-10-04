"""Pydantic schemas of the reference resources: every 422 case of the phase 1 spec."""
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import reference as s


class TestCommonCreate:
    def test_valid_payload(self):
        data = s.ReferenceCreate(code="psionic", name="Psionic", description="Mind stuff")
        assert data.code == "psionic"
        assert data.campaign_ids is None

    @pytest.mark.parametrize("code", [
        "Psionic", "psi-onic", "psi onic", "_psionic", "psionic_", "psi__onic", "", "ção", "a" * 51,
    ])
    def test_invalid_code_is_rejected(self, code):
        with pytest.raises(ValidationError):
            s.ReferenceCreate(code=code, name="Psionic")

    @pytest.mark.parametrize("code", ["psionic", "1_4", "0", "thieves_cant", "a" * 50])
    def test_valid_codes(self, code):
        assert s.ReferenceCreate(code=code, name="X").code == code

    @pytest.mark.parametrize("name", ["", "   "])
    def test_empty_name_is_rejected(self, name):
        with pytest.raises(ValidationError):
            s.ReferenceCreate(code="psionic", name=name)

    def test_name_is_required(self):
        with pytest.raises(ValidationError):
            s.ReferenceCreate(code="psionic")

    @pytest.mark.parametrize("field,value", [
        ("source", "srd"), ("is_homebrew", False), ("created_by", str(uuid.uuid4())), ("unknown", 1),
    ])
    def test_forbidden_extra_fields(self, field, value):
        with pytest.raises(ValidationError):
            s.ReferenceCreate(code="psionic", name="Psionic", **{field: value})

    def test_duplicate_campaign_ids_are_rejected(self):
        cid = uuid.uuid4()
        with pytest.raises(ValidationError):
            s.ReferenceCreate(code="psionic", name="Psionic", campaign_ids=[cid, cid])

    def test_campaign_ids_accepted(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        assert s.ReferenceCreate(code="psionic", name="Psionic", campaign_ids=ids).campaign_ids == ids


class TestCommonUpdate:
    def test_all_optional(self):
        assert s.ReferenceUpdate().model_fields_set == set()

    @pytest.mark.parametrize("field,value", [
        ("code", "other"), ("source", "srd"), ("is_homebrew", True), ("created_by", str(uuid.uuid4())),
    ])
    def test_forbidden_fields(self, field, value):
        with pytest.raises(ValidationError):
            s.ReferenceUpdate(**{field: value})

    @pytest.mark.parametrize("name", ["", "  ", None])
    def test_name_cannot_be_emptied(self, name):
        with pytest.raises(ValidationError):
            s.ReferenceUpdate(name=name)

    def test_only_payload_fields_are_exposed(self):
        assert set(s.ReferenceUpdate.model_fields) == {"name", "description", "campaign_ids"}
        with pytest.raises(ValidationError):
            s.ReferenceUpdate(nullable_fields=["name"], name=None)

    def test_description_can_be_cleared(self):
        assert s.ReferenceUpdate(description=None).description is None

    def test_duplicate_campaign_ids_are_rejected(self):
        cid = uuid.uuid4()
        with pytest.raises(ValidationError):
            s.ReferenceUpdate(campaign_ids=[cid, cid])

    def test_empty_campaign_ids_allowed(self):
        assert s.ReferenceUpdate(campaign_ids=[]).campaign_ids == []


class TestSizes:
    def test_valid(self):
        data = s.SizeCreate(code="colossal", name="Colossal", hit_die=30, carry_multiplier=Decimal("240"), sort_order=7)
        assert data.hit_die == 30

    @pytest.mark.parametrize("field,value", [("hit_die", 0), ("hit_die", -4), ("carry_multiplier", 0), ("carry_multiplier", -1)])
    def test_non_positive_values_are_rejected(self, field, value):
        payload = dict(code="colossal", name="Colossal", hit_die=30, carry_multiplier=240, sort_order=7)
        payload[field] = value
        with pytest.raises(ValidationError):
            s.SizeCreate(**payload)

    @pytest.mark.parametrize("field", ["hit_die", "carry_multiplier", "sort_order"])
    def test_game_columns_required_on_create(self, field):
        payload = dict(code="colossal", name="Colossal", hit_die=30, carry_multiplier=240, sort_order=7)
        payload.pop(field)
        with pytest.raises(ValidationError):
            s.SizeCreate(**payload)

    @pytest.mark.parametrize("field,value", [("hit_die", 0), ("carry_multiplier", 0), ("sort_order", None)])
    def test_update_validation(self, field, value):
        with pytest.raises(ValidationError):
            s.SizeUpdate(**{field: value})


class TestLanguages:
    def test_rarity_required(self):
        with pytest.raises(ValidationError):
            s.LanguageCreate(code="aquan", name="Aquan")

    def test_unknown_rarity(self):
        with pytest.raises(ValidationError):
            s.LanguageCreate(code="aquan", name="Aquan", rarity="exotic")
        with pytest.raises(ValidationError):
            s.LanguageUpdate(rarity="exotic")

    def test_valid(self):
        assert s.LanguageCreate(code="aquan", name="Aquan", rarity="rare").rarity == "rare"


class TestChallengeRatings:
    def test_negative_proficiency_bonus(self):
        with pytest.raises(ValidationError):
            s.ChallengeRatingCreate(code="31", name="31", numeric_value=31, proficiency_bonus=-1)
        with pytest.raises(ValidationError):
            s.ChallengeRatingUpdate(proficiency_bonus=-1)

    def test_valid(self):
        data = s.ChallengeRatingCreate(code="1_16", name="1/16", numeric_value=Decimal("0.0625"), proficiency_bonus=2)
        assert data.numeric_value == Decimal("0.0625")


class TestCharacterLevels:
    def test_valid(self):
        data = s.CharacterLevelCreate(level=21, min_xp=400000, proficiency_bonus=7)
        assert data.level == 21

    @pytest.mark.parametrize("field,value", [("level", 0), ("min_xp", -1), ("proficiency_bonus", -1)])
    def test_bounds(self, field, value):
        payload = dict(level=21, min_xp=400000, proficiency_bonus=7)
        payload[field] = value
        with pytest.raises(ValidationError):
            s.CharacterLevelCreate(**payload)

    @pytest.mark.parametrize("field", ["code", "name", "description", "source"])
    def test_no_code_name_description(self, field):
        with pytest.raises(ValidationError):
            s.CharacterLevelCreate(level=21, min_xp=400000, proficiency_bonus=7, **{field: "x"})

    def test_update_cannot_change_level(self):
        with pytest.raises(ValidationError):
            s.CharacterLevelUpdate(level=22)

    def test_update_bounds(self):
        with pytest.raises(ValidationError):
            s.CharacterLevelUpdate(min_xp=-1)


class TestPointBuyCosts:
    def test_negative_cost(self):
        with pytest.raises(ValidationError):
            s.PointBuyCostCreate(score=16, cost=-1)
        with pytest.raises(ValidationError):
            s.PointBuyCostUpdate(cost=-1)

    def test_update_cannot_change_score(self):
        with pytest.raises(ValidationError):
            s.PointBuyCostUpdate(score=16)

    def test_valid(self):
        assert s.PointBuyCostCreate(score=16, cost=12).cost == 12


class TestSkills:
    def test_ability_code_required_on_create(self):
        with pytest.raises(ValidationError):
            s.SkillCreate(code="psionics", name="Psionics")

    def test_ability_code_must_look_like_a_code(self):
        with pytest.raises(ValidationError):
            s.SkillCreate(code="psionics", name="Psionics", ability_code="INT")

    def test_valid(self):
        assert s.SkillCreate(code="psionics", name="Psionics", ability_code="int").ability_code == "int"

    def test_update_ability_code_cannot_be_null(self):
        with pytest.raises(ValidationError):
            s.SkillUpdate(ability_code=None)


class TestConditions:
    def test_implies_defaults_to_empty(self):
        assert s.ConditionCreate(code="dazed", name="Dazed").implies == []

    def test_implies_cannot_include_itself(self):
        with pytest.raises(ValidationError):
            s.ConditionCreate(code="dazed", name="Dazed", implies=["incapacitated", "dazed"])

    def test_implies_rejects_duplicates_and_bad_codes(self):
        with pytest.raises(ValidationError):
            s.ConditionCreate(code="dazed", name="Dazed", implies=["prone", "prone"])
        with pytest.raises(ValidationError):
            s.ConditionCreate(code="dazed", name="Dazed", implies=["Prone"])

    def test_update_implies(self):
        assert s.ConditionUpdate(implies=["prone"]).implies == ["prone"]
        with pytest.raises(ValidationError):
            s.ConditionUpdate(implies=None)

    def test_implies_only_on_conditions(self):
        with pytest.raises(ValidationError):
            s.ReferenceCreate(code="psionic", name="Psionic", implies=["prone"])


class TestOut:
    @pytest.mark.parametrize("out", [
        s.ReferenceOut, s.SkillOut, s.ConditionOut, s.SizeOut, s.LanguageOut,
        s.ChallengeRatingOut, s.CharacterLevelOut, s.PointBuyCostOut,
    ])
    def test_out_never_exposes_created_by(self, out):
        assert "created_by" not in out.model_fields
        assert {"source", "is_homebrew", "campaign_ids"} <= set(out.model_fields)

    def test_numeric_columns_serialize_as_numbers(self):
        out = s.SizeOut(
            code="tiny", name="Tiny", description=None, source="srd", is_homebrew=False,
            hit_die=4, carry_multiplier=Decimal("7.5"), sort_order=1, campaign_ids=None,
        )
        assert out.model_dump(mode="json")["carry_multiplier"] == 7.5
        cr = s.ChallengeRatingOut(
            code="1_4", name="1/4", description=None, source="srd", is_homebrew=False,
            numeric_value=Decimal("0.25"), proficiency_bonus=2, campaign_ids=None,
        )
        assert cr.model_dump(mode="json")["numeric_value"] == 0.25

    def test_condition_out_has_implies(self):
        assert "implies" in s.ConditionOut.model_fields
