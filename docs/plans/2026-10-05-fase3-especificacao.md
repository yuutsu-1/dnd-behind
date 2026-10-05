# Especificação Refinada — Fase 3: magias estruturadas e `spell_materials` (sem JSONB `components`)

Esta fase faz parte do redesenho em `2026-10-04-redesenho-modelo-srd.md` (seção "3. Magias"). Segue os padrões já entregues nas fases 1 e 2:

- tabelas de referência no padrão `code`, com router genérico GET/POST/PATCH/DELETE e homebrew com escopo via `campaign_homebrew_rules`;
- entidades globais com PATCH/DELETE só pelo autor (padrão de `/items`);
- seed na squash única `c1fcfd7fe014` com UUID determinístico (uuid5);
- `cost_gp NUMERIC(12,4)`;
- testes HTTP com httpx + ASGITransport.

## Decisões do usuário (gate #1, 2026-10-05)

Todas seguem o default recomendado:

- **D1:** cria a referência `spell_lists` (8 codes SRD) e a tabela `spell_list_spells`, que substituem `spell_class_lists`. A ligação classe → lista fica para a fase 6.
- **D2:** o seed das 339 magias entra nesta fase. Os dados extraídos de `spells.md` ficam versionados em código e são conferidos contra as listas de `classes.md`.
- **D3:** cria a referência `area_shapes` e a tabela filha `spell_areas`. O seed só inclui áreas explícitas no texto.
- **D4:** Plant Growth fica com a ação `action`, e a linha original "Casting Time: Action (Overgrowth) or 8 hours (Enrichment)" é acrescentada à `description`.
- **D5:** `range_ft` sempre em pés, com milhas convertidas (1 mile = 5280 ft).
- **D6:** `range_types`, `duration_types` e `time_units` viram tabelas de referência (extensíveis). A ação de conjuração usa a referência `action_types`, que já existe.
- **D7:** a coluna `has_material` é mantida e validada contra os materiais. O material só vira várias linhas quando custo, consumo, "por alvo" ou quantidade diferem. Não há FK para itens.
- **D8:** dano, salvaguarda e ataque ficam só no texto nesta fase.
- **Extra:** PATCH e DELETE de magia homebrew seguem exatamente o padrão de `/items`.

## REVISÃO DO USUÁRIO NO GATE #2 (2026-10-05) — PREVALECE SOBRE O RESTO DO DOCUMENTO

**Princípio:** só ganha estrutura própria o que afeta a mecânica ou leva uma informação específica para a ficha. O que é só exibição vira uma coluna de texto. Aplicado às magias:

| Campo | Novo modelo | Observação |
|---|---|---|
| Duração | `duration` (texto, NOT NULL), ex. "Concentration, up to 1 minute", "Until dispelled or triggered" | Saem `duration_types`, `duration_amount`, `duration_unit_code` e as regras de coerência de duração |
| Concentração | `concentration` (bool) | Mantido, porque é mecânica |
| Alcance | `range` (texto, NOT NULL), ex. "90 feet", "Self", "1 mile" | Saem `range_types`, `range_ft` e as regras de coerência de alcance |
| Área | `area` (texto, nullable), ex. "20-foot radius", "100-foot Line, 5 feet wide" | Preenchido só quando a magia **afeta** uma área. Teleportation Circle não é área; Light é "20-foot radius" |
| Forma da área | `area_shape_code` (FK `area_shapes`, nullable, obrigatório quando houver `area`) | Palavra-chave que define o ícone na ficha |
| Tempo de conjuração | `casting_time_code` (FK, NOT NULL) para a nova referência `casting_times` | Um campo só |
| Gatilho | **sem campo** (decisão do usuário) | Nas 8 magias com condição de conjuração (4 reações e 4 smites), a linha original do tempo de conjuração, por exemplo "Casting Time: Reaction, which you take when …", é anexada ao fim de `description`, igual ao Plant Growth |
| Ritual | `ritual` (bool) | Mantido |

- **`area_shapes`, seed:** cone, cube, cylinder, emanation, line, sphere, mais as palavras-chave que aparecem de fato nas áreas do SRD: `radius` e `square`. Não entra nenhuma forma que não esteja no texto.
- **`casting_times`, seed:** action, bonus_action, reaction, `1_minute`, `10_minutes`, `1_hour`, `8_hours`, `12_hours`, `24_hours`, todos derivados dos tempos que existem no SRD. Não tem colunas extras.
- **Plant Growth:** `casting_time_code=action`, e a linha original do tempo de conjuração vai ao fim de `description`.
- **Saem:** as referências `time_units`, `range_types` e `duration_types`, as colunas `casting_action_type_code`, `casting_time_amount` e `casting_time_unit_code`, e a tabela `spell_areas`. Com isso `REFERENCE_MODELS` passa de 24 para **27** (+ `area_shapes`, `spell_lists`, `casting_times`).
- **Ficam como estão:** `spell_materials` (D7), `spell_lists` + `spell_list_spells` (D1), seed das 339 magias (D2), `has_verbal`/`has_somatic`/`has_material`, `higher_levels`/`cantrip_upgrade`, e a matriz de PATCH/DELETE.
- **Listas (H4):** valem os cabeçalhos do `spells.md`. Phantasmal Force entra em Bard/Sorcerer/Wizard e Mind Spike em Sorcerer, mesmo divergindo das tabelas do `classes.md`.
- **Invocações:** os stat blocks embutidos (Animate Objects, Find Steed, Giant Insect, Summon Dragon) **saem** de `description`. Na fase 8 eles entram como monstros genéricos e a magia passa a referenciá-los. Nada de JSON em coluna.
- **Áreas (H8):** o usuário aceitou o critério do planejador (91 magias com área) e corrige depois, se precisar. O que importa é a modelagem estar certa.
- **B13:** só se aplica a magias com área. `area` e `area_shape_code` vão juntos, e uma magia sem área deixa os dois vazios.
- **Testes e documentação:** **nenhum teste lê `docs/`**, que existe só como referência. O seed é conferido por testes com números e valores fixos. O extrator é uma ferramenta de desenvolvimento, rodada à mão, que gera o módulo de dados versionado.
- **Critérios de contagem:** saem os de `until_dispelled` e de tipo de duração/alcance. Entram:
  - 339 magias;
  - 27 truques;
  - 29 rituais;
  - 4 `reaction` com gatilho;
  - 133 com concentração;
  - 124 com `higher_levels` ou `cantrip_upgrade`;
  - toda magia SRD com pelo menos uma lista.

## Objetivo

Trocar a representação de `spell_definitions`, hoje em texto e JSONB, por colunas tipadas, com uma informação por coluna:

- escola como FK;
- componentes V/S/M como booleanos;
- tempo de conjuração, alcance e duração decompostos em tipo + quantidade + unidade;
- concentração e ritual.

Também entram:

- `spell_materials`: material com custo em ouro, consumo, "por alvo" e quantidade;
- `spell_areas`: áreas de efeito;
- `spell_lists`: listas de magias, ligáveis sem precisar das classes no seed.

O SRD 2024 inteiro (339 magias) entra como seed. Sai o JSONB `components`. Os endpoints de magia ganham PATCH e DELETE.

## Escopo

### Incluído

**`spell_definitions` reestruturada**

- **Saem:**
  - `school`, `casting_time`, `range` e `duration` (texto);
  - `components` (JSONB);
  - `material_component` (texto);
  - o UNIQUE em `name`.
- **Ficam:** `id`, `name`, `level` (0 = cantrip), `concentration`, `ritual`, `description`, `higher_levels`, `source`, `is_homebrew`, `created_by`, `created_at`.
- **Entram:**

  | Grupo | Coluna | Tipo |
  |---|---|---|
  | Escola | `school_code` | FK `spell_schools`, NOT NULL |
  | Componentes | `has_verbal`, `has_somatic`, `has_material` | bool, NOT NULL |
  | Tempo de conjuração | `casting_action_type_code` | FK `action_types`, nullable |
  | | `casting_time_amount` | int, nullable |
  | | `casting_time_unit_code` | FK `time_units`, nullable |
  | | `casting_trigger` | texto, nullable |
  | Alcance | `range_type_code` | FK `range_types`, NOT NULL |
  | | `range_ft` | int, nullable |
  | Duração | `duration_type_code` | FK `duration_types`, NOT NULL |
  | | `duration_amount` | int, nullable |
  | | `duration_unit_code` | FK `time_units`, nullable |
  | Texto | `cantrip_upgrade` | texto, nullable |

**Novas referências**

Todas no padrão `code` da fase 1: router genérico, homebrew com escopo e seed do SRD.

| Referência | Colunas extras | Seed |
|---|---|---|
| `time_units` | `seconds` (int > 0) | `round` 6, `minute` 60, `hour` 3600, `day` 86400 |
| `range_types` | `has_distance` (bool) | `self`, `touch`, `distance` (true), `sight`, `unlimited`, `special` |
| `duration_types` | `has_amount` (bool) | `instantaneous`, `timed` (true), `until_dispelled`, `until_dispelled_or_triggered`, `special` |
| `area_shapes` | — | `cone`, `cube`, `cylinder`, `emanation`, `line`, `sphere` |
| `spell_lists` | — | `bard`, `cleric`, `druid`, `paladin`, `ranger`, `sorcerer`, `warlock`, `wizard` |

**Novas tabelas filhas da magia**

Todas com FK `spell_id` e ON DELETE CASCADE.

- **`spell_materials`:**
  - `id` (uuid), `spell_id`, `sort_order`;
  - `description` (texto, NOT NULL);
  - `cost_gp` (NUMERIC(12,4), nullable): custo mínimo **por unidade**;
  - `consumed` (bool);
  - `per_target` (bool);
  - `quantity` (int ≥ 1, default 1).
- **`spell_areas`:**
  - `id`, `spell_id`, `sort_order`;
  - `shape_code` (FK `area_shapes`);
  - `size_ft` (int > 0): raio de Sphere/Cylinder, comprimento de Cone/Line, aresta de Cube, distância de Emanation;
  - `height_ft`: só para Cylinder;
  - `width_ft`: só para Line.
- **`spell_list_spells`:** PK (`spell_list_code`, `spell_id`).

**Removidos**

- A tabela `spell_class_lists` e a relação `SpellDefinition.class_list`.
- Os campos textuais listados acima.

**Atualizados**

- `REFERENCE_MODELS` passa de 24 para **29** recursos.
- O CHECK de `campaign_homebrew_rules.resource_table` inclui as novas referências.

**Seed do SRD na squash `c1fcfd7fe014`**

- As 339 magias de `spells.md`, com seus materiais, áreas e listas.
- A migration **não** lê `docs/` em runtime. Os dados extraídos ficam versionados em código Python, no próprio arquivo da migration ou num módulo auxiliar importado por ela. O planejador decide qual.

**API `/api/compendium/spells`:** GET (lista e detalhe), POST, PATCH e DELETE.

### Fora de escopo

- **Dano, salvaguarda, ataque, condições e escalonamento estruturados.** Ficam no texto de `description`, `higher_levels` e `cantrip_upgrade` (fases 4 e 8).
- **Alvos:** quantidade, tipo e "willing"; também linha de visão.
- **Proficiência, escolha, preparação, slots e conjuração por personagem** (fases 6 e 7). `character_spells` não muda de estrutura.
- **Features que concedem magias** (fase 4), a ligação classe → lista de magias e o `spell_list_code` em classe e talento (fases 6 e 7).
- **FK de material para `item_definitions`.**
- **Regras que só são derivadas**, sem coluna própria:
  - bolsa de componentes ou foco substituindo materiais sem custo e não consumidos;
  - +10 minutos ao conjurar como ritual;
  - conjuração longa exigindo concentração.
- **Monstros conjuradores** (fase 8).
- **Tradução PT-BR.**

## Regras de negócio

### Identidade e visibilidade

- **Magia é entidade global.** Tem `id` uuid e os campos `source`, `is_homebrew` e `created_by`, como os itens.
- **Nome:** grafia do SRD, e **não é único**. Um homebrew pode repetir o nome de uma magia SRD.
- **Seed:** `source='srd'`, `is_homebrew=false`, `created_by=NULL`, `id = uuid5(SRD_SPELL_NAMESPACE, name)`.
- **Codes referenciados** (escola, ação, unidades, tipos, formas, listas) seguem a regra 6f da fase 1: precisam existir e ser visíveis, senão 400 com mensagem única.

### Nível e textos

- `level` vai de 0 a 9.
- `description` é o corpo da magia **sem** os parágrafos "_Using a Higher-Level Spell Slot._" e "_Cantrip Upgrade._". Esses vão, sem o rótulo, para `higher_levels` e `cantrip_upgrade`.
- **Coerência com o nível** (422 na API e CHECK no banco):
  - `cantrip_upgrade` só existe se `level = 0`;
  - `higher_levels` só existe se `level ≥ 1`.

### Componentes

- Pelo menos um entre V, S e M é verdadeiro (CHECK).
- `has_material = true` se e somente se existe ao menos 1 linha em `spell_materials` (validado na aplicação).
- O rótulo "Component:" no singular (12 magias) é tratado igual a "Components:".

### Materiais

- **Descrição:** cada linha usa o trecho do SRD que descreve aquele material.
- **Divisão em linhas:**
  - material sem custo, sem consumo e sem "por alvo" vira **uma** linha, com o texto inteiro do parêntese;
  - só se divide em várias linhas quando custo, consumo, "por alvo" ou quantidade diferem.
- **`cost_gp`:** o mínimo "worth X+ GP" por unidade, em ouro. CP e SP são convertidos (1 CP = 0,01). Fica null quando o SRD não dá custo.
- **`consumed`:** true só quando o SRD diz que a magia consome o material.
- **`per_target`:** true para "for each of the spell's targets" e "for each corpse".
- **`quantity`:** vem de expressões como "four ...", "a pair of ..." e "2 Copper Pieces".
- **Casos de referência:**

  | Magia | Materiais |
  |---|---|
  | Clone | diamante, 1000, consumido + vaso, 2000, não consumido |
  | Legend Lore | incenso, 250, consumido + 4 tiras de marfim, 50 cada |
  | Astral Projection | jacinto, 1000 + barra de prata, 100; ambos consumidos e por alvo |
  | Create Undead | ônix, 150, por alvo, não consumido |
  | Warding Bond | anéis, quantidade 2, 50 cada |
  | Gentle Repose | Copper Piece, quantidade 2, 0,01, consumido |
  | True Strike | arma, custo 0,01 |

### Tempo de conjuração

- **Exatamente uma das duas formas** (CHECK):
  - **ação:** `casting_action_type_code` preenchido, com quantidade e unidade nulas (Action, Bonus Action, Reaction);
  - **tempo:** `casting_time_amount > 0` e `casting_time_unit_code` preenchidos, com a ação nula.
- `ritual` é true quando o texto traz "or Ritual".
- **`casting_trigger`** guarda o texto após "which you take ...":
  - obrigatório em `reaction`;
  - opcional em `bonus_action`;
  - proibido nos demais casos (422).
- **Plant Growth:** ver D4.

### Alcance

- O tipo `distance` exige `range_ft > 0`. Os demais tipos exigem `range_ft` null (422).
- **Conversão de milhas:** 1 mile = 5280 ft; 500 miles = 2.640.000 ft.
- **Área não faz parte do alcance.** "Self" continua `self` mesmo em magias com Emanation ou Cone.

### Duração

- O tipo `timed` exige `duration_amount > 0` e `duration_unit_code`. Os demais tipos exigem ambos nulos.
- **Concentração:**
  - "Concentration, up to X" vira `timed` com X e `concentration = true`;
  - concentração só é aceita com `timed` (422).
- "Up to X" **sem** concentração (Etherealness, Prestidigitation, Thaumaturgy) vira `timed` com X e `concentration = false`.
- "Until dispelled or triggered" é um tipo próprio.
- "Special" vira o tipo `special`.

### Áreas

- Uma magia tem de 0 a N áreas, com `sort_order`.
- **Medidas por forma:**
  - `cylinder`: `height_ft` obrigatório e `width_ft` null;
  - `line`: `width_ft` obrigatório e `height_ft` null;
  - demais formas: ambos null.
- **Seed:**
  - entram só áreas declaradas explicitamente no texto, com forma e medida, inclusive em variações de redação; nada é inferido;
  - medidas fora de pés são convertidas.

### Listas de magias

- `spell_list_spells` liga cada magia às listas.
- **Seed:** vem dos parênteses do cabeçalho "Level N School (Classes)" ou "School Cantrip (Classes)".
- O conjunto de cada lista deve bater com as tabelas "<Class> Spell List" de `classes.md`. Divergência é falha a reportar, nunca a corrigir em silêncio.

### Endpoints

- **`GET /spells`** (usuário opcional; token inválido dá 401):
  - filtros: `level`, `school`, `spell_list` (substitui `class_name`), `concentration`, `ritual`, `search` (ILIKE com escape de `%` e `_`);
  - ordem: `level`, `name`, `id`;
  - code desconhecido não casa nada.
- **`GET /spells/{id}`:**
  - retorna todas as colunas, com code e nome das referências (ex.: `school_code` + `school_name`);
  - `materials`, ordenado por `sort_order`;
  - `areas`;
  - `spell_lists`: lista de `{code, name}`, ordenada por code;
  - inexistente dá 404.
- **`POST /spells`** (usuário logado):
  - recebe os campos acima, mais `materials`, `areas` e `spell_list_codes`;
  - grava `source=homebrew`, `is_homebrew=true` e `created_by`;
  - `source`, `is_homebrew`, `created_by`, `id` ou campo desconhecido dão 422.
- **`PATCH /spells/{id}`** (só o autor, só homebrew):
  - `materials`, `areas` e `spell_list_codes`, quando enviados, substituem o conjunto inteiro;
  - a coerência é validada sobre o estado final.
- **`DELETE /spells/{id}`** (só o autor, só homebrew):
  - 204, apagando materiais, áreas e links em cascata;
  - **409** se a magia for referenciada por `character_spells`.
- **Matriz de PATCH e DELETE:**

  | Situação | Resposta |
  |---|---|
  | magia SRD | 403 |
  | homebrew de outro autor | 403 |
  | inexistente | 404 |
  | sem token | 401 |

- **Atomicidade:** qualquer erro em POST ou PATCH não grava nada.
- **409 no DELETE de referência homebrew em uso:** vale para `spell_schools`, `action_types`, `time_units`, `range_types`, `duration_types`, `area_shapes` e `spell_lists`, quando usadas por uma magia, um material, uma área ou um link.

## Casos de borda e erros

- **422:**
  - `level` fora de 0..9;
  - nenhum componente marcado;
  - `has_material` incoerente com a lista de materiais;
  - tempo de conjuração com as duas formas ou com nenhuma;
  - `casting_trigger` ausente em reação, ou presente fora de reação e ação bônus;
  - `range_ft`, `duration_amount` ou `duration_unit_code` incoerentes com o tipo;
  - concentração sem `timed`;
  - `cantrip_upgrade` com `level ≥ 1`, ou `higher_levels` com `level 0`;
  - `quantity < 1`, `cost_gp < 0` ou `size_ft ≤ 0`;
  - `height_ft` ou `width_ft` incoerentes com a forma;
  - `spell_list_codes` duplicados;
  - campos proibidos ou desconhecidos.
- **400:** code inexistente ou invisível.
- **403, 404 e 409:** conforme a matriz acima.
- **Seed:** um cabeçalho não reconhecido faz a extração falhar explicitamente; nenhuma magia é pulada. As 339 precisam entrar.

## Impacto em dados e modelos

- **Banco:** recriado. A squash `c1fcfd7fe014` é reescrita e continua sendo a única revisão.
- **`SpellDefinition`, `SpellOut` e `SpellCreate`** mudam, e entra `SpellUpdate`. Somem `components` e `class_list`.
- **`spell_class_lists`** é removida. Hoje não há classes no seed nem testes de magia.
- **`character_spells`** não muda de estrutura. Passa a bloquear o DELETE de magia (409).
- **`REFERENCE_MODELS`** fica com 29 recursos, e o CHECK de shares é atualizado.
- **JSONB restante:** depois desta fase, `grep -rn JSONB backend/app/db/models/compendium.py` só mostra `FeatureGrant.effect_data` e `SpeciesDefinition.special_traits`.

## Permissões

- **GET:** autenticação opcional.
- **POST:** qualquer usuário logado.
- **PATCH e DELETE:** só o autor, só homebrew.
- **Novas referências:** seguem a matriz da fase 1.
- Não existe papel admin.

## Critérios de aceite

- [ ] **Migration e limpeza:**
  - em banco novo, `alembic upgrade head` aplica só `c1fcfd7fe014`, e `alembic check` não aponta drift;
  - `SpellDefinition` não tem JSONB nem as colunas textuais antigas;
  - `grep -rn "spell_class_lists\|material_component" backend/app backend/alembic` volta vazio.
- [ ] **Referências novas:**
  - `GET /time-units`, `/range-types`, `/duration-types`, `/area-shapes` e `/spell-lists` respondem 200 sem token, com 4, 6, 5, 6 e 8 linhas SRD;
  - DELETE de `time_units` homebrew usada por uma magia dá 409.
- [ ] **Seed, contagens:**

  | Critério | Esperado |
  |---|---|
  | magias | 339 |
  | `level=0` | 27 |
  | `ritual=true` | 29 |
  | `reaction`, todas com `casting_trigger` | 4 |
  | `concentration=true` | 133 |
  | `instantaneous` | 101 |
  | `until_dispelled` | 14 |
  | `until_dispelled_or_triggered` | 2 |
  | `special` | 1 |
  | com `higher_levels` ou `cantrip_upgrade` | 124 |

  Toda magia tem ao menos 1 lista, e o conteúdo de cada lista bate com `classes.md`.
- [ ] **Seed, valores pontuais:**

  | Magia | Esperado |
  |---|---|
  | Acid Arrow | nível 2, evocation, `action`, `distance` 90, V/S/M, 1 material "powdered rhubarb leaf" sem custo e não consumido, instantaneous, `higher_levels` preenchido, listas [wizard] |
  | Acid Splash | nível 0, `cantrip_upgrade` preenchido, sem material, área sphere 5 |
  | Alarm | 1 minute, ritual, timed 8 hour, área cube 20 |
  | Alter Self | `self`, concentração, timed 1 hour |
  | Counterspell | `reaction`, com o trigger do SRD |
  | Etherealness | timed 8 hour, sem concentração |
  | Clone, Legend Lore, Astral Projection, Create Undead, Warding Bond, Gentle Repose, True Strike | materiais conforme a tabela de casos de referência |
  | magia com "500 miles" | `range_ft = 2640000` |
  | magia com Range "Sight" | `range_type = sight`, `range_ft` null |
  | Ice Storm | área cylinder 20/40 |
  | Lightning Bolt | área line 100/5 |

- [ ] **`GET /spells`:**
  - resultado determinístico;
  - `spell_list=wizard` bate com `classes.md`; `level=0` retorna 27; `ritual=true` retorna 29;
  - `search` não diferencia maiúsculas de minúsculas;
  - o detalhe traz materiais, áreas e listas; inexistente dá 404.
- [ ] **`POST /spells`:**
  - homebrew com 2 materiais e uma área dá 201;
  - sem token dá 401;
  - cada regra de 422 tem pelo menos um teste;
  - code invisível dá 400;
  - em caso de erro, nada é gravado.
- [ ] **`PATCH /spells`:** substituir os materiais dá 200; SRD dá 403; outro autor dá 403; inexistente dá 404.
- [ ] **`DELETE /spells`:** homebrew sem uso dá 204 e as tabelas filhas somem; magia referenciada por `character_spells` dá 409; SRD dá 403.
- [ ] **Testes:** `python -m pytest -q` passa.

## Suposições

- Nome de magia não é único.
- O UUID do seed é uuid5 com namespace próprio de magias.
- "Up to X" sem concentração vira `timed`, sem flag de "máximo".
- `time_units.seconds` serve para comparar e ordenar unidades.
- "Action or Ritual" vira `action` com `ritual=true`.
- `casting_trigger` é texto livre, sem motor que o interprete.
- `per_target` e o custo por unidade servem para derivar o custo total.
- A lista ordena por nível e depois por nome.

## Perguntas em aberto (não bloqueiam)

- A ligação lista ↔ classe fica para a fase 6.
- Dispensar uma magia antes do fim da duração não é modelado.
- A coluna "Special" de `classes.md` é derivável dos dados e serve só como verificação cruzada do seed.
