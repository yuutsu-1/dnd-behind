# Especificação Refinada — Fase 4: features, efeitos, escolhas, recursos e escalonamento; talentos e classes emitem features (sai o JSONB `FeatureGrant.effect_data`)

Faz parte do redesenho descrito em `2026-10-04-redesenho-modelo-srd.md` (seção "4. Features e efeitos"). A ideia de origem está em `2026-10-03-teste-guerreiro-e-feature-effects.md`.

Segue os padrões das fases 1 a 3:
- referências com `code` no router genérico, com homebrew com escopo;
- entidades globais com `id` uuid, PATCH/DELETE só do autor e só homebrew;
- seed na squash única `c1fcfd7fe014` com uuid5;
- dados versionados num módulo gerado por extrator rodado à mão (padrão `scripts/extract_srd_spells.py` → `app/db/seed/srd_spells.py`);
- testes HTTP com httpx + ASGITransport;
- **nenhum teste lê `docs/`**.

**Critério geral:** só ganha estrutura o que afeta a mecânica ou leva informação específica à ficha. O resto fica em `description`.

## Decisões do usuário (gate #1, 2026-10-05)

| # | Decisão | Exemplo |
|---|---|---|
| D1 | Estruturar concessões e números de ficha; o que é situacional fica em texto. Concessões: talento, magia, proficiência, expertise, sentido, velocidade, resistência e imunidade, ASI. Números de ficha: bônus fixos, `set`, vantagem em teste fixo, cura com fórmula, recursos | Defense = +1 CA com `condition_text`; Great Weapon Fighting e Savage Attacker = texto |
| D2 | Fórmula = `value_bases` + multiplicador + dados + fixo + mín./máx. Os números por nível vêm de `feature_scaling` | Second Wind = 1d10 + `class_level`; usos 2/3/4 por scaling |
| D3 | **Seed dos 17 talentos + classe Fighter + subclasse Champion, com todas as suas features** (ver "Seed"). As outras 11 classes ficam para a fase 6 | — |
| D4 | Nova referência `feature_kinds` (`fighting_style`, `spellcasting`), usada por features e por pré-requisitos | — |
| D5 | **Magic Initiate fica só em texto**: as features existem, sem efeitos estruturados. A parametrização ("Magic Initiate (Cleric)") vai para a fase 7 | — |
| D6 | Tabela filha `feature_resource_recharges` com 1..N linhas (tipo de recarga + quanto recupera). O seed grava literalmente o que o SRD diz | Second Wind = (short_rest, 1) + (long_rest, todos) |
| D7 | Só o autor de um dono homebrew pode adicionar ou alterar features dele. Dono SRD é imutável (403) | — |
| D8 | **Features embutidas no dono.** Talento, classe e subclasse são criados e editados com as features no mesmo payload. Não existe POST/PATCH/DELETE próprio de feature | — |

**Observação do usuário sobre D6:** no jogo, tudo que recupera num descanso curto também recupera no longo. Isso é regra do motor (fora do redesenho). O seed registra só o que o SRD escreve.

## Objetivo

Trocar o `FeatureGrant` atual (`source_type`/`source_id` soltos, `effect_type` em texto e `effect_data` JSONB) por um modelo relacional:

- **`feature_definitions`**: o dono é uma FK tipada.
- **`feature_effects`**: "o que afetar" + "como afetar", com FKs tipadas.
- **`feature_choices`** + **`feature_choice_options`**: "escolha N de…".
- **`feature_resources`** + **`feature_resource_recharges`**: usos e recargas.
- **`feature_scaling`**: valores por nível.

Os talentos ganham categoria como FK e pré-requisitos tipados. Talentos, classes e subclasses passam a carregar suas features.

## Escopo

### Incluído

**1. `feature_definitions`** (substitui `feature_grants`)

| Grupo | Colunas e regras |
|---|---|
| Identidade | `id`, `name`, `description`, `sort_order` |
| Dono | `class_id`, `subclass_id`, `feat_id`: FKs nullable, ON DELETE CASCADE, CHECK "exatamente uma". `species_id`/`lineage_id` entram na fase 5 |
| Nível | `level` 1..20: obrigatório para dono classe ou subclasse; NULL para dono talento |
| Ação | `action_type_code` (FK `action_types`, nullable). Ex.: Second Wind = `bonus_action` |
| Tipo | `feature_kind_code` (FK `feature_kinds`, nullable) |
| Substituição | `replaces_feature_id` (FK para a própria tabela, nullable). Ex.: Two Extra Attacks substitui Extra Attack; Superior Critical substitui Improved Critical |
| Opção de escolha | `is_choice_option` (bool): a feature só existe como opção de escolha, não é concedida automaticamente (Metamagic, Invocations, conteúdo da fase 6) |
| Origem | `source`, `is_homebrew`, `created_by`, `created_at`. Os valores são herdados do dono |

**2. `feature_effects`** (N por feature, ON DELETE CASCADE)

- `id`, `feature_id`, `sort_order`.
- `operation_code`: FK `effect_operations`.
- `target_code`: FK `effect_targets`, nullable.
- **Alvo tipado**, nullable, no máximo um: `feat_id`, `spell_id`, `granted_feature_id`, `proficiency_grant_id`, `skill_code`, `ability_code`, `damage_type_code`, `condition_code`, `sense_code`, `movement_mode_code`, `item_id`.
- **Valor:**
  - `value`, `dice_count`, `die_size`;
  - `value_basis_code` (FK `value_bases`), `value_basis_ability_code`;
  - `value_multiplier` (default 1), `min_value`, `max_value`.
- **Magia concedida:** `spell_ability_code`, `always_prepared` (bool) e `resource_id` (FK `feature_resources`, nullable).
- `condition_text`: texto de ficha. Ex.: "while wearing Light, Medium, or Heavy armor".
- **Regra:** o efeito tem **ou** um alvo tipado fixo **ou** exatamente uma `feature_choice` que fornece o alvo.

**3. `feature_choices`** (0..1 por efeito)

- `id`, `effect_id`, `choose_count` ≥ 1, `allow_repeat` (bool).
- `pool_type_code`: FK `choice_pool_types`.
- **Filtros**, todos nullable: `feat_category_code`, `spell_list_code`, `spell_level`, `weapon_category_code`, `tool_category_code` e `spell_list_from_choice_id` (FK para `feature_choices`).
- `swap_rule_code`: FK `choice_swap_rules`, nullable.
- **`feature_choice_options`**: lista explícita de opções. Colunas `choice_id` + uma FK tipada entre `feat_id`, `spell_id`, `skill_code`, `tool_type_code`, `ability_code`, `item_id`, `spell_list_code` e `feature_id`, com CHECK "exatamente uma".

**4. `feature_resources`** (0..N por feature)

- `id`, `feature_id`, `name` (NOT NULL; nome na ficha).
- Usos: `value`, `value_basis_code`, `value_basis_ability_code`, `value_multiplier`, `min_value`.
- **`feature_resource_recharges`** (1..N por recurso): `resource_id`, `recharge_type_code` (FK `recharge_types`) e `recovers` (int nullable; NULL = recupera todos). Não pode repetir o mesmo `recharge_type` no mesmo recurso.

**5. `feature_scaling`**

- `id` + FK tipada com CHECK "exatamente uma" entre `effect_id`, `choice_id` e `resource_id`.
- `level`, `value`, `dice_count`, `die_size`.
- O nível é o de classe se o dono for classe ou subclasse; para talento, o nível do personagem. É derivado, sem coluna própria.
- Cada linha vale do seu nível até a linha seguinte.
- Níveis únicos por alvo e ≥ ao nível da feature.

**6. Talentos**

- `feat_definitions`:
  - `category` vira `category_code` (FK `feat_categories`);
  - saem `level_prerequisite` e `prerequisite_description`;
  - `name` deixa de ser único;
  - `repeatable` fica.
- **`feat_prerequisites`** (N por talento):
  - `id`, `feat_id`, `or_group` (int): linhas no mesmo grupo valem como OU; grupos diferentes, como E;
  - alvo com CHECK "exatamente um": `min_character_level`, **ou** `ability_code` + `min_score` (1..30), **ou** `feature_kind_code`.

**7. Novas referências**

Padrão `code`, router genérico, homebrew com escopo, seed do SRD.

| Referência | Seed |
|---|---|
| `effect_operations` | `grant`, `expertise`, `ability_score_increase`, `damage_resistance`, `damage_immunity`, `condition_immunity`, `bonus`, `set`, `advantage`, `heal`, `spellcasting_ability`, `spell_list` |
| `effect_targets` | `armor_class`, `initiative`, `attack_roll`, `damage_roll`, `hit_points`, `hit_point_max`, `speed`, `critical_range`, `attacks_per_action`, `saving_throw`, `ability_check`, `death_saving_throw` |
| `value_bases` | `proficiency_bonus`, `ability_modifier`, `class_level`, `character_level` |
| `choice_pool_types` | `feat`, `spell`, `skill`, `tool_type`, `skill_or_tool`, `ability_score`, `weapon`, `spell_list`, `feature` |
| `choice_swap_rules` | `on_class_level_up`, `on_level_up_one`, `on_long_rest_one` |
| `feature_kinds` | `fighting_style`, `spellcasting` |

`REFERENCE_MODELS` passa de 27 para **33**, e o CHECK de shares é atualizado.

**8. Seed (D3)**

Os dados são gerados por extrator e ficam versionados (ex.: `app/db/seed/srd_feats.py` e `app/db/seed/srd_fighter.py`). A migration não lê `docs/`.

- **17 talentos** de `feats.md` (4 origin, 2 general, 4 fighting_style, 7 epic_boon), com pré-requisitos e features.
  - **Cada bloco em itálico vira uma feature.** Ex.: Alert → "Initiative Proficiency" + "Initiative Swap".
  - Talento sem blocos vira uma única feature com o nome do talento.
  - O bloco "_Repeatable._" só define `repeatable`.
- **Classe Fighter** (`classes.md`, Core Fighter Traits), no modelo atual da classe:
  - `hit_die` 10, `primary_ability` str/dex;
  - grants: saves STR e CON, armas Simple e Martial, armaduras Light, Medium, Heavy e Shield;
  - `skill_choices` 2, com as 9 perícias da lista;
  - equipamento inicial A/B/C com os itens do seed.
  - A distinção "ou/e" do atributo primário e a tabela de níveis ficam para a fase 6.
- **Features do Fighter, níveis 1–20** (`classes.md` l. ~4788–4860):
  - Fighting Style;
  - Second Wind;
  - Weapon Mastery;
  - Action Surge;
  - Tactical Mind;
  - Fighter Subclass (só texto);
  - Ability Score Improvement nos níveis 4, 6, 8, 12, 14 e 16 (uma feature por nível);
  - Extra Attack;
  - Tactical Shift;
  - Indomitable;
  - Tactical Master;
  - Two Extra Attacks;
  - Studied Attacks;
  - Epic Boon (19);
  - Three Extra Attacks (20).
- **Subclasse Champion e suas features** (`classes.md` l. ~4860–4890):
  - Improved Critical (3);
  - Remarkable Athlete (3);
  - Additional Fighting Style (7);
  - Heroic Warrior (10);
  - Superior Critical (15);
  - Survivor (18).
- **Estrutura de cada feature:**
  - **Estruturado:**
    - Fighting Style e Additional Fighting Style: `grant` de talento, por escolha na categoria `fighting_style`;
    - Fighting Style: swap `on_class_level_up`;
    - Ability Score Improvement e Epic Boon: `grant` de talento, por escolha na categoria correspondente;
    - Second Wind: `heal` 1d10 + `class_level`;
    - Second Wind: recurso de 2 usos, com scaling 4→3 e 10→4 e recargas (short_rest, 1) + (long_rest, todos);
    - Weapon Mastery: escolha `weapon` de 3, scaling 4→4, 10→5 e 16→6, swap `on_long_rest_one`;
    - Action Surge: recurso de 1 uso, scaling 17→2;
    - Indomitable: recurso de 1 uso, scaling 13→2 e 17→3;
    - Extra Attack, Two Extra Attacks e Three Extra Attacks: `set` em `attacks_per_action` 2, 3 e 4, com `replaces_feature_id`;
    - Improved Critical e Superior Critical: `set` em `critical_range` 19 e 18, com `replaces_feature_id`;
    - Remarkable Athlete: `advantage` em `initiative` e em `ability_check` de athletics.
  - **Recargas:** o tipo e a quantidade de cada recurso seguem literalmente o texto do SRD.
  - **Só texto** (pela regra de D1): Tactical Mind, Tactical Shift, Tactical Master, Studied Attacks, Heroic Warrior, Survivor e Fighter Subclass. Se o extrator ou o planejador encontrar algo dessas features que seja claramente número de ficha, deve reportar, nunca inventar.

**9. API (D8: features embutidas no dono)**

- **`/api/compendium/feats`**
  - GET de lista com filtros `category` e `search`.
  - GET de detalhe (novo), com pré-requisitos e features completas.
  - POST com `prerequisites` e `features` (cada feature já com efeitos, escolhas, opções, recursos, recargas e scaling).
  - PATCH: as coleções enviadas substituem o conjunto inteiro.
  - DELETE.
- **`/api/compendium/classes`**: POST passa a aceitar `features`. Ganham **PATCH** (substitui `features` e os demais campos enviados) e **DELETE**. GET de lista e detalhe trazem as features.
- **`/api/compendium/subclasses`**: mesmo padrão. Hoje só existem GET e POST, sem detalhe. Ganham GET de detalhe, PATCH e DELETE, com as features.
- **`/api/compendium/features`**: só leitura (GET de lista e de detalhe).
  - Filtros: `class_id`, `subclass_id`, `feat_id`, `level`, `kind`.
  - Ordem: dono, `level` (nulos primeiro), `sort_order`, `name`, `id`.
  - POST, PATCH e DELETE nessa rota dão **405**.
- **`/api/compendium/feature-grants`**: removida (404).

**10. Removidos**

- `feature_grants`, `FeatureGrant`, `FeatureGrantOut` e `FeatureGrantCreate`.
- As colunas `effect_type` e `effect_data`.
- As colunas de talento removidas no item 6.

### Fora de escopo

- **Espécies e linhagens** como donas de features: fase 5.
- **Antecedente:** não tem features no SRD 2024. A parametrização de talento fica para a fase 7.
- **As outras 11 classes e suas subclasses e features** (fase 6). Também ficam para a fase 6: a tabela de níveis da classe, os slots, a conjuração, a distinção "ou/e" de `primary_ability` e "coluna da tabela de classe" como base de valor.
- **Lado do personagem** (fase 7):
  - `character_choice_selections`;
  - `CharacterResource` apontando para `feature_resources`;
  - `CharacterFeat.choices`;
  - validação de pré-requisito ao pegar um talento;
  - repetição do Magic Initiate com outra lista.
- **Monstros** (fase 8).
- **Motor que aplica efeitos à ficha**, incluindo a regra "descanso curto ⊂ descanso longo".
- **Magic Initiate estruturado** (D5): fica em texto.

## Regras de negócio

### Operações e alvos

Os codes do seed validam o alvo esperado (422). Codes homebrew só exigem "no máximo um alvo tipado".

| Operação | Alvo esperado | Exemplo |
|---|---|---|
| `grant` | `feat_id`, `spell_id`, `granted_feature_id`, `proficiency_grant_id`, `sense_code` + `value` (pés) ou `movement_mode_code` + `value` | Boon of Truesight: Truesight 60; Fighting Style |
| `expertise` | `skill_code`, ou escolha `skill` | — |
| `ability_score_increase` | `ability_code`, ou escolha `ability_score`, com `value` e `max_value` | ASI: escolha de 2 com `allow_repeat`, +1, teto 20; Boons: teto 30 |
| `damage_resistance` / `damage_immunity` | `damage_type_code` | — |
| `condition_immunity` | `condition_code` | — |
| `bonus` | `target_code` + valor ou fórmula | Defense: `armor_class` +1; Archery: `attack_roll` +2; Alert: `initiative` + `proficiency_bonus` |
| `set` | `target_code` + `value` | Extra Attack: `attacks_per_action` 2; Improved Critical: `critical_range` 19 |
| `advantage` | `target_code`, opcionalmente com `skill_code` ou `ability_code` | Remarkable Athlete |
| `heal` | `target_code=hit_points` + dados ou fórmula | Second Wind |
| `spellcasting_ability`, `spell_list` | escolha com opções | Fica no catálogo; o Magic Initiate não usa (D5) |

**Ficam só em texto:** Initiative Swap, Punch and Grab, Fast Wrestler, Great Weapon Fighting, Two-Weapon Fighting, Savage Attacker, Magic Initiate, Overcome Defenses, Overwhelming Strike, Free Casting, Blink Steps, Peerless Aim e as features "Tactical" e "Studied" do Fighter, entre outras com o mesmo perfil.

### Fórmula

`valor = (dice_count d die_size) + base × multiplier + value`, limitado por `min_value` e `max_value`.

Validações (422):
- `ability_modifier` exige `value_basis_ability_code`;
- `dice_count` e `die_size` vêm juntos;
- `die_size` ∈ {4, 6, 8, 10, 12, 20}.

### Substituição

- `replaces_feature_id` precisa ter o mesmo dono e um nível menor (422).
- A feature substituída deixa de valer a partir do nível da nova.

### Escolhas

- `choose_count` ≥ 1.
- As opções precisam ser coerentes com o `pool_type` (422).
- Os filtros precisam ser compatíveis com o pool. Ex.: `feat_category_code` só vale com pool `feat` (422).
- `spell_list_from_choice_id` precisa apontar para uma escolha de pool `spell_list`.

### Pré-requisitos do seed

| Talento | Pré-requisito |
|---|---|
| ASI | nível 4 |
| Grappler | nível 4 E (STR 13 OU DEX 13) |
| 4 Fighting Styles | `feature_kind=fighting_style` |
| 7 Boons | nível 19 |
| Boon of Spell Recall | nível 19 E `feature_kind=spellcasting` |

A feature Fighting Style do Fighter e a Additional Fighting Style do Champion têm `kind=fighting_style`.

### Identidade

- **Seed:** `source='srd'`, `is_homebrew=false`, `created_by=NULL`.
- **uuid5:** cada tipo de entidade tem seu próprio namespace (talentos, classe, subclasse e features).
- **Nome da feature no uuid5:** composto com o nome do dono e o nível, porque `name` não é único.

### Endpoints

- **Escrita embutida:** POST e PATCH de talento, classe e subclasse validam o payload inteiro, incluindo as features e tudo o que vem dentro delas.
  - Qualquer erro devolve **422** (forma ou coerência) ou **400** (code ou id inexistente ou invisível) e não grava nada.
  - No PATCH, uma coleção enviada substitui a anterior inteira. A coerência é validada no estado final.
- **Matriz de PATCH e DELETE** (talento, classe e subclasse):

  | Situação | Status |
  |---|---|
  | SRD | 403 |
  | Homebrew de outro autor | 403 |
  | Inexistente | 404 |
  | Sem token | 401 |

- **DELETE responde 409 quando o dono está em uso:**
  - **talento:** referenciado por `background_definitions.feat_id`, `character_feats`, um efeito de outra feature ou uma opção de escolha;
  - **classe:** usada por `character_classes`, por uma subclasse ou por um efeito ou opção;
  - **subclasse:** usada por `character_classes`.
- **DELETE do dono sem uso:** remove as features em cascata. Se alguma dessas features for referenciada de fora do dono (`granted_feature_id`, opção, `replaces_feature_id`), responde **409**.
- **DELETE de referência homebrew em uso:** 409. Vale para as 6 referências novas e para as já existentes usadas por features.

## Casos de borda e erros

### 422
- **Dono e nível:** nenhum dono, ou mais de um. `level` ausente quando o dono é classe ou subclasse, presente quando é talento, ou fora de 1..20.
- **Efeito:** alvo fixo e escolha ao mesmo tempo; nenhum dos dois quando a operação exige alvo; alvo incompatível com a operação.
- **Fórmula:** valores incoerentes (ver "Fórmula").
- **Escolha:** `choose_count` < 1; opção incompatível com o pool; filtro inválido para o pool.
- **Recurso:** sem nenhuma recarga; `recovers` < 1; recarga duplicada.
- **Scaling:** nível duplicado ou menor que o da feature; mais de um alvo.
- **Substituição:** `replaces_feature_id` de outro dono ou de nível maior ou igual.
- **Pré-requisito:** 0 alvos ou mais de 1; `min_score` fora de 1..30.
- **Campos:** proibidos ou desconhecidos.

### Demais códigos
- **400:** code inexistente ou invisível (regra 6f); `class_id`, `subclass_id`, `feat_id`, `spell_id`, `item_id`, `granted_feature_id` ou `proficiency_grant_id` inexistente; `item_id` de escolha `weapon` que não é arma.
- **403, 404 e 409:** conforme a seção "Endpoints".
- **405:** escrita em `/features`.

### Seed
Um talento, bloco ou feature do Fighter/Champion que o extrator não reconhece faz o processo falhar explicitamente. Nada é pulado.

## Impacto em dados e modelos

- **Banco e migration:** o banco é recriado. A squash `c1fcfd7fe014` é reescrita e continua sendo a única revisão.
- **`FeatDefinition`:** muda como descrito no item 6.
  - Adaptar `FeatOut`/`FeatCreate` e criar `FeatUpdate`.
  - Adaptar `seed_feat` em `tests/integration/conftest.py` e `tests/unit/test_compendium_models.py`, que hoje usa `category="origin"`.
- **Schemas de classe e subclasse:** ganham `features`, Update e Out completos.
- **`BackgroundDefinition.feat_id`:** sem mudança. Passa a bloquear o DELETE do talento (409).
- **`CharacterFeat` e `CharacterResource`:** sem mudança (fase 7).
- **Cenário de teste manual:** já existe no banco de dev uma classe homebrew "Fighter", criada pelo cenário da fase 2. Com o seed do Fighter SRD, o cenário passa a usar a classe do seed.
- **JSONB restante:** depois desta fase, `grep JSONB backend/app/db/models/compendium.py` só mostra `SpeciesDefinition.special_traits`.

## Permissões

- **GET:** autenticação opcional. Token inválido dá 401.
- **POST de talento, classe ou subclasse:** qualquer usuário logado. O resultado é homebrew com o autor gravado.
- **PATCH e DELETE:** só o autor, só homebrew (D7).
- **Referências novas:** seguem a matriz da fase 1.
- Não existe papel admin.

## Critérios de aceite

- [ ] **Migration:** em banco novo, `alembic upgrade head` aplica só `c1fcfd7fe014`, e `alembic check` não aponta drift.
- [ ] **Limpeza:**
  - `grep -rn "feature_grants\|FeatureGrant\|effect_data\|level_prerequisite\|prerequisite_description" backend/app backend/alembic` volta vazio;
  - `GET /feature-grants` dá 404;
  - escrita em `/features` dá 405.
- [ ] **Estrutura:** CHECK "exatamente um" em dono, opções, scaling e pré-requisitos. Nenhuma tabela nova usa JSONB.
- [ ] **Referências:** as 6 novas respondem 200 sem token, com o seed. DELETE de `effect_targets` homebrew em uso dá 409.
- [ ] **Seed de talentos:** 17 no total (4/2/4/7 por categoria), com estes valores pontuais:

  | Talento | Esperado |
  |---|---|
  | Grappler | 2 grupos de pré-requisito; ASI STR/DEX +1, teto 20 |
  | Archery | `bonus attack_roll +2`; pré-requisito `fighting_style` |
  | Defense | `bonus armor_class +1` com `condition_text` |
  | Alert | "Initiative Proficiency" estruturada; "Initiative Swap" só texto |
  | ASI | escolha `ability_score` de 2, com `allow_repeat`; nível 4; `repeatable` |
  | Skilled | escolha `skill_or_tool` de 3; `repeatable` |
  | Boon of Truesight | `grant` truesight 60 + ASI teto 30 |
  | Boon of Fate | 3 recargas |
  | Boon of Spell Recall | pré-requisitos nível 19 + `spellcasting` |
  | Magic Initiate | features só em texto (D5) |

- [ ] **Seed do Fighter e do Champion:**
  - o Fighter tem os traços e o equipamento da fase 2 e todas as features dos níveis 1–20, com ASI em 6 níveis;
  - o Champion tem as 6 features;
  - os valores estruturados batem com o item 8 (Second Wind, Weapon Mastery, Action Surge, Indomitable, Extra Attack ×3, Improved/Superior Critical, Remarkable Athlete, Fighting Style/Additional com `kind`);
  - as features "só texto" não têm efeitos;
  - o detalhe de `/classes/{fighter}` e o de `/subclasses/{champion}` trazem tudo.
- [ ] **Escrita embutida:**
  - POST de talento homebrew com 2 features (efeito, escolha, recurso com 2 recargas e scaling) dá 201 e o detalhe ecoa tudo;
  - PATCH substitui as features;
  - classe e subclasse homebrew seguem o mesmo fluxo;
  - cada regra 422 tem teste;
  - code invisível dá 400;
  - nada é gravado quando há erro.
- [ ] **Matriz de PATCH/DELETE** coberta para talento, classe e subclasse. Os 409 de uso estão cobertos (talento usado por antecedente; classe usada por personagem; feature referenciada fora do dono).
- [ ] **Testes:** `python -m pytest -q` passa.

## Suposições

- Sem coluna `level_basis`: o nível é derivado do dono.
- Recargas são registradas literalmente como estão no SRD.
- Shadowy Form vira 11 linhas de `damage_resistance` com `condition_text`. Se o QA julgar isso inferência, vira só texto.
- "Once per turn" e "until the start of your next turn" ficam em texto.
- Expertise exige proficiência prévia, mas essa validação é feita no personagem (fase 7).
- O nome de talento e de feature não é único.
- O DELETE de classe ou subclasse remove as features em cascata.

## Perguntas em aberto (não bloqueiam)

- Metamagic e Eldritch Invocations (`is_choice_option` + pool `feature`): fase 6.
- Fonte da verdade entre a coluna da tabela de classe e `feature_scaling`: fase 6. A recomendação é a coluna ser derivada do scaling.
- `CharacterFeat.source` e as escolhas concretas do personagem: fase 7.
