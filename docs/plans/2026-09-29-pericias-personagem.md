# Plano de Execução: Perícias do personagem (`character_skills`)

## Referência
Especificação: tabela filha `character_skills` (N:1 com `Character`) registrando perícia, origem (`source`) e `expertise`, exposta na API (POST/DELETE/PATCH sub-recurso, lote na criação, antecedente automático, leitura em `CharacterOut`).

## Etapas técnicas (ordem de execução)

1. **Modelo `CharacterSkill`** — `backend/app/db/models/character.py` (e registro no `__init__` de models, se existir)
   - Resultado: tabela `character_skills` com PK uuid, `character_id` FK `characters.id` CASCADE, `skill_id` FK `skill_definitions.id`, `source` string curta, `expertise` bool default false, `UniqueConstraint(character_id, skill_id)`. `Character.skills` com `cascade="all, delete-orphan"`. Propriedades derivadas nome/atributo-base (padrão de `species_name`). Comentário TODO de `Character.choices` (linha 32) atualizado: perícias não vão mais nele.
   - Pronto: teste de modelo/integração persiste linha; duplicata (character, skill) gera IntegrityError; apagar personagem remove as linhas.

2. **Migration Alembic reversível** — `backend/alembic/versions/<nova>.py` (down_revision `c1fcfd7fe014`)
   - Resultado: `upgrade` cria a tabela; `downgrade` a remove. Sem migração de dados.
   - Pronto: upgrade -> downgrade -> upgrade sem erro em banco de teste; `alembic check` sem diff contra os modelos. (**Ação humana** para aplicar fora do teste.)

3. **Schemas Pydantic** — `backend/app/schemas/character.py`
   - Resultado: schema de entrada (skill_id, source, expertise opcional), schema de saída (skill_id, nome, atributo-base, source, expertise), schema de update de expertise; `CharacterCreate` ganha lista opcional de perícias; `CharacterOut` (e por herança `CharacterWithInventory`) ganha lista de perícias. `source` restrito ao conjunto {class, background, species, feat, other}.
   - Pronto: source inválido -> 422; `CharacterOut` serializa perícias.

4. **Eager loading** — `backend/app/services/character.py` (`_character_eager_load_options`), `backend/app/api/characters.py` (`/me` linhas ~58-63 duplica as opções manualmente; `/campaign/{id}` ~264), e `refresh` em `create_character`
   - Resultado: `Character.skills` + `CharacterSkill.skill` carregados em GET /{id}, /me, /campaign/{id}, POST, PATCH. Preferir reusar `_character_eager_load_options` no `/me`.
   - Pronto: cada endpoint retorna perícias sem `MissingGreenlet`/lazy-load error.

5. **Serviço: validação e CRUD de perícia** — `backend/app/services/character.py`
   - Resultado: adicionar, remover e alterar expertise, com regras: perícia inexistente 404; duplicata 400; `class` sem classe 400, fora de `class_skills` da primeira classe 400, total `class` > `skill_choices` 400, só a primeira classe concede; `background` só se pertencer ao antecedente atual (senão 400); species/feat/other só validam existência; expertise (PATCH, evento `character.skill.expertise`) só em perícia possuída (senão 404), SEM restrição de classe e SEM limite de quantidade. DECISÃO DO USUÁRIO: a constante de classes com Expertise foi DESCARTADA (classe não concede expertise por padrão; features/talentos que concedem pertencem ao motor de features, gap 10, fora de escopo); `CharacterSkillCreate` não aceita `expertise` (só via PATCH). Personagem inexistente/inativo 404, sem permissão 403 (`assert_owner_or_dm`).
   - Pronto: testes unitários/integração para cada 400/404 acima e para o caminho feliz.

6. **Serviço: perícias automáticas de antecedente** — `backend/app/services/character.py` (`create_character`, `update_character`)
   - Resultado: ao definir/trocar `background_id` cria linhas `source="background"` a partir de `background_skills`, pulando perícias já existentes por outra fonte; ao trocar remove as linhas `background` antigas. Não dispara se `background_id` não mudou.
   - Pronto: criar com antecedente gera linhas; PATCH trocando remove antigas e cria novas; perícia já presente por outra fonte não duplica; PATCH sem mudar background não altera nada.

7. **Serviço: lote no `create_character`** — `backend/app/services/character.py`
   - Resultado: perícias do payload validadas e gravadas na mesma transação do personagem (um único commit; falha -> rollback, personagem não criado). Ordem: antecedente automático primeiro, depois as do lote (lote em conflito com automática -> duplicata 400, ou tratar conforme decisão humana abaixo).
   - Pronto: lote válido cria personagem + perícias; lote com item inválido retorna 4xx e nenhum personagem existe no banco.

8. **Endpoints sub-recurso** — `backend/app/api/characters.py`
   - Resultado: `POST /characters/{id}/skills` (201, retorna nome, atributo, source, expertise), `DELETE /characters/{id}/skills/{skill_id}` (204), `PATCH /characters/{id}/skills/{skill_id}` (expertise). Cada mutação chama `_broadcast` com `character.skill.add`, `character.skill.remove` e um evento de update de expertise (nome do evento de expertise a cargo do dev, seguindo o padrão `character.*`). Remoção de perícia inexistente no personagem -> 404.
   - Pronto: status codes corretos, 403 para terceiro sem permissão, DM da campanha permitido, broadcast chamado (mock/spy) nas 3 mutações.

9. **Testes de integração completos e regressão** — `backend/tests/integration/test_character_skills_integration.py` (novo; seguir padrão de `test_character_ability_scores_integration.py`) + unit em `backend/tests/unit/test_character_service.py`
   - Pronto: todos os critérios de aceite cobertos; suíte existente inteira passa.

Observação de TDD: as etapas 1 a 9 são escritas teste-primeiro; 1->2->3->4 são a base bloqueante; 5 e 6 dependem de 1 a 4; 7 depende de 5 e 6; 8 depende de 5; 9 é contínuo.

## Pontos que exigem ação humana
- [ ] Revisar e aplicar a migration (`alembic upgrade head`) em qualquer banco compartilhado/produção — motivo: altera schema fora do ambiente de teste — quando: após a etapa 2 e antes de deploy.
- [ ] Decidir o caso de lote na criação com `source="class"` — motivo: hoje `create_character` NÃO aceita classes (classes entram via `POST /characters/{id}/classes`), então "class sem classe -> 400" torna perícias de classe impossíveis no lote. Opções: (a) aceitar e deixar só `background/species/feat/other` no lote na prática; (b) rejeitar `class` no lote com mensagem clara; (c) incluir classe no `CharacterCreate` (fora do escopo aprovado). — quando: antes da etapa 7. Sugestão do plano se não houver resposta: (b) ou comportamento natural (a), ambos produzem 400.
- [ ] Confirmar a política de conflito entre lote e perícia automática de antecedente (o item do lote com `source="background"` duplica a automática: 400 ou idempotente) — quando: antes da etapa 7. Sugestão: 400 por duplicata, consistente com a regra geral.
- [x] (DESCARTADO: sem constante de classes) Confirmar a lista fixa de classes com Expertise e como casar (por nome de `ClassDefinition`, "Ladino"/"Bardo" vs. nomes em inglês do compêndio; verificar os nomes reais no seed) — quando: antes da etapa 5.
- [ ] Commit, push e merge em `main` — motivo: ação de versionamento restrita ao humano — quando: após QA aprovado.

## Workflow para os próximos agentes
- Ordem: refinamento (concluído) -> **planejamento (este)** -> dev-tdd -> QA
- dev-tdd segue TDD estrito, etapa a etapa, na ordem acima; etapas 1 a 4 bloqueantes e sequenciais; 5 e 6 podem ser paralelas após a 4 (mesmo arquivo de serviço, então na prática sequenciais); 8 pode andar em paralelo à 7 depois da 5.
- Checkpoint intermediário de QA opcional após a etapa 4 (schema + migration + leitura) e checkpoint final após a etapa 9. QA completo obrigatório ao final.
- Critério de aprovação do QA:
  - Tabela com FKs, source, expertise, unicidade; migration sobe e desce.
  - POST 201, DELETE 204, expertise atualizável; broadcast nas três mutações; 403 sem permissão; 404 personagem/perícia inexistente.
  - GET /{id}, /me, /campaign/{id} retornam perícias sem erro de lazy loading.
  - 400 para: classe fora do pool, excede `skill_choices`, duplicata, antecedente não pertencente, `class` sem classe; expertise em perícia não possuída -> 404 (regra de classe Expertise descartada).
  - Lote transacional (falha não cria personagem).
  - Antecedente automático criado/removido/sem duplicar.
  - Suíte existente verde; `Character.choices` intocado.

## Riscos / bloqueios conhecidos
- Lacuna de spec sobre lote com `source="class"` (ver ação humana 2); não bloqueia as etapas 1 a 6 e 8.
- `/me` duplica opções de eager loading manualmente; esquecer de atualizar causa erro de lazy load em async.
- `create_character` faz `refresh` com lista explícita de atributos; incluir `skills` (e `skill` aninhado) para serialização.
- Trocar de antecedente com PATCH: garantir remoção apenas das linhas `background`, sem tocar em `class`/outras.
- Trocar de classe depois deixa linhas antigas inválidas por decisão (validação só na escrita); não tratar como bug.
- (Resolvido) Expertise sem regra de classe; descartada a dependência dos nomes de classes no seed.
