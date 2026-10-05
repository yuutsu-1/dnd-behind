"""Schemas of /api/compendium/spells (app/schemas/spells.py)."""
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.spells import SpellCreate, SpellMaterialIn, SpellOut, SpellUpdate


def payload(**overrides) -> dict:
    data = dict(
        name="Homebrew Bolt", level=1, school_code="evocation", casting_time_code="action",
        range="60 feet", duration="Instantaneous", description="A bolt.", has_verbal=True,
    )
    data.update(overrides)
    return data


class TestSpellCreate:
    def test_minimal_payload_and_defaults(self):
        spell = SpellCreate(**payload())
        assert (spell.has_verbal, spell.has_somatic, spell.has_material) == (True, False, False)
        assert (spell.ritual, spell.concentration) == (False, False)
        assert spell.materials == [] and spell.spell_list_codes == []
        assert spell.area is None and spell.area_shape_code is None
        assert spell.higher_levels is None and spell.cantrip_upgrade is None

    def test_full_payload(self):
        spell = SpellCreate(**payload(
            has_material=True, ritual=True, concentration=True, area="10-foot-radius Sphere",
            area_shape_code="sphere", higher_levels="More.", spell_list_codes=["wizard", "sorcerer"],
            materials=[{"description": "a ruby", "cost_gp": "50.5", "consumed": True, "per_target": True,
                        "quantity": 2}],
        ))
        assert spell.materials[0].cost_gp == Decimal("50.5")
        assert spell.materials[0].quantity == 2

    @pytest.mark.parametrize("level", [-1, 10])
    def test_level_out_of_range(self, level):
        with pytest.raises(ValidationError):
            SpellCreate(**payload(level=level))

    @pytest.mark.parametrize("field", ["name", "range", "duration", "description"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_required_text_cannot_be_blank(self, field, value):
        with pytest.raises(ValidationError):
            SpellCreate(**payload(**{field: value}))

    @pytest.mark.parametrize("field", ["area", "higher_levels", "cantrip_upgrade"])
    def test_optional_text_cannot_be_blank(self, field):
        with pytest.raises(ValidationError):
            SpellCreate(**payload(**{field: " "}))

    @pytest.mark.parametrize("field", ["name", "range", "duration", "description", "school_code", "casting_time_code"])
    def test_required_fields(self, field):
        data = payload()
        del data[field]
        with pytest.raises(ValidationError):
            SpellCreate(**data)

    def test_duplicate_spell_list_codes(self):
        with pytest.raises(ValidationError, match="duplicates"):
            SpellCreate(**payload(spell_list_codes=["wizard", "wizard"]))

    @pytest.mark.parametrize("field", ["school_code", "casting_time_code", "area_shape_code"])
    def test_codes_must_have_code_shape(self, field):
        with pytest.raises(ValidationError):
            SpellCreate(**payload(**{field: "Not A Code"}))

    @pytest.mark.parametrize("field", ["id", "source", "is_homebrew", "created_by", "components", "casting_trigger"])
    def test_forbidden_or_unknown_fields(self, field):
        with pytest.raises(ValidationError):
            SpellCreate(**payload(**{field: str(uuid.uuid4())}))


class TestSpellMaterialIn:
    def test_defaults(self):
        material = SpellMaterialIn(description="ash")
        assert (material.cost_gp, material.consumed, material.per_target, material.quantity) == (None, False, False, 1)

    @pytest.mark.parametrize("quantity", [0, -1])
    def test_quantity_below_one(self, quantity):
        with pytest.raises(ValidationError):
            SpellMaterialIn(description="ash", quantity=quantity)

    def test_negative_cost(self):
        with pytest.raises(ValidationError):
            SpellMaterialIn(description="ash", cost_gp="-0.01")

    def test_cost_with_more_than_four_decimals(self):
        with pytest.raises(ValidationError):
            SpellMaterialIn(description="ash", cost_gp="0.00001")

    def test_blank_description(self):
        with pytest.raises(ValidationError):
            SpellMaterialIn(description=" ")

    def test_unknown_field(self):
        with pytest.raises(ValidationError):
            SpellMaterialIn(description="ash", sort_order=3)


class TestSpellUpdate:
    def test_everything_is_optional(self):
        assert SpellUpdate().model_fields_set == set()

    @pytest.mark.parametrize("field", ["area", "area_shape_code", "higher_levels", "cantrip_upgrade"])
    def test_nullable_columns_accept_null(self, field):
        assert getattr(SpellUpdate(**{field: None}), field) is None

    @pytest.mark.parametrize("field", [
        "name", "level", "school_code", "has_verbal", "has_somatic", "has_material", "casting_time_code", "ritual",
        "concentration", "range", "duration", "description", "materials", "spell_list_codes",
    ])
    def test_non_nullable_columns_reject_null(self, field):
        with pytest.raises(ValidationError, match="cannot be null"):
            SpellUpdate(**{field: None})

    @pytest.mark.parametrize("field", ["id", "source", "is_homebrew", "created_by"])
    def test_forbidden_fields(self, field):
        with pytest.raises(ValidationError):
            SpellUpdate(**{field: "x"})

    def test_same_rules_as_create(self):
        with pytest.raises(ValidationError):
            SpellUpdate(level=10)
        with pytest.raises(ValidationError):
            SpellUpdate(spell_list_codes=["bard", "bard"])
        with pytest.raises(ValidationError):
            SpellUpdate(materials=[{"description": "ash", "quantity": 0}])


class TestSpellOut:
    def _spell(self, **overrides):
        material = SimpleNamespace(
            description="1 Copper Piece", cost_gp=Decimal("0.0100"), consumed=False, per_target=False, quantity=1,
        )
        data = dict(
            id=uuid.uuid4(), name="Detect Test", level=2, school_code="divination", school_name="Divination",
            has_verbal=True, has_somatic=True, has_material=True, casting_time_code="action",
            casting_time_name="Action", ritual=False, concentration=True, range="Self",
            duration="Concentration, up to 1 minute", area=None, area_shape_code=None, area_shape_name=None,
            description="Read minds.", higher_levels=None, cantrip_upgrade=None, materials=[material],
            spell_lists=[SimpleNamespace(code="wizard", name="Wizard"), SimpleNamespace(code="bard", name="Bard")],
            source="srd", is_homebrew=False, created_by=uuid.uuid4(),
        )
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_cost_is_a_json_number(self):
        body = SpellOut.model_validate(self._spell()).model_dump(mode="json")
        assert body["materials"][0]["cost_gp"] == 0.01

    def test_lists_are_sorted_by_code_and_created_by_is_hidden(self):
        body = SpellOut.model_validate(self._spell()).model_dump(mode="json")
        assert body["spell_lists"] == [{"code": "bard", "name": "Bard"}, {"code": "wizard", "name": "Wizard"}]
        assert "created_by" not in body

    def test_reference_names(self):
        body = SpellOut.model_validate(self._spell()).model_dump(mode="json")
        assert (body["school_code"], body["school_name"]) == ("divination", "Divination")
        assert (body["casting_time_code"], body["casting_time_name"]) == ("action", "Action")
        assert (body["area_shape_code"], body["area_shape_name"]) == (None, None)
