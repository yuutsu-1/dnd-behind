# Relatório de gaps — descobertos ao tentar criar um personagem real (Sir Alcino)

## Contexto
Tentativa de criar um personagem real via API/serviços (Guerreiro 3 / Campeão, Humano, Nobre) para validar o sistema ponta a ponta. O banco estava completamente vazio (nenhuma classe/subclasse/espécie/antecedente/talento/item/perícia/usuário cadastrado), o que já era esperado. Durante a tentativa, surgiram gaps de modelagem que impedem representar corretamente o personagem sem inventar dados ou forçar tudo em campos genéricos. Parado antes de implementar qualquer coisa — este documento é o inventário desses gaps, para virar entrada de um ciclo de refinamento/planejamento futuro.

## Gaps por área

### 1. `BackgroundDefinition` é essencialmente uma casca vazia
Hoje só tem `id`, `name`, `description`, `source`, `is_homebrew`, `created_by`, `created_at`. Não existe nenhum lugar para guardar o que um antecedente concede: bônus/escolha de atributos (regra 2024 — é o antecedente que dá o incremento de atributo, não a espécie), perícias concedidas, proficiência de ferramenta (inclusive quando é "escolha um tipo de X", como "Conjunto de Jogos"), talento concedido (fixo, ex. Nobre sempre dá Habilidoso/Skilled), e opções de equipamento inicial (A/B).
**Impacto**: nenhum antecedente pode ser modelado de forma completa hoje.

### 2. Nenhuma tabela registra as escolhas reais de perícia de um personagem
Existe `SkillDefinition` + `class_skills` (pool de opções da classe) + `ClassDefinition.skill_choices` (quantas escolher), mas nada grava **quais** perícias um personagem específico efetivamente tem — nem as escolhidas da classe, nem as de traço de espécie (ex. "Habilidoso" do Humano), nem as fixas de antecedente (ex. História/Persuasão do Nobre).
**Impacto**: não dá pra saber quais perícias um personagem realmente possui depois de criado.

### 3. Nenhuma tabela registra Maestria com Armas (Weapon Mastery) do personagem
O Guerreiro (e outras classes) concede acesso à propriedade de maestria de N tipos de arma à escolha, reatribuível após descanso longo (N cresce por nível: 3 → 4 → 5 → 6). Não existe nenhuma estrutura para "quais armas este personagem tem maestria agora". Além disso, "maestria" como conceito de arma (qual propriedade cada arma tem — Cleave, Roçar, Derrubar, Vexar, etc.) também não tem campo próprio em `ItemDefinition`.
**Impacto**: confirmado nesta sessão — ficaria só em `Character.custom_data` sem estrutura, o que o usuário preferiu não fazer.

### 4. `ItemDefinition` não modela dados mecânicos de arma de forma estruturada
Dano (dado + tipo), propriedades (Leve, Pesada, Acuidade, Versátil, Arremesso, Duas Mãos, Munição, Recarga, Alcance), categoria (Simples/Marcial), corpo-a-corpo vs. à distância, e a propriedade de maestria da arma são todos atributos específicos de arma sem coluna dedicada — teriam que ir todos dentro do `properties: JSONB` genérico, sem convenção documentada nem validação, arriscando formatos inconsistentes conforme mais itens forem cadastrados.
**Impacto**: qualquer cadastro de arma hoje seria ad-hoc.

### 5. Sem rastreio de moeda/ouro do personagem
Nenhum campo de carteira/moeda existe em `Character` nem em nenhum outro modelo. As opções de equipamento inicial de classe e antecedente sempre têm uma opção "só dinheiro" (ex. 155 PO ao invés de equipamento do Guerreiro, 50 PO ao invés de equipamento do Nobre) e mesmo as opções com itens sobram PO (4 PO, 29 PO).
**Impacto**: dinheiro do personagem não tem onde ser guardado.

### 6. Sem suporte a itens compostos/kits
"Pacote de Explorador de Masmorras" é um kit com vários itens dentro. `ItemDefinition`/`CharacterInventory` só suportam item simples + quantidade, sem conteúdo aninhado.
**Impacto**: um kit desses só pode ser cadastrado como item opaco, sem detalhar o que tem dentro.

### 7. Nenhuma ligação entre `ItemDefinition` (arma) e as categorias de proficiência
`WeaponProficiencyOption`/`ArmorProficiencyOption` guardam só categorias soltas (ex. "Simples", "Marcial", "Leve", "Pesada") sem relação formal com os itens de arma/armadura cadastrados em `ItemDefinition`. Não há como consultar "quais armas são Marciais" a partir do cadastro de proficiência — a categoria de cada arma ficaria só implícita/duplicada manualmente.

### 8. `FeatDefinition` não tem lugar para o efeito mecânico do talento
O modelo tem `category`, `level_prerequisite`, `prerequisite_description`, `repeatable`, mas nada equivalente ao `effect_type`/`effect_data` que `FeatureGrant` tem para classes. Talentos como Robusto (+2×nível de PV máx., +2 por nível depois) ou Defesa (+1 CA usando armadura) não têm onde guardar essa regra de forma computável — só descrição em texto. O docstring do `FeatureGrant` já lista "feito" como fonte válida (`source_type`), sugerindo que o talento deveria emitir seus próprios `FeatureGrant`s, mas isso nunca foi conectado a `FeatDefinition`/`CharacterFeat`.

### 9. `CharacterFeat.source` não cobre todos os casos reais
Valores hoje: `"background"`, `"asi_replacement"`, `"class_feature"`, `"epic_boon"`. Não hpa valor para "concedido por traço de espécie" (ex. Versátil do Humano, que dá um Talento de Origem à escolha) nem diferencia "antecedente concede um talento fixo automaticamente" (ex. Nobre sempre dá Habilidoso/Skilled) de "antecedente permite escolher". Ficou ambíguo durante a tentativa de criação qual `source` usar para cada talento do Sir Alcino.

### 10. Nenhum "motor" que aplica `FeatureGrant`/talentos ao personagem
O próprio docstring de `FeatureGrant` diz: *"O motor lê effect_type + effect_data e aplica o resultado a um personagem"* — esse motor não existe. Mesmo que os dados fossem todos cadastrados certinho, nada calcula automaticamente PV máximo (com bônus de Robusto escalando por nível), CA (com bônus de Defesa), perícias, etc. Tudo teve que ser calculado manualmente durante esta tentativa (ex.: PV do Sir Alcino nível 3 = base fixo por nível + CON + 2×nível de Robusto).
**Impacto**: mesmo resolvendo os gaps 1-9, ainda faltaria a camada que transforma dado cadastrado em ficha computada.

### 11. Inconsistência de unidade em `SpeciesDefinition.base_speed`
O default do campo é `30` (sugerindo pés, convenção do SRD em inglês), mas o material fonte em PT-BR usado nesta sessão dá deslocamento em metros (9m para Humano). Não há documentação de qual unidade o campo espera.
**Impacto**: menor, mas pode gerar inconsistência quando mais espécies forem cadastradas.

## Não são gaps (contexto, não bloqueiam)
- Banco vazio (sem usuários/compêndio) — esperado, é só seed de dados, não gap de modelagem.
- O bug de FK de `spell_ability` já foi identificado e corrigido em sessão anterior (commit `7552f29`) — não é mais um gap em aberto.

## Sugestão de priorização (não vinculante, para discussão no refinamento)
1. **Gaps 1, 2, 8** (antecedente vazio, perícias do personagem, talentos do personagem) — são o bloqueio mais direto para criar qualquer personagem completo, independente de classe.
2. **Gap 4 e 7** (modelagem de arma) — necessário para qualquer classe marcial, não só Guerreiro.
3. **Gap 3** (maestria de armas) — específico de mecânica 2024, mas depende do gap 4 estar resolvido primeiro.
4. **Gap 10** (motor de aplicação) — maior escopo, mas é o que realmente entrega valor de produto (ficha calculada automaticamente); pode ser faseado depois que os dados tiverem onde morar.
5. **Gaps 5, 6, 9, 11** — menores/pontuais, podem entrar juntos com os itens acima ou ser tratados à parte.
