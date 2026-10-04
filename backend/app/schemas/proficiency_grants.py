"""Proficiency grants: descriptors (write side) and output (read side).

Clients never create grants directly. Classes and backgrounds send descriptors such as
`{"weapon_category_code": "martial", "required_weapon_property_code": "light"}`; the
server reuses the grant with that exact target or creates it
(app/services/proficiency_grants.py)."""
import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.db.models.compendium import GRANT_KEY_COLUMNS, GRANT_TARGETS
from app.schemas.reference import Code, _Write


class ProficiencyGrantDescriptor(_Write):
    """Exactly one target; `required_weapon_property_code` only narrows a
    `weapon_category_code` (it is not a target of its own)."""

    weapon_category_code: Code | None = None
    required_weapon_property_code: Code | None = None
    armor_category_code: Code | None = None
    tool_type_code: Code | None = None
    tool_category_code: Code | None = None
    skill_code: Code | None = None
    saving_throw_ability_code: Code | None = None
    language_code: Code | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self):
        filled = [kind for kind, (column, _) in GRANT_TARGETS.items() if getattr(self, column) is not None]
        if len(filled) != 1:
            raise ValueError("a proficiency grant needs exactly one target")
        if self.required_weapon_property_code is not None and self.weapon_category_code is None:
            raise ValueError("required_weapon_property_code is only allowed with weapon_category_code")
        return self

    @property
    def kind(self) -> str:
        return next(kind for kind, (column, _) in GRANT_TARGETS.items() if getattr(self, column) is not None)

    @property
    def key(self) -> tuple[str | None, ...]:
        """The values of every identifying column (same key = same grant)."""
        return tuple(getattr(self, column) for column in GRANT_KEY_COLUMNS)


def _no_duplicate_descriptors(descriptors: list[ProficiencyGrantDescriptor]) -> list[ProficiencyGrantDescriptor]:
    keys = [descriptor.key for descriptor in descriptors]
    if len(set(keys)) != len(keys):
        raise ValueError("proficiency_grants must not contain duplicates")
    return descriptors


GrantDescriptors = Annotated[list[ProficiencyGrantDescriptor], AfterValidator(_no_duplicate_descriptors)]


class ProficiencyGrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # weapon_category | armor_category | tool | tool_category | skill | saving_throw | language
    kind: str
    weapon_category_code: str | None
    required_weapon_property_code: str | None
    armor_category_code: str | None
    tool_type_code: str | None
    tool_category_code: str | None
    skill_code: str | None
    saving_throw_ability_code: str | None
    language_code: str | None
    target_name: str | None
    # Only set when the grant requires a weapon property (e.g. Martial with Light).
    required_weapon_property_name: str | None
