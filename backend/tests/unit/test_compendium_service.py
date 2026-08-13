import uuid

from app.schemas.compendium import SkillCreate
from app.services.compendium import resolve_skills
from tests.conftest import make_result, make_skill


class TestResolveSkills:
    async def test_empty_list_returns_empty_list_without_querying(self, fake_db):
        result = await resolve_skills(fake_db, [])
        assert result == []
        fake_db.execute.assert_not_awaited()

    async def test_reuses_existing_skill_matching_name_and_ability_score(self, fake_db):
        from app.db.models.compendium import AbilityScoreOption

        existing = make_skill(name="Athletics", ability_score="STR")
        fake_db.execute.side_effect = [
            make_result(scalars_list=[AbilityScoreOption(name="STR")]),  # STR already exists
            make_result(scalars_list=[existing]),  # skill lookup
        ]

        result = await resolve_skills(fake_db, [SkillCreate(name="Athletics", ability_score="STR")])

        assert result == [existing]
        fake_db.add.assert_not_called()

    async def test_creates_missing_ability_score_option_before_creating_skill(self, fake_db):
        fake_db.execute.side_effect = [
            make_result(scalars_list=[]),  # no existing ability_score_options
            make_result(scalars_list=[]),  # no existing skill
        ]

        result = await resolve_skills(fake_db, [SkillCreate(name="Insight", ability_score="INT")])

        assert len(result) == 1
        assert result[0].name == "Insight"
        assert result[0].ability_score == "INT"
        # One add for the AbilityScoreOption("INT") row, one for the SkillDefinition.
        assert fake_db.add.call_count == 2
        fake_db.flush.assert_awaited()

    async def test_duplicate_requested_skills_are_deduplicated(self, fake_db):
        fake_db.execute.side_effect = [
            make_result(scalars_list=[]),  # ability_score_options check
            make_result(scalars_list=[]),  # skill lookup
        ]

        result = await resolve_skills(
            fake_db,
            [
                SkillCreate(name="Stealth", ability_score="DEX"),
                SkillCreate(name="Stealth", ability_score="DEX"),
            ],
        )

        assert len(result) == 1
        # One add for AbilityScoreOption("DEX"), one for the single deduplicated skill.
        assert fake_db.add.call_count == 2
