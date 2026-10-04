import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.characters import campaign_characters, get_character, my_characters
from app.db.models.character import CharacterSkill
from app.schemas.character import CharacterOut, CharacterWithInventory
from tests.integration.conftest import (
    seed_campaign,
    seed_campaign_member,
    seed_character,
    seed_character_skill,
    seed_skill,
    seed_user,
)


# --------------------------------------------------------------------------
# Step 1: model
# --------------------------------------------------------------------------
class TestCharacterSkillModel:
    async def test_persists_row_with_defaults(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session, name="Stealth", ability_code="dex")

        row = CharacterSkill(character_id=character.id, skill_code=skill.code, source="other")
        db_session.add(row)
        await db_session.flush()

        assert isinstance(row.id, uuid.UUID)
        assert row.expertise is False

    async def test_duplicate_character_skill_raises_integrity_error(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await seed_character_skill(db_session, character, skill)

        db_session.add(CharacterSkill(character_id=character.id, skill_code=skill.code, source="feat"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_deleting_character_removes_its_skill_rows(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await seed_character_skill(db_session, character, skill)
        character_id = character.id

        await db_session.delete(character)
        await db_session.flush()

        result = await db_session.execute(select(CharacterSkill).where(CharacterSkill.character_id == character_id))
        assert result.scalars().all() == []

    async def test_derived_name_and_ability_score_properties(self, db_session):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session, name="Athletics", ability_code="str")
        row = await seed_character_skill(db_session, character, skill)
        await db_session.refresh(row, attribute_names=["skill"])

        assert row.skill_name == "Athletics"
        assert row.ability_code == "str"


# --------------------------------------------------------------------------
# Step 3: schemas
# --------------------------------------------------------------------------
class TestSkillSchemas:
    def test_invalid_source_rejected(self):
        from pydantic import ValidationError

        from app.schemas.character import CharacterSkillCreate

        with pytest.raises(ValidationError):
            CharacterSkillCreate(skill_code="no_such_skill", source="homebrew")

    @pytest.mark.parametrize("source", ["class", "background", "species", "feat", "other"])
    def test_valid_sources_accepted(self, source):
        from app.schemas.character import CharacterSkillCreate

        assert CharacterSkillCreate(skill_code="no_such_skill", source=source).source == source

    async def test_character_out_serializes_skills(self, db_session):
        from app.services.character import get_character_or_404

        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session, name="Arcana", ability_code="int")
        await seed_character_skill(db_session, character, skill, source="class")
        character_id = character.id
        db_session.expire_all()

        fetched = await get_character_or_404(db_session, character_id)
        out = CharacterOut.model_validate(fetched, from_attributes=True)

        assert len(out.skills) == 1
        entry = out.skills[0]
        assert entry.skill_code == skill.code
        assert entry.skill_name == "Arcana"
        assert entry.ability_code == "int"
        assert entry.source == "class"
        assert entry.expertise is False

    def test_character_create_accepts_skills_and_initial_class(self):
        from app.schemas.character import CharacterCreate, CharacterSkillCreate

        data = CharacterCreate(
            name="X",
            initial_class={"class_id": uuid.uuid4(), "level": 1},
            skills=[CharacterSkillCreate(skill_code="no_such_skill", source="other")],
        )
        assert data.initial_class.level == 1
        assert len(data.skills) == 1

    def test_character_create_defaults_have_no_skills_or_class(self):
        from app.schemas.character import CharacterCreate

        data = CharacterCreate(name="X")
        assert data.skills == []
        assert data.initial_class is None

    def test_character_update_accepts_background_id(self):
        from app.schemas.character import CharacterUpdate

        bg = uuid.uuid4()
        assert CharacterUpdate(background_id=bg).background_id == bg


# --------------------------------------------------------------------------
# Step 4: eager loading on every read endpoint
# --------------------------------------------------------------------------
class TestReadEndpointsIncludeSkills:
    async def _setup(self, db_session):
        owner = await seed_user(db_session)
        campaign = await seed_campaign(db_session, owner)
        await seed_campaign_member(db_session, campaign, owner, role="dm")
        character = await seed_character(db_session, owner=owner, campaign_id=campaign.id)
        skill = await seed_skill(db_session, name="Insight", ability_code="wis")
        await seed_character_skill(db_session, character, skill, source="species")
        character_id = character.id
        db_session.expire_all()
        await db_session.refresh(owner)
        await db_session.refresh(campaign)
        return owner, campaign, character_id

    async def test_get_character(self, db_session):
        owner, _, character_id = await self._setup(db_session)
        result = await get_character(character_id, current_user=owner, db=db_session)
        out = CharacterWithInventory.model_validate(result, from_attributes=True)
        assert [s.skill_name for s in out.skills] == ["Insight"]

    async def test_my_characters(self, db_session):
        owner, _, _ = await self._setup(db_session)
        result = await my_characters(current_user=owner, db=db_session)
        out = [CharacterOut.model_validate(c, from_attributes=True) for c in result]
        assert [s.skill_name for s in out[0].skills] == ["Insight"]

    async def test_campaign_characters(self, db_session):
        owner, campaign, _ = await self._setup(db_session)
        result = await campaign_characters(campaign.id, current_user=owner, db=db_session)
        out = [CharacterWithInventory.model_validate(c, from_attributes=True) for c in result]
        assert [s.skill_name for s in out[0].skills] == ["Insight"]

    async def test_create_character_returns_empty_skills_without_lazy_load(self, db_session):
        from app.api.characters import create_character
        from app.schemas.character import CharacterCreate

        owner = await seed_user(db_session)
        character = await create_character(CharacterCreate(name="Fresh"), current_user=owner, db=db_session)
        out = CharacterOut.model_validate(character, from_attributes=True)
        assert out.skills == []

    async def test_update_character_returns_skills_without_lazy_load(self, db_session, no_redis):
        from app.api.characters import update_character
        from app.schemas.character import CharacterUpdate

        owner, _, character_id = await self._setup(db_session)
        updated = await update_character(character_id, CharacterUpdate(name="New"), current_user=owner, db=db_session)
        out = CharacterOut.model_validate(updated, from_attributes=True)
        assert [s.skill_name for s in out.skills] == ["Insight"]


class TestSkillCodeRoutes:
    def test_skill_routes_use_skill_code(self):
        from app.main import app

        paths = {(route.path, method) for route in app.routes for method in getattr(route, "methods", ())}
        assert ("/api/characters/{character_id}/skills/{skill_code}", "DELETE") in paths
        assert ("/api/characters/{character_id}/skills/{skill_code}", "PATCH") in paths

    async def test_invisible_homebrew_skill_is_400(self, db_session, no_redis):
        from fastapi import HTTPException

        from app.api.characters import add_character_skill
        from app.db.models.reference import Skill
        from app.schemas.character import CharacterSkillCreate
        from tests.integration.conftest import seed_reference

        author, owner = await seed_user(db_session), await seed_user(db_session)
        hidden = await seed_reference(db_session, Skill, author=author, ability_code="int")
        character = await seed_character(db_session, owner=owner)
        await db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await add_character_skill(
                character.id, CharacterSkillCreate(skill_code=hidden.code, source="other"),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400

    async def test_skill_out_shape(self, db_session):
        from app.schemas.character import CharacterSkillOut

        assert set(CharacterSkillOut.model_fields) == {"skill_code", "skill_name", "ability_code", "source", "expertise"}
