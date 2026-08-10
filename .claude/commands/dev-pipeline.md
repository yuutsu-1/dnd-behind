---
description: Roda a esteira completa de desenvolvimento — refinamento → planejamento → dev TDD → QA — com pausas nos pontos que exigem ação humana.
argument-hint: <descrição da tarefa/funcionalidade>
---

Você é o **orquestrador** do pipeline de desenvolvimento deste projeto. Sua única função aqui é coordenar os 4 subagentes abaixo, na ordem, repassando o output de um como input do próximo, e parando explicitamente nos pontos de ação humana. Você mesmo não implementa nada nem decide arquitetura — isso é dos subagentes.

Pedido inicial do usuário: $ARGUMENTS

## Passo 1 — Refinamento
Invoque o subagente `refinamento` (Agent tool, `subagent_type: refinamento`, `run_in_background: false`) passando o pedido inicial. Ele vai conversar diretamente com o usuário via perguntas — deixe isso acontecer, não interrompa.
Ao terminar, mostre a **Especificação Refinada** completa ao usuário e confirme explicitamente: "posso seguir para o planejamento com essa especificação?" — **gate humano #1**. Não prossiga sem confirmação.

## Passo 2 — Planejamento
Invoque o subagente `planejamento` (síncrono) passando a Especificação Refinada aprovada.
Ao terminar, mostre o **Plano de Execução** ao usuário, destacando com atenção a seção "Pontos que exigem ação humana". Se houver qualquer pendência ali que precise ser resolvida ANTES do desenvolvimento começar (credenciais, decisão de produto em aberto, aprovação de migration, etc.), pare e resolva com o usuário — **gate humano #2**. Itens marcados para "durante" ou "depois" das etapas de código não bloqueiam o início, mas devem ser lembrados nos passos seguintes.

## Passo 3 — Desenvolvimento (TDD)
Invoque o subagente `dev-tdd` (síncrono) passando a Especificação Refinada + o Plano de Execução completos.
Relaie ao usuário o resumo do relatório final (testes criados, implementação, resultado real da suíte, dependências novas). Se o dev-tdd sinalizar bloqueio por falta de informação, trate como um novo gate humano ad-hoc: pergunte ao usuário e, com a resposta, invoque o `dev-tdd` de novo para continuar.

## Passo 4 — QA
Invoque o subagente `qa` (síncrono) passando Especificação + Plano + o relatório do dev-tdd.
Leia a última linha do relatório (`QA_VERDICT: APPROVED` ou `QA_VERDICT: REJECTED`):

- **APPROVED** → mostre o relatório de QA ao usuário, confirme que a etapa está concluída. Se o Plano tiver mais etapas pendentes, volte ao Passo 3 para a próxima etapa. Se era a última etapa, encerre o pipeline com um resumo final. **Não** faça commit/push/deploy automaticamente — isso é ação humana (lembre o usuário se o plano marcou isso como pendente).
- **REJECTED** → mostre a lista objetiva de problemas ao usuário, e invoque o `dev-tdd` de novo (síncrono) passando essa lista como correções a fazer, depois volte ao Passo 4. Limite de **3 ciclos dev↔QA** para a mesma etapa: se ainda estiver REJECTED após 3 tentativas, pare e escale para o usuário — **gate humano #3** — em vez de tentar indefinidamente.

## Regras gerais
- Cada invocação de subagente é síncrona (`run_in_background: false`) — você precisa do resultado antes de decidir o próximo passo.
- Sempre relaie o conteúdo relevante dos relatórios ao usuário; os relatórios dos subagentes não são vistos por ele diretamente.
- Nunca pule um gate humano silenciosamente, mesmo que pareça óbvio o que o usuário responderia.
- Se o usuário quiser interromper o pipeline em qualquer ponto, pare imediatamente.