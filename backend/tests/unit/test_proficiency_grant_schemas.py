"""Schemas of proficiency grants: the write-side descriptor (classes/backgrounds send
descriptors; the server reuses or creates the grant) and the read-side output."""
import uuid

import pytest
from pydantic import BaseModel, ValidationError

from app.db.models.compendium import ProficiencyGrant
from app.db.models.reference import Skill, WeaponCategory, WeaponProperty
from app.schemas.proficiency_grants import (
    GrantDescriptors,
    ProficiencyGrantDescriptor,
    ProficiencyGrantOut,
)

TARGET_FIELDS = [
    "weapon_category_code", "armor_category_code", "tool_type_code", "tool_category_code",
    "skill_code", "saving_throw_ability_code", "language_code",
]


class TestDescriptor:
    @pytest.mark.parametrize("field,kind", [
        ("weapon_category_code", "weapon_category"),
        ("armor_category_code", "armor_category"),
        ("tool_type_code", "tool"),
        ("tool_category_code", "tool_category"),
        ("skill_code", "skill"),
        ("saving_throw_ability_code", "saving_throw"),
        ("language_code", "language"),
    ])
    def test_single_target_is_valid_and_has_a_kind(self, field, kind):
        descriptor = ProficiencyGrantDescriptor(**{field: "some_code"})
        assert descriptor.kind == kind

    def test_weapon_category_with_required_property(self):
        descriptor = ProficiencyGrantDescriptor(weapon_category_code="martial", required_weapon_property_code="light")
        assert descriptor.kind == "weapon_category"
        assert descriptor.required_weapon_property_code == "light"

    def test_no_target_is_rejected(self):
        with pytest.raises(ValidationError):
            ProficiencyGrantDescriptor()

    def test_only_required_property_is_rejected(self):
        with pytest.raises(ValidationError):
            ProficiencyGrantDescriptor(required_weapon_property_code="light")

    @pytest.mark.parametrize("first,second", [
        ("weapon_category_code", "armor_category_code"),
        ("skill_code", "tool_type_code"),
        ("tool_category_code", "tool_type_code"),
        ("saving_throw_ability_code", "language_code"),
    ])
    def test_more_than_one_target_is_rejected(self, first, second):
        with pytest.raises(ValidationError):
            ProficiencyGrantDescriptor(**{first: "a", second: "b"})

    def test_required_property_needs_weapon_category(self):
        with pytest.raises(ValidationError):
            ProficiencyGrantDescriptor(armor_category_code="light", required_weapon_property_code="light")

    @pytest.mark.parametrize("field,value", [
        ("weapon_item_id", str(uuid.uuid4())), ("kind", "skill"), ("id", str(uuid.uuid4())),
        ("target_name", "Stealth"),
    ])
    def test_extra_fields_are_forbidden(self, field, value):
        with pytest.raises(ValidationError):
            ProficiencyGrantDescriptor(skill_code="stealth", **{field: value})

    def test_codes_must_look_like_codes(self):
        with pytest.raises(ValidationError):
            ProficiencyGrantDescriptor(skill_code="Stealth")


class _Owner(BaseModel):
    proficiency_grants: GrantDescriptors


class TestDescriptorList:
    def test_duplicates_are_rejected(self):
        with pytest.raises(ValidationError):
            _Owner(proficiency_grants=[{"skill_code": "stealth"}, {"skill_code": "stealth"}])

    def test_same_category_with_and_without_property_are_different(self):
        owner = _Owner(proficiency_grants=[
            {"weapon_category_code": "martial"},
            {"weapon_category_code": "martial", "required_weapon_property_code": "light"},
            {"weapon_category_code": "martial", "required_weapon_property_code": "finesse"},
        ])
        assert len(owner.proficiency_grants) == 3

    def test_empty_list_is_valid(self):
        assert _Owner(proficiency_grants=[]).proficiency_grants == []


class TestOut:
    def test_from_orm_with_required_property(self):
        grant = ProficiencyGrant(
            id=uuid.uuid4(), weapon_category_code="martial", required_weapon_property_code="light",
            weapon_category=WeaponCategory(code="martial", name="Martial"),
            required_weapon_property=WeaponProperty(code="light", name="Light"),
        )
        out = ProficiencyGrantOut.model_validate(grant)
        assert out.kind == "weapon_category"
        assert out.target_name == "Martial"
        assert out.required_weapon_property_name == "Light"
        assert out.weapon_category_code == "martial"
        assert out.skill_code is None

    def test_fields(self):
        assert set(ProficiencyGrantOut.model_fields) == {
            "id", "kind", "target_name", "required_weapon_property_code", "required_weapon_property_name",
            *TARGET_FIELDS,
        }

    def test_skill_grant(self):
        grant = ProficiencyGrant(
            id=uuid.uuid4(), skill_code="stealth", skill=Skill(code="stealth", name="Stealth", ability_code="dex"),
        )
        out = ProficiencyGrantOut.model_validate(grant).model_dump()
        assert out["kind"] == "skill"
        assert out["target_name"] == "Stealth"
        assert out["required_weapon_property_name"] is None
