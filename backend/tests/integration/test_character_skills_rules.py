"""Steps 5-8: skill CRUD rules, automatic background skills, transactional batch on create."""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.characters import (
    add_character_skill,
    create_character,
    remove_character_skill,
    update_character,
    update_character_skill_expertise,
)
from app.db.models.character import Character, CharacterClass, CharacterSkill
from app.schemas.character import (
    CharacterCreate,
    CharacterOut,
    CharacterSkillCreate,
    CharacterSkillExpertiseUpdate,
    CharacterSkillOut,
    CharacterUpdate,
)
from tests.integration.conftest import (
    seed_background,
    seed_background_skill,
    seed_campaign,
    seed_campaign_member,
    seed_character,
    seed_character_class,
    seed_character_skill,
    seed_class,
    seed_class_skill,
    seed_skill,
    seed_user,
)


async def _reset(db_session, *_ignored):
    """Release the seeding savepoint, drop stale identity-map state (collections seeded
    as empty) and re-load every tracked object so they stay usable (ids, `current_user`)."""
    await db_session.commit()
    db_session.expire_all()
    for obj in list(db_session.identity_map.values()):
        await db_session.refresh(obj)


async def _skills_of(db_session, character_id):
    result = await db_session.execute(select(CharacterSkill).where(CharacterSkill.character_id == character_id))
    return {row.skill_code: row for row in result.scalars().all()}


def _add(character_id, skill, source, user, db):
    return add_character_skill(
        character_id, CharacterSkillCreate(skill_code=skill.code, source=source), current_user=user, db=db
    )


# --------------------------------------------------------------------------
# Step 5 + 8: POST /characters/{id}/skills
# --------------------------------------------------------------------------
class TestAddSkill:
    async def test_other_source_returns_entry_with_name_ability_source_expertise(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session, name="Stealth", ability_code="dex")
        await _reset(db_session, owner)

        entry = await _add(character.id, skill, "other", owner, db_session)
        out = CharacterSkillOut.model_validate(entry, from_attributes=True)

        assert (out.skill_code, out.skill_name, out.ability_code, out.source, out.expertise) == (
            skill.code, "Stealth", "dex", "other", False
        )
        assert skill.code in await _skills_of(db_session, character.id)

    async def test_nonexistent_skill_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await add_character_skill(
                character.id, CharacterSkillCreate(skill_code="no_such_skill", source="other"),
                current_user=owner, db=db_session,
            )
        # Unknown (or invisible) codes are a 400, like every code reference.
        assert exc.value.status_code == 400

    async def test_nonexistent_character_404(self, db_session, no_redis):
        owner = await seed_user(db_session)
        skill = await seed_skill(db_session)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _add(uuid.uuid4(), skill, "other", owner, db_session)
        assert exc.value.status_code == 404

    async def test_duplicate_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await seed_character_skill(db_session, character, skill, source="feat")
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _add(character.id, skill, "other", owner, db_session)
        assert exc.value.status_code == 400

    @pytest.mark.parametrize("source", ["species", "feat", "other"])
    async def test_free_sources_only_validate_existence(self, db_session, no_redis, source):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await _reset(db_session, owner)

        entry = await _add(character.id, skill, source, owner, db_session)
        assert entry.source == source

    # --- source == "class" ---
    async def test_class_source_without_class_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _add(character.id, skill, "class", owner, db_session)
        assert exc.value.status_code == 400

    async def test_class_source_in_pool_ok(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session, skill_choices=2)
        skill = await seed_skill(db_session)
        await seed_class_skill(db_session, klass, skill)
        await seed_character_class(db_session, character, klass)
        await _reset(db_session, owner)

        entry = await _add(character.id, skill, "class", owner, db_session)
        assert entry.source == "class"

    async def test_class_source_outside_pool_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session)
        in_pool, outside = await seed_skill(db_session), await seed_skill(db_session)
        await seed_class_skill(db_session, klass, in_pool)
        await seed_character_class(db_session, character, klass)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _add(character.id, outside, "class", owner, db_session)
        assert exc.value.status_code == 400

    async def test_class_source_exceeding_skill_choices_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        klass = await seed_class(db_session, skill_choices=2)
        s1, s2, s3 = [await seed_skill(db_session) for _ in range(3)]
        await seed_class_skill(db_session, klass, s1, s2, s3)
        await seed_character_class(db_session, character, klass)
        await _reset(db_session, owner)

        await _add(character.id, s1, "class", owner, db_session)
        await _add(character.id, s2, "class", owner, db_session)
        with pytest.raises(HTTPException) as exc:
            await _add(character.id, s3, "class", owner, db_session)
        assert exc.value.status_code == 400

    async def test_only_first_class_grants_class_skills(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        first, second = await seed_class(db_session), await seed_class(db_session)
        only_second = await seed_skill(db_session)
        await seed_class_skill(db_session, second, only_second)
        await seed_character_class(db_session, character, first)
        await seed_character_class(db_session, character, second)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _add(character.id, only_second, "class", owner, db_session)
        assert exc.value.status_code == 400

    # --- source == "background" ---
    async def test_background_source_belonging_to_current_background_ok(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        skill = await seed_skill(db_session)
        await seed_background_skill(db_session, bg, skill)
        character = await seed_character(db_session, owner=owner, background_id=bg.id)
        await _reset(db_session, owner)

        entry = await _add(character.id, skill, "background", owner, db_session)
        assert entry.source == "background"

    async def test_background_source_not_in_background_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        skill = await seed_skill(db_session)
        character = await seed_character(db_session, owner=owner, background_id=bg.id)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _add(character.id, skill, "background", owner, db_session)
        assert exc.value.status_code == 400

    async def test_background_source_without_background_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _add(character.id, skill, "background", owner, db_session)
        assert exc.value.status_code == 400

    # --- permissions + broadcast ---
    async def test_stranger_gets_403(self, db_session, no_redis):
        owner, stranger = await seed_user(db_session), await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await _reset(db_session, stranger)

        with pytest.raises(HTTPException) as exc:
            await _add(character.id, skill, "other", stranger, db_session)
        assert exc.value.status_code == 403
        assert await _skills_of(db_session, character.id) == {}

    async def test_campaign_dm_allowed_and_event_broadcast(self, db_session, no_redis):
        owner, dm = await seed_user(db_session), await seed_user(db_session)
        campaign = await seed_campaign(db_session, dm)
        await seed_campaign_member(db_session, campaign, dm, role="dm")
        character = await seed_character(db_session, owner=owner, campaign_id=campaign.id)
        skill = await seed_skill(db_session)
        await _reset(db_session, dm)

        await _add(character.id, skill, "other", dm, db_session)

        assert len(no_redis) == 1
        channel, msg = no_redis[0]
        assert channel == f"campaign:{campaign.id}"
        assert msg["event"] == "character.skill.add"
        assert msg["character_id"] == str(character.id)
        assert msg["payload"]["skill_code"] == str(skill.code)
        assert msg["actor_id"] == str(dm.id)


# --------------------------------------------------------------------------
# Step 8: DELETE /characters/{id}/skills/{skill_code}
# --------------------------------------------------------------------------
class TestRemoveSkill:
    async def test_removes_row_and_broadcasts(self, db_session, no_redis):
        owner = await seed_user(db_session)
        campaign = await seed_campaign(db_session, owner)
        character = await seed_character(db_session, owner=owner, campaign_id=campaign.id)
        skill = await seed_skill(db_session)
        await seed_character_skill(db_session, character, skill)
        await _reset(db_session, owner)

        result = await remove_character_skill(character.id, skill.code, current_user=owner, db=db_session)

        assert result is None
        assert await _skills_of(db_session, character.id) == {}
        assert [m["event"] for _, m in no_redis] == ["character.skill.remove"]
        assert no_redis[0][1]["payload"]["skill_code"] == str(skill.code)

    async def test_skill_not_on_character_404(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await remove_character_skill(character.id, skill.code, current_user=owner, db=db_session)
        assert exc.value.status_code == 404

    async def test_stranger_gets_403(self, db_session, no_redis):
        owner, stranger = await seed_user(db_session), await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await seed_character_skill(db_session, character, skill)
        await _reset(db_session, stranger)

        with pytest.raises(HTTPException) as exc:
            await remove_character_skill(character.id, skill.code, current_user=stranger, db=db_session)
        assert exc.value.status_code == 403
        assert skill.code in await _skills_of(db_session, character.id)


# --------------------------------------------------------------------------
# PATCH /characters/{id}/skills/{skill_code} (expertise; no class restriction, no limit)
# --------------------------------------------------------------------------
def _patch(character_id, skill, value, user, db):
    return update_character_skill_expertise(
        character_id, skill.code, CharacterSkillExpertiseUpdate(expertise=value), current_user=user, db=db
    )


class TestSkillExpertise:
    async def test_mark_and_unmark_expertise(self, db_session, no_redis):
        owner = await seed_user(db_session)
        campaign = await seed_campaign(db_session, owner)
        character = await seed_character(db_session, owner=owner, campaign_id=campaign.id)
        skill = await seed_skill(db_session, name="Stealth", ability_code="dex")
        await seed_character_skill(db_session, character, skill, source="class")
        await _reset(db_session, owner)

        out = CharacterSkillOut.model_validate(
            await _patch(character.id, skill, True, owner, db_session), from_attributes=True
        )
        assert (out.skill_code, out.skill_name, out.ability_code, out.source, out.expertise) == (
            skill.code, "Stealth", "dex", "class", True,
        )
        assert (await _skills_of(db_session, character.id))[skill.code].expertise is True

        out = await _patch(character.id, skill, False, owner, db_session)
        assert out.expertise is False
        assert (await _skills_of(db_session, character.id))[skill.code].expertise is False

    async def test_skill_not_owned_404(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _patch(character.id, skill, True, owner, db_session)
        assert exc.value.status_code == 404
        assert no_redis == []

    async def test_nonexistent_character_404(self, db_session, no_redis):
        owner = await seed_user(db_session)
        skill = await seed_skill(db_session)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await _patch(uuid.uuid4(), skill, True, owner, db_session)
        assert exc.value.status_code == 404

    async def test_stranger_gets_403(self, db_session, no_redis):
        owner, stranger = await seed_user(db_session), await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        skill = await seed_skill(db_session)
        await seed_character_skill(db_session, character, skill)
        await _reset(db_session, stranger)

        with pytest.raises(HTTPException) as exc:
            await _patch(character.id, skill, True, stranger, db_session)
        assert exc.value.status_code == 403
        assert (await _skills_of(db_session, character.id))[skill.code].expertise is False

    async def test_dm_allowed_and_event_broadcast(self, db_session, no_redis):
        owner, dm = await seed_user(db_session), await seed_user(db_session)
        campaign = await seed_campaign(db_session, dm)
        await seed_campaign_member(db_session, campaign, dm, role="dm")
        character = await seed_character(db_session, owner=owner, campaign_id=campaign.id)
        skill = await seed_skill(db_session)
        await seed_character_skill(db_session, character, skill)
        await _reset(db_session, dm)

        await _patch(character.id, skill, True, dm, db_session)

        assert len(no_redis) == 1
        channel, msg = no_redis[0]
        assert channel == f"campaign:{campaign.id}"
        assert msg["event"] == "character.skill.expertise"
        assert msg["character_id"] == str(character.id)
        assert msg["payload"] == {"skill_code": str(skill.code), "expertise": True}
        assert msg["actor_id"] == str(dm.id)

    async def test_create_schema_has_no_expertise_field(self):
        assert "expertise" not in CharacterSkillCreate.model_fields


# --------------------------------------------------------------------------
# Step 6: automatic background skills
# --------------------------------------------------------------------------
class TestAutomaticBackgroundSkills:
    async def test_create_with_background_creates_background_rows(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        s1, s2 = await seed_skill(db_session), await seed_skill(db_session)
        await seed_background_skill(db_session, bg, s1, s2)
        await _reset(db_session, owner)

        character = await create_character(
            CharacterCreate(name="Bg Hero", background_id=bg.id), current_user=owner, db=db_session
        )
        out = CharacterOut.model_validate(character, from_attributes=True)

        assert {(s.skill_code, s.source) for s in out.skills} == {(s1.code, "background"), (s2.code, "background")}

    async def test_create_without_background_creates_no_rows(self, db_session, no_redis):
        owner = await seed_user(db_session)
        await _reset(db_session, owner)
        character = await create_character(CharacterCreate(name="Plain"), current_user=owner, db=db_session)
        assert character.skills == []

    async def test_create_with_nonexistent_background_404(self, db_session, no_redis):
        owner = await seed_user(db_session)
        await _reset(db_session, owner)
        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(name="Ghost Bg", background_id=uuid.uuid4()), current_user=owner, db=db_session
            )
        assert exc.value.status_code == 404

    async def test_patch_swapping_background_replaces_only_background_rows(self, db_session, no_redis):
        owner = await seed_user(db_session)
        old_bg, new_bg = await seed_background(db_session), await seed_background(db_session)
        old_only, shared, new_only, other_src = [await seed_skill(db_session) for _ in range(4)]
        await seed_background_skill(db_session, old_bg, old_only, shared)
        await seed_background_skill(db_session, new_bg, shared, new_only)
        character = await seed_character(db_session, owner=owner, background_id=old_bg.id)
        await seed_character_skill(db_session, character, old_only, source="background")
        await seed_character_skill(db_session, character, shared, source="background")
        await seed_character_skill(db_session, character, other_src, source="feat")
        await _reset(db_session, owner)

        updated = await update_character(
            character.id, CharacterUpdate(background_id=new_bg.id), current_user=owner, db=db_session
        )
        out = CharacterOut.model_validate(updated, from_attributes=True)

        assert {(s.skill_code, s.source) for s in out.skills} == {
            (shared.code, "background"), (new_only.code, "background"), (other_src.code, "feat"),
        }
        assert out.background_id == new_bg.id

    async def test_background_skill_already_owned_by_other_source_is_not_duplicated(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        skill, extra = await seed_skill(db_session), await seed_skill(db_session)
        await seed_background_skill(db_session, bg, skill, extra)
        character = await seed_character(db_session, owner=owner)
        await seed_character_skill(db_session, character, skill, source="species")
        await _reset(db_session, owner)

        updated = await update_character(
            character.id, CharacterUpdate(background_id=bg.id), current_user=owner, db=db_session
        )
        out = CharacterOut.model_validate(updated, from_attributes=True)

        assert {(s.skill_code, s.source) for s in out.skills} == {(skill.code, "species"), (extra.code, "background")}

    async def test_patch_without_background_change_leaves_skills_untouched(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        skill, removed = await seed_skill(db_session), await seed_skill(db_session)
        await seed_background_skill(db_session, bg, skill, removed)
        character = await seed_character(db_session, owner=owner, background_id=bg.id)
        row = await seed_character_skill(db_session, character, skill, source="background")
        # `removed` is in the background pool but not owned (e.g. manually removed):
        # neither an unrelated PATCH nor a same-value background_id may bring it back.
        await _reset(db_session, owner)

        await update_character(character.id, CharacterUpdate(name="Renamed"), current_user=owner, db=db_session)
        await update_character(character.id, CharacterUpdate(background_id=bg.id), current_user=owner, db=db_session)

        rows = await _skills_of(db_session, character.id)
        assert set(rows) == {skill.code}
        assert rows[skill.code].id == row.id

    async def test_patch_nonexistent_background_404(self, db_session, no_redis):
        owner = await seed_user(db_session)
        character = await seed_character(db_session, owner=owner)
        await _reset(db_session, owner)
        with pytest.raises(HTTPException) as exc:
            await update_character(
                character.id, CharacterUpdate(background_id=uuid.uuid4()), current_user=owner, db=db_session
            )
        assert exc.value.status_code == 404


# --------------------------------------------------------------------------
# Step 7: batch on create (class + skills in one transaction)
# --------------------------------------------------------------------------
class TestCreateWithInitialClassAndSkills:
    async def _world(self, db_session):
        owner = await seed_user(db_session)
        klass = await seed_class(db_session, skill_choices=2)
        c1, c2, c3, outside = [await seed_skill(db_session) for _ in range(4)]
        await seed_class_skill(db_session, klass, c1, c2, c3)
        await _reset(db_session, owner)
        return owner, klass, c1, c2, c3, outside

    async def _assert_nothing_created(self, db_session, name):
        chars = (await db_session.execute(select(Character).where(Character.name == name))).scalars().all()
        assert chars == []
        classes = (await db_session.execute(select(CharacterClass))).scalars().all()
        assert classes == []
        skills = (await db_session.execute(select(CharacterSkill))).scalars().all()
        assert skills == []

    async def test_valid_batch_creates_character_class_and_skills(self, db_session, no_redis):
        owner = await seed_user(db_session)
        klass = await seed_class(db_session, skill_choices=2)
        c1, c2, other, species_skill = [await seed_skill(db_session) for _ in range(4)]
        await seed_class_skill(db_session, klass, c1, c2)
        await _reset(db_session, owner)

        character = await create_character(
            CharacterCreate(
                name="Batch Hero",
                initial_class={"class_id": klass.id, "level": 1},
                skills=[
                    CharacterSkillCreate(skill_code=c1.code, source="class"),
                    CharacterSkillCreate(skill_code=c2.code, source="class"),
                    CharacterSkillCreate(skill_code=species_skill.code, source="species"),
                    CharacterSkillCreate(skill_code=other.code, source="other"),
                ],
            ),
            current_user=owner, db=db_session,
        )
        out = CharacterOut.model_validate(character, from_attributes=True)

        assert [(c.class_id, c.level) for c in out.classes] == [(klass.id, 1)]
        assert out.total_level == 1
        assert {(s.skill_code, s.source) for s in out.skills} == {
            (c1.code, "class"), (c2.code, "class"), (species_skill.code, "species"), (other.code, "other"),
        }

    async def test_initial_class_without_skills_is_persisted(self, db_session, no_redis):
        owner, klass, *_ = await self._world(db_session)
        character = await create_character(
            CharacterCreate(name="Just Class", initial_class={"class_id": klass.id, "level": 3}),
            current_user=owner, db=db_session,
        )
        out = CharacterOut.model_validate(character, from_attributes=True)
        assert [(c.class_id, c.level, c.hit_dice_used) for c in out.classes] == [(klass.id, 3, 0)]

    async def test_class_skill_outside_pool_rolls_everything_back(self, db_session, no_redis):
        owner, klass, c1, _, _, outside = await self._world(db_session)

        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(
                    name="Rolled Back",
                    initial_class={"class_id": klass.id},
                    skills=[
                        CharacterSkillCreate(skill_code=c1.code, source="class"),
                        CharacterSkillCreate(skill_code=outside.code, source="class"),
                    ],
                ),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400
        await self._assert_nothing_created(db_session, "Rolled Back")

    async def test_class_skills_exceeding_skill_choices_400(self, db_session, no_redis):
        owner, klass, c1, c2, c3, _ = await self._world(db_session)
        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(
                    name="Too Many",
                    initial_class={"class_id": klass.id},
                    skills=[CharacterSkillCreate(skill_code=s.code, source="class") for s in (c1, c2, c3)],
                ),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400
        await self._assert_nothing_created(db_session, "Too Many")

    async def test_class_skill_without_initial_class_400(self, db_session, no_redis):
        owner, _, c1, _, _, _ = await self._world(db_session)
        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(name="No Class", skills=[CharacterSkillCreate(skill_code=c1.code, source="class")]),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400
        await self._assert_nothing_created(db_session, "No Class")

    async def test_nonexistent_initial_class_404_and_nothing_created(self, db_session, no_redis):
        owner, *_ = await self._world(db_session)
        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(name="Bad Class", initial_class={"class_id": uuid.uuid4()}),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 404
        await self._assert_nothing_created(db_session, "Bad Class")

    async def test_nonexistent_skill_400_and_nothing_created(self, db_session, no_redis):
        owner, klass, *_ = await self._world(db_session)
        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(
                    name="Bad Skill", initial_class={"class_id": klass.id},
                    skills=[CharacterSkillCreate(skill_code="no_such_skill", source="other")],
                ),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400
        await self._assert_nothing_created(db_session, "Bad Skill")

    async def test_duplicate_inside_batch_400(self, db_session, no_redis):
        owner, _, c1, *_ = await self._world(db_session)
        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(
                    name="Dup",
                    skills=[
                        CharacterSkillCreate(skill_code=c1.code, source="other"),
                        CharacterSkillCreate(skill_code=c1.code, source="feat"),
                    ],
                ),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400
        await self._assert_nothing_created(db_session, "Dup")

    async def test_batch_item_with_background_source_conflicts_with_automatic_row_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        skill = await seed_skill(db_session)
        await seed_background_skill(db_session, bg, skill)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(
                    name="Bg Dup", background_id=bg.id,
                    skills=[CharacterSkillCreate(skill_code=skill.code, source="background")],
                ),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400
        await self._assert_nothing_created(db_session, "Bg Dup")

    async def test_batch_skill_overlapping_automatic_background_skill_400(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        skill = await seed_skill(db_session)
        await seed_background_skill(db_session, bg, skill)
        await _reset(db_session, owner)

        with pytest.raises(HTTPException) as exc:
            await create_character(
                CharacterCreate(
                    name="Overlap", background_id=bg.id,
                    skills=[CharacterSkillCreate(skill_code=skill.code, source="species")],
                ),
                current_user=owner, db=db_session,
            )
        assert exc.value.status_code == 400
        await self._assert_nothing_created(db_session, "Overlap")

    async def test_background_automatic_and_batch_together(self, db_session, no_redis):
        owner = await seed_user(db_session)
        bg = await seed_background(db_session)
        bg_skill, species_skill = await seed_skill(db_session), await seed_skill(db_session)
        await seed_background_skill(db_session, bg, bg_skill)
        await _reset(db_session, owner)

        character = await create_character(
            CharacterCreate(
                name="Both", background_id=bg.id,
                skills=[CharacterSkillCreate(skill_code=species_skill.code, source="species")],
            ),
            current_user=owner, db=db_session,
        )
        out = CharacterOut.model_validate(character, from_attributes=True)
        assert {(s.skill_code, s.source) for s in out.skills} == {
            (bg_skill.code, "background"), (species_skill.code, "species"),
        }
