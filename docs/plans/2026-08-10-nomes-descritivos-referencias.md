# Plano de Execução: Exposição de nomes descritivos ao lado de IDs de referência

## Referência
Especificação: adicionar campos `_name` (ex. `user_name`, `campaign_name`, `species_name`) ao lado de cada ID de referência já existente em `CharacterOut`, `InventoryItemOut`, `CampaignOut`, `MemberOut` e `SubclassOut`, sem remover/renomear campos atuais e sem gerar N+1 nos endpoints de lista.

## Estado atual relevante (ancoragem no código)
- `backend/app/db/models/character.py` — `Character` já tem `owner` (→`User`) e `campaign` (→`Campaign`); **faltam** relationships para `SpeciesDefinition`, `BackgroundDefinition`, `ClassDefinition`, `SubclassDefinition`. `CharacterInventory` já tem `item` (→`ItemDefinition`); **falta** relationship para `User` via `added_by`.
- `backend/app/db/models/campaign.py` — `Campaign` **falta** relationship para `User` via `created_by`. `CampaignMember` já tem `user` e `campaign` — nenhuma mudança de model necessária aqui.
- `backend/app/db/models/compendium.py` — `SubclassDefinition.class_def` (→`ClassDefinition`) já existe — nenhuma mudança de model necessária.
- `backend/app/db/session.py` — `async_session = async_sessionmaker(engine, expire_on_commit=False)`. Isso importa para a Etapa 3 (ver nota técnica sobre `db.refresh()`).
- `backend/app/services/character.py` — `get_character_or_404` e `list_characters_for_campaign` só fazem `selectinload(Character.inventory)`. `create_character`, `update_character`, `apply_hp_update`, `add_item` fazem `db.refresh(obj)` sem `attribute_names`.
- `backend/app/api/characters.py` — `my_characters` (GET `/characters/me`) faz um `select(Character)` cru, **sem nenhum eager-load**. `update_inventory_item` (PATCH inventory) faz um `select(CharacterInventory)` cru, sem eager-load de `item`/`added_by`.
- `backend/app/api/campaigns.py` — `create_campaign`, `list_my_campaigns`, `get_campaign`, `update_campaign`, `join_campaign`, `list_members` fazem `select()` sem eager-load de `creator`/`user`/`campaign`.
- `backend/app/api/compendium.py` — `list_subclasses`/`create_subclass` sem eager-load de `class_def`.
- `backend/tests/conftest.py` — `FakeAsyncSession.execute` é um `AsyncMock` que ignora o conteúdo real da query (`make_result()` fixo), e os factories (`make_character`, `make_campaign`, etc.) constroem objetos ORM **sem** setar relationships. Os 73 testes unitários não tocam banco real e não validam serialização Pydantic de `*Out` — baixo risco de regressão confirmado, mas eles também não vão pegar erros de mapeamento SQLAlchemy nem de serialização.
- Não existe hoje suíte de testes de integração contra Postgres real (`backend/tests/unit/` é 100% mockado). `backend/pytest.ini` tem `testpaths = tests` (cobriria uma futura pasta `tests/integration/` automaticamente). `backend/requirements-dev.txt` só tem `pytest`, `pytest-asyncio`, `pytest-mock` — sem `httpx`/cliente de teste assíncrono.
- `docker-compose.yml` sobe um Postgres 16 com credenciais `dnd`/`dndpass`/db `dnd` — **diferente** do default hardcoded em `tests/conftest.py` (`postgresql+asyncpg://test:test@localhost:5432/test_db`), que hoje nunca é realmente usado porque os testes são mockados. Essa divergência vira relevante na Etapa 7.

## Decisão técnica de Planejamento: dado órfão (ID não-nulo, entidade referenciada ausente)
**Decisão: retornar `None` no campo `_name`, nunca erro 500.** Isso é o comportamento nativo de `selectinload`/`joinedload` do SQLAlchemy sobre uma relationship to-one cujo FK aponta para uma linha inexistente — a relationship simplesmente fica `None` após o carregamento, sem exceção. Não é necessário nenhum tratamento de erro especial no código do endpoint/serviço.

Nota de risco a registrar (não bloqueia a etapa): todas as FKs afetadas (`species_id`, `background_id`, `class_id`, `subclass_id`, `added_by`, `created_by`) têm `ForeignKey(...)` sem `ondelete` configurado — ou seja, Postgres aplica `RESTRICT`/`NO ACTION` por padrão. Isso significa que, no fluxo normal da aplicação (que hoje nem expõe `DELETE` para `User`/`SpeciesDefinition`/`ClassDefinition`/etc.), um "dado órfão" de verdade **não é alcançável** — o banco impediria a exclusão da linha referenciada. A regra "`None` em vez de 500" é, portanto, uma garantia defensiva/de robustez, não um cenário reproduzível via API hoje. Isso muda como o caso de borda deve ser testado (ver Etapa 2 e Etapa 7).

## Etapas técnicas (ordem de execução)

### Etapa 1 — Models: relationships novas
Arquivos: `backend/app/db/models/character.py`, `backend/app/db/models/campaign.py`

- `Character`: adicionar relationships to-one (nullable, sem necessidade de `back_populates` pois as definições de compêndio não precisam de coleção reversa) para `SpeciesDefinition` (via `species_id`), `BackgroundDefinition` (via `background_id`), `ClassDefinition` (via `class_id`), `SubclassDefinition` (via `subclass_id`). Seguir o padrão já usado em `owner`/`campaign` (forward ref em string + `# noqa: F821`). Atenção: `class_id` não pode virar atributo Python `class` (palavra reservada) — nome do atributo é decisão do agente de Desenvolvimento, sugestão: `character_class` (mantendo `class_def` livre pois já é usado por `SubclassDefinition`).
- `CharacterInventory`: adicionar relationship to-one nullable para `User` via `added_by`.
- `Campaign`: adicionar relationship to-one não-nula para `User` via `created_by`.
- Nenhuma mudança em `user.py`, `compendium.py` (já tem `SubclassDefinition.class_def`) ou em `CampaignMember` (já tem `user`/`campaign`).
- **Nenhuma migration Alembic** — são apenas relationships ORM sobre colunas/FKs já existentes.

Resultado esperado: todas as 8 relationships da tabela da especificação existem e resolvem sem erro de mapeamento.
Critério de pronto (testável): importar `app.main` (ou rodar `python -c "import app.main"`) não lança `sqlalchemy.exc.InvalidRequestError` de mapeador; suíte unitária existente (`pytest backend/tests/unit`) continua 73/73 verde (os testes usam `FakeAsyncSession`/objetos ORM crus, não são afetados por relationships novas não utilizadas).

### Etapa 2 — Schemas: campos `_name` + testes unitários de serialização
Arquivos: `backend/app/schemas/character.py`, `backend/app/schemas/campaign.py`, `backend/app/schemas/compendium.py`; novo arquivo de teste em `backend/tests/unit/` (ex. `test_schema_serialization.py`); extensão de `backend/tests/conftest.py`.

- Adicionar os campos exatamente conforme a tabela da especificação, com nullability espelhando a nullability do ID correspondente (`user_name: str`, `campaign_name: str | None`, etc.).
- Restrição de arquitetura a respeitar: hoje toda rota faz `return <objeto_orm>` e deixa o FastAPI serializar via `response_model=...` (`model_validate(obj, from_attributes=True)`), sem transformação manual. Para preservar esse padrão sem reescrever todas as rotas, a fonte de cada campo `_name` deve ser algo que o `from_attributes=True` consiga ler via `getattr` diretamente do objeto ORM retornado (ex.: uma propriedade Python no modelo SQLAlchemy que leia a relationship eager-loaded, tipo `Character.user_name -> self.owner.username`). O mecanismo exato (propriedade no model, `model_validator(mode="before")` no schema, ou outra técnica) é decisão do agente de Desenvolvimento — a única exigência não-negociável é: (a) não alterar o padrão `return <objeto_orm>` das rotas, (b) `_name` é `None` sempre que o ID for `None` ou a relationship carregada for `None`, nunca `""` nem campo omitido.
- Estender os factories de `backend/tests/conftest.py` (`make_character`, `make_campaign`, `make_campaign_member`, `make_inventory_entry`, e novos `make_species`/`make_background`/`make_class`/`make_subclass` se necessário) para permitir setar as relationships novas (ex. `make_character(owner=make_user(username="foo"))`).
- Testes unitários novos (TDD, sem banco real) cobrindo cada schema afetado nos 3 estados por campo: (1) ID setado + relationship carregada → `_name` = valor esperado; (2) ID `None` → `_name` é `None`; (3) ID setado + relationship `None` (simula dado órfão via mock, sem precisar de Postgres) → `_name` é `None`, sem exceção.

Resultado esperado: schemas com os novos campos; comportamento de nulos e do caso "órfão simulado" coberto por teste unitário rápido.
Critério de pronto: novos testes unitários passam; suíte completa (`pytest backend/tests/unit`) permanece verde, incluindo os 73 testes pré-existentes.

**Checkpoint QA #1 (intermediário):** após Etapas 1–2, QA roda a suíte unitária completa (73 testes existentes + novos testes de schema) e confirma: zero regressão, todos os campos `_name` corretos em isolamento (mock), casos `None`/órfão-simulado cobertos. Isso não valida ainda comportamento real contra Postgres nem ausência de N+1 — isso fica para o Checkpoint QA #2.

### Etapa 3 — Eager-loading em `backend/app/services/character.py`
Funções afetadas: `get_character_or_404`, `list_characters_for_campaign`, `create_character`, `update_character`, `apply_hp_update`, `add_item`.

Estratégia de carregamento (usar `selectinload` uniformemente — evita produto cartesiano ao combinar com a coleção `inventory`, e faz o lookup em lote via `WHERE id IN (...)`, garantindo custo O(1) por tipo de relationship independente de N linhas):
- `selectinload(Character.owner)`
- `selectinload(Character.campaign)`
- `selectinload(Character.species)` *(nome sugerido)*
- `selectinload(Character.background)`
- `selectinload(Character.character_class)` *(nome sugerido para o FK `class_id`)*
- `selectinload(Character.subclass)`
- `selectinload(Character.inventory).selectinload(CharacterInventory.item)`
- `selectinload(Character.inventory).selectinload(CharacterInventory.added_by_user)` *(nome sugerido)*

Aplicar em `get_character_or_404` e `list_characters_for_campaign` (ambas hoje só têm `selectinload(Character.inventory)`).

**Nota técnica crítica (não é só performance, é correção):** com `expire_on_commit=False` (já configurado em `app/db/session.py`), relationships eager-loaded em um objeto **sobrevivem** a um `db.commit()` subsequente sem re-fetch — mas `db.refresh(obj)` sem `attribute_names` só recarrega relationships que **já estavam carregadas** no objeto antes do refresh (ele preserva a estratégia de carregamento original). Ou seja:
- Em `update_character` e `apply_hp_update`, o `character` recebido já veio de `get_character_or_404` (que passa a ter os `.options()` acima) — então `db.refresh(character)` deve manter as relationships populadas. **Ainda assim, validar empiricamente na Etapa 8** (não assumir apenas pela documentação do SQLAlchemy).
- Em `create_character`, o objeto `Character(...)` é construído em memória e nunca teve as relationships carregadas antes do `db.commit()`/`db.refresh(character)` — um `refresh()` sem `attribute_names` **não** vai forçar o carregamento dessas relationships pela primeira vez. É necessário carregá-las explicitamente antes do `return` (ex. `db.refresh(character, attribute_names=[...])` incluindo as relationships novas, ou um `select()` de acompanhamento com os mesmos `.options()`). Sem isso, a serialização Pydantic (síncrona) vai tentar lazy-load implícito fora de contexto assíncrono e lançar `MissingGreenlet`/erro equivalente — isso quebra o endpoint, não é só um problema de N+1.
- Mesma observação vale para `add_item` (novo `CharacterInventory` recém-criado, precisa de `item` e `added_by_user` carregados antes do `return`).

Resultado esperado: `get_character_or_404`, `list_characters_for_campaign`, `create_character`, `update_character`, `apply_hp_update`, `add_item` retornam objetos com todas as relationships necessárias já carregadas.
Critério de pronto: nenhuma regressão nos 73 testes unitários (eles usam `FakeAsyncSession.execute` como `AsyncMock` genérico que ignora a query real, então adicionar `.options()` não quebra os mocks); validação funcional completa fica para a Etapa 8 (precisa de Postgres real).

### Etapa 4 — Eager-loading em `backend/app/api/characters.py`
Funções afetadas: `my_characters` (GET `/characters/me`), `update_inventory_item` (PATCH `/characters/{id}/inventory/{inventory_id}`) — ambas fazem `select()` cru fora da camada de serviço, sem nenhum eager-load hoje.

- `my_characters`: aplicar os mesmos `.options()` de `character`/`campaign`/`species`/`background`/`character_class`/`subclass` usados na Etapa 3 (não precisa de `inventory`, pois `CharacterOut` — usado como `response_model` aqui — não inclui esse campo; incluir ou não o eager-load de `inventory` fica a critério do Desenvolvimento, mas incluí-lo desnecessariamente gera uma query extra sem benefício).
- `update_inventory_item`: adicionar `.options(selectinload(CharacterInventory.item), selectinload(CharacterInventory.added_by_user))` na query de `CharacterInventory`.

Resultado esperado: `GET /characters/me` e `PATCH /characters/{id}/inventory/{inventory_id}` não dependem de lazy-load implícito.
Critério de pronto: mesma observação de regressão unitária da Etapa 3; validação funcional na Etapa 8.

### Etapa 5 — Eager-loading em `backend/app/api/campaigns.py`
Funções afetadas: `create_campaign`, `list_my_campaigns`, `get_campaign`, `update_campaign`, `join_campaign`, `list_members`.

- `list_my_campaigns`, `get_campaign`, `update_campaign` (na query de leitura antes do `setattr`): adicionar `.options(selectinload(Campaign.creator))`.
- `create_campaign`: o `creator` é o próprio `current_user`, já disponível na função — carregar via `.options(selectinload(Campaign.creator))` num refresh/re-select, **ou** atribuir a relationship em memória a partir de `current_user` antes do `return` (evita 1 query redundante); escolha de implementação fica com o Desenvolvimento, mas o resultado final tem que ter `campaign.creator` populado antes da serialização.
- `join_campaign`: `MemberOut` precisa de `user_name` (= `current_user.username`, já disponível) e `campaign_name` (= `campaign.name`, já disponível pois `campaign` foi buscado antes nesta mesma função pelo `invite_code`). Recomenda-se reaproveitar esses objetos já carregados em memória em vez de emitir novas queries — novamente, mecanismo exato é decisão de Desenvolvimento, mas o `member` retornado precisa ter `user`/`campaign` populados (ou os campos `_name` já resolvidos) antes do `return`.
- `list_members`: adicionar `.options(selectinload(CampaignMember.user), selectinload(CampaignMember.campaign))` na query `select(CampaignMember).where(CampaignMember.campaign_id == campaign_id)` — é o endpoint de lista mais sensível a N+1 desta etapa (`MemberOut` exige `user_name` **e** `campaign_name` por item).

Resultado esperado: todos os endpoints de `campaigns.py` retornam `created_by_name`/`user_name`/`campaign_name` sem lazy-load implícito.
Critério de pronto: regressão unitária ok; validação funcional na Etapa 8; N+1 de `list_members` validado na Etapa 9.

### Etapa 6 — Eager-loading em `backend/app/api/compendium.py`
Funções afetadas: `list_subclasses` (GET `/compendium/subclasses`), `create_subclass` (POST `/compendium/subclasses`).

- `list_subclasses`: adicionar `.options(selectinload(SubclassDefinition.class_def))` na query.
- `create_subclass`: após `db.commit()`/`db.refresh(obj)`, `class_name` precisa de `obj.class_def` carregado — mesma observação da Etapa 3 sobre objetos recém-criados: usar `attribute_names=["class_def"]` no refresh, ou re-selecionar com `.options()`, ou aproveitar que `data.class_id` já foi validado implicitamente pelo FK e buscar o `ClassDefinition` correspondente antes do `return`.

Resultado esperado: `SubclassOut.class_name` populado em ambos os endpoints sem erro de lazy-load.
Critério de pronto: regressão unitária ok; validação funcional na Etapa 8.

**Fim do bloco de mudanças de código.** As Etapas 1–6 são a superfície completa de mudança de produção da feature (models + schemas + eager-loading). As Etapas 7–9 são sobre **como validar** o que foi construído — e envolvem uma mudança de escopo técnico de teste (ver seção de ação humana).

### Etapa 7 — Infraestrutura de testes de integração (NOVA, requer decisão/ação humana antes de iniciar)
Arquivos novos: `backend/tests/integration/__init__.py`, `backend/tests/integration/conftest.py` (fixture de `AsyncSession` real contra Postgres, helpers de seed via ORM), possível marker `integration` em `backend/pytest.ini`.

Por que é necessária: os critérios de aceite "sem N+1 nos endpoints de lista" e "valores `_name` corretos end-to-end via relationships carregadas" só são verificáveis contra um banco real — a suíte atual (`backend/tests/unit/`) usa `FakeAsyncSession` com `execute` mockado, que **ignora** o conteúdo da query (não distingue 1 query de 10, nem valida que um `selectinload` de fato populou uma relationship). Isso é uma mudança de escopo técnico de teste em relação à rodada anterior (que era 100% unitária/mockada) — **ver seção "Pontos que exigem ação humana"**.

Estratégia recomendada (minimiza dependências novas): testes de integração operam preferencialmente na **camada de serviço** (chamando `char_service.get_character_or_404`, `char_service.list_characters_for_campaign`, etc. diretamente com uma `AsyncSession` real) mais um subconjunto pequeno de chamadas às funções de rota que têm lógica própria fora de `services/` (`my_characters`, `update_inventory_item`, `create_campaign`, `list_my_campaigns`, `get_campaign`, `update_campaign`, `join_campaign`, `list_members`, `list_subclasses`, `create_subclass`) — isso evita introduzir um cliente HTTP assíncrono (`httpx`) como dependência nova, mantendo o padrão já usado pela suíte atual de testar a camada de serviço diretamente. Se o time preferir cobertura end-to-end via HTTP real (mais fiel, porém com dependência nova), isso é uma escolha válida mas **precisa de aprovação explícita** (ver seção de ação humana).

Resultado esperado: fixture(s) reutilizável(is) de sessão real + seed de dados (`User`, `Campaign`, `Character`, `SpeciesDefinition` etc.) + um contador de queries SQL (via `sqlalchemy.event.listens_for(engine.sync_engine, "before_cursor_execute", ...)`) plugável em qualquer teste.
Critério de pronto: `pytest backend/tests/integration -m integration` conecta com sucesso ao Postgres de teste, cria e limpa dados de seed, e um teste trivial (ex. round-trip de criação de personagem) passa.

### Etapa 8 — Testes de integração: corretude funcional
Arquivos: `backend/tests/integration/test_character_name_fields.py`, `test_campaign_name_fields.py`, `test_compendium_name_fields.py` (nomes sugeridos).

Cobrir, contra Postgres real:
- Cada campo `_name` da tabela da especificação, populado corretamente a partir de dados semeados via ORM.
- Caso `id = None` → `_name = None` para todos os campos nuláveis, usando dados reais (personagem sem `species_id`, sem `campaign_id` etc.), não só mock.
- **Todos** os endpoints/funções de escrita listados (`create_character`, `update_character`, `apply_hp_update`/HP, `add_item`, `create_campaign`, `join_campaign`, `create_subclass`) executam sem `MissingGreenlet`/`DetachedInstanceError` ao serializar a resposta — este é o teste que valida a nota técnica crítica da Etapa 3 (é um teste de corretude, não de performance).
- Caso de "dado órfão": dado que os FKs afetados usam `ondelete` padrão (`RESTRICT`), **não** tentar recriar um órfão de fato no Postgres (exigiria desabilitar constraints, o que é invasivo e não reflete um cenário real). Esse caso já está coberto pelo teste unitário de schema da Etapa 2 (mock com relationship `None`); a Etapa 8 não precisa reproduzi-lo com banco real — registrar isso explicitamente no teste/README para não haver dúvida futura sobre cobertura.
- Nenhuma mudança em `FeatureGrantOut`/`WSEvent` — teste de regressão simples confirmando que esses dois schemas continuam com o mesmo conjunto de campos de antes.

Critério de pronto: todos os testes acima verdes contra Postgres 16 com as migrations existentes aplicadas (nenhuma migration nova é necessária/criada nesta feature).

### Etapa 9 — Testes de integração: ausência de N+1
Arquivo: `backend/tests/integration/test_no_n_plus_one.py` (nome sugerido).

Endpoints/funções-alvo (conforme a seção "Performance" da especificação): `GET /characters/me` (`my_characters`), `GET /characters/campaign/{id}` (`list_characters_for_campaign`), `GET /campaigns` (`list_my_campaigns`), `GET /campaigns/{id}/members` (`list_members`).

Técnica: usar o contador de queries da Etapa 7 (`before_cursor_execute`). Para cada endpoint, semear pelo menos dois tamanhos de dataset (ex. 2 e 6 registros relacionados — personagens, membros, etc.) e comparar a contagem total de statements SQL emitidos. Critério de aprovação: a contagem **não cresce proporcionalmente a N** (idealmente é idêntica entre os dois tamanhos — O(1) por tipo de relationship via `selectinload` batelado, não O(N)). Uma contagem que dobra/triplica junto com N indica N+1 e reprova o critério de aceite.

Critério de pronto: contagem de queries constante (não-proporcional a N) nos 4 endpoints listados, com o número de queries documentado no teste (ex. via `assert query_count_n2 == query_count_n6`).

**Checkpoint QA #2 (final):** após Etapas 7–9, QA roda a suíte completa: 73 testes unitários pré-existentes + testes unitários novos da Etapa 2 + suíte de integração das Etapas 8–9 contra Postgres real. Só após esse checkpoint a feature é considerada pronta para revisão de merge (ação humana, fora do escopo deste plano).

## Pontos que exigem ação humana
- [ ] **Provisionar/confirmar banco Postgres de teste** (host, credenciais, nome do banco) — motivo: hoje há divergência entre as credenciais do `docker-compose.yml` (`dnd`/`dndpass`/db `dnd`) e o default hardcoded em `tests/conftest.py` (`test:test@localhost:5432/test_db`), que nunca foi de fato exercitado porque a suíte é mockada; alguém precisa decidir se cria um usuário/DB `test_db` dedicado, se reaproveita o serviço `db` do `docker-compose`, ou se usa outro mecanismo (ex. container efêmero) — quando: antes da Etapa 7.
- [ ] **Rodar `alembic upgrade head` contra o banco de teste escolhido** — motivo: aplicar migrations em um banco real (mesmo que seja "só" de teste/CI) é uma ação sobre infraestrutura compartilhada que não deve ser executada silenciosamente por um agente; precisa de aprovação/execução humana (ou de um pipeline de CI já aprovado para isso) — quando: antes da Etapa 7/8.
- [ ] **Aprovar a mudança de escopo de teste** (a rodada anterior era 100% unitária/mockada; esta feature introduz uma suíte de integração nova contra Postgres real, nas Etapas 7–9) — motivo: é uma decisão de processo/política de QA do projeto (custo de manutenção, tempo de CI, necessidade de infraestrutura), não uma decisão técnica que o Planejamento deva tomar sozinho — quando: antes de iniciar a Etapa 7.
- [ ] **Decidir e aprovar se os testes de integração cobrirão a camada HTTP completa** (o que exigiria adicionar `httpx` — ou equivalente — a `backend/requirements-dev.txt`) **ou só a camada de serviço** (estratégia recomendada neste plano, sem dependência nova) — motivo: adicionar uma dependência nova ao projeto, mesmo de baixo risco/custo, é uma decisão que deve ser confirmada por um humano antes de codificar a Etapa 7 — quando: antes da Etapa 7.
- [ ] **Nenhum merge em `main`/deploy** deve ocorrer automaticamente ao final do Checkpoint QA #2 — isso é aprovação humana padrão do processo do repositório, fora do escopo deste plano.

## Workflow para os próximos agentes
- Ordem: refinamento (concluído) → planejamento (este) → dev-tdd → QA
- dev-tdd deve seguir TDD estrito, etapa por etapa, na ordem 1 → 9 acima. Etapas 1–2 podem ser desenvolvidas e testadas (unitariamente) sem depender de infraestrutura nova; Etapas 3–6 dependem de 1–2 estarem prontas (schemas precisam existir para os endpoints retornarem algo válido) mas podem ser feitas em qualquer ordem entre si (são arquivos independentes: `services/character.py`, `api/characters.py`, `api/campaigns.py`, `api/compendium.py`) — podem ser paralelizadas entre desenvolvedores diferentes se necessário. Etapas 7–9 são estritamente sequenciais e dependem de TODAS as Etapas 1–6 concluídas, além de dependerem da resolução dos pontos de ação humana listados acima.
- QA roda em dois checkpoints explícitos, não só ao final:
  - **Checkpoint QA #1** (após Etapa 2): suíte unitária completa (73 testes existentes + novos testes de schema), sem dependência de infraestrutura nova. Serve de gate rápido antes de investir nas Etapas 3–9.
  - **Checkpoint QA #2** (após Etapa 9, final): suíte unitária completa + suíte de integração completa contra Postgres real. Este é o gate de aprovação da feature.
- Critério de aprovação do QA (Checkpoint #2, resumo dos critérios de aceite da especificação em termos verificáveis):
  1. Todos os campos `_name` da especificação presentes nas respostas dos endpoints afetados, IDs originais inalterados (testes de integração da Etapa 8).
  2. `_name` é `None` sempre que o ID correspondente é `None` (testes unitários da Etapa 2 + integração da Etapa 8), nunca `""` nem omitido.
  3. Zero regressão nos 73 testes unitários pré-existentes (Checkpoints #1 e #2).
  4. Contagem de queries SQL não cresce proporcionalmente a N nos 4 endpoints de lista citados (teste de integração da Etapa 9, com contagem explícita comparada entre dois tamanhos de dataset).
  5. `FeatureGrantOut` e `WSEvent` permanecem com o mesmo conjunto de campos de antes (teste de regressão simples na Etapa 8).
  6. Nenhum endpoint de escrita (`POST`/`PATCH` afetados) lança erro de serialização (`MissingGreenlet`/`DetachedInstanceError`) devido a relationship não carregada (teste de integração da Etapa 8).

## Riscos / bloqueios conhecidos
- **Divergência de credenciais de banco de teste** entre `docker-compose.yml` e o default de `tests/conftest.py` — não resolvida neste plano, listada como ação humana (ver acima). Bloqueia o início da Etapa 7 até ser decidida.
- **Nova dependência de teste em potencial** (`httpx` ou equivalente) se optarem por integração via HTTP completo em vez de camada de serviço — decisão explicitamente delegada a humano antes da Etapa 7.
- **Nuance de `db.refresh()` + `expire_on_commit=False`** (detalhada na Etapa 3): objetos recém-criados (`create_character`, `add_item`, `create_campaign`, `join_campaign`, `create_subclass`) precisam de carregamento explícito das relationships novas antes do `return`, porque um `db.refresh()` sem `attribute_names` não força o primeiro carregamento de uma relationship nunca acessada. Se essa nuance for esquecida na implementação, o sintoma será um erro em runtime (`MissingGreenlet`) nos endpoints de criação/escrita, não um teste unitário quebrado (a suíte mockada não pega esse tipo de erro) — só a Etapa 8 (integração real) detecta isso, reforçando por que ela é necessária antes de considerar a feature pronta.
- **Caso de "dado órfão" não é reproduzível via API hoje** (FKs afetadas usam `RESTRICT` por padrão, sem endpoint de exclusão para as entidades de compêndio/usuário) — a decisão de retornar `None` já foi tomada por este plano e está coberta por teste unitário com mock (Etapa 2); não é um bloqueio, apenas uma limitação de cobertura de teste de integração documentada explicitamente para evitar retrabalho futuro tentando forçar esse cenário contra Postgres real.
- **Nomes de relationships/atributos sugeridos neste plano** (`species`, `background`, `character_class`, `subclass`, `added_by_user`, `creator`) são sugestões para evitar ambiguidade na tabela de eager-loading — o nome final é decisão do agente de Desenvolvimento, desde que consistente entre model/eager-load/schema.
