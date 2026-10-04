# Teste de criação de personagem (Guerreiro) e modelagem de features

Data: 2026-10-03 — status: **em andamento / ideia de features em amadurecimento**

## Objetivo do teste

Validar a modelagem criando um personagem real, usando apenas os endpoints
existentes, sem inventar dados nem adaptar o modelo. O que não couber volta
para decisão.

Etapas planejadas:

1. Escolher a classe — **Guerreiro** (feito, parcial: falta a parte de features)
2. Determinar a origem (antecedente / espécie) — pendente, bloqueada (ver "Banco local")
3. Determinar os valores de atributos — pendente
4. Escolher o alinhamento — pendente
5. Preencher os detalhes — pendente

## Classe Guerreiro — dados informados

- Atributo primário: Força ou Destreza
- Dado de vida: d10
- Salvaguardas: Força, Constituição
- Perícias: escolher 2 entre Acrobacia, Atletismo, História, Intimidação,
  Intuição, Lidar com Animais, Percepção, Persuasão, Sobrevivência
- Armas: simples e marciais
- Armaduras: leves, médias, pesadas e escudos
- Equipamento inicial (escolher A, B ou C):
  - **A**: 8 azagaias, cota de malha, espada grande, kit de aventureiro, mangual, 4 PO
  - **B**: 20 flechas, aljava, arco longo, armadura de couro batido, cimitarra,
    espada curta, kit de aventureiro, 11 PO
  - **C**: 155 PO
- Nível 1: **Estilo de Luta** — "Você apurou sua proeza marcial e ganha um
  talento de estilo de luta à sua escolha, sempre que ganhar um nível em
  guerreiro você pode substituir o talento que escolheu por um talento de
  estilo de luta diferente". Mais 2 features de nível 1 ainda não informadas.

## O que foi cadastrado (banco local de dev)

- Usuário de teste: `teste.guerreiro@example.com` / `senha12345`
- Itens (`POST /api/compendium/items`), apenas `name` + `item_type`
  (peso, custo, dano e propriedades não foram informados, ficaram vazios):
  - weapon: Azagaia, Espada Grande, Mangual, Arco Longo, Cimitarra, Espada Curta
  - armor: Cota de Malha, Armadura de Couro Batido
  - gear: Kit de Aventureiro, Flecha, Aljava
  - currency: Peça de Ouro, Peça de Prata, Peça de Cobre, Peça de Platina
- Classe Guerreiro (`POST /api/compendium/classes`): hit_die 10, primary
  STR/DEX, salvaguardas STR/CON, 4 proficiências de armadura, 2 de armas,
  `skill_choices=2` com as 9 perícias (atributo de cada uma pelo SRD),
  equipamento A/B/C com ouro, `subclass_level=3` (default, não informado).
  O payload usado está reproduzível a partir da lista acima.

## Decisões tomadas

- **Moedas são itens** (`item_type="currency"`): PO, PP, PC, PL. Equipamento
  inicial em ouro usa `ClassInitialEquipment` com a quantidade.
- **Kit de Aventureiro** é um item único — o modelo não tem itens compostos.
- **Features**: seguir a ideia de tabela relacional "o que afetar / como afetar"
  (detalhada abaixo), substituindo `FeatureGrant.effect_data` (JSONB).

## Problemas encontrados

1. **Bug corrigido** — `POST /classes` (e depois `GET /classes`) retornava 500:
   `ClassInitialEquipment.item` e `BackgroundInitialEquipment.item` eram lazy
   load síncrono; ao serializar `item_name` fora do contexto async, dava
   `MissingGreenlet`. Os testes não pegavam porque o item continuava no
   identity map da sessão. Correção: `relationship(lazy="selectin")` nos dois
   modelos + 2 testes de regressão.
2. **Banco local desatualizado** — `GET /backgrounds` retorna 500
   (`background_definitions.feat_id does not exist`). O commit 748929e editou a
   migration squashed `c1fcfd7fe014` em vez de criar uma nova, então bancos
   criados antes dela ficaram sem as colunas/tabelas de antecedente. Não cabe
   migration nova (duplicaria em banco novo). Solução: recriar o schema local
   (a partir da raiz do repo):
   ```
   docker compose exec -T db psql -U dnd -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
   docker compose exec -T backend alembic upgrade head
   ```
   Depois disso, recadastrar usuário, itens e classe acima.
3. **Estilo de Luta** — não há talentos `fighting_style` cadastrados nem como
   registrar a escolha do personagem / a troca a cada nível.

## Modelagem de features — ideia em amadurecimento

Hoje: `FeatureGrant` (source_type, source_id, name, description,
level_requirement, is_optional, sort_order) + `effect_type` + `effect_data`
JSONB. Objetivo: trocar o JSON por tabela relacional.

### Proposta base: `feature_effects` ("o que afetar" + "como afetar")

N linhas por `FeatureGrant`:

```
feature_effects
  id
  feature_grant_id   FK feature_grants
  operation          -- "grant" | "choose" | "add" | "set" | "grant_proficiency"
                     --  | "grant_expertise" | "advantage" | "reroll"
  target_type        -- "feat" | "spell" | "feature" | "item" | "ability_score"
                     --  | "skill" | "saving_throw" | "armor_prof" | "weapon_prof"
                     --  | "ac" | "speed" | "hp_max" | "attack_roll" | "damage_roll" | "resource"
  -- referência tipada (CHECK: no máximo uma preenchida, coerente com target_type)
  feat_id            FK null
  spell_id           FK null
  granted_feature_id FK feature_grants null
  item_id            FK null
  ability_score      FK ability_score_options null
  skill_id           FK null
  value              int null
  value_formula      text null   -- ex.: "proficiency_bonus", "1d10+fighter_level"
  condition          text null   -- ex.: "wielding_two_handed", "wearing_armor"
```

### Features que concedem outras entidades (ideia do usuário)

Muitas features só dizem "ganhe X": "ganhe o talento X", "ganhe a magia X",
"ganhe a feature X de outra classe". Isso vira `operation="grant"` com
`target_type` apontando para a entidade e o FK tipado preenchido — o banco
garante que X existe (por isso FKs tipados em vez de um `target_ref` texto).

### Grant fixo vs. escolha

O Estilo de Luta não concede um talento fixo: é **escolha** de qualquer talento
da categoria `fighting_style`. Proposta:

- `operation="choose"` + filtro do conjunto de opções, ex.:
  `pool_target_type="feat"`, `pool_category="fighting_style"`, `choose_count=1`
  (alternativa: tabela `feature_effect_options` listando as opções permitidas
  explicitamente, quando o conjunto não for definível por filtro)
- Tabela do personagem para registrar a escolha, ex.
  `character_feature_choices (character_id, feature_effect_id, chosen_*_id, chosen_at_level)`
  — permite a troca a cada nível de guerreiro.

Exemplos: "ganhe a magia X" → `grant`; "escolha um truque de mago" → `choose`.

### Parâmetros extras de magia concedida

Magias concedidas costumam ter atributo de conjuração, número de usos e recarga
(ex.: magias de espécie 1x por descanso longo). Colunas no efeito ou tabela
satélite (ex. `spell_ability`, `uses`, `recharge`).

### Recursos com usos

Features como Retomar o Fôlego / Surto de Ação são recursos limitados
(`max_uses` ou fórmula, `recharge` = short/long rest, escala por nível),
ligáveis a `character_resources` (já existe).

### Em aberto para discutir

- Fórmulas (`value_formula`): texto livre interpretado pelo motor ou um
  conjunto fechado de variáveis?
- `condition`: texto livre ou enum/lookup table?
- Escolha por filtro vs. lista explícita de opções (ou ambos).
- Tabela única `feature_effects` com FKs tipados vs. tabelas por tipo de efeito.
- O que fazer com features puramente narrativas (só `description`, sem efeito).
- Migração do `effect_data` existente (hoje não há `feature_grants` cadastrados).
- As outras 2 features de nível 1 do Guerreiro.
