from app.api.compendium import create_subclass, list_subclasses
from app.schemas.character import WSEvent
from app.schemas.compendium import FeatureGrantOut, SubclassCreate, SubclassOut
from tests.integration.conftest import seed_class, seed_subclass, seed_user


class TestSubclassOutClassName:
    async def test_populated_from_seeded_class(self, db_session):
        klass = await seed_class(db_session, name="Cleric")
        subclass = await seed_subclass(db_session, klass, name="Life Domain")

        subclasses = await list_subclasses(db=db_session, class_id=klass.id)
        out = [SubclassOut.model_validate(s, from_attributes=True) for s in subclasses]

        found = next(s for s in out if s.id == subclass.id)
        assert found.class_name == "Cleric"


class TestNoMissingGreenletOnCreateSubclass:
    async def test_create_subclass_serializes_without_error(self, db_session):
        creator = await seed_user(db_session)
        klass = await seed_class(db_session, name="Wizard")

        obj = await create_subclass(
            SubclassCreate(class_id=klass.id, name="School of Evocation"),
            current_user=creator,
            db=db_session,
        )

        out = SubclassOut.model_validate(obj, from_attributes=True)
        assert out.name == "School of Evocation"
        assert out.class_name == "Wizard"


class TestFeatureGrantAndWSEventUnaffected:

    def test_feature_grant_out_field_set_unchanged(self):
        assert set(FeatureGrantOut.model_fields.keys()) == {
            "id",
            "source_type",
            "source_id",
            "name",
            "description",
            "effect_type",
            "effect_data",
            "level_requirement",
            "is_optional",
            "sort_order",
        }

    def test_ws_event_field_set_unchanged(self):
        assert set(WSEvent.model_fields.keys()) == {
            "event",
            "character_id",
            "payload",
            "actor_id",
        }