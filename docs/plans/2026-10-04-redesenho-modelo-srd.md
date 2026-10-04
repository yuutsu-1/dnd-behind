# Redesenho do modelo a partir do SRD 2024 (sem JSONB)

Data: 2026-10-04 · status: **plano aprovado, fase 0 concluída**.

Documentos relacionados:
- `2026-08-13-gaps-criacao-personagem.md`: primeiro inventário de gaps (Sir Alcino).
- `2026-10-03-teste-guerreiro-e-feature-effects.md`: segundo teste (Guerreiro) e as ideias de efeitos de features.
- Fonte das regras: `docs/dnd-5e-srd-markdown-master/` (SRD 5.2 / D&D 2024).

## Aprendizados por etapa da criação de personagem

As etapas seguem `character-creation.md`: classe → origem → atributos → alinhamento → detalhes.

### 1. Escolher a classe
- **O que funcionou:** dado de vida, atributos primários, salvaguardas, pool de perícias, proficiências de arma e armadura, e equipamento inicial A/B/C (depois de definir que ouro é item).
- **O que faltou:**
  - Features por nível ficam em JSON (`FeatureGrant.effect_data`). Por isso não há onde registrar "ganhe um talento de Estilo de Luta à escolha" nem a troca desse talento a cada nível.
  - A tabela de níveis da classe não existe: Weapon Mastery, Second Wind, slots de magia etc.
  - O "Strength **ou** Dexterity" do atributo primário não distingue "ou" de "e". Essa diferença importa para o pré-requisito de multiclasse.
  - Proficiências são textos soltos ("Armas Marciais"), sem relação com as armas cadastradas.
- **Bug encontrado e corrigido** (commit 61073ab): `POST` e `GET /classes` davam 500 por lazy load de `item` (MissingGreenlet).

### 2. Determinar a origem
- **Antecedente:**
  - O banco local estava sem as colunas novas porque a migration squash foi editada.
  - O Nobre não existe no SRD; os únicos antecedentes do SRD são Acolyte, Criminal, Sage e Soldier.
  - Talento parametrizado, como "Magic Initiate (Cleric)", não tem onde ser representado.
  - A ferramenta escolhida dentro de uma categoria, como o Gaming Set do Soldier, é reaproveitada no equipamento ("same as above").
- **Espécie:**
  - `POST /species` dá 500 sempre: `creature_type` é obrigatório no model, mas não existe no schema.
  - `size` aceita um único valor, e Human/Tiefling escolhem entre Small e Medium.
  - Traços ficam em `special_traits` (JSONB, fora da API).
  - Skillful, Versatile e as linhagens (Elf, Gnome, Tiefling, Dragonborn, Goliath) são escolhas.
  - Há traços que escalam pelo nível do **personagem**, não da classe (Breath Weapon, Draconic Flight).

### 3. Determinar os atributos (pendente no teste; levantado no SRD)
- **Métodos:** standard array, point buy (27 pontos, tabela de custo) ou 4d6.
- **Bônus do antecedente:** +2/+1 ou +1/+1/+1 sobre os 3 atributos listados, com teto 20.
- **Hoje:** não guardamos o valor base separado do bônus, nem a origem de cada aumento.

### 4. Escolher o alinhamento (pendente no teste)
- `Character` **não tem coluna de alinhamento**.

### 5. Preencher os detalhes (pendente no teste)
- `appearance` e `custom_data` são JSONB livres.
- Idiomas do personagem não existem (Common + 2 à escolha).
- O tamanho escolhido também não é guardado.

### Transversais
- 12 colunas JSONB no total, todas a remover (tabela abaixo).
- Valores em dinheiro: `cost_gp` era float; vira decimal com ouro como base.
- Kits (Explorer's Pack, Adventurer's Kit) não têm conteúdo.
- Monstros não têm modelo nenhum.

## Mapa: gaps antigos → fase que resolve

Gaps do relatório de 2026-08-13:

| Gap | Fase |
|---|---|
| 1. Antecedente vazio | resolvido em 748929e; ajustes na fase 7 do redesenho |
| 2. Perícias do personagem | resolvido (`character_skills`); a origem por escolha entra na fase 7 |
| 3. Weapon Mastery do personagem | fases 2 e 7 |
| 4. Dados mecânicos de arma | fase 2 |
| 5. Moeda do personagem | fase 2 (moeda como item) |
| 6. Kits | fase 2 (`item_contents`) |
| 7. Arma ↔ categoria de proficiência | fase 2 (`proficiency_grants`) |
| 8. Efeito mecânico de talento | fase 4 |
| 9. `CharacterFeat.source` | fase 7 (`character_choice_selections`) |
| 10. Motor que aplica efeitos | fora deste redesenho; depende das fases 4 a 7 |
| 11. Unidade de `base_speed` | fase 5 (pés, como no SRD) |

## Context

O teste de criar um personagem real (Guerreiro, Humano, Nobre) só com os endpoints atuais mostrou que o modelo não representa o D&D 2024. Os problemas apareceram em todas as etapas:

- **Classe:**
  - não tinha lugar para o ouro (resolvido tratando moeda como item);
  - as features ficam em JSON (`FeatureGrant.effect_data`);
  - não há onde registrar a escolha do Estilo de Luta.
- **Origem:**
  - o banco local estava desatualizado porque a migration squash foi editada;
  - o antecedente Nobre não existe no SRD;
  - `POST /species` sempre dá 500 (`creature_type` existe no model, mas não no schema);
  - `size` aceita um valor só, e o Humano escolhe entre Small e Medium;
  - `special_traits` é JSONB e não aparece na API.
- **Bug já corrigido nesta sessão, ainda sem commit:** lazy load de `item` no equipamento inicial (MissingGreenlet).

O usuário também quer **eliminar todos os campos JSONB** para ter um modelo fixo no banco. Hoje são 12:

| Model | Campos JSONB |
|---|---|
| `Campaign` | `settings` |
| `Character` | `death_saves`, `conditions`, `choices`, `spell_slots_remaining`, `appearance`, `custom_data` |
| `CharacterFeat` | `choices` |
| `FeatureGrant` | `effect_data` |
| `SpeciesDefinition` | `special_traits` |
| `SpellDefinition` | `components` |
| `ItemDefinition` | `properties` |

O desenho parte da leitura dos 13 arquivos de `docs/dnd-5e-srd-markdown-master/`.

**Resultado esperado:** um modelo relacional e extensível (homebrew) que represente o SRD 2024 para personagens e monstros, entregue em fases pela esteira (refinamento → planejamento → dev-tdd → qa).

## Decisões do usuário

- **Escopo:**
  - Entra: o personagem completo (classes, subclasses, espécies com linhagens, antecedentes, talentos, equipamento, magias, features/efeitos, estado de runtime) e **monstros**, com tabelas, models e endpoints próprios.
  - Fica de fora por enquanto: itens mágicos, encontros, armadilhas, venenos e viagem.
- **Endpoints existentes podem mudar** para acomodar o novo modelo.
- **Migrations:** reescrever a squash `c1fcfd7fe014`, absorvendo `a7d3e91b4c52`, e recriar o banco local a cada fase.
- **Idioma:** nomes exatamente como no SRD (inglês), mais um `code` estável. A tradução PT-BR fica para depois.
- **Extensibilidade:**
  - Toda tabela de referência é tabela real, sem enum Python, e tem endpoint de criação. Assim dá para criar tipos de dano, tamanhos, idiomas, alinhamentos etc.
  - O conteúdo do SRD que já existe entra como seed.
- **Dinheiro:**
  - Unidade base é o **ouro**: custos em `cost_gp NUMERIC(10,2)`, onde 1 PC = 0,01 e 1 PE = 0,5.
  - Moedas são itens: PC, PP, PE, PO, PL.
- **Uma informação por coluna:** se algo carrega várias informações, vira tabela própria. Exemplos:
  - os tamanhos possíveis de uma espécie viram `species_size_options`;
  - armas e armaduras viram tabelas próprias, não colunas genéricas em `item_definitions`.
- **Só ganha coluna o que afeta o jogo.**
  - Regra só de referência fica fora: tempo de vestir/tirar armadura, faixa de d12 de idioma, eixos do alinhamento.
  - O que mexe em estatística entra: força mínima da armadura pesada, desvantagem em Furtividade, capacidade de carga por tamanho, dado de vida de monstro por tamanho.
- **Conteúdo de kits:** tabela many-to-one `item_contents`, várias linhas apontando para o mesmo kit.

## Convenções do novo modelo

- **Tabela de referência:**
  - colunas: `code` (PK, string), `name`, `description` (nullable), `source`, `is_homebrew`, `created_by`, e só as colunas que afetam o jogo;
  - endpoints `GET` e `POST` em `/api/compendium/<recurso>`;
  - seed do SRD via `op.bulk_insert` na squash.
- **Entidades de compêndio:** mantêm o padrão atual (`id` uuid, `source`, `is_homebrew`, `created_by`, `created_at`).
- **Referência polimórfica:** sempre FKs tipadas nullable, com `CHECK` "exatamente uma preenchida". Nunca `source_type` + `source_id` soltos.
- **Uma informação por coluna:**
  - dado + tipo de dano vira `dice_count`, `die_size`, `flat_bonus` e `damage_type_code`;
  - alcance "80/320" vira `range_normal_ft` e `range_long_ft`.
- **Mecanismo único de escolha** ("escolha N de…"): `choice` (quantidade e filtro), `choice_option` (opções explícitas) e, do lado do personagem, `character_choice_selection`.

## Modelo alvo por área

### 1. Tabelas de referência (com seed do SRD)

| Tabela | Conteúdo |
|---|---|
| `ability_scores` | já existe |
| `skills` | já existe; ganha `code` |
| `damage_types` | 13 |
| `conditions` + `condition_implications` | 15; Paralyzed implica Incapacitated etc. |
| `creature_types` | 14 |
| `sizes` | `hit_die` (HP de monstro), `carry_multiplier`, `sort_order` |
| `alignments` | 9 + Unaligned |
| `languages` | `rarity` |
| `senses` | 4 |
| `movement_modes` | 5 |
| `weapon_categories` | Simple, Martial |
| `weapon_properties` | 10 |
| `weapon_masteries` | 8 |
| `armor_categories` | Light, Medium, Heavy, Shield |
| `tool_categories` | — |
| `spell_schools` | 8 |
| `recharge_types` | short_rest, long_rest, dawn, initiative, turn |
| `action_types` | action, bonus_action, reaction |
| `character_levels` | nível → XP mínimo, proficiency bonus |
| `challenge_ratings` | CR → XP, proficiency bonus |
| `point_buy_costs` | — |
| `feat_categories` | — |

### 2. Itens (substitui `ItemDefinition.properties`)

**Estrutura base**
- `item_definitions` é a base comum: `name`, `item_type`, `cost_gp`, `weight_lb`, `description`.
  - É ela que inventário, equipamento inicial e kits referenciam.
- Cada tipo de item tem tabela própria, ligada à base por `item_id` (1:1).

**Tabelas por tipo**

| Tabela | Colunas |
|---|---|
| `weapons` | `category_code`, `is_ranged`, `damage_dice_count`, `damage_die_size`, `damage_flat`, `damage_type_code`, `mastery_code` |
| `weapon_property_links` | arma, propriedade, `range_normal_ft`, `range_long_ft`, `versatile_die_size`, `ammunition_item_id` (cada linha guarda só os parâmetros da propriedade dela) |
| `armors` | `category_code`, `base_ac`, `adds_dex_modifier`, `max_dex_modifier`, `strength_requirement`, `stealth_disadvantage` |
| `tools` | `category_code`, `ability_code` |
| `containers` | `capacity_weight_lb` |
| `item_contents` (many-to-one) | `pack_item_id`, `item_id`, `quantity` |

**Moedas:** `item_type = currency`, e o próprio `cost_gp` dá o valor da moeda.

**Proficiências**
- `proficiency_grants` é uma tabela com FKs tipadas: categoria de arma (com propriedade exigida opcional), arma específica, categoria de armadura, ferramenta, categoria de ferramenta, perícia, salvaguarda ou idioma.
- Classes, antecedentes, features e personagem apontam para ela.
- Substitui as tabelas `*_proficiency_options` de texto.

**Plugar itens mágicos depois:** basta criar uma tabela `magic_items` ligada a `item_definitions`, no mesmo padrão.

### 3. Magias (substitui `SpellDefinition.components`)

- **Novas colunas em `spell_definitions`:**
  - `school_code`
  - componentes: `has_verbal`, `has_somatic`, `has_material`
  - tempo de conjuração: `casting_time_unit`, `casting_time_amount`, `ritual`, `reaction_trigger`
  - alcance: `range_type`, `range_distance`, `range_unit`
  - área: `area_shape`, `area_size_ft`
  - duração: `duration_type`, `duration_amount`, `duration_unit`, `concentration`
  - textos: `higher_levels`, `cantrip_upgrade`
- **`spell_materials`:** magia, descrição, `cost_gp`, `consumed`, `per_target`, `quantity`.
- `spell_class_lists` continua.

### 4. Features e efeitos (substitui `FeatureGrant.effect_type` + `effect_data`)

- **`feature_definitions`**
  - Dono por FK tipada: class, subclass, species, lineage, background ou feat.
  - Colunas: `level`, `level_basis`, `name`, `description`, `sort_order`, `replaces_feature_id`.
  - Feature só narrativa tem apenas descrição.
- **`feature_effects`** ("o que afetar" + "como afetar")
  - `operation` e `target_type`.
  - FKs tipadas: skill, ability, damage_type, condition, sense, movement_mode, spell, feat, feature, item, proficiency_grant.
  - Valores: `value`, `dice_count`, `die_size`, `value_basis`, `condition_text`.
  - Cobre "ganhar o talento X", "ganhar a magia X", AC por fórmula, Extra Attack, faixa de crítico, resistências etc.
- **`feature_choices` + `feature_choice_options`**
  - Colunas: quantidade, tipo do pool, filtros (categoria de talento; classe e nível máximo da lista de magias), `swap_rule`.
  - Cobre Estilo de Luta, Skillful, Versatile, Expertise, Weapon Mastery, Metamagic, Invocações.
- **`feature_resources`**
  - Colunas: usos (`value_basis`), `recharge_type`, `short_rest_recovers_one`.
- **`feature_scaling`**
  - Colunas: feature, nível, `dice_count`, `die_size`, `value`.
- **Talentos**
  - Emitem features.
  - `feat_prerequisites` tipada: nível mínimo, atributo mínimo (com grupo OR), possui feature, conjuração.

### 5. Espécies (substitui `special_traits`; corrige `POST /species`)

- `creature_type_code` passa a ser FK e entra no schema de criação.
- `species_size_options`, `species_speeds` e `species_senses` são tabelas.
- `species_lineages` cobre as linhagens de Elf, Gnome e Tiefling e as ancestralidades de Dragonborn e Goliath. Cada linhagem é dona de features.
- Os traços da espécie e da linhagem viram `feature_definitions`.

### 6. Classes

**Atributo primário e perícias**
- `class_primary_abilities` ganha `group_operator` (and/or).
- Nova flag `any_skill`.

**Tabela de níveis da classe**
- `class_table_columns` define as colunas (Rages, Sneak Attack, Cantrips, Prepared Spells, Weapon Mastery…).
- `class_level_values` guarda classe, nível, coluna, `int_value`, `dice_count` e `die_size`.
- `class_level_spell_slots` guarda os slots por nível. O Pact Magic usa a mesma tabela.

**Conjuração (colunas na classe)**
- `spell_ability`
- `slot_progression`, `slot_recovery`
- `prepared_change_rule`, `cantrip_swap_rule`
- `uses_spellbook`

**Multiclasse**
- `multiclass_spell_slots`
- `class_multiclass_proficiencies`

**Equipamento inicial**
- Opção, item, quantidade. O ouro é um item.

### 7. Antecedentes

- A ferramenta passa a usar `proficiency_grant`, ou uma escolha dentro de uma categoria (por exemplo, o Gaming Set do Soldier).
- Novo `feat_spell_list_class_id`, para "Magic Initiate (Cleric)".

### 8. Personagem (remove os JSONB de `Character`, `CharacterFeat` e `Campaign`)

**Novas colunas em `characters`**

| Coluna | Observação |
|---|---|
| `death_save_successes`, `death_save_failures` | CHECK 0..3 |
| `is_stable` | — |
| `heroic_inspiration` | — |
| `alignment_code` | — |
| `size_code` | tamanho escolhido |
| `ability_generation_method` | — |
| campos de aparência | só os da etapa "Details" de `character-creation.md` que forem confirmados na fase |

**Novas tabelas**
- `character_conditions`
- `character_spell_slots`, com `slot_kind` e `max_slots`
- `character_choice_selections`: substitui `choices`, `custom_data` e `CharacterFeat.choices`
- `character_languages`
- `character_ability_increases`, com a origem do aumento
- `character_level_ups`, com `hp_roll` e `used_fixed`
- `character_proficiencies`
- `character_weapon_masteries`

**Ajustes**
- `CharacterResource` passa a apontar para `feature_resources`.
- `Campaign.settings` é removido. Colunas tipadas entram quando houver configurações definidas.

### 9. Monstros (novo)

**`monsters`**

| Grupo | Colunas |
|---|---|
| Identificação | `name`, `group_name`, `creature_type_code`, `alignment_code`, `is_animal` |
| Defesa | `armor_class` |
| Iniciativa | `initiative_bonus` |
| Pontos de vida | `hp_average`, `hp_dice_count`, `hp_die_size`, `hp_bonus` |
| Desafio | `challenge_rating_code`, `xp_override`, `xp_in_lair` |
| Percepção | `passive_perception` |
| Ações lendárias | `legendary_action_uses`, `legendary_action_uses_in_lair` |
| Comunicação | `telepathy_ft` |
| Enxame | `swarm_unit_size_code` |

**Tabelas filhas**

| Tabela | Conteúdo |
|---|---|
| `monster_size_options` | tamanhos possíveis |
| `monster_tags` | — |
| `monster_ability_scores` | atributo, `score`, `saving_throw_bonus` |
| `monster_skills` | perícia, bônus |
| `monster_speeds` | modo, pés, `hover` |
| `monster_senses` | sentido, alcance |
| `monster_languages` | idioma, `can_speak` |
| `monster_damage_affinities` | tipo, resistance/vulnerability/immunity |
| `monster_condition_immunities` | — |
| `monster_gear` | item, quantidade |

**Ações e traços**
- `monster_actions`, com as colunas:
  - `section`: trait, action, bonus_action, reaction ou legendary;
  - `name`, `description`, `sort_order`;
  - `usage_type`, `uses_per_day`, `uses_per_day_in_lair`, `recharge_min`;
  - `trigger_text`.
- Sub-tabelas de uma ação:
  - `monster_action_attacks`: corpo a corpo ou à distância, bônus, alcance e distância normal/longa;
  - `monster_action_saves`: atributo, CD, `half_on_success`;
  - `monster_action_damages`: N por ação, com outcome, dados, bônus e tipo;
  - `monster_action_conditions`: condição, `escape_dc`.
- Conjuração do monstro:
  - `monster_spellcasting`: atributo, CD, bônus de ataque;
  - `monster_spellcasting_spells`: magia, frequência, usos, nível.

**Estado em campanha**
- `campaign_monsters`: instância do monstro com `current_hp`, `temp_hp` e condições (via tabela).

**Seed e endpoints**
- Seed: as tabelas de referência entram já. O import dos 300+ stat blocks é etapa opcional, com parser dos `.md`.
- Endpoints: CRUD em `/api/compendium/monsters`.

## Fases de execução (cada uma pela esteira)

Antes de tudo, commitar o que está pendente: a correção do lazy load, os testes e `docs/plans/2026-10-03-...md`.

| Fase | Conteúdo |
|---|---|
| 0 | Registrar as melhorias em `docs/plans/2026-10-04-redesenho-modelo-srd.md`: aprendizados por etapa da criação, o modelo alvo e as decisões acima. Atualizar `2026-10-03-...md` e o relatório de gaps `2026-08-13`, marcando qual fase resolve cada item |
| 1 | Tabelas de referência: padrão `code`, GET/POST e seed do SRD |
| 2 | Itens: tabelas por tipo, `item_contents`, moedas, `cost_gp`, `proficiency_grants`. Sai o JSONB `properties` |
| 3 | Magias estruturadas e `spell_materials`. Sai o JSONB `components` |
| 4 | Features, efeitos, escolhas, recursos e escalonamento; talentos emitem features. Sai `effect_data` |
| 5 | Espécies e linhagens. Sai `special_traits`; corrige o POST |
| 6 | Classes: tabela de níveis, slots de magia, conjuração e multiclasse |
| 7 | Personagem e campanha: saem os JSONB restantes; entram as tabelas de escolhas e de estado de runtime |
| 8 | Monstros: model, endpoints, `campaign_monsters` e import opcional dos stat blocks |
| 9 | Reteste ponta a ponta: Guerreiro + Humano + Soldier (e um monstro), só pelos endpoints e sem inventar dados |

## Arquivos críticos

- `backend/app/db/models/`: `compendium.py`, `character.py`, `campaign.py` e o novo `monster.py`
- `backend/app/schemas/` e `backend/app/api/`: equivalentes aos models, mais o novo `monsters`
- `backend/app/services/compendium.py`: generalizar `_resolve_options`, `resolve_skills` e `ensure_ability_score_options` para o padrão `code`
- `backend/app/enums.py`: `AbilityScore` e `CreatureSize` saem; quem valida passa a ser a FK
- `backend/alembic/versions/c1fcfd7fe014_initial_schema.py` (reescrita) e `a7d3e91b4c52` (absorvida)
- `backend/tests/integration/conftest.py`: helpers `seed_*`

## Verificação

- **Toda fase:**
  - `python -m pytest -q` em `backend/`;
  - banco recriado e `alembic upgrade head` seguido de `alembic check` sem drift.
- **Fim da fase 7:** `grep -rn JSONB backend/app backend/alembic` não retorna nada.
- **Fase 9:** com o container no ar e o schema recriado, cadastrar pelos endpoints Guerreiro, Humano (tamanho à escolha; Skillful e Versatile como escolhas), Soldier, Savage Attacker e um monstro do SRD (ex.: Goblin Warrior). Depois criar o personagem e confirmar que tudo é representável sem adaptação.
