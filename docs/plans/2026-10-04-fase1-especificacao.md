# Especificação Refinada — Fase 1: tabelas de referência no padrão `code` (SRD 2024), com homebrew com escopo

Aprovada pelo usuário em 2026-10-04 (gate humano #1). Faz parte do redesenho em
`2026-10-04-redesenho-modelo-srd.md`.

> **Ajuste do usuário no gate #1 (prevalece sobre o texto abaixo):** o vínculo homebrew↔campanha
> é **uma única tabela many-to-many**, com colunas **`resource_table` | `resource_key` | `campaign_id`**,
> não uma tabela por recurso:
> - `resource_table` diz a qual tabela de referência a linha pertence;
> - `resource_key` é o code (ou a chave numérica, convertida para string) da linha naquela tabela;
> - `campaign_id` é FK para `campaigns`.
>
> Toda menção a `<tabela>_campaign_shares` neste documento passa a significar essa tabela única.
>
> Não existe FK para o recurso. Por isso, ao apagar uma entrada homebrew, a aplicação remove os shares
> dela; não há cascade de banco desse lado. Do lado de `campaigns`, a FK continua com cascade.

## Objetivo

Hoje as lookups são ad-hoc (texto livre com get-or-create) e há enums Python (`AbilityScore`, `CreatureSize`). Esta fase troca tudo isso por tabelas de referência reais, com estas características:

- todas no mesmo padrão: PK `code` string;
- já preenchidas (seed) com o SRD 2024;
- CRUD de homebrew em `/api/compendium/<recurso>`:
  - a leitura mostra só o que o usuário enxerga;
  - criar, editar e apagar é só para o autor;
  - o autor pode compartilhar a entrada com campanhas onde é DM.

Classe, antecedente, personagem e espécie passam a ser validados por FK e por visibilidade.

## Escopo

### Incluído

- **Tabelas de referência:** as 22 do plano, mais `condition_implications`:
  - `ability_scores`, `skills`, `damage_types`, `conditions`, `creature_types`, `sizes`;
  - `alignments`, `languages`, `senses`, `movement_modes`;
  - `weapon_categories`, `weapon_properties`, `weapon_masteries`, `armor_categories`, `tool_categories`;
  - `spell_schools`, `recharge_types`, `action_types`;
  - `character_levels`, `challenge_ratings`, `point_buy_costs`, `feat_categories`.
- **Tabela transitória** `tool_proficiency_options`, já no padrão `code`, válida até a fase 2.
- **Compartilhamento** homebrew↔campanha (ver o ajuste no topo).
- **Endpoints por recurso:**
  - `GET` lista (`?search=`);
  - `GET /{chave}`;
  - `POST`;
  - `PATCH /{chave}`;
  - `DELETE /{chave}`.
- **Seed** do SRD dentro da migration squash reescrita `c1fcfd7fe014`, que absorve `a7d3e91b4c52` (o arquivo dela é apagado). O banco de dev é recriado.
- **Migração das lookups existentes:**

  | Antes | Depois |
  |---|---|
  | `ability_score_options` | `ability_scores` (codes `str`/`dex`/`con`/`int`/`wis`/`cha`) |
  | `skill_definitions` | `skills`, com PK `code`; `skill_id` vira `skill_code` em toda a API |
  | proficiência de armadura | FK para `armor_categories` |
  | proficiência de arma | FK para `weapon_categories` |
  | proficiência de ferramenta | FK para `tool_proficiency_options` |

- **Remoção de `AbilityScore` e `CreatureSize`** de `app/enums.py`. A validação passa para FK em:
  - `SpeciesDefinition.size_code`;
  - `ClassDefinition.spell_ability`;
  - tabelas de associação de classe e de antecedente;
  - `CharacterAbilityScore`;
  - `CharacterSkill`.
- **Fim do get-or-create implícito:** saem `_resolve_options`, `ensure_ability_score_options` e `resolve_skills` nessa função.

### Fora de escopo

- `proficiency_grants` e itens: fase 2.
- FK `spell_definitions.school`: fase 3.
- FK `feat_definitions.category`: fase 4. A tabela `feat_categories` já é criada e semeada, mas o campo continua texto.
- `creature_type` como FK e correção do `POST /species`: fase 5.
- `species_size_options`: fase 5.
- Alinhamento, idiomas e tamanho do personagem: fase 7.
- `CharacterResource.reset_on`.
- Monstros: fase 8.
- Escopo/visibilidade de entidades (classes, antecedentes, espécies, talentos, magias, itens): continuam globais.
- Tradução PT-BR.
- Dialetos de Primordial.
- Remoção de JSONB.
- Coluna `space_ft` em `sizes`.
- Coluna `xp` em `challenge_ratings`.

## Regras de negócio

### Padrão comum

- **Colunas:**
  - `code` (PK, string até 50);
  - `name` (NOT NULL, **não é único**);
  - `description` (TEXT, nullable);
  - `source`, `is_homebrew`;
  - `created_by` (FK `users.id`, nullable);
  - colunas de jogo de cada tabela.

  Não há `id` uuid nem `created_at`.
- **Exceção:** `character_levels` e `point_buy_costs` usam chave numérica e não têm `name` nem `description`.
- **Formato do `code`:** snake_case minúsculo, regex `^[a-z0-9]+(_[a-z0-9]+)*$`. É único globalmente e colisão dá 409.
- **`name`:** grafia exata do SRD em inglês.
- **Seed:** `source="srd"`, `is_homebrew=false`, `created_by=NULL`.
- **POST:**
  - grava `source="homebrew"`, `is_homebrew=true` e `created_by` = usuário logado;
  - se o cliente mandar `source`, `is_homebrew` ou `created_by`, a resposta é 422 (campos extras proibidos).
- **URLs** (kebab-case, plural):
  - `ability-scores`, `skills`, `damage-types`, `conditions`, `creature-types`, `sizes`;
  - `alignments`, `languages`, `senses`, `movement-modes`;
  - `weapon-categories`, `weapon-properties`, `weapon-masteries`, `armor-categories`, `tool-categories`;
  - `spell-schools`, `recharge-types`, `action-types`;
  - `character-levels`, `challenge-ratings`, `point-buy-costs`, `feat-categories`, `tool-proficiencies`.

### Visibilidade e compartilhamento

- **Quem vê o quê:**
  - Anônimo: só SRD.
  - Logado: SRD, o próprio homebrew e o homebrew compartilhado com qualquer campanha da qual é membro (`campaign_members`, papel dm ou player).
  - A regra vale no momento da consulta: quem sai da campanha deixa de ver; se o autor deixar de ser DM, os shares continuam; se a campanha for apagada, os shares saem em cascata.
- **GET lista:** mostra só o que é visível. `?search=` faz ILIKE em `name`. A ordenação é determinística:

  | Tabela | Ordem |
  |---|---|
  | `sizes` | `sort_order` |
  | `character_levels`, `point_buy_costs` | chave numérica |
  | `challenge_ratings` | `numeric_value` |
  | demais | `name` |

- **GET detalhe:** 404 se a entrada não existe ou não é visível.
- **Resposta:** todas as colunas de dados, mais `source` e `is_homebrew`. `campaign_ids` vem como lista para o autor e `null` para os demais. `created_by` não é exposto.
- **`campaign_ids` no POST e no PATCH:**
  - opcional, sem duplicatas;
  - campanha inexistente dá 400; campanha onde o usuário não é DM dá 403;
  - no PATCH, se o campo vier, substitui o conjunto inteiro. `[]` remove todos.

### Edição e remoção

- **PATCH:**
  - só o autor, e só em homebrew;
  - campos editáveis: `name`, `description`, colunas de jogo, `campaign_ids` e `implies` (este só em conditions);
  - mandar `code` ou a chave numérica no corpo dá 422.
- **DELETE:**
  - só o autor, e só em homebrew; sucesso dá 204;
  - se a entrada é referenciada por qualquer FK, dá 409. Contam como referência:
    - perícias que apontam para o atributo;
    - implicação **de entrada** (a condição é implicada por outra);
    - associações de classe e de antecedente;
    - `character_skills`, `character_ability_scores`;
    - `species_definitions.size_code`, `class_definitions.spell_ability`.
  - Os shares e as implicações **de saída** são removidos junto com a entrada.
- **Matriz de permissão:**

  | Situação | Resposta |
  |---|---|
  | Entrada SRD | 403 |
  | Homebrew de outro autor que o usuário enxerga | 403 |
  | Homebrew de outro autor que o usuário não enxerga | 404 |
  | Chave inexistente | 404 |
  | Sem token | 401 |

### Colunas de jogo e seed

| Tabela | Colunas extras | Seed |
|---|---|---|
| ability_scores | — | `str` Strength, `dex` Dexterity, `con` Constitution, `int` Intelligence, `wis` Wisdom, `cha` Charisma |
| skills | `ability_code` (FK, NOT NULL) | 18 perícias:<br>• **dex:** acrobatics, sleight_of_hand, stealth<br>• **str:** athletics<br>• **int:** arcana, history, investigation, nature, religion<br>• **wis:** animal_handling, insight, medicine, perception, survival<br>• **cha:** deception, intimidation, performance, persuasion |
| damage_types | — | 13: acid, bludgeoning, cold, fire, force, lightning, necrotic, piercing, poison, psychic, radiant, slashing, thunder |
| conditions | — | 15: blinded, charmed, deafened, exhaustion, frightened, grappled, incapacitated, invisible, paralyzed, petrified, poisoned, prone, restrained, stunned, unconscious |
| condition_implications | PK (`condition_code`, `implied_condition_code`). CHECK impede que a condição implique a si mesma. FK de saída CASCADE; FK de entrada RESTRICT | paralyzed→incapacitated, petrified→incapacitated, stunned→incapacitated, unconscious→incapacitated, unconscious→prone |
| creature_types | — | 14: aberration, beast, celestial, construct, dragon, elemental, fey, fiend, giant, humanoid, monstrosity, ooze, plant, undead |
| sizes | `hit_die`, `carry_multiplier` (NUMERIC), `sort_order` (único) | Formato hit_die / carry_multiplier / sort_order:<br>• tiny 4 / 7.5 / 1<br>• small 6 / 15 / 2<br>• medium 8 / 15 / 3<br>• large 10 / 30 / 4<br>• huge 12 / 60 / 5<br>• gargantuan 20 / 120 / 6 |
| alignments | — | 10: lawful_good, neutral_good, chaotic_good, lawful_neutral, neutral, chaotic_neutral, lawful_evil, neutral_evil, chaotic_evil, unaligned |
| languages | `rarity` (CHECK `standard`/`rare`) | • **standard:** common, common_sign_language, draconic, dwarvish, elvish, giant, gnomish, goblin, halfling, orc<br>• **rare:** abyssal, celestial, deep_speech, druidic, infernal, primordial, sylvan, thieves_cant, undercommon |
| senses | — | blindsight, darkvision, tremorsense, truesight |
| movement_modes | — | walk, burrow, climb, fly, swim |
| weapon_categories | — | simple, martial |
| weapon_properties | — | ammunition, finesse, heavy, light, loading, range, reach, thrown, two_handed, versatile |
| weapon_masteries | — | cleave, graze, nick, push, sap, slow, topple, vex |
| armor_categories | — | light, medium, heavy, shield |
| tool_categories | — | artisans_tools, gaming_set, musical_instrument |
| spell_schools | — | 8 escolas |
| recharge_types | — | short_rest, long_rest, dawn, initiative, turn |
| action_types | — | action, bonus_action, reaction |
| feat_categories | — | origin, general, fighting_style, epic_boon |
| challenge_ratings | `numeric_value` (NUMERIC, único), `proficiency_bonus` | 34 linhas, de `0`, `1_8`, `1_4`, `1_2`, `1` até `30`. Proficiency bonus por faixa de CR:<br>• 0–4: +2<br>• 5–8: +3<br>• 9–12: +4<br>• 13–16: +5<br>• 17–20: +6<br>• 21–24: +7<br>• 25–28: +8<br>• 29–30: +9<br>**Sem coluna `xp`**: o XP é por monstro |
| character_levels | PK `level` (≥ 1), `min_xp` (≥ 0), `proficiency_bonus` | níveis 1–20 (Character Advancement) |
| point_buy_costs | PK `score`, `cost` (≥ 0) | 8→0, 9→1, 10→2, 11→3, 12→4, 13→5, 14→7, 15→9 |
| tool_proficiency_options | — | Tools de `equipment.md`: os 17 Artisan's Tools e as Other Tools. Gaming Set e Musical Instrument entram como entradas genéricas |

- Descrições no seed são opcionais.
- **conditions:** o POST e o PATCH aceitam `implies` (lista de codes). Os GETs retornam `implies` filtrado pelo que o usuário enxerga.
- **skills:** o POST e o PATCH exigem `ability_code` existente e visível.

### Referências reescritas para FK por code

Todo code recebido precisa existir e ser visível ao usuário. Se não for, a resposta é 400, com a mesma mensagem para os dois casos.

- **Classe:**
  - `primary_ability`, `saving_throw_proficiencies` e `spell_ability` passam a ser codes;
  - armadura, arma e ferramenta usam codes das tabelas da seção de migração;
  - `skills` vira lista de codes; a criação inline de perícia sai;
  - `ClassOut.skills` retorna `{code, name, ability_code}`.
- **Antecedente:** usa codes e mantém a cardinalidade atual: exatamente 3 atributos, exatamente 2 perícias, ao menos 1 ferramenta, sem duplicatas.
- **Personagem:**
  - `ability_scores` usa codes como chave; o default é `{"str":10,"dex":10,"con":10,"int":10,"wis":10,"cha":10}`;
  - `CharacterSkillCreate.skill_code`;
  - rotas de perícia passam a usar `/{skill_code}`;
  - `CharacterSkillOut` retorna `skill_code`, `skill_name` e `ability_code`;
  - as regras atuais de perícia continuam iguais.
- **Espécie:** `size_code`, FK com default `"medium"`.
- **Perda de visibilidade:** referências já gravadas permanecem. O GET continua devolvendo o code.

## Casos de borda e erros

- **409:**
  - code ou chave já existente, inclusive homebrew invisível de outro usuário;
  - `numeric_value` repetido em challenge_ratings;
  - `sort_order` repetido em sizes;
  - DELETE de entrada referenciada.
- **422:**
  - code fora do formato;
  - `name` vazio;
  - coluna de jogo inválida: `hit_die` ≤ 0, `carry_multiplier` ≤ 0, `rarity` desconhecida, `level` < 1, `min_xp`/`cost` < 0, `proficiency_bonus` < 0;
  - campos extras proibidos;
  - `implies` contendo o próprio code;
  - `campaign_ids` com duplicatas;
  - PATCH que tenta alterar `code` ou chave numérica.
- **400:**
  - code referenciado inexistente ou não visível;
  - campanha inexistente em `campaign_ids`;
  - chave de ability do personagem desconhecida (ex.: `"STR"`, `"luck"`).
- **403:** campanha onde o usuário não é DM; PATCH/DELETE em SRD; PATCH/DELETE em homebrew visível de outro autor.
- **404:** chave inexistente ou não visível.
- **Atomicidade:** qualquer erro em POST ou PATCH não grava nada.
- **Ciclos:** não há verificação de ciclo indireto em implicações.
- **Busca vazia:** `search` sem resultado retorna 200 com `[]`.

## Impacto em dados/modelos

- **Banco:** recriado, sem migração de dados. Fica uma única revisão, e `character_skills` passa a nascer na squash.
- **Tabelas renomeadas ou removidas:**
  - `ability_score_options` vira `ability_scores`;
  - `skill_definitions` vira `skills` (PK `code`, sem uuid);
  - `armor_proficiency_options` e `weapon_proficiency_options` são removidas;
  - `tool_proficiency_options` muda de forma.
- **FKs renomeadas:**
  - `class_primary_abilities`, `class_saving_throws`, `background_ability_scores`: `ability_code`;
  - `class_definitions.spell_ability`: aponta para `ability_scores.code`;
  - `class_armor_proficiencies`: `armor_category_code`;
  - `class_weapon_proficiencies`: `weapon_category_code`;
  - `class_tool_proficiencies`, `background_tool_proficiencies`: `tool_proficiency_code`;
  - `class_skills`, `background_skills`, `character_skills`: `skill_code`;
  - `character_ability_scores`: `ability_code`;
  - `species_definitions.size`: vira `size_code`; o enum PG `creaturesize` é removido.
- **Comportamento das FKs:** RESTRICT, exceto as implicações de saída, que são CASCADE.
- **Perda temporária aceita:** "Martial com Finesse/Light" não é representável até a fase 2.
- **Código e testes:**
  - `app/enums.py` perde `AbilityScore` e `CreatureSize` (e o arquivo sai se ficar vazio);
  - helpers `seed_*` e testes que usam `"STR"`, `skill_id` ou perícia inline precisam de ajuste.

## Permissões

- **GET:**
  - autenticação opcional: anônimo vê SRD, logado vê o que está visível para ele;
  - é preciso criar uma dependência de usuário opcional, porque hoje `deps.py` só tem `CurrentUser`, que é obrigatório;
  - token inválido no GET dá 401.
- **POST:** qualquer usuário logado. `campaign_ids` só aceita campanhas onde ele é DM.
- **PATCH e DELETE:** só o autor, e só em homebrew.
- **Referências por code:** respeitam a visibilidade de quem faz a requisição.
- Não existe papel admin.

## Critérios de aceite

- [ ] **Migration:** em banco novo, `alembic upgrade head` aplica só `c1fcfd7fe014`, e `alembic check` não aponta drift. `a7d3e91b4c52` não existe mais.
- [ ] **Contagens do seed:** todas as linhas com `source='srd'` e `is_homebrew=false`.

  | Tabela | Linhas |
  |---|---|
  | ability_scores | 6 |
  | skills | 18 |
  | damage_types | 13 |
  | conditions | 15 |
  | condition_implications | 5 |
  | creature_types | 14 |
  | sizes | 6 |
  | alignments | 10 |
  | languages | 19 |
  | senses | 4 |
  | movement_modes | 5 |
  | weapon_categories | 2 |
  | weapon_properties | 10 |
  | weapon_masteries | 8 |
  | armor_categories | 4 |
  | tool_categories | 3 |
  | spell_schools | 8 |
  | recharge_types | 5 |
  | action_types | 3 |
  | feat_categories | 4 |
  | character_levels | 20 |
  | challenge_ratings | 34 |
  | point_buy_costs | 8 |

- [ ] **Valores pontuais:**
  - gargantuan: `hit_die=20`, `carry_multiplier=120`;
  - tiny: `carry_multiplier=7.5`;
  - nível 5: `min_xp=6500`, PB 3;
  - nível 20: `min_xp=355000`, PB 6;
  - CR `1_4`: `numeric_value=0.25`, PB 2;
  - CR `30`: PB 9;
  - score 14: `cost=7`;
  - stealth: `ability_code=dex`;
  - thieves_cant: `rarity=rare`.
- [ ] **Estrutura:** `challenge_ratings` sem `xp`; `sizes` sem `space_ft`; nenhuma tabela nova com JSONB.
- [ ] **GET público:** os 23 recursos respondem 200 sem token, só com SRD, em ordem determinística. `?search=` não diferencia maiúsculas.
- [ ] **POST:** 201 com `is_homebrew=true` e `source=homebrew`; 401 sem token; 409 para code repetido (inclusive de outro usuário); 422 para code inválido.
- [ ] **Visibilidade sem compartilhar:** A cria `damage_types/psionic` sem compartilhar. A vê a entrada com `campaign_ids=[]`. B e o anônimo não veem, e o detalhe dá 404.
- [ ] **Visibilidade por campanha:**
  - A compartilha `psionic` com a campanha C, onde A é DM. O jogador P de C vê a entrada com `campaign_ids=null`. B não vê.
  - P sai de C e deixa de ver.
  - Compartilhar com campanha onde A é player dá 403; com campanha inexistente dá 400.
- [ ] **PATCH:**
  - o autor altera `name` e `campaign_ids` e recebe 200, com os shares substituídos;
  - mandar `code` no corpo dá 422;
  - P recebe 403, B recebe 404;
  - PATCH em SRD (`damage_types/fire`) dá 403.
- [ ] **DELETE:**
  - homebrew sem referências: 204, e a entrada some dos GETs e dos shares;
  - `ability_scores/luck` homebrew com perícia apontando para ele: 409;
  - condição homebrew que é alvo de implicação: 409;
  - SRD: 403;
  - B: 404.
- [ ] **conditions:** POST com `implies:["incapacitated"]` cria a implicação, e `GET /conditions/paralyzed` retorna `implies:["incapacitated"]`.
- [ ] **skills:** POST com `ability_code` inexistente ou homebrew invisível dá 400.
- [ ] **Classe:**
  - POST com codes SRD válidos dá 201 e devolve os mesmos codes;
  - code desconhecido ou invisível dá 400 e não grava nada;
  - homebrew visível dá 201.
- [ ] **Antecedente:** POST e PATCH aceitam codes, respondem 422 por cardinalidade e 400 para code inválido.
- [ ] **Personagem:**
  - POST sem `ability_scores` grava as 6 chaves minúsculas com valor 10;
  - `"STR"` ou `"luck"` (invisível) dá 400;
  - as rotas de perícia funcionam com `skill_code`.
- [ ] **Espécie:** `size_code="huge"` grava; `size_code="colossal"` dá 400.
- [ ] **Limpeza:** `grep -rn "AbilityScore\b\|CreatureSize\|ability_score_options\|skill_definitions\|ensure_ability_score_options\|_resolve_options" backend/app backend/alembic` não retorna nada.
- [ ] **Testes:** `python -m pytest -q` em `backend/` passa.

## Suposições confirmadas pelo usuário

- `name` não é único.
- Quem não é autor recebe 403 se enxerga a entrada e 404 se não enxerga.
- `campaign_ids` só aparece para o autor.
- Shares numa única tabela many-to-many (ajuste no topo).

## Perguntas em aberto (não bloqueiam)

- **Vazamento de code:** classes e antecedentes são globais. Se referenciarem um homebrew compartilhado, o code dele aparece para quem não enxerga a entrada (e o detalhe dá 404).
- Verificação de ciclos indiretos em implicações.
- Dialetos de Primordial (fase 8).

## Fontes do seed

Todas em `docs/dnd-5e-srd-markdown-master/`:

- `character-creation.md`: idiomas (l. 206–292), point buy (l. 310), Character Advancement (l. 655);
- `monsters.md`: Hit Dice by Size (l. 91), lista de CRs (l. 209);
- `rules-glossary.md`: Carrying Capacity (l. 387) e condições;
- `equipment.md`: Tools (l. 604).
