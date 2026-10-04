"""Species `size_code` (FK to `sizes`, default "medium").

NOTE: `POST /species` is still broken by the missing `creature_type` (phase 5, out of
scope). The size validation runs before the insert, so the 400 path is exercised end
to end through the handler; acceptance of a valid size is checked at the validation
and FK level without depending on the broken insert."""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.compendium import create_species, validate_species_size
from app.db.models.compendium import SpeciesDefinition
from app.db.models.reference import Size
from app.schemas.compendium import SpeciesCreate, SpeciesOut
from tests.integration.conftest import seed_reference, seed_species, seed_user


async def _species_count(db_session, name: str) -> int:
    return (await db_session.execute(
        select(func.count()).select_from(SpeciesDefinition).where(SpeciesDefinition.name == name)
    )).scalar_one()


class TestSpeciesSchema:
    def test_size_code_defaults_to_medium(self):
        assert SpeciesCreate(name="Elf").size_code == "medium"
        assert "size" not in SpeciesCreate.model_fields

    def test_out_exposes_size_code(self):
        assert "size_code" in SpeciesOut.model_fields
        assert "size" not in SpeciesOut.model_fields


class TestSpeciesSizeValidation:
    async def test_unknown_size_is_400_and_writes_nothing(self, db_session):
        user = await seed_user(db_session)
        await db_session.commit()
        name = f"Species-{uuid.uuid4().hex[:8]}"

        with pytest.raises(HTTPException) as exc_info:
            await create_species(SpeciesCreate(name=name, size_code="colossal"), current_user=user, db=db_session)

        assert exc_info.value.status_code == 400
        assert await _species_count(db_session, name) == 0

    async def test_invisible_homebrew_size_is_400(self, db_session):
        author = await seed_user(db_session)
        outsider = await seed_user(db_session)
        await seed_reference(db_session, Size, author=author, code="colossal", hit_die=30,
                             carry_multiplier=240, sort_order=7)
        with pytest.raises(HTTPException) as exc_info:
            await validate_species_size(db_session, "colossal", outsider)
        assert exc_info.value.status_code == 400
        await validate_species_size(db_session, "colossal", author)

    async def test_srd_size_is_accepted(self, db_session):
        user = await seed_user(db_session)
        await validate_species_size(db_session, "huge", user)

    async def test_huge_is_persisted(self, db_session):
        species = await seed_species(db_session, size_code="huge")
        stored = (await db_session.execute(
            select(SpeciesDefinition.size_code).where(SpeciesDefinition.id == species.id)
        )).scalar_one()
        assert stored == "huge"
        assert SpeciesOut.model_validate(species).size_code == "huge"

    async def test_default_size_code_is_medium_in_db(self, db_session):
        species = SpeciesDefinition(name=f"Species-{uuid.uuid4().hex[:8]}", creature_type="humanoid",
                                    base_speed=30, special_traits=[], source="srd", is_homebrew=False)
        db_session.add(species)
        await db_session.flush()
        assert species.size_code == "medium"

    async def test_db_rejects_unknown_size(self, db_session):
        with pytest.raises(IntegrityError):
            await seed_species(db_session, size_code="colossal")
