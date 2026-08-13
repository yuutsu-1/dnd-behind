import uuid

from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from app.db.models.compendium import (
    ClassDefinition,
    ClassInitialEquipment,
    ItemDefinition,
    SkillDefinition,
    class_skills,
)


def _relationship_names(model) -> set[str]:
    return {rel.key for rel in inspect(model).relationships}


def _column_names(model) -> set[str]:
    return {col.name for col in inspect(model).columns}


class TestMapperConfiguration:
    def test_configure_mappers_does_not_raise(self):
        configure_mappers()


class TestSkillDefinition:
    def test_has_expected_columns(self):
        columns = _column_names(SkillDefinition)
        assert {"id", "name", "ability_score"} <= columns

    def test_assignable(self):
        skill = SkillDefinition(id=uuid.uuid4(), name="Athletics", ability_score="STR")
        assert skill.name == "Athletics"
        assert skill.ability_score == "STR"

    def test_unique_constraint_on_name_and_ability_score(self):
        constraint_columns = [
            tuple(c.name for c in constraint.columns)
            for constraint in SkillDefinition.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]
        assert ("name", "ability_score") in constraint_columns


class TestClassSkillsJunctionTable:
    def test_junction_table_has_class_id_and_skill_id_columns(self):
        assert "class_id" in class_skills.c
        assert "skill_id" in class_skills.c

    def test_class_definition_no_longer_has_skill_pool_column(self):
        assert "skill_pool" not in _column_names(ClassDefinition)

    def test_class_definition_has_skills_relationship(self):
        assert "skills" in _relationship_names(ClassDefinition)


class TestClassInitialEquipment:
    def test_has_expected_columns(self):
        columns = _column_names(ClassInitialEquipment)
        assert {"id", "class_id", "item_id", "option", "quantity"} <= columns

    def test_assignable(self):
        item = ItemDefinition(id=uuid.uuid4(), name="Longsword", item_type="weapon")
        entry = ClassInitialEquipment(
            id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            item_id=item.id,
            item=item,
            option="A",
            quantity=1,
        )
        assert entry.item is item
        assert entry.option == "A"
        assert entry.quantity == 1
