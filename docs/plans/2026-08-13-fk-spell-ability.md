# Plano de Execução: FK real para `ClassDefinition.spell_ability`

## Referência
Especificação: corrigir `ClassDefinition.spell_ability` para usar uma foreign key real (`ForeignKey`/`ForeignKeyConstraint`) apontando para `ability_score_options.name`, no modelo, na migration squashed e no fluxo de criação de classe, seguindo o padrão já usado por `SkillDefinition.ability_score`.

## Etapas técnicas (ordem de execução)

1. **Corrigir o modelo SQLAlchemy** — arquivo: `backend/app/db/models/compendium.py:141`
   - Resultado esperado: trocar o kwarg inválido `foreign_key="ability_score_options.name"` pelo argumento posicional `ForeignKey("ability_score_options.name")` na coluna `spell_ability` de `ClassDefinition`, igual ao padrão de `SkillDefinition.ability_score` (mesmo arquivo).
   - Critério de pronto (testável): importar `app.db.models.compendium` (ou rodar a suíte) não emite mais `SAWarning` sobre kwarg desconhecido; a definição da coluna permanece `String(3)` + FK, sem qualquer outra alteração em `ClassDefinition`.

2. **Corrigir a migration squashed** — arquivo: `backend/alembic/versions/c1fcfd7fe014_initial_schema.py` (coluna `spell_ability` na linha ~96, dentro do `op.create_table('class_definitions', ...)` que começa na linha ~89)
   - Resultado esperado: remover `foreign_key='ability_score_options.name'` do `sa.Column('spell_ability', ...)` e adicionar `sa.ForeignKeyConstraint(['spell_ability'], ['ability_score_options.name'], )` na lista de constraints da tabela `class_definitions`, ao lado do `sa.ForeignKeyConstraint(['created_by'], ['users.id'], )` já existente (linha ~102) — mesmo padrão sintático usado em `skill_definitions` (linha ~110). Não criar nova revisão Alembic; editar esta migration diretamente (squash), conforme decisão já registrada na especificação.
   - Critério de pronto (testável): a migration não referencia mais `foreign_key=` em nenhum `sa.Column`; `ability_score_options` já é criada antes de `class_definitions` no arquivo (confirmado: linha 22 vs linha 89), então a ordem de criação de tabelas continua válida sem necessidade de reordenar `op.create_table` calls.
   - Depende da Etapa 1 (mesmo shape de FK, para manter modelo e migration consistentes), mas pode ser feita em paralelo por não haver dependência técnica real — recomenda-se sequencial para evitar divergência.

3. **Corrigir ordenação em `create_class`** — arquivo: `backend/app/api/compendium.py` (endpoint `create_class`, linhas ~102-136; construção do `ClassDefinition` linha ~104, `flush()` linha ~116)
   - Resultado esperado: antes do `db.add(obj)` / primeiro `flush()`, garantir a existência da `AbilityScoreOption` correspondente a `data.spell_ability` (quando não `None`), reaproveitando `ensure_ability_score_options()` de `backend/app/services/compendium.py` (já usado por `resolve_skills()` e documentado ali como get-or-create para esse exato propósito). Não implementar uma nova função de resolução — só chamar a existente com o conjunto `{data.spell_ability.value}` quando presente.
   - Critério de pronto (testável): criar uma classe com `spell_ability` apontando para uma ability score ainda não usada por nenhuma classe/skill anterior no banco não gera `ForeignKeyViolation` e persiste com o valor correto; comportamento para `spell_ability=None` permanece inalterado (sem chamada extra).
   - Depende das Etapas 1 e 2 (só é observável com a FK real ativa).

4. **Escrever testes novos cobrindo a FK** — arquivos: local a decidir pelo agente de Dev seguindo a estrutura existente de testes de integração/unit do compêndio (ex.: onde já existem testes de `create_class` — localizar via `tests/integration/` e `tests/`)
   - Resultado esperado: pelo menos dois testes novos, seguindo TDD (escritos antes do fix ser considerado "pronto" nas etapas 1-3, na ordem etapa por etapa):
     a. Teste de integração: `create_class` com `spell_ability` = ability score ainda não referenciada por nenhuma classe/skill no teste (get-or-create) persiste corretamente e o valor é lido de volta via API/refresh.
     b. Teste de integração/nível de banco: um `INSERT`/`UPDATE` direto (via SQLAlchemy Core/`db.execute` bypassando a validação Pydantic) em `class_definitions.spell_ability` com um valor que não existe em `ability_score_options.name` é rejeitado pelo banco (`ForeignKeyViolation`/`IntegrityError`), comprovando que a constraint existe de fato — não apenas a validação Pydantic do enum `AbilityScore`.
   - Critério de pronto (testável): ambos os testes passam contra o Postgres local recriado (ver ação humana abaixo) e falham (ou não seriam sequer executáveis) contra o estado anterior ao fix — i.e., cobrem exatamente o comportamento corrigido.
   - Depende das Etapas 1-3.

5. **Validar suíte completa sem regressão**
   - Resultado esperado: suíte completa (147 unit + 53 integration + os testes novos da Etapa 4) executada e passando, contra o schema recriado do zero (ver ação humana abaixo).
   - Critério de pronto (testável): 100% dos testes passam; nenhum teste existente foi alterado além do necessário para acomodar a mudança (fixtures de `conftest.py` já fixam `spell_ability=None`, então não deveriam precisar de alteração).
   - Depende de todas as etapas anteriores e da ação humana de recriar o banco local.

## Pontos que exigem ação humana
- [ ] **Recriar o schema Postgres local do zero** (via docker-compose local, dropar/recriar o banco e rodar `alembic upgrade head` com a migration corrigida) — motivo: a migration squashed foi editada diretamente (sem nova revisão), então qualquer banco local já existente com o schema antigo não vai refletir a nova `ForeignKeyConstraint`; um agente não deve assumir que tem permissão/contexto para destruir e recriar um banco, mesmo local, sem confirmação explícita — quando: antes da Etapa 4 (os testes novos, especialmente o 4b, só fazem sentido contra a constraint real no banco) e antes da Etapa 5.
- [ ] **Rodar a suíte de testes de integração contra o Postgres recriado e confirmar visualmente `\d class_definitions` (ou consulta equivalente ao catálogo)** mostrando a FK — motivo: é o critério de aceite explícito da especificação ("verificável via catálogo") e serve de confirmação humana de que a constraint existe de fato no banco, não só no código-fonte — quando: depois da Etapa 2 e antes de finalizar a Etapa 5.
- Nenhuma outra ação humana identificada: não há segredos, credenciais, deploy, merge em `main` ou decisão de produto/UX em aberto neste escopo.

## Workflow para os próximos agentes
- Ordem: refinamento (concluído) → planejamento (este) → dev-tdd → QA.
- dev-tdd segue TDD estrito, etapa por etapa, na ordem 1 → 2 → 3 → 4 (testes acompanhando/guiando cada mudança de código, não só ao final) → 5.
- Não há paralelismo real recomendado: as etapas são pequenas e sequenciais (modelo → migration → fix de ordenação → testes → validação de suíte completa). É um bug fix pontual, sem etapas independentes que justifiquem paralelizar.
- QA roda depois de TODAS as etapas de código (1-4) estarem implementadas e da suíte completa (Etapa 5) já ter sido executada com sucesso pelo dev-tdd — não há checkpoints intermediários de QA neste escopo por ser pequeno e coeso.
- Critério de aprovação do QA:
  - Modelo usa `ForeignKey(...)` posicional, sem `SAWarning` ao importar.
  - Migration tem `sa.ForeignKeyConstraint` real para `spell_ability`, sem `foreign_key=` inválido em `sa.Column`.
  - FK existe de fato no banco após `alembic upgrade head` do zero (verificável via catálogo), e um `INSERT`/`UPDATE` direto com `spell_ability` inválido é rejeitado pelo banco.
  - `create_class` com `spell_ability` apontando para ability ainda não usada funciona sem erro e persiste corretamente.
  - Suíte completa (200 testes existentes + novos) passa sem regressão.
  - Nenhuma mudança de comportamento visível pela API além da correção de integridade (validação Pydantic do enum `AbilityScore` continua sendo a primeira barreira).

## Riscos / bloqueios conhecidos
- Nenhum bloqueio de especificação identificado — escopo, decisões (squash sem nova revisão, sem seed estático, sem dado real a migrar) já estão fechadas na Especificação Refinada.
- Risco operacional único: se o Postgres local do desenvolvedor já tiver dados de teste manual (fora da suíte automatizada) com `spell_ability` preenchido de forma inconsistente, a recriação do schema do zero é o caminho recomendado (e já é necessária de qualquer forma, dado o squash) — não requer tratamento especial além da ação humana já listada.
