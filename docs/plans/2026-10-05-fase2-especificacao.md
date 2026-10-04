# Especificação Refinada — Fase 2: itens estruturados, moedas, kits, ferramentas e `proficiency_grants` (sem JSONB `properties`)

Faz parte do redesenho descrito em `2026-10-04-redesenho-modelo-srd.md` e incorpora as decisões D1–D8 do usuário (2026-10-05).

## Objetivo

1. Trocar `ItemDefinition.properties` (JSONB) por um modelo relacional:
   - `item_definitions` continua como base comum;
   - cada tipo de item ganha uma tabela própria 1:1: `weapons`, `armors`, `tools`, `containers`;
   - `weapon_property_links` guarda as propriedades de arma e `item_contents` guarda o conteúdo dos kits;
   - moedas passam a ser itens;
   - `cost_gp` e `weight_lb` viram decimais, com o ouro como unidade base.
2. Separar a **ferramenta como alvo de proficiência** (tabela de referência `tool_types`) da **ferramenta como item físico**.
3. Criar `proficiency_grants`, uma entidade reutilizável que substitui:
   - a tabela `tool_proficiency_options`;
   - as associações de proficiência e de salvaguarda da classe;
   - as associações de perícias e de ferramentas do antecedente.
4. Fazer o seed com o SRD 2024.

Esta fase fecha os gaps 3 (a parte do item, que é a mastery da arma), 4, 5, 6 e 7.

## Escopo

### Incluído

- **Base `item_definitions`:**
  - colunas: `id` (uuid), `name`, `item_type_code` (FK para `item_types`), `cost_gp` e `weight_lb` (ambos NUMERIC(12,4), nullable), `description`, `source`, `is_homebrew`, `created_by`, `created_at`;
  - saem: `properties`, `subtype`, `rarity`, `requires_attunement`, `attunement_prerequisite` e `weight` (Float).
- **Novas tabelas de referência** no padrão `code` da fase 1. Usam o router genérico (GET/POST/PATCH/DELETE) e o homebrew com escopo via `campaign_homebrew_rules`:
  - `item_types`: sem colunas extras. Seed: `weapon`, `armor`, `tool`, `ammunition`, `adventuring_gear`, `pack`, `currency`.
  - `tool_types`: `category_code` (FK para `tool_categories`, nullable para as "Other Tools") e `ability_code` (FK para `ability_scores`, NOT NULL). Seed com 37 linhas:
    - 17 Artisan's Tools;
    - 6 Other Tools;
    - 4 Gaming Sets;
    - 10 Musical Instruments.
- **Tabelas por tipo de item.** Todas são 1:1, com PK = `item_id` e FK para `item_definitions` com ON DELETE CASCADE:

  | Tabela | Colunas |
  |---|---|
  | `weapons` | `category_code`, `is_ranged`, `damage_dice_count`, `damage_die_size`, `damage_flat`, `damage_type_code`, `mastery_code` |
  | `weapon_property_links` | PK (`weapon_item_id`, `property_code`), mais `range_normal_ft`, `range_long_ft`, `versatile_die_size`, `ammunition_item_id` |
  | `armors` | `category_code`, `base_ac`, `adds_dex_modifier`, `max_dex_modifier`, `strength_requirement`, `stealth_disadvantage` |
  | `tools` | `tool_type_code` (FK para `tool_types`, NOT NULL). Categoria e atributo ficam só em `tool_types` |
  | `containers` | `capacity_weight_lb` |

- **`item_contents`:** PK (`pack_item_id`, `item_id`) e `quantity` ≥ 1.
- **Moedas:** 5 itens do tipo `currency`. O dinheiro do personagem são linhas de inventário com quantidade.
- **`proficiency_grants`:** entidade reutilizável e deduplicada, com tabelas de link por dono: `class_proficiency_grants` e `background_proficiency_grants`.
- **Removidos:**
  - a tabela `tool_proficiency_options`, a rota `tool-proficiencies`, a entrada em `REFERENCE_MODELS` e a entrada no CHECK de shares;
  - as tabelas `class_saving_throws`, `class_armor_proficiencies`, `class_weapon_proficiencies`, `class_tool_proficiencies`, `background_skills` e `background_tool_proficiencies`.
- **Seed:** todo o equipamento SRD listado abaixo, feito na squash `c1fcfd7fe014` reescrita. O banco é recriado.
- **API:**
  - `/api/compendium/items` com GET (lista e detalhe), POST, PATCH e DELETE;
  - `GET /api/compendium/proficiency-grants` (lista e detalhe);
  - classe e antecedente passam a usar grants.

### Fora de escopo

- **Itens mágicos.** Ficam apenas plugáveis, numa futura `magic_items` 1:1 com `item_definitions`. Raridade e sintonização voltam junto com ela.
- **Carga e inventário físico:** encumbrance, capacidade de carga por Força, peso total do inventário e itens dentro de containers.
- **Foco de conjuração:** a mecânica fica para as fases 3 e 6.
- **Escolhas concretas do personagem**, que ficam para a fase 7:
  - qual Gaming Set o Soldier escolhe;
  - "same as above";
  - "Musical Instrument of your choice".
- **Quantidade e alternativa de escolha** (fases 4 e 6):
  - Bard: "Choose 3 Musical Instruments";
  - Monk: "Artisan's Tools ou Musical Instrument".
- **Outras fases:**
  - `character_proficiencies` e `character_weapon_masteries` (fase 7);
  - links de feature para grant (fase 4).
- **Pool de escolha de perícias da classe** (`class_skills` + `skill_choices`): continua como está.
- **Fora do jogo modelado:** montarias, veículos, estilo de vida, comida, hospedagem e contratados. Também não entram compra, venda, troco nem conversão de moedas.
- **Sem coluna própria:** tempo de vestir e tirar armadura, e as entradas Utilize/Craft das ferramentas. Se houver, vão como texto em `description`.

## Regras de negócio

### Base de item

- `name` usa a grafia do SRD e não é único: um homebrew pode repetir o nome de um item SRD.
- **O item representa uma unidade.**
  - Na munição, preço e peso por unidade = valor do pacote SRD ÷ quantidade do pacote. "20 Arrows" é o item Arrow com `quantity=20`.
  - Peso "—" no SRD vira `0`.
  - "Waterskin 5 lb. (full)" vira `5`.
- **Coerência entre tipo e sub-tabela:**

  | Tipo | Sub-tabela |
  |---|---|
  | `weapon` | exatamente 1 linha em `weapons` |
  | `armor` | exatamente 1 linha em `armors` |
  | `tool` | exatamente 1 linha em `tools` |
  | `pack` | ≥ 1 linha em `item_contents` |
  | `adventuring_gear` | `containers` opcional; nenhuma outra |
  | `ammunition`, `currency` e tipos homebrew | nenhuma |

### Armas

- `is_ranged` segue a seção do SRD. Dart é ranged; Dagger e Javelin são melee com Thrown.
- **Dano:**
  - normal: `damage_dice_count` ≥ 1, `damage_die_size` ∈ {4, 6, 8, 10, 12, 20} e `damage_flat` com default 0;
  - Blowgun ("1 Piercing"): dados nulos e `damage_flat=1`;
  - CHECK: os dois campos de dado são ambos nulos ou ambos preenchidos; se forem nulos, `damage_flat` ≥ 1.
- `mastery_code` é FK para `weapon_masteries`. É nullable para homebrew; no seed, toda arma tem mastery.
- **`weapon_property_links`:** cada linha guarda só o parâmetro da propriedade dela.

  | Propriedade | Parâmetros |
  |---|---|
  | `range` | `range_normal_ft` > 0 e `range_long_ft` ≥ normal, ambos obrigatórios |
  | `versatile` | `versatile_die_size` obrigatório |
  | `ammunition` | `ammunition_item_id` obrigatório, apontando para um item `ammunition` |
  | demais, inclusive homebrew | todos os parâmetros nulos |

  "Thrown (Range 20/60)" vira duas linhas: `thrown` e `range(20,60)`.
- **Lance:** "Two-Handed (unless mounted)" vira só `two_handed`. A exceção vai em `description`.

### Armaduras

- `adds_dex_modifier`: booleano.
- `max_dex_modifier`: nullable. Medium = 2; Light, Heavy e Shield = null.
- `strength_requirement`: nullable. Chain Mail = 13; Splint e Plate = 15.
- `stealth_disadvantage`: booleano.
- **Shield:** `category_code=shield` e `base_ac=2`. Para shield, esse valor é um bônus; isso fica documentado no model.

### Ferramentas: referência × item

- **`tool_types`** é o alvo de proficiência: `code`, `name`, `category_code`, `ability_code`.
  - Categorias: `artisans_tools` (17), `gaming_set` (4), `musical_instrument` (10).
  - Categoria null para as 6 Other Tools: Disguise Kit, Forgery Kit, Herbalism Kit, Navigator's Tools, Poisoner's Kit e Thieves' Tools.
  - Cada variante é uma linha, porque o SRD exige proficiência separada por variante.
- **`tools`** é o item físico e aponta para `tool_types` por `tool_type_code`. Exemplo: o item "Dice Set" aponta para `dice_set`.
  - Não existem itens genéricos "Gaming Set" nem "Musical Instrument".
  - Vários itens podem apontar para o mesmo `tool_type` (caso de homebrew).
- **Codes do seed:** snake_case do nome, sem apóstrofo. Exemplos: `alchemists_supplies`, `thieves_tools`, `dice_set`, `pan_flute`.

### Containers

- Só os 4 com capacidade em libras: Backpack 30, Basket 40, Pouch 6 e Sack 30.
- Capacidade em volume ou em contagem não é modelada.

### Kits (`item_contents`)

- O pack precisa ter `item_type=pack`.
- O conteúdo não pode ser um `pack` nem o próprio item.
- Não pode haver pares (pack, item) duplicados; `quantity` ≥ 1.
- Peso e custo do pack são os do SRD, não a soma do conteúdo.

### Moedas

| Moeda | `cost_gp` | `weight_lb` |
|---|---|---|
| Copper Piece | 0.01 | 0.02 |
| Silver Piece | 0.1 | 0.02 |
| Electrum Piece | 0.5 | 0.02 |
| Gold Piece | 1 | 0.02 |
| Platinum Piece | 10 | 0.02 |

- O peso vem da regra "50 moedas = 1 lb".
- "14 GP" no inventário é uma linha Gold Piece com `quantity=14`.
- No equipamento inicial, "8 GP" é o item Gold Piece com `quantity=8`. A estrutura de `class_initial_equipment` e `background_initial_equipment` não muda.

### Proficiency grants

- **Colunas:** `id` (uuid) mais as colunas de alvo, todas nullable e todas com FK RESTRICT.

  | Coluna | Aponta para |
  |---|---|
  | `weapon_category_code` | `weapon_categories` |
  | `required_weapon_property_code` | `weapon_properties` (opcional, só junto com `weapon_category_code`) |
  | `armor_category_code` | `armor_categories` |
  | `tool_type_code` | `tool_types` |
  | `tool_category_code` | `tool_categories` |
  | `skill_code` | `skills` |
  | `saving_throw_ability_code` | `ability_scores` |
  | `language_code` | `languages` |

- CHECK: exatamente um alvo preenchido.
- `UNIQUE NULLS NOT DISTINCT` sobre as colunas de alvo, para que o mesmo alvo seja sempre o mesmo grant.
- **Semântica:**
  - Categoria de arma ou de armadura: **todas** as armas ou armaduras daquela categoria, filtradas pela propriedade exigida se houver. O "Martial com Finesse ou Light" do Rogue vira 2 grants.
  - `tool_category_code`: **escolha uma** ferramenta da categoria. A escolha concreta fica para a fase 7.
  - Os demais alvos são fixos.
- **`kind`:** valor derivado, sem coluna. Pode ser `weapon_category`, `armor_category`, `tool`, `tool_category`, `skill`, `saving_throw` ou `language`.
- **Criação:**
  - O cliente não cria grant diretamente. Classe e antecedente recebem descritores, como `{"weapon_category_code":"martial","required_weapon_property_code":"light"}`.
  - O servidor reaproveita o grant existente ou cria um novo, na mesma transação.
  - Grants órfãos permanecem no banco.
- **Saída:**
  - `ProficiencyGrantOut` = `{id, kind, <colunas de alvo>, target_name}`;
  - quando há propriedade exigida, inclui também `required_weapon_property_name`.

### Classe

- **Entrada (`ClassCreate`):**
  - saem `saving_throw_proficiencies`, `armor_proficiencies`, `weapon_proficiencies` e `tool_proficiencies`;
  - entra `proficiency_grants: list[descritor]`, que aceita qualquer `kind`;
  - descritores duplicados dão 422;
  - não mudam: `skills` + `skill_choices` (pool de escolha), `primary_ability` e `spell_ability`.
- **Saída (`ClassOut`):**
  - `proficiency_grants`;
  - `saving_throw_proficiencies: list[str]`, só leitura, derivado dos grants `saving_throw` e ordenado por code;
  - saem as listas de proficiência de armadura, arma e ferramenta.
- **Semântica:** todos os grants da classe são fixos, exceto `tool_category`, que significa "escolha uma".

### Antecedente

- **Entrada (`BackgroundCreate` e `BackgroundUpdate`):**
  - saem `skills` e `tool_proficiencies`;
  - entra `proficiency_grants: list[descritor]`.
- **Validação no schema (422):**
  - exatamente 2 grants `skill`, distintos;
  - pelo menos 1 grant `tool` ou `tool_category`;
  - nenhum outro `kind`;
  - sem duplicatas.
- **PATCH:** se `proficiency_grants` vier, substitui o conjunto inteiro.
- **Semântica:**
  - todos os grants do antecedente são fixos; a escolha é expressa por `tool_category`;
  - Soldier: um único grant `tool_category=gaming_set`;
  - a regra antiga "várias ferramentas = escolhe uma" deixa de existir.
- **Saída (`BackgroundOut`):**
  - `proficiency_grants`;
  - `skills: list[SkillOut]`, só leitura, derivado dos grants `skill` e ordenado por `name`;
  - sai `tool_proficiencies`.
- As regras de perícia do personagem com origem `background` (validação e sincronização) não mudam. Elas passam a ler as perícias derivadas dos grants.

### Endpoints de item

- **`GET /items`:**
  - público, com usuário opcional;
  - filtros: `item_type`, `search` (ILIKE em `name`, com escape de `%` e `_`), `weapon_category`, `armor_category`, `tool_category` (via `tool_types`) e `tool_type`;
  - ordem por `name`, com desempate por `id`.
- **`GET /items/{id}`:** devolve a base mais os sub-objetos; os que não se aplicam vêm null.
  - `weapon`, que inclui `properties: [{code, name, range_normal_ft, range_long_ft, versatile_die_size, ammunition_item_id, ammunition_item_name}]`;
  - `armor`;
  - `tool`: `{tool_type_code, tool_type_name, category_code, ability_code}`;
  - `container`;
  - `contents: [{item_id, item_name, quantity}]`.
- **`POST /items`** (usuário logado):
  - corpo com a base mais o sub-objeto do tipo;
  - grava `source=homebrew`, `is_homebrew=true` e `created_by`;
  - mandar `source`, `is_homebrew` ou `created_by` dá 422.
- **`PATCH /items/{id}`** (só o autor, só homebrew):
  - campos editáveis: `name`, `description`, `cost_gp`, `weight_lb` e o sub-objeto do tipo;
  - o sub-objeto enviado substitui o anterior inteiro. Vale para `weapon` (incluindo `properties`), `armor`, `tool`, `container` (`null` remove) e `contents`;
  - mandar `item_type_code`, `source`, `is_homebrew`, `created_by` ou `id` dá 422;
  - sub-objeto incompatível com o tipo dá 422.
- **`DELETE /items/{id}`** (só o autor, só homebrew):
  - responde 204 e apaga em cascata as próprias sub-linhas;
  - responde **409** se o item for referenciado por:
    - `character_inventory`;
    - `class_initial_equipment` ou `background_initial_equipment`;
    - `item_contents`, como conteúdo de outro pack;
    - `weapon_property_links.ammunition_item_id` de outra arma.
- **Matriz de PATCH/DELETE:**

  | Caso | Status |
  |---|---|
  | item SRD | 403 |
  | item de outro autor (itens são globais) | 403 |
  | item inexistente | 404 |
  | sem token | 401 |

- **Visibilidade e codes:** itens são globais (D6). Todo code referenciado num item segue a regra 6f da fase 1: precisa existir e ser visível, senão 400 com mensagem única.
- **Seed:** `source='srd'`, `is_homebrew=false`, `created_by=NULL`.

### Integridade com as tabelas de referência

O DELETE de uma referência homebrew também dá 409 quando ela é usada por:

- `weapons`: categoria, damage type ou mastery;
- `weapon_property_links`;
- `armors`;
- `tools.tool_type_code`;
- `tool_types`: categoria ou ability;
- `proficiency_grants`: qualquer coluna;
- `item_definitions.item_type_code`.

## Casos de borda e erros

### 422

**No item:**
- sub-objeto incompatível com o tipo;
- `pack` sem `contents`.

**No dano e nas propriedades de arma:**
- dados de dano parciais;
- `damage_die_size` inválido;
- range ≤ 0, ou long < normal;
- propriedade duplicada.

**Valores numéricos fora do intervalo:**
- `quantity` < 1;
- `cost_gp` ou `weight_lb` < 0;
- `base_ac` < 0;
- `max_dex_modifier` < 0;
- `strength_requirement` < 1;
- `capacity_weight_lb` ≤ 0.

**Conteúdo de kit:**
- conteúdo duplicado.

**Campos proibidos:**
- `item_type_code` no PATCH;
- `source`, `is_homebrew` ou `created_by` em qualquer escrita.

**No descritor de grant:**
- 0 alvos ou mais de 1 alvo;
- propriedade exigida sem `weapon_category_code`;
- descritores duplicados no mesmo dono.

**No antecedente:**
- número de skills diferente de 2;
- nenhuma ferramenta;
- `kind` não permitido.

### 400

- code referenciado inexistente ou invisível;
- `ammunition_item_id` inexistente ou que não é `ammunition`;
- conteúdo inexistente, que é um `pack` ou que é o próprio item;
- propriedade SRD sem o parâmetro exigido, ou propriedade sem parâmetro recebendo um parâmetro.

### Demais status e regras

- **403:** PATCH ou DELETE em item SRD ou de outro autor.
- **404:** item ou grant inexistente.
- **409:** DELETE de item referenciado, ou de referência em uso.
- **Atomicidade:** qualquer erro em POST ou PATCH de item, classe ou antecedente não grava nada.
- **Moeda:** a quantidade pode ir a 0 pelo PATCH de inventário. Não há troco nem soma automática.

## Impacto em dados e modelos

- **Banco:** recriado. A squash `c1fcfd7fe014` é reescrita e continua sendo a única revisão. Não há migração de dados.
- **`item_definitions`:** muda conforme o Escopo. `ItemOut` e `ItemCreate` mudam, e entra `ItemUpdate`.
- **Tabelas removidas:**
  - `tool_proficiency_options` (e o model `ToolProficiencyOption`);
  - `class_saving_throws`, `class_armor_proficiencies`, `class_weapon_proficiencies`, `class_tool_proficiencies`;
  - `background_skills`, `background_tool_proficiencies`.
- **`REFERENCE_MODELS`:** sai `tool_proficiency_options`; entram `item_types` e `tool_types`, num total de **24 recursos**. O CHECK de `campaign_homebrew_rules.resource_table` é atualizado.
- **Schemas** de classe e antecedente mudam conforme as seções acima.
- **`app/services/character.py`** continua funcionando com as perícias do antecedente derivadas dos grants.
- **Sem mudança estrutural:** `CharacterInventory`, `ClassInitialEquipment` e `BackgroundInitialEquipment`. `CharacterInventory.attuned` permanece.
- **Testes e factories:** precisam ser adaptados. As regras de negócio de perícia do personagem não mudam.

## Permissões

- `GET /items`, `GET /items/{id}` e `GET /proficiency-grants`: autenticação opcional; token inválido dá 401.
- `POST /items`: qualquer usuário logado.
- `PATCH /items/{id}` e `DELETE /items/{id}`: só o autor, só homebrew.
- `item_types` e `tool_types`: seguem a matriz da fase 1.
- Classe e antecedente: mantêm as regras atuais, e os codes respeitam a visibilidade.
- Não existe papel admin.

## Critérios de aceite

- [ ] **Migration:** em banco novo, `alembic upgrade head` aplica só `c1fcfd7fe014` e `alembic check` não aponta drift.
- [ ] **Limpeza:**
  - o grep abaixo não retorna nada:

    ```
    grep -rn "tool_proficiency_options\|ToolProficiencyOption\|class_saving_throws\|class_armor_proficiencies\|class_weapon_proficiencies\|class_tool_proficiencies\|background_skills\|background_tool_proficiencies" backend/app backend/alembic
    ```

  - `ItemDefinition` não tem coluna JSONB.
- [ ] **Estrutura:**
  - as tabelas novas existem e nenhuma usa JSONB;
  - `cost_gp` e `weight_lb` são NUMERIC(12,4);
  - `tools` tem só `item_id` e `tool_type_code`;
  - `proficiency_grants` tem o CHECK de alvo único, o UNIQUE NULLS NOT DISTINCT e `tool_type_code` com FK para `tool_types`.
- [ ] **Seed** (todas as linhas com `source='srd'`):

  | Conjunto | Contagem |
  |---|---|
  | `item_types` | 7 |
  | `tool_types` | 37 (17 / 4 / 10 / 6 null) |
  | moedas | 5 |
  | `weapons` | 38 (10 / 4 / 18 / 6) |
  | `armors` | 13 |
  | `tools` | 37 |
  | `ammunition` | 5 |
  | `pack` | 7 |
  | `containers` | 4 |
  | `item_contents` | 64 |
  | `adventuring_gear` | 82 (71 da tabela, menos 4 "Varies" e 7 packs, mais 11 variantes de foco) |
  | **total `item_definitions`** | **187** |

- [ ] **Valores pontuais:**

  | Item | Valores esperados |
  |---|---|
  | Dagger | 1d4 piercing, simple, melee, mastery nick; propriedades finesse, light, thrown e range(20/60) |
  | Longbow | ranged, martial, 1d8; ammunition → Arrow; range(150/600); heavy; two_handed |
  | Longsword | versatile d10 |
  | Blowgun | dados nulos, `damage_flat=1` |
  | Greatsword | 2d6 |
  | Plate Armor | 18, força 15, stealth disadvantage, sem Dex, 1500 GP |
  | Hide Armor | 12, adiciona Dex, máximo 2 |
  | Shield | categoria shield, `base_ac=2` |
  | `tool_types/thieves_tools` | categoria null, dex |
  | `tool_types/lute` | musical_instrument, cha |
  | `tool_types/dice_set` | gaming_set, wis |
  | Item Lute | `tool_type_code=lute`, 35 GP, 2 lb |
  | Item Dice Set | `dice_set`, 0.1 GP |
  | Arrow | 0.05 GP, 0.05 lb |
  | Bullet, Sling | 0.002 GP, 0.075 lb |
  | Bullet, Firearm | 0.3 GP, 0.2 lb |
  | Needle | 0.02 GP, 0.02 lb |
  | Copper Piece | 0.01 GP, 0.02 lb |
  | Electrum Piece | 0.5 GP |
  | Explorer's Pack | 10 GP, 55 lb, 8 conteúdos, incluindo Torch ×10 e Rations ×10 |
  | Backpack | capacidade 30 |
  | Entertainer's Pack | 58.5 lb |

- [ ] **Referências novas:**
  - `GET /tool-types` e `GET /item-types` respondem 200 sem token, só com SRD;
  - POST de `tool_types` com categoria invisível dá 400;
  - DELETE de `tool_types` homebrew usado por um item ou por um grant dá 409;
  - `GET /tool-proficiencies` dá 404.
- [ ] **`GET /items`:**
  - respostas determinísticas;
  - `item_type=weapon` retorna 38, `weapon_category=martial` retorna 24 e `tool_category=gaming_set` retorna 4;
  - `search=sword` não diferencia maiúsculas;
  - o detalhe traz o sub-objeto certo e null nos outros;
  - inexistente dá 404.
- [ ] **`POST /items`:**
  - arma, pack e ferramenta homebrew válidos dão 201;
  - sem token dá 401;
  - sub-objeto incompatível dá 422;
  - code inválido ou invisível dá 400;
  - munição que não é ammunition dá 400;
  - nada é gravado em caso de erro.
- [ ] **`PATCH /items`:**
  - o autor altera o nome e substitui as propriedades: 200;
  - `item_type_code` no corpo dá 422;
  - item SRD dá 403, outro autor dá 403, inexistente dá 404.
- [ ] **`DELETE /items`:**
  - sem referências: 204, e as sub-linhas somem;
  - 409 em cada um dos casos: inventário, equipamento inicial de classe, conteúdo de outro pack e munição de outra arma;
  - item SRD dá 403.
- [ ] **Classe:**
  - POST com saves str/con, simple, martial+light, armor light, armor shield e tool herbalism_kit dá 201 e ecoa os grants com `kind`;
  - `saving_throw_proficiencies=["con","str"]`;
  - uma segunda classe com `simple` reusa o mesmo `grant.id`;
  - descritor com 2 alvos dá 422;
  - code invisível dá 400 sem gravar nada.
- [ ] **Antecedente:**
  - Soldier com 2 skills e `tool_category=gaming_set` dá 201;
  - `skills` derivado traz 2 itens; o grant aparece com `kind=tool_category`;
  - 1 ou 3 skills dão 422; sem ferramenta dá 422; `armor_category` dá 422;
  - PATCH substitui os grants.
- [ ] **Perícias do personagem:** os testes de origem `background` e de sincronização continuam passando, alterando só o setup.
- [ ] **Moeda:**
  - POST de inventário com Gold Piece e `quantity=14` grava a linha `item_name="Gold Piece"` com 14;
  - o equipamento inicial aceita Gold Piece ×8.
- [ ] **409 em referência homebrew usada:** `weapon_masteries` usada por arma, `item_types` usada por item, `weapon_properties` usada como `required_weapon_property_code`, `skills` usada por grant de antecedente.
- [ ] **`GET /proficiency-grants`:** lista e detalhe públicos; inexistente dá 404.
- [ ] **Testes:** `python -m pytest -q` passa.

## Decisão do usuário no gate #1 (2026-10-05)

- **Não existe proficiência em arma específica.** No SRD, a proficiência em arma é sempre por categoria (Simple, Martial), com filtro de propriedade opcional (Monk: Martial com Light; Rogue: Martial com Finesse ou Light).
- Por isso `proficiency_grants` **não tem** `weapon_item_id` nem o `kind` `weapon`. O alvo de arma é só `weapon_category_code`, com o `required_weapon_property_code` opcional.

## Suposições

- **Nomes de tabelas:** `tool_types` (rota `tool-types`) é a referência alvo de proficiência; `tools` é o 1:1 do item físico.
- **Gaming Sets:** grafia do SRD 5.1 — Dice Set, Dragonchess Set, Playing Card Set e Three-Dragon Ante Set. Peso 0.
- **Instrumentos:** Bagpipes, Drum, Dulcimer, Flute, Horn, Lute, Lyre, Pan Flute, Shawm e Viol. O item físico tem o mesmo nome do `tool_type`.
- **Munição:** nomes no singular, um por unidade — Arrow, Bolt, "Bullet, Firearm", "Bullet, Sling" e Needle.
- **Focos:** são `adventuring_gear`, com nomes como "Arcane Focus (Crystal)". "Staff (also a Quarterstaff)" é um item separado da arma Quarterstaff.
- **Potion of Healing e Spell Scroll** (Cantrip e Level 1) entram como `adventuring_gear`.
- **Inventário:** não soma quantidades e não faz troco.
- **Grants órfãos:** permanecem no banco.
- **Ordenação dos derivados:** `saving_throw_proficiencies` por code; `skills` do antecedente por `name`.
- **UUIDs do seed:** podem ser determinísticos; decisão do planejador.

## Perguntas em aberto

- **Quantidade e alternativa de escolha** (Bard e Monk): dependem do mecanismo de escolha das fases 4 e 6.
- **Vazamento de code**, herdado da fase 1.
- **Containers com capacidade em volume ou em contagem:** só serão modelados quando houver uma regra que os use.
