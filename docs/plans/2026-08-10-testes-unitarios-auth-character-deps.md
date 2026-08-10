# Plano de Execução: Testes unitários para auth, character e camada de permissões (deps/security)

## Referência
Especificação: cobrir com testes unitários isolados (sem Postgres/Redis reais) `app/core/security.py`, `app/services/auth.py`, `app/services/character.py` e `app/core/deps.py`, com foco em autenticação, controle de acesso e na matemática de HP/inventário.

## Contexto verificado no código
- Não existe hoje nenhuma estrutura de testes no repositório (`backend/tests/` não existe, sem `pytest.ini`/`pyproject.toml`, sem dependências de teste em `backend/requirements.txt`).
- `backend/app/core/config.py` instancia `settings = Settings()` no import, exigindo `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` (sem default). `backend/app/db/session.py` chama `create_async_engine(settings.DATABASE_URL, ...)` no import de `app.db.session` — isso **não abre conexão de rede** (lazy), então importar `app.core.deps`, `app.services.auth`, `app.services.character` é seguro sem Postgres real, desde que as env vars existam.
- Não há `backend/.env` (só `.env`/`.env.example` na raiz do repo, fora do `WORKDIR` usado pelo pydantic-settings quando rodado a partir de `backend/`). Logo, ao rodar `pytest` com cwd em `backend/`, `Settings(env_file=".env")` não vai encontrar arquivo nenhum e vai depender exclusivamente de variáveis de ambiente do processo — isso resolve a lacuna apontada na especificação: basta popular `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` via `os.environ` em `conftest.py`, antes de qualquer `import app...`, e a suíte fica portátil (funciona igual localmente e em CI, sem depender do `.env` real do desenvolvedor).
- `db.execute(...)` é chamado com `await` e o retorno expõe `.scalar_one_or_none()` / `.scalars().all()` (síncronos sobre o objeto `Result`); `db.add(...)` é síncrono (sem `await`); `db.commit()`, `db.refresh()`, `db.flush()`, `db.delete()` são chamados com `await`. Isso define exatamente a forma do dublê de `AsyncSession` a ser usado nos testes (detalhado abaixo).
- `require_campaign_dm`/`require_campaign_member`/`get_current_user` em `app/core/deps.py` são funções `async def` simples com parâmetros `Annotated[..., Depends(...)]` — os `Depends` só são resolvidos pelo injector do FastAPI; nos testes unitários elas podem ser chamadas diretamente (`await get_current_user(token="...", db=fake_db)`) sem subir a aplicação FastAPI nem usar `TestClient`/`httpx`.
- Modelos SQLAlchemy (`app/db/models/user.py`, `campaign.py`, `character.py`) são classes declarativas comuns: instanciá-las diretamente em memória (ex.: `User(id=..., email=..., hashed_password=..., is_active=True)`) não toca o banco, servindo como dublês de dados retornados pelo `AsyncSession` mockado.

## Etapas técnicas (ordem de execução)

### Etapa 0 — Infraestrutura de testes (bloqueante para todas as demais)
Arquivo(s):
- `backend/requirements-dev.txt` (novo) — referenciando `-r requirements.txt` + `pytest`, `pytest-asyncio`, `pytest-mock` (dependências de teste, sem impacto em runtime de produção).
- `backend/pytest.ini` (novo) — configurar `testpaths`, `asyncio_mode = auto` (ou modo estrito com `@pytest.mark.asyncio`, a critério do dev-tdd) e `pythonpath` apontando para a raiz de `backend/` para que `import app...` funcione com `pytest` rodado a partir de `backend/`.
- `backend/tests/__init__.py` e `backend/tests/unit/__init__.py` (se o dev-tdd optar por pacotes explícitos).
- `backend/tests/conftest.py` (novo):
  - No topo do módulo, **antes de qualquer import de `app.*`**, definir valores dummy para `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` via `os.environ.setdefault(...)`, garantindo que `app.core.config.Settings()` seja instanciável sem `.env` real e sem depender do ambiente do desenvolvedor.
  - Fornecer um dublê de `AsyncSession` reutilizável pelos testes de `auth.py`/`character.py`/`deps.py`, com a forma: `execute` como `AsyncMock` (retorno configurável por teste, expondo `.scalar_one_or_none()` e `.scalars().all()` como `MagicMock` síncronos), `add` como `MagicMock` síncrono, `commit`/`refresh`/`flush`/`delete` como `AsyncMock`.
  - Opcional: fábricas/helpers para instanciar rapidamente `User`, `RefreshToken`, `Character`, `CharacterInventory`, `Campaign`, `CampaignMember` em memória com valores padrão sensatos (a estrutura exata fica a critério do dev-tdd).
- Resultado esperado: `pytest` consegue coletar e rodar a partir de `backend/` sem exigir Postgres/Redis reais e sem depender do `.env` do repositório.
- Critério de pronto (testável): rodando `cd backend && pytest` (com ao menos um teste trivial, ex. `assert True`, ou já com os testes da Etapa 1), a coleta e execução terminam sem erro de import de `app.core.config`/`app.db.session`, e nenhuma tentativa de conexão de rede/socket ocorre.

### Etapa 1 — Testes de `app/core/security.py`
Arquivo: `backend/tests/unit/test_security.py`
Depende de: Etapa 0.
- Resultado esperado: cobertura de `hash_password`/`verify_password` (hash não determinístico entre duas chamadas com a mesma senha, `verify_password` correto/incorreto), `create_access_token`/`create_refresh_token` (claims `sub`, `type` diferenciando access/refresh, `exp`, `jti` presentes e únicos entre chamadas), `decode_token` (token válido retorna payload, token malformado retorna `None`, token assinado com outra chave retorna `None`, token expirado retorna `None`).
- Critério de pronto: `pytest tests/unit/test_security.py -q` totalmente verde, sem qualquer chamada de rede/DB.

### CHECKPOINT QA #1 (parcial, recomendado antes de escalar para os demais módulos)
- Escopo: revisar apenas a Etapa 0 (infraestrutura/config) e a Etapa 1 (`security.py`).
- Objetivo: validar cedo que a estratégia de variáveis de ambiente via `conftest.py` e o padrão de dublê de `AsyncSession` (ainda não usado em `security.py`, mas já definido na Etapa 0) estão corretos, antes de replicar o padrão em auth/character/deps — evita retrabalho em massa se algo na infraestrutura estiver errado.
- Critério de aprovação do checkpoint: `pytest` roda limpo a partir de `backend/`, sem tocar rede, e os testes de `security.py` cobrem os casos listados acima.

### Etapa 2 — Testes de `app/core/deps.py`
Arquivo: `backend/tests/unit/test_deps.py`
Depende de: Etapa 0 (usa o dublê de `AsyncSession` e `security.py` já validado). Pode ser feita em paralelo às Etapas 3 e 4, pois não compartilha lógica de negócio com `auth.py`/`character.py`.
- Resultado esperado, chamando as funções diretamente (sem FastAPI app/TestClient):
  - `get_current_user`: token inválido/malformado → `401`; `type` do payload diferente de `access` → `401`; `sub` ausente ou não é UUID válido → `401`; usuário não encontrado no "banco" (mock) → `401`; usuário encontrado mas `is_active=False` → `401`; caminho feliz retorna o `User`.
  - `require_campaign_dm`: campanha inexistente → `404`; campanha existe mas usuário não é `dm` (sem membership ou membership com role diferente) → `403`; caminho feliz retorna a `Campaign`.
  - `require_campaign_member`: sem `CampaignMember` para o usuário/campanha → `403`; caminho feliz retorna o `CampaignMember` (papel `player` ou `dm`, ambos válidos como "membro").
- Critério de pronto: todos os cenários acima cobertos, usando o dublê de `AsyncSession` da Etapa 0, sem chamada HTTP real.

### Etapa 3 — Testes de `app/services/auth.py`
Arquivo: `backend/tests/unit/test_auth_service.py`
Depende de: Etapa 0 e Etapa 1 (usa `hash_password`/`create_access_token`/`create_refresh_token`/`decode_token` reais, não mockados — o objetivo é testar a integração real entre `auth.py` e `security.py`).
- Resultado esperado:
  - `register`: sucesso cria e persiste `User` (via dublê de sessão) com senha hasheada; `409` quando já existe usuário com mesmo email OU mesmo username (`existing.scalar_one_or_none()` simulando linha encontrada).
  - `login`: sucesso retorna `TokenResponse` com `access_token`/`refresh_token`; `401` para email inexistente; `401` para senha incorreta; **mensagem/detail e status idênticos** entre os dois casos acima (não deve ser possível diferenciar "email não existe" de "senha errada" pela resposta); `403` para usuário inativo — e esse caso só deve ocorrer **depois** de a senha já ter sido validada como correta (ou seja, senha errada em conta inativa deve retornar `401`, não `403`).
  - `refresh`: sucesso rotaciona o token — o `RefreshToken` antigo (mock) deve ficar com `revoked=True` e um novo `TokenResponse` deve ser emitido; `401` para token malformado/indecodificável; `401` quando `type` do payload é `access` (não `refresh`); `401` quando o hash do token não é encontrado (nenhum `RefreshToken` correspondente); `401` quando o `RefreshToken` encontrado está `revoked=True`; `401` quando `expires_at` já passou; `401` quando o `user_id` do token não corresponde a nenhum usuário ou o usuário está inativo.
  - `_hash_token`: determinístico (mesma entrada produz o mesmo hash) e compatível com SHA-256 (tamanho/forma do hex digest).
- Critério de pronto: matriz de erros acima 100% coberta; teste específico garantindo paridade de resposta entre "email inexistente" e "senha errada" no `login`.

### Etapa 4 — Testes de `app/services/character.py`
Arquivo: `backend/tests/unit/test_character_service.py`
Depende de: Etapa 0. Pode rodar em paralelo à Etapa 3.
- Resultado esperado:
  - `get_character_or_404`: encontrado → retorna `Character`; não encontrado ou `is_active=False` → `404`.
  - `assert_owner_or_dm`: `character.user_id == requesting_user_id` → autorizado; usuário é `dm` da `campaign_id` do personagem (via `CampaignMember`) → autorizado; usuário não é dono, personagem sem `campaign_id` → `403`; usuário não é dono, é membro da campanha mas não `dm` (ex. `role="player"`) → `403`.
  - `create_character`: monta `Character` a partir de `CharacterCreate`, persiste via dublê de sessão (verificar campos propagados: `name`, `species_id`, `background_id`, `class_id`, `ability_scores`, `appearance`, `notes`, além de `user_id`/`campaign_id` recebidos por parâmetro).
  - `update_character`: aplica apenas os campos não-`None` de `CharacterUpdate` (usar `model_dump(exclude_none=True)`), preservando os demais valores existentes do personagem.
  - `apply_hp_update` (cobertura extensiva, mínimo dos casos abaixo, todos com asserção sobre `current_hp`/`temp_hp` resultantes):
    - Cura simples (`delta` positivo, `is_temp=False`) somando a `current_hp`.
    - Cura que excede `max_hp` → `current_hp` limitado a `max_hp` (nunca ultrapassa).
    - Dano (`delta` negativo, `is_temp=False`) menor ou igual ao `temp_hp` disponível → absorvido inteiramente pelo `temp_hp`, `current_hp` inalterado.
    - Dano maior que `temp_hp` → `temp_hp` zera e o excedente desconta de `current_hp`.
    - Dano maior que `temp_hp + current_hp` → `current_hp` chega a `0`, nunca fica negativo.
    - `delta = 0` em dano e em cura → sem efeito colateral (idempotente).
    - `is_temp=True` com `delta` positivo → soma a `temp_hp`; `is_temp=True` com `delta` negativo → resultado nunca fica abaixo de `0` (`max(0, temp_hp + delta)`).
  - `add_item`: cria `CharacterInventory` associado ao `character.id`, propagando `item_id`, `quantity`, `custom_notes`, `added_by`.
  - `remove_item`: chama `assert_owner_or_dm` internamente (cenário de usuário sem permissão deve propagar `403` sem tentar deletar); entrada de inventário não encontrada (ou de outro `character_id`) → `404`; sucesso remove a entrada via `db.delete`.
  - `list_characters_for_campaign`: retorna apenas personagens com o `campaign_id` informado e `is_active=True` (validar que o filtro é aplicado na query simulada, ou pelo menos que a função retorna a lista tal como fornecida pelo dublê, cobrindo lista vazia e lista com itens).
- Critério de pronto: todos os cenários listados cobertos, com destaque para a matriz completa de `apply_hp_update`.

### Etapa 5 — Consolidação e execução completa
Depende de: Etapas 1 a 4 concluídas.
- Resultado esperado: suíte completa (`cd backend && pytest`) executando de forma determinística, em qualquer ordem de coleta, sem estado compartilhado entre testes e sem qualquer tentativa de I/O de rede real (Postgres/Redis/HTTP).
- Critério de pronto: 100% dos testes definidos nas Etapas 1-4 passam em uma única execução do `pytest` a partir de `backend/`.

## Pontos que exigem ação humana
- [ ] **Instalar as novas dependências de teste no(s) ambiente(s) real(is)** (`pip install -r backend/requirements-dev.txt`, ou equivalente na imagem/venv usada pelo dev-tdd/CI) — motivo: este plano só altera arquivos de configuração/dependência; a instalação efetiva de pacotes em um ambiente Python de execução é uma ação de ambiente que precisa ser confirmada/rodada por um humano (ou pipeline de CI configurado por um humano) caso o agente de dev-tdd não tenha permissão/capacidade de executar `pip install` de fato — quando: antes de considerar a Etapa 0 "pronta" e antes de qualquer execução real de `pytest`. Não bloqueia a escrita do código de teste, mas bloqueia a validação de que os testes realmente passam.
- [ ] **Confirmar/rodar `pytest` de fato para validar os critérios de pronto de cada etapa** — motivo: o agente de planejamento e o de dev-tdd podem escrever os testes, mas a confirmação final de "suíte verde" depende de execução real em um ambiente com as dependências instaladas (ver ponto acima); se o agente de QA tiver capacidade de executar comandos, isso pode ser feito por ele — caso contrário, precisa de um humano — quando: ao final de cada etapa (checkpoint) e na Etapa 5.
- [ ] **Decisão sobre bugs de comportamento eventualmente descobertos ao escrever os testes** — motivo: se o dev-tdd perceber, ao caracterizar o comportamento atual (ex. alguma borda de fuso horário em `expires_at` no `refresh`, ou algum caso de `apply_hp_update` não coberto pela especificação), que o código de produção diverge do que a especificação descreve como esperado, ele não deve alterar silenciosamente o comportamento de produção só para o teste passar — deve documentar o achado e sinalizar para decisão humana se é bug a corrigir nesta rodada ou comportamento a apenas documentar — quando: durante as Etapas 1 a 4, caso surja.
- [ ] **Revisão de que nenhum segredo real vaza para os testes** — motivo: `backend/tests/conftest.py` deve usar apenas valores dummy fixos (não ler `.env` real nem segredos de produção); isso é uma verificação de segurança que deve ser confirmada por revisão humana antes do merge — quando: revisão de código (PR), antes de qualquer merge em `main`.
- [ ] **Merge em `main`** — ação humana padrão de qualquer fluxo deste pipeline, não específica desta especificação — quando: após aprovação do QA.

## Workflow para os próximos agentes
- Ordem: refinamento (concluído) → planejamento (este) → dev-tdd → QA.
- dev-tdd segue as Etapas 0 a 5 nesta ordem sequencial entre si, podendo paralelizar internamente a Etapa 2 com as Etapas 3 e 4 (não há dependência de código entre `deps.py`, `auth.py` e `character.py` além de ambos dependerem da infraestrutura da Etapa 0 e, no caso de `auth.py`/`deps.py`, da correção de `security.py` validada na Etapa 1).
- Existe um **checkpoint de QA intermediário** após a Etapa 1 (ver "CHECKPOINT QA #1"), focado em validar a infraestrutura de testes e a estratégia de env vars/mock antes de escalar para os demais módulos — isso é opcional mas recomendado dado que é a primeira vez que o projeto ganha uma suíte de testes.
- O QA final roda **depois de todas as Etapas (0 a 5) implementadas**, cobrindo a suíte completa.
- Critério de aprovação do QA final:
  - `pytest` executa a partir de `backend/` sem exigir Postgres/Redis reais nem `.env` do desenvolvedor, e sem qualquer chamada HTTP real.
  - Todas as funções listadas no escopo (`security.py`, `auth.py`, `character.py`, `deps.py`) têm teste de caminho feliz e de cada erro/borda listados na especificação e detalhados neste plano.
  - `apply_hp_update` tem a matriz de casos-limite completa (dano > temp+current, cura > max_hp, delta=0, dano parcial em temp_hp, `is_temp=True` positivo/negativo).
  - `login` tem teste explícito garantindo resposta idêntica (status + detail) para "email inexistente" vs. "senha errada".
  - `refresh` tem teste explícito de rotação (token antigo revogado, novo token emitido) e cobre todos os motivos de `401` listados na especificação.
  - Nenhum teste depende de ordem de execução ou de estado deixado por outro teste.

## Riscos / bloqueios conhecidos
- Nenhum bloqueio de especificação identificado para esta rodada — o único ponto que a especificação deixou em aberto ("resolver a exigência de env vars obrigatórias na etapa de planejamento") foi resolvido tecnicamente neste plano (bootstrap de `os.environ` em `conftest.py`, independente do `.env` real, que nem sequer existe em `backend/`).
- Risco técnico: se o dev-tdd optar por `asyncio_mode = strict` em vez de `auto` no `pytest.ini`, cada teste assíncrono precisará do marcador `@pytest.mark.asyncio` explicitamente — decisão de estilo, não bloqueia o plano, mas deve ser consistente em todos os arquivos de teste criados.
- Risco de escopo: como não existe hoje nenhuma suíte de testes nem pipeline de CI no repositório, a criação de um workflow de CI (ex. GitHub Actions) para rodar `pytest` automaticamente a cada push/PR **não está no escopo desta especificação** — deixado como melhoria futura, não bloqueante para esta rodada.
