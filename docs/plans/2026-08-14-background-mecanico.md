# Plano de Execução: Antecedente (`BackgroundDefinition`) mecanicamente completo

## Referência
Especificação: dar a `BackgroundDefinition` os cinco componentes mecânicos exigidos pela SRD 2024 (atributos elegíveis, talento de origem, perícias, proficiência de ferramenta, equipamento inicial), reaproveitando os padrões já usados por `ClassDefinition` em `backend/app/db/models/compendium.py` — Gap #1 de `docs/plans/2026-08-13-gaps-criacao-personagem.md`.

## Etapas técnicas (ordem de execução)

### 1. Modelo ORM — `backend/app/db/models/compendium.py`
- Adicionar duas `Table()` Core novas, ao lado de `class_primary_abilities`/`class_skills` (linhas 46-93):
  - `background_ability_scores`: colunas `background_id` (UUID, FK `background_definitions.id`, `ondelete="CASCADE"`, PK) e `ability_score` (String(3), FK `ability_score_options.name`, PK) — espelha `class_primary_abilities` linha por linha.
  - `background_skills`: colunas `background_id` (UUID, FK `background_definitions.id`, `ondelete="CASCADE"`, PK) e `skill_id` (UUID, FK `skill_definitions.id`, PK) — espelha `class_skills`.
- Editar `BackgroundDefinition` (atualmente linhas 191-200):
  - Novas colunas: `feat_id` (UUID, FK `feat_definitions.id`, `nullable=False`) e `tool_proficiency` (String(60), FK `tool_proficiency_options.name`, `nullable=False`).
  - Novas relações, todas `lazy="selectin"`: `ability_scores` (M2M via `background_ability_scores` → `AbilityScoreOption`), `skills` (M2M via `background_skills` → `SkillDefinition`), `feat` (`relationship()` simples para `FeatDefinition`, mesmo padrão do `item`/`class_def` em `ClassInitialEquipment`/`SubclassDefinition`), `initial_equipment` (`relationship(back_populates=..., cascade="all, delete-orphan", lazy="selectin")`).
  - Property `feat_name` espelhando `SubclassDefinition.class_name` (linhas 186-188) / `ClassInitialEquipment.item_name` (linhas 279-281).
- Nova classe ORM `BackgroundInitialEquipment`, posicionada perto de `ClassInitialEquipment` (linhas 266-281), espelhando-a campo a campo: `id`, `background_id` (FK `background_definitions.id`, `ondelete="CASCADE"`, `nullable=False`), `item_id` (FK `item_definitions.id`, `nullable=False`), `option` (String(10), `nullable=False`), `quantity` (Integer, `nullable=False`, `default=1`), `__table_args__ = (CheckConstraint("quantity >= 1", name="ck_background_initial_equipment_quantity_positive"),)`, relationships `background: Mapped["BackgroundDefinition"] = relationship(back_populates="initial_equipment")` e `item: Mapped["ItemDefinition"] = relationship()`, property `item_name`.
- **Resultado esperado**: `BackgroundDefinition` e `BackgroundInitialEquipment` com a mesma forma estrutural que `ClassDefinition`/`ClassInitialEquipment`.
- **Critério de pronto**: `python -c "import app.db.models.compendium"` sem erro; `Base.metadata.tables` contém `background_ability_scores`, `background_skills`, `background_initial_equipment`; nenhuma outra tabela/model existente foi alterada.

### 2. Migration squash — `backend/alembic/versions/c1fcfd7fe014_initial_schema.py`
- Editar diretamente esta migration (decisão já tomada e reiterada em rodadas anteriores da sessão — squash, sem `alembic revision --autogenerate` novo, sem dado real em nenhum ambiente).
- Em `upgrade()`:
  - Adicionar `feat_id` (UUID, not null, FK `feat_definitions.id`) e `tool_proficiency` (String(60), not null, FK `tool_proficiency_options.name`) a `background_definitions`.
  - **Atenção de ordenação**: `background_definitions` é criada na linha 64, antes de `feat_definitions` (linha 115) e antes de `tool_proficiency_options` já existir (linha 45, essa já vem antes — ok). Como `feat_definitions` só é criada depois, as duas novas colunas FK de `background_definitions` só podem ser adicionadas com `sa.ForeignKeyConstraint` depois que `feat_definitions` existir — mover a criação de `background_definitions` para depois de `feat_definitions`, ou emitir as colunas via `op.add_column`/`op.create_foreign_key` após a criação de `feat_definitions`. Deixo a escolha da técnica para o agente de dev; o critério de pronto abaixo é o que importa.
  - Criar `background_ability_scores`, `background_skills`, `background_initial_equipment` (com `CheckConstraint`) na mesma região onde as tabelas `class_*` análogas são criadas (linhas 209-261), respeitando que todas as tabelas referenciadas (`background_definitions`, `ability_score_options`, `skill_definitions`, `item_definitions`) já existam antes.
- Em `downgrade()`: inverter exatamente — `drop_table` das 3 tabelas novas antes de `drop_table('background_definitions')`, e reverter as colunas `feat_id`/`tool_proficiency` (drop de FK/coluna) na ordem inversa da criação.
- **Resultado esperado**: uma única migration squashed que cria o schema final (antigo + novo) do zero.
- **Critério de pronto** (requer banco Postgres local ativo, ver seção de ação humana):
  - `alembic downgrade base` seguido de `alembic upgrade head` roda limpo, sem erro de FK/ordem.
  - `alembic check` (ou equivalente `--autogenerate` a seco) não acusa drift entre modelos e migration.
  - Round-trip `upgrade head` → `downgrade base` → `upgrade head` idempotente.

### 3. Schemas Pydantic — `backend/app/schemas/compendium.py`
- Adicionar `BackgroundInitialEquipmentOut`/`BackgroundInitialEquipmentCreate`, espelhando `ClassInitialEquipmentOut`/`ClassInitialEquipmentCreate` (linhas 74-88), trocando `class_id` por `background_id`.
- Reescrever `BackgroundOut` (atualmente linhas 158-166): campos adicionais `ability_scores: list[AbilityScore]` (com o mesmo padrão `field_validator(mode="before")` + `_pluck` usado em `ClassOut.primary_ability`, linhas 112-115), `feat_id: uuid.UUID`, `feat_name: str`, `skills: list[SkillOut]`, `tool_proficiency: str`, `initial_equipment: list[BackgroundInitialEquipmentOut]`.
- Reescrever `BackgroundCreate` (atualmente linhas 168-171): `ability_scores: list[AbilityScore]` com `field_validator` que rejeita cardinalidade ≠ 3 e duplicatas; `feat_id: uuid.UUID`; `skills: list[SkillCreate]` com `field_validator` que rejeita cardinalidade ≠ 2 e duplicatas; `tool_proficiency: str`; `initial_equipment: list[BackgroundInitialEquipmentCreate] = Field(default_factory=list)`.
- **Resultado esperado**: `BackgroundCreate`/`BackgroundOut` com a mesma riqueza estrutural de `ClassCreate`/`ClassOut`.
- **Critério de pronto**: instanciar `BackgroundCreate` com 2 ou 4 `ability_scores`, ou com duplicata em `ability_scores`/`skills`, levanta `pydantic.ValidationError` (422 quando exposto via FastAPI); payload do caso Nobre da especificação valida sem erro.

### 4. Serviço / fluxo de resolução — `backend/app/services/compendium.py` e `backend/app/api/compendium.py`
- Não é necessário criar abstrações de serviço novas: reaproveitar `_resolve_options` (já em `app/api/compendium.py`, linhas 41-55) para `ability_scores` (contra `AbilityScoreOption`) e para `tool_proficiency` (contra `ToolProficiencyOption`, get-or-create de uma lista de 1 nome), e `resolve_skills`/`ensure_ability_score_options` (`app/services/compendium.py`) para `skills`.
- Reescrever `create_background` (`app/api/compendium.py`, a partir da linha 205) seguindo o fluxo de `create_class` (linhas 102-157):
  1. Construir `BackgroundDefinition` sem os campos M2M/relacionais, `db.add`, `db.flush()`.
  2. `db.refresh(obj, attribute_names=["ability_scores", "skills", "initial_equipment"])` antes de reatribuir essas coleções (mesma correção de `MissingGreenlet` já aplicada em `create_class`, linhas 128-131).
  3. Validar `feat_id`: buscar `FeatDefinition` por id; se não existir, `HTTPException(status_code=400, ...)` — **400, não 404** (a especificação confirma 400 tanto em "Casos de borda" quanto em "Critérios de aceite", mesmo padrão do `item_id` inválido em `create_class` linhas 144-147).
  4. `obj.ability_scores = await _resolve_options(db, AbilityScoreOption, [a.value for a in data.ability_scores])`.
  5. `obj.tool_proficiency` já é uma FK simples (string) — resolver/criar a linha em `ToolProficiencyOption` via `_resolve_options` (get-or-create de 1 elemento) antes de atribuir `obj.tool_proficiency = <nome>`, do mesmo jeito que `spell_ability` é tratado em `create_class` (linhas 104-108, `ensure_ability_score_options`), pois é FK e pode referenciar um valor ainda não cadastrado.
  6. `obj.skills = await resolve_skills(db, data.skills)`.
  7. Iterar `data.initial_equipment`: validar cada `item_id` existe (`HTTPException(400, ...)` se não, mesmo padrão de `create_class` linhas 144-147); `db.add(BackgroundInitialEquipment(background_id=obj.id, ...))`.
  8. `await db.commit()`; `await db.refresh(obj)` antes de retornar.
- **Resultado esperado**: `create_background` mecanicamente equivalente a `create_class`.
- **Critério de pronto**: chamar `create_background` com o payload do caso Nobre da especificação retorna um objeto com todos os 5 componentes populados; `feat_id` inexistente e `item_id` inexistente cada um levanta `HTTPException(400)`.

### 5. Infraestrutura de teste — `backend/tests/integration/conftest.py`
- `seed_background` (linhas 131-143) hoje não fornece `feat_id`/`tool_proficiency`; como esses campos passam a ser `nullable=False`, `seed_background` (e qualquer chamada existente, ex. `backend/tests/integration/test_character_name_fields.py:32`) vai quebrar sem ajuste.
- Ajustar `seed_background` para, por padrão, garantir (get-or-create, mesmo estilo de `_ensure_ability_score_options`) um `FeatDefinition` e um `ToolProficiencyOption` mínimos quando não informados via `overrides`, preservando a assinatura pública atual (chamadas existentes continuam funcionando sem mudança).
- Adicionar helpers análogos aos já existentes para uso pelos novos testes de integração: `seed_feat` (mesmo estilo de `seed_species`/`seed_class`) e `seed_background_initial_equipment` (mesmo estilo de `seed_class_initial_equipment`, linhas 355-369).
- **Resultado esperado**: nenhuma quebra em testes existentes que usam `seed_background`; novos helpers disponíveis para os testes do passo 6.
- **Critério de pronto**: suíte de testes existente que usa `seed_background` (`test_character_name_fields.py`) continua passando sem alteração no próprio arquivo de teste.

### 6. Testes novos — novo arquivo `backend/tests/integration/test_compendium_background_mechanics.py`
- Seguir o padrão de `backend/tests/integration/test_compendium_skills_equipment.py` (import direto das funções do router, `db_session` fixture, helpers `seed_*`).
- Cobrir, no mínimo, cada item de "Critérios de aceite" da especificação:
  - Criação completa do caso Nobre (`ability_scores=["STR","INT","CHA"]`, `feat_id` válido, `skills` com 2 entradas, `tool_proficiency`, `initial_equipment` com 3 itens) via `create_background` retorna objeto com os 5 componentes ecoados corretamente.
  - `ability_scores` com 2 ou 4 elementos → `pydantic.ValidationError` ao construir `BackgroundCreate` (422 na camada FastAPI).
  - `skills` com 1 ou 3 elementos → `ValidationError`.
  - `ability_scores` e `skills` com duplicata → `ValidationError`.
  - `feat_id` inexistente → `create_background` levanta `HTTPException(400)`.
  - `item_id` inexistente em `initial_equipment` → `HTTPException(400)`.
  - `quantity < 1` em `BackgroundInitialEquipmentCreate` → erro de validação Pydantic (`ge=1`, mesmo padrão de `ClassInitialEquipmentCreate`).
  - Deletar um `background_id` via `db_session.delete`/`db.execute(delete(...))` propaga cascade para `background_initial_equipment`, `background_skills`, `background_ability_scores` (teste de integração direto no banco, análogo ao que já existe implicitamente via `ondelete="CASCADE"` nas tabelas `class_*` — verificar se já existe um teste de cascade para classe a reaproveitar como modelo; se não existir, este é o primeiro).
- **Resultado esperado**: cobertura de todos os critérios de aceite verificáveis da especificação.
- **Critério de pronto**: `pytest backend/tests/integration/test_compendium_background_mechanics.py -v` — todos os testes passam contra o banco de teste local pós-migration.

### 7. Validação de regressão completa
- Rodar a suíte inteira (`pytest backend/tests`) e confirmar: os 203 testes pré-existentes continuam passando (sem regressão) + os testes novos do passo 6.
- Rodar novamente o round-trip de migration (`alembic downgrade base && alembic upgrade head`, mais uma vez, como sanity final pós-todas-as-edições).
- **Resultado esperado**: suíte verde, migration limpa.
- **Critério de pronto**: 0 falhas, 0 erros; nenhum teste pré-existente foi modificado além do necessário no passo 5 (`conftest.py`, se aplicável).

## Pontos que exigem ação humana
- [ ] **Confirmar que nenhum ambiente compartilhado/produção já aplicou a migration `c1fcfd7fe014`** — motivo: editar uma migration já aplicada em qualquer ambiente fora do local do desenvolvedor quebra o histórico do Alembic nesse ambiente (a revision hash muda de significado); esta sessão já tratou isso como não-bloqueante em rodadas anteriores, mas a squash edit direta é irreversível uma vez que outro ambiente exista — quando: antes da etapa 2.
- [ ] **Resetar/recriar o banco de teste local (`dnd_test`, via `docker-compose`) do zero antes de validar a migration** — motivo: `alembic downgrade base && upgrade head` e o round-trip de validação exigem um Postgres local acessível e limpo; ação de infraestrutura local, não de código. **Pré-aprovado nesta sessão** (mesmo padrão já executado nas rodadas anteriores documentadas em `docs/plans/2026-08-12-multiclasse-skills-equipamento.md` e `docs/plans/2026-08-13-fk-spell-ability.md`) — o agente de dev pode executar diretamente (`docker compose down -v && docker compose up -d`, ou `dropdb`/`createdb`) sem nova aprovação explícita, desde que seja o banco local `dnd_test`/`dnd_dev`, nunca um ambiente remoto — quando: antes da etapa 2 (validação de migration) e novamente na etapa 7.
- [ ] **Decisão em aberto: adicionar `GET /backgrounds/{id}` e `PATCH /backgrounds/{id}`** — motivo: a especificação deixa isso explicitamente como não exigido nesta rodada, mas sugere que o planejador avalie se vale adicionar "sem custo extra relevante". Avaliação técnica: o custo NÃO é desprezível — mudar o escopo da API é decisão de produto, e hoje nem `GET /classes/{id}` tem um padrão de edição (`PATCH`) implementado para reaproveitar; adicionar só para `backgrounds` quebraria a simetria com `classes`/`species`/etc., que também não têm `PATCH`. **Recomendação: não incluir nesta rodada**, por consistência (mesma decisão já vigente para `classes`). Isso fica como decisão explícita do usuário caso queira contrariar a recomendação — quando: antes de iniciar a etapa 6 (não bloqueia etapas 1-5, que não dependem dessa decisão).

## Workflow para os próximos agentes
- Ordem: refinamento (concluído) → planejamento (este) → dev-tdd → QA.
- dev-tdd segue TDD estrito, etapa por etapa, na ordem 1→2→3→4→5→6→7 acima. Etapas 1-2 (modelo + migration) são bloqueantes para todas as demais (schemas/API/testes dependem das colunas e tabelas existirem). Etapa 3 (schemas) e a preparação da etapa 5 (helpers de teste) podem ser feitas em paralelo entre si, mas ambas bloqueiam a etapa 4 (API) e a etapa 6 (testes de comportamento). Etapa 7 só roda depois de 1-6 completas.
- Checkpoint intermediário sugerido para o QA: nada impede QA revisar a etapa 1-2 isoladamente (schema + migration limpos) antes do restante estar pronto, mas o critério de aprovação final abaixo só se aplica após TODAS as etapas.
- Critério de aprovação do QA (derivado dos critérios de aceite da especificação):
  - `BackgroundDefinition` tem M2M para 3 `AbilityScoreOption`, FK obrigatória para `FeatDefinition`, M2M para 2 `SkillDefinition`, FK obrigatória para `ToolProficiencyOption`, relação `initial_equipment`.
  - `BackgroundInitialEquipment` existe com `id, background_id, item_id, option, quantity`, `CheckConstraint(quantity>=1)`, `ondelete="CASCADE"` em `background_id`.
  - `POST /backgrounds` aceita o payload do caso Nobre e retorna 201 com os 5 componentes ecoados em `BackgroundOut`.
  - `ability_scores`/`skills` com cardinalidade errada ou duplicata → 422.
  - `feat_id` inexistente → 400; `item_id` inexistente em `initial_equipment` → 400.
  - Migration squashed roda limpa do zero, round-trip `downgrade`→`upgrade` sem drift.
  - Suíte completa (203 testes pré-existentes + novos) verde, sem regressão.

## Riscos / bloqueios conhecidos
- Ordem de criação de tabelas na migration squashed: `background_definitions` é criada antes de `feat_definitions` no arquivo atual; a etapa 2 precisa resolver essa dependência circular de ordem (mover a criação da tabela ou usar `add_column`/`create_foreign_key` pós-hoc) sem quebrar a ordem de `downgrade()`. Risco baixo, mas fácil de errar silenciosamente (só aparece ao rodar `upgrade head` do zero).
- `seed_background` em `tests/integration/conftest.py` é usado por pelo menos um teste fora do escopo direto desta mudança (`test_character_name_fields.py`); qualquer alteração de assinatura (em vez de valores-padrão internos get-or-create) quebraria esse teste — a etapa 5 deve preservar compatibilidade retroativa.
- `feat_id`/`tool_proficiency` como `NOT NULL` sem dado semente (seed data) de antecedentes/talentos/ferramentas reais da SRD 2024 no banco: fora do escopo desta mudança popular o catálogo real (Nobre, Habilidoso, etc.) — isso é dado de conteúdo, não de schema/API, mas fica registrado como próximo gap natural após este.
- Nenhuma dependência nova, nenhum segredo novo, nenhum deploy — risco de infraestrutura limitado ao reset do banco de teste local (já coberto na seção de ação humana).
