"""SRD 2024 Fighter + Champion, gerado por scripts/extract_srd_fighter.py — não editar à mão.

Só dados (sem import de `app`): importado pela migration c1fcfd7fe014. Para mudar,
ajuste o extrator e rode `python -m scripts.extract_srd_fighter` em backend/.
Itens por nome (uuid5 de SRD_ITEM_NAMESPACE na migration); `replaces` = (nome, nível)
de uma feature do mesmo dono. Estrutura das features: mesmos nomes do payload da API.
"""

CLASS = {'name': 'Fighter',
 'description': None,
 'hit_die': 10,
 'primary_ability': ('dex', 'str'),
 'proficiency_grants': ({'saving_throw_ability_code': 'str'},
                        {'saving_throw_ability_code': 'con'},
                        {'weapon_category_code': 'simple'},
                        {'weapon_category_code': 'martial'},
                        {'armor_category_code': 'light'},
                        {'armor_category_code': 'medium'},
                        {'armor_category_code': 'heavy'},
                        {'armor_category_code': 'shield'}),
 'skill_choices': 2,
 'skills': ('acrobatics',
            'animal_handling',
            'athletics',
            'history',
            'insight',
            'intimidation',
            'perception',
            'persuasion',
            'survival'),
 'initial_equipment': ({'option': 'A', 'item': 'Chain Mail', 'quantity': 1},
                       {'option': 'A', 'item': 'Greatsword', 'quantity': 1},
                       {'option': 'A', 'item': 'Flail', 'quantity': 1},
                       {'option': 'A', 'item': 'Javelin', 'quantity': 8},
                       {'option': 'A', 'item': "Dungeoneer's Pack", 'quantity': 1},
                       {'option': 'A', 'item': 'Gold Piece', 'quantity': 4},
                       {'option': 'B', 'item': 'Studded Leather Armor', 'quantity': 1},
                       {'option': 'B', 'item': 'Scimitar', 'quantity': 1},
                       {'option': 'B', 'item': 'Shortsword', 'quantity': 1},
                       {'option': 'B', 'item': 'Longbow', 'quantity': 1},
                       {'option': 'B', 'item': 'Arrow', 'quantity': 20},
                       {'option': 'B', 'item': 'Quiver', 'quantity': 1},
                       {'option': 'B', 'item': "Dungeoneer's Pack", 'quantity': 1},
                       {'option': 'B', 'item': 'Gold Piece', 'quantity': 11},
                       {'option': 'C', 'item': 'Gold Piece', 'quantity': 155}),
 'subclass_level': 3,
 'spell_ability': None,
 'spellcasting_type': None,
 'features': ({'name': 'Fighting Style',
               'description': 'You have honed your martial prowess and gain a Fighting Style feat of your choice (see '
                              '"Feats"). Defense is recommended.\n'
                              '\n'
                              'Whenever you gain a Fighter level, you can replace the feat you chose with a different '
                              'Fighting Style feat.',
               'level': 1,
               'action_type_code': None,
               'feature_kind_code': 'fighting_style',
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant',
                            'choice': {'pool_type_code': 'feat',
                                       'choose_count': 1,
                                       'feat_category_code': 'fighting_style',
                                       'swap_rule_code': 'on_class_level_up'}},),
               'resources': ()},
              {'name': 'Second Wind',
               'description': 'You have a limited well of physical and mental stamina that you can draw on. As a Bonus '
                              'Action, you can use it to regain Hit Points equal to 1d10 plus your Fighter level.\n'
                              '\n'
                              'You can use this feature twice. You regain one expended use when you finish a Short '
                              'Rest, and you regain all expended uses when you finish a Long Rest.\n'
                              '\n'
                              'When you reach certain Fighter levels, you gain more uses of this feature, as shown in '
                              'the Second Wind column of the Fighter Features table.',
               'level': 1,
               'action_type_code': 'bonus_action',
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'heal',
                            'target_code': 'hit_points',
                            'dice_count': 1,
                            'die_size': 10,
                            'value_basis_code': 'class_level'},),
               'resources': ({'name': 'Second Wind',
                              'recharges': ({'recharge_type_code': 'short_rest', 'recovers': 1},
                                            {'recharge_type_code': 'long_rest', 'recovers': None}),
                              'value': 2,
                              'scaling': ({'level': 4, 'value': 3}, {'level': 10, 'value': 4})},)},
              {'name': 'Weapon Mastery',
               'description': 'Your training with weapons allows you to use the mastery properties of three kinds of '
                              'Simple or Martial weapons of your choice. Whenever you finish a Long Rest, you can '
                              'practice weapon drills and change one of those weapon choices.\n'
                              '\n'
                              'When you reach certain Fighter levels, you gain the ability to use the mastery '
                              'properties of more kinds of weapons, as shown in the Weapon Mastery column of the '
                              'Fighter Features table.',
               'level': 1,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant',
                            'choice': {'pool_type_code': 'weapon',
                                       'swap_rule_code': 'on_long_rest_one',
                                       'choose_count': 3,
                                       'scaling': ({'level': 4, 'value': 4},
                                                   {'level': 10, 'value': 5},
                                                   {'level': 16, 'value': 6})}},),
               'resources': ()},
              {'name': 'Action Surge',
               'description': 'You can push yourself beyond your normal limits for a moment. On your turn, you can '
                              'take one additional action, except the Magic action.\n'
                              '\n'
                              "Once you use this feature, you can't do so again until you finish a Short or Long Rest. "
                              'Starting at level 17, you can use it twice before a rest but only once on a turn.',
               'level': 2,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': (),
               'resources': ({'name': 'Action Surge',
                              'recharges': ({'recharge_type_code': 'short_rest', 'recovers': None},
                                            {'recharge_type_code': 'long_rest', 'recovers': None}),
                              'value': 1,
                              'scaling': ({'level': 17, 'value': 2},)},)},
              {'name': 'Tactical Mind',
               'description': 'You have a mind for tactics on and off the battlefield. When you fail an ability check, '
                              'you can expend a use of your Second Wind to push yourself toward success. Rather than '
                              'regaining Hit Points, you roll 1d10 and add the number rolled to the ability check, '
                              'potentially turning it into a success. If the check still fails, this use of Second '
                              "Wind isn't expended.",
               'level': 2,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': (),
               'resources': ()},
              {'name': 'Fighter Subclass',
               'description': 'You gain a Fighter subclass of your choice. The Champion subclass is detailed after '
                              "this class's description. A subclass is a specialization that grants you features at "
                              "certain Fighter levels. For the rest of your career, you gain each of your subclass's "
                              'features that are of your Fighter level or lower.',
               'level': 3,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': (),
               'resources': ()},
              {'name': 'Ability Score Improvement',
               'description': 'You gain the Ability Score Improvement feat (see "Feats") or another feat of your '
                              'choice for which you qualify. You gain this feature again at Fighter levels 6, 8, 12, '
                              '14, and 16.',
               'level': 4,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant', 'choice': {'pool_type_code': 'feat', 'choose_count': 1}},),
               'resources': ()},
              {'name': 'Extra Attack',
               'description': 'You can attack twice instead of once whenever you take the Attack action on your turn.',
               'level': 5,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'set', 'target_code': 'attacks_per_action', 'value': 2},),
               'resources': ()},
              {'name': 'Tactical Shift',
               'description': 'Whenever you activate your Second Wind with a Bonus Action, you can move up to half '
                              'your Speed without provoking Opportunity Attacks.',
               'level': 5,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': (),
               'resources': ()},
              {'name': 'Ability Score Improvement',
               'description': 'You gain the Ability Score Improvement feat (see "Feats") or another feat of your '
                              'choice for which you qualify. You gain this feature again at Fighter levels 6, 8, 12, '
                              '14, and 16.',
               'level': 6,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant', 'choice': {'pool_type_code': 'feat', 'choose_count': 1}},),
               'resources': ()},
              {'name': 'Ability Score Improvement',
               'description': 'You gain the Ability Score Improvement feat (see "Feats") or another feat of your '
                              'choice for which you qualify. You gain this feature again at Fighter levels 6, 8, 12, '
                              '14, and 16.',
               'level': 8,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant', 'choice': {'pool_type_code': 'feat', 'choose_count': 1}},),
               'resources': ()},
              {'name': 'Indomitable',
               'description': 'If you fail a saving throw, you can reroll it with a bonus equal to your Fighter level. '
                              "You must use the new roll, and you can't use this feature again until you finish a Long "
                              'Rest.\n'
                              '\n'
                              'You can use this feature twice before a Long Rest starting at level 13 and three times '
                              'before a Long Rest starting at level 17.',
               'level': 9,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': (),
               'resources': ({'name': 'Indomitable',
                              'recharges': ({'recharge_type_code': 'long_rest', 'recovers': None},),
                              'value': 1,
                              'scaling': ({'level': 13, 'value': 2}, {'level': 17, 'value': 3})},)},
              {'name': 'Tactical Master',
               'description': 'When you attack with a weapon whose mastery property you can use, you can replace that '
                              'property with the Push, Sap, or Slow property for that attack.',
               'level': 9,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': (),
               'resources': ()},
              {'name': 'Two Extra Attacks',
               'description': 'You can attack three times instead of once whenever you take the Attack action on your '
                              'turn.',
               'level': 11,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': ('Extra Attack', 5),
               'effects': ({'operation_code': 'set', 'target_code': 'attacks_per_action', 'value': 3},),
               'resources': ()},
              {'name': 'Ability Score Improvement',
               'description': 'You gain the Ability Score Improvement feat (see "Feats") or another feat of your '
                              'choice for which you qualify. You gain this feature again at Fighter levels 6, 8, 12, '
                              '14, and 16.',
               'level': 12,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant', 'choice': {'pool_type_code': 'feat', 'choose_count': 1}},),
               'resources': ()},
              {'name': 'Studied Attacks',
               'description': 'You study your opponents and learn from each attack you make. If you make an attack '
                              'roll against a creature and miss, you have Advantage on your next attack roll against '
                              'that creature before the end of your next turn.',
               'level': 13,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': (),
               'resources': ()},
              {'name': 'Ability Score Improvement',
               'description': 'You gain the Ability Score Improvement feat (see "Feats") or another feat of your '
                              'choice for which you qualify. You gain this feature again at Fighter levels 6, 8, 12, '
                              '14, and 16.',
               'level': 14,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant', 'choice': {'pool_type_code': 'feat', 'choose_count': 1}},),
               'resources': ()},
              {'name': 'Ability Score Improvement',
               'description': 'You gain the Ability Score Improvement feat (see "Feats") or another feat of your '
                              'choice for which you qualify. You gain this feature again at Fighter levels 6, 8, 12, '
                              '14, and 16.',
               'level': 16,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant', 'choice': {'pool_type_code': 'feat', 'choose_count': 1}},),
               'resources': ()},
              {'name': 'Epic Boon',
               'description': 'You gain an Epic Boon feat (see "Feats") or another feat of your choice for which you '
                              'qualify. Boon of Combat Prowess is recommended.',
               'level': 19,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': None,
               'effects': ({'operation_code': 'grant', 'choice': {'pool_type_code': 'feat', 'choose_count': 1}},),
               'resources': ()},
              {'name': 'Three Extra Attacks',
               'description': 'You can attack four times instead of once whenever you take the Attack action on your '
                              'turn.',
               'level': 20,
               'action_type_code': None,
               'feature_kind_code': None,
               'is_choice_option': False,
               'replaces': ('Two Extra Attacks', 11),
               'effects': ({'operation_code': 'set', 'target_code': 'attacks_per_action', 'value': 4},),
               'resources': ()})}

SUBCLASSES = ({'name': 'Champion',
  'class': 'Fighter',
  'description': '_Pursue Physical Excellence in Combat_\n'
                 '\n'
                 'A Champion focuses on the development of martial prowess in a relentless pursuit of victory. '
                 'Champions combine rigorous training with physical excellence to deal devastating blows, withstand '
                 'peril, and garner glory. Whether in athletic contests or bloody battle, Champions strive for the '
                 'crown of the victor.',
  'features': ({'name': 'Improved Critical',
                'description': 'Your attack rolls with weapons and Unarmed Strikes can score a Critical Hit on a roll '
                               'of 19 or 20 on the d20.',
                'level': 3,
                'action_type_code': None,
                'feature_kind_code': None,
                'is_choice_option': False,
                'replaces': None,
                'effects': ({'operation_code': 'set',
                             'target_code': 'critical_range',
                             'value': 19,
                             'condition_text': 'with weapons and Unarmed Strikes'},),
                'resources': ()},
               {'name': 'Remarkable Athlete',
                'description': 'Thanks to your athleticism, you have Advantage on Initiative rolls and Strength '
                               '(Athletics) checks.\n'
                               '\n'
                               'In addition, immediately after you score a Critical Hit, you can move up to half your '
                               'Speed without provoking Opportunity Attacks.',
                'level': 3,
                'action_type_code': None,
                'feature_kind_code': None,
                'is_choice_option': False,
                'replaces': None,
                'effects': ({'operation_code': 'advantage', 'target_code': 'initiative'},
                            {'operation_code': 'advantage', 'target_code': 'ability_check', 'skill_code': 'athletics'}),
                'resources': ()},
               {'name': 'Additional Fighting Style',
                'description': 'You gain another Fighting Style feat of your choice.',
                'level': 7,
                'action_type_code': None,
                'feature_kind_code': 'fighting_style',
                'is_choice_option': False,
                'replaces': None,
                'effects': ({'operation_code': 'grant',
                             'choice': {'pool_type_code': 'feat',
                                        'choose_count': 1,
                                        'feat_category_code': 'fighting_style'}},),
                'resources': ()},
               {'name': 'Heroic Warrior',
                'description': 'The thrill of battle drives you toward victory. During combat, you can give yourself '
                               'Heroic Inspiration whenever you start your turn without it.',
                'level': 10,
                'action_type_code': None,
                'feature_kind_code': None,
                'is_choice_option': False,
                'replaces': None,
                'effects': (),
                'resources': ()},
               {'name': 'Superior Critical',
                'description': 'Your attack rolls with weapons and Unarmed Strikes can now score a Critical Hit on a '
                               'roll of 18–20 on the d20.',
                'level': 15,
                'action_type_code': None,
                'feature_kind_code': None,
                'is_choice_option': False,
                'replaces': ('Improved Critical', 3),
                'effects': ({'operation_code': 'set',
                             'target_code': 'critical_range',
                             'value': 18,
                             'condition_text': 'with weapons and Unarmed Strikes'},),
                'resources': ()},
               {'name': 'Survivor',
                'description': 'You attain the pinnacle of resilience in battle, giving you these benefits.\n'
                               '\n'
                               '_Defy Death._ You have Advantage on Death Saving Throws. Moreover, when you roll 18–20 '
                               'on a Death Saving Throw, you gain the benefit of rolling a 20 on it.\n'
                               '\n'
                               '_Heroic Rally._ At the start of each of your turns, you regain Hit Points equal to 5 '
                               'plus your Constitution modifier if you are Bloodied and have at least 1 Hit Point.',
                'level': 18,
                'action_type_code': None,
                'feature_kind_code': None,
                'is_choice_option': False,
                'replaces': None,
                'effects': ({'operation_code': 'advantage', 'target_code': 'death_saving_throw'},),
                'resources': ()})},)
