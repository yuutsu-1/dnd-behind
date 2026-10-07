"""The "exactly one" CHECKs of phase 4 hold in the database itself (direct INSERT, not
through the API): the IntegrityError names the violated constraint."""
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.integration.conftest import seed_class, seed_feat, seed_feature, seed_subclass


async def _insert_fails(db_session, sql: str, constraint: str, **params) -> None:
    with pytest.raises(IntegrityError) as error:
        async with db_session.begin_nested():
            await db_session.execute(text(sql), params)
    assert constraint in str(error.value)


FEATURE_SQL = (
    "INSERT INTO feature_definitions (id, name, sort_order, class_id, subclass_id, feat_id, level, "
    "is_choice_option, source, is_homebrew) VALUES (:id, 'X', 0, :class_id, :subclass_id, :feat_id, :level, "
    "false, 'srd', false)"
)


@pytest.fixture
async def owners(db_session):
    klass = await seed_class(db_session)
    return {"class": klass.id, "subclass": (await seed_subclass(db_session, klass)).id,
            "feat": (await seed_feat(db_session)).id}


async def test_feature_without_owner(db_session, owners):
    await _insert_fails(db_session, FEATURE_SQL, "ck_feature_definitions_single_owner",
                        id=uuid.uuid4(), class_id=None, subclass_id=None, feat_id=None, level=1)


async def test_feature_with_two_owners(db_session, owners):
    await _insert_fails(db_session, FEATURE_SQL, "ck_feature_definitions_single_owner",
                        id=uuid.uuid4(), class_id=owners["class"], subclass_id=owners["subclass"], feat_id=None, level=1)


async def test_class_feature_without_level(db_session, owners):
    await _insert_fails(db_session, FEATURE_SQL, "ck_feature_definitions_level_by_owner",
                        id=uuid.uuid4(), class_id=owners["class"], subclass_id=None, feat_id=None, level=None)


async def test_feat_feature_with_level(db_session, owners):
    await _insert_fails(db_session, FEATURE_SQL, "ck_feature_definitions_level_by_owner",
                        id=uuid.uuid4(), class_id=None, subclass_id=None, feat_id=owners["feat"], level=3)


async def test_valid_rows_are_accepted(db_session, owners):
    for column, level in (("class_id", 1), ("subclass_id", 3), ("feat_id", None)):
        params = {"class_id": None, "subclass_id": None, "feat_id": None, column: owners[column[:-3]]}
        await db_session.execute(text(FEATURE_SQL), {"id": uuid.uuid4(), "level": level, **params})


@pytest.fixture
async def choice_id(db_session, owners):
    feat = await seed_feat(db_session)
    feature = await seed_feature(db_session, feat=feat, effects=[dict(
        operation_code="grant", choice=dict(pool_type_code="skill", choose_count=1))])
    effect_id = (await db_session.execute(text("SELECT id FROM feature_effects WHERE feature_id = :f"),
                                          {"f": feature.id})).scalar_one()
    return (await db_session.execute(text("SELECT id FROM feature_choices WHERE effect_id = :e"),
                                     {"e": effect_id})).scalar_one(), effect_id


OPTION_SQL = (
    "INSERT INTO feature_choice_options (id, choice_id, skill_code, ability_code) "
    "VALUES (:id, :choice_id, :skill, :ability)"
)


async def test_option_without_target(db_session, choice_id):
    await _insert_fails(db_session, OPTION_SQL, "ck_feature_choice_options_single_target",
                        id=uuid.uuid4(), choice_id=choice_id[0], skill=None, ability=None)


async def test_option_with_two_targets(db_session, choice_id):
    await _insert_fails(db_session, OPTION_SQL, "ck_feature_choice_options_single_target",
                        id=uuid.uuid4(), choice_id=choice_id[0], skill="stealth", ability="str")


async def test_scaling_with_two_targets(db_session, choice_id):
    await _insert_fails(
        db_session,
        "INSERT INTO feature_scaling (id, effect_id, choice_id, level, value) VALUES (:id, :e, :c, 5, 2)",
        "ck_feature_scaling_single_target", id=uuid.uuid4(), e=choice_id[1], c=choice_id[0],
    )


async def test_scaling_without_target(db_session):
    await _insert_fails(
        db_session, "INSERT INTO feature_scaling (id, level, value) VALUES (:id, 5, 2)",
        "ck_feature_scaling_single_target", id=uuid.uuid4(),
    )


PREREQ_SQL = (
    "INSERT INTO feat_prerequisites (id, feat_id, or_group, min_character_level, feature_kind_code) "
    "VALUES (:id, :feat, 1, :level, :kind)"
)


async def test_prerequisite_without_target(db_session, owners):
    await _insert_fails(db_session, PREREQ_SQL, "ck_feat_prerequisites_single_target",
                        id=uuid.uuid4(), feat=owners["feat"], level=None, kind=None)


async def test_prerequisite_with_two_targets(db_session, owners):
    await _insert_fails(db_session, PREREQ_SQL, "ck_feat_prerequisites_single_target",
                        id=uuid.uuid4(), feat=owners["feat"], level=4, kind="fighting_style")
