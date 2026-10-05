import uuid

from sqlalchemy import select

from app.db.models.character import Character
from tests.integration.conftest import seed_character, seed_user


class TestIntegrationInfra:
    async def test_round_trip_character_creation(self, db_session):
        user = await seed_user(db_session)
        character = await seed_character(db_session, owner=user, name="Smoke Test Hero")

        result = await db_session.execute(select(Character).where(Character.id == character.id))
        fetched = result.scalar_one()

        assert fetched.id == character.id
        assert fetched.name == "Smoke Test Hero"
        assert fetched.user_id == user.id

    async def test_transaction_is_rolled_back_between_tests(self, db_session):
        result = await db_session.execute(select(Character).where(Character.name == "Smoke Test Hero"))
        assert result.scalar_one_or_none() is None

class TestReferenceFactories:
    async def test_seed_skill_uses_valid_code_and_srd_ability(self, db_session):
        import re

        from tests.integration.conftest import seed_skill

        skill = await seed_skill(db_session)
        assert re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", skill.code)
        assert skill.ability_code == "str"

    async def test_seed_reference_creates_homebrew_with_shares(self, db_session):
        from app.db.models.reference import CampaignHomebrewRule, DamageType
        from tests.integration.conftest import seed_campaign, seed_reference

        author = await seed_user(db_session)
        campaign = await seed_campaign(db_session, creator=author)
        entry = await seed_reference(db_session, DamageType, author=author, campaigns=[campaign])

        assert entry.is_homebrew is True
        assert entry.source == "homebrew"
        assert entry.created_by == author.id
        shares = (await db_session.execute(
            select(CampaignHomebrewRule).where(CampaignHomebrewRule.resource_key == entry.code)
        )).scalars().all()
        assert [(s.resource_table, s.campaign_id) for s in shares] == [("damage_types", campaign.id)]


class TestItemFactories:
    async def test_seed_item_defaults_to_adventuring_gear_with_decimals(self, db_session):
        from decimal import Decimal

        from tests.integration.conftest import seed_item

        item = await seed_item(db_session)
        assert item.item_type_code == "adventuring_gear"
        assert isinstance(item.cost_gp, Decimal) and isinstance(item.weight_lb, Decimal)
        assert item.source == "srd" and item.is_homebrew is False

    async def test_srd_item_by_name(self, db_session):
        from tests.integration.conftest import srd_item

        gold = await srd_item(db_session, "Gold Piece")
        assert gold.item_type_code == "currency"
        assert gold.source == "srd"

    async def test_homebrew_weapon_armor_tool_and_pack_get_their_sub_rows(self, db_session):
        from sqlalchemy import func

        from app.db.models.items import Armor, ItemContent, Tool, Weapon, WeaponPropertyLink
        from tests.integration.conftest import seed_armor, seed_pack, seed_tool, seed_weapon, srd_item

        author = await seed_user(db_session)
        arrow = await srd_item(db_session, "Arrow")
        weapon = await seed_weapon(db_session, author=author, properties=[
            {"property_code": "ammunition", "ammunition_item_id": arrow.id},
            {"property_code": "range", "range_normal_ft": 80, "range_long_ft": 320},
        ])
        armor = await seed_armor(db_session, author=author)
        tool = await seed_tool(db_session, author=author, tool_type_code="lute")
        pack = await seed_pack(db_session, author=author, contents=[(arrow, 20)])

        assert (weapon.item_type_code, weapon.is_homebrew, weapon.created_by) == ("weapon", True, author.id)
        assert await db_session.scalar(select(func.count()).select_from(Weapon).where(Weapon.item_id == weapon.id)) == 1
        assert await db_session.scalar(
            select(func.count()).select_from(WeaponPropertyLink).where(WeaponPropertyLink.weapon_item_id == weapon.id)
        ) == 2
        assert armor.item_type_code == "armor"
        assert await db_session.scalar(select(func.count()).select_from(Armor).where(Armor.item_id == armor.id)) == 1
        assert await db_session.scalar(select(Tool.tool_type_code).where(Tool.item_id == tool.id)) == "lute"
        assert pack.item_type_code == "pack"
        assert await db_session.scalar(
            select(ItemContent.quantity).where(ItemContent.pack_item_id == pack.id, ItemContent.item_id == arrow.id)
        ) == 20


class TestGrantFactories:
    async def test_seed_grant_reuses_the_same_target(self, db_session):
        from tests.integration.conftest import seed_grant

        first = await seed_grant(db_session, weapon_category_code="martial", required_weapon_property_code="light")
        again = await seed_grant(db_session, weapon_category_code="martial", required_weapon_property_code="light")
        plain = await seed_grant(db_session, weapon_category_code="martial")
        assert first.id == again.id
        assert plain.id != first.id
        assert first.kind == "weapon_category"

    async def test_background_skill_and_class_grant_links(self, db_session):
        from tests.integration.conftest import (
            seed_background,
            seed_background_grant,
            seed_background_skill,
            seed_class,
            seed_class_grant,
            seed_skill,
        )

        background = await seed_background(db_session)
        b_skill = await seed_skill(db_session, name="Bbb")
        a_skill = await seed_skill(db_session, name="Aaa")
        await seed_background_skill(db_session, background, b_skill, a_skill)
        await seed_background_grant(db_session, background, tool_category_code="gaming_set")
        await db_session.refresh(background)
        assert [s.code for s in background.skills] == [a_skill.code, b_skill.code]
        assert sorted(g.kind for g in background.proficiency_grants) == ["skill", "skill", "tool_category"]

        klass = await seed_class(db_session)
        await seed_class_grant(db_session, klass, saving_throw_ability_code="str")
        await seed_class_grant(db_session, klass, saving_throw_ability_code="con")
        await db_session.refresh(klass)
        assert klass.saving_throw_proficiencies == ["con", "str"]

    async def test_seed_reference_accepts_item_types_and_tool_types(self, db_session):
        from app.db.models.reference import ItemType, ToolType
        from tests.integration.conftest import seed_reference

        author = await seed_user(db_session)
        item_type = await seed_reference(db_session, ItemType, author=author)
        tool_type = await seed_reference(db_session, ToolType, author=author, category_code="gaming_set")
        assert item_type.is_homebrew and tool_type.is_homebrew
        assert tool_type.ability_code == "str"
        assert tool_type.category_code == "gaming_set"


class TestSpellFactories:
    async def test_seed_spell_with_materials_area_and_list(self, db_session):
        from decimal import Decimal

        from app.db.models.spells import SpellMaterial, spell_list_spells
        from tests.integration.conftest import seed_spell

        author = await seed_user(db_session)
        spell = await seed_spell(
            db_session, author=author,
            materials=[dict(description="a ruby", cost_gp=Decimal("50"), consumed=True), dict(description="ash")],
            spell_lists=["wizard"], area="10-foot-radius Sphere", area_shape_code="sphere",
        )
        assert (spell.source, spell.is_homebrew, spell.created_by) == ("homebrew", True, author.id)
        assert spell.has_material is True and spell.has_verbal is True
        assert (spell.casting_time_code, spell.range, spell.duration) == ("action", "Self", "Instantaneous")
        rows = (await db_session.execute(
            select(SpellMaterial).where(SpellMaterial.spell_id == spell.id).order_by(SpellMaterial.sort_order)
        )).scalars().all()
        assert [(m.sort_order, m.description, m.cost_gp, m.consumed, m.quantity) for m in rows] == [
            (0, "a ruby", Decimal("50"), True, 1), (1, "ash", None, False, 1),
        ]
        lists = (await db_session.execute(
            select(spell_list_spells.c.spell_list_code).where(spell_list_spells.c.spell_id == spell.id)
        )).scalars().all()
        assert lists == ["wizard"]

    async def test_seed_spell_defaults_look_like_srd_and_are_coherent(self, db_session):
        from tests.integration.conftest import seed_spell

        spell = await seed_spell(db_session)
        assert (spell.source, spell.is_homebrew, spell.created_by) == ("srd", False, None)
        assert spell.has_material is False and spell.area is None and spell.area_shape_code is None

    async def test_srd_spell_by_name_is_the_uuid5_row(self, db_session):
        from tests.integration.conftest import srd_spell, srd_spell_id

        spell = await srd_spell(db_session, "Fireball")
        assert spell.id == srd_spell_id("Fireball")
        assert (spell.level, spell.school_code) == (3, "evocation")

    async def test_seed_character_spell(self, db_session):
        from app.db.models.character import CharacterSpell
        from tests.integration.conftest import seed_character_spell, seed_spell

        user = await seed_user(db_session)
        character = await seed_character(db_session, owner=user)
        spell = await seed_spell(db_session, author=user)
        link = await seed_character_spell(db_session, character, spell)
        fetched = (await db_session.execute(select(CharacterSpell).where(CharacterSpell.id == link.id))).scalar_one()
        assert (fetched.character_id, fetched.spell_id) == (character.id, spell.id)
