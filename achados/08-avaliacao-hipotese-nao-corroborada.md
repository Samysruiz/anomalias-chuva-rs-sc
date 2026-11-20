# Achado 08 — Avaliação: a hipótese não foi corroborada

**Data da execução:** 20/11/2026, notebook `05_avaliacao` (versão 1), sobre os escores da rodada de 17/11/2026.
**Pré-registro:** `decisoes.json` v1.2, hash `d4c58a627755c8f9`.
**Decisões registradas pelo grupo em 20/11/2026, antes da execução:** emenda do limiar **rejeitada**; limiar
principal do nível 1 calculado no **treino**, com o da validação reportado ao lado.
**Dados de apoio:** `achados/dados/05/` e `achados/figuras/05_*.png`.

## Auditoria antes de qualquer métrica

A célula de auditoria terminou com **0 falhas**: notebook 04 fora do modo de demonstração e com o pré-registro
v1.2; 13.643.010 linhas de escore, iguais a (janelas de validação + teste) × modelos-semente; nenhuma linha de
treino; datas dentro das partições; sem duplicatas; só estações elegíveis; medianas iguais às da rodada de
17/11; 121 episódios e 37 severos; janela de detecção de 3 dias antes do início até o fim.

## Resultado principal: recall dos 37 episódios severos

| Modelo | Sementes | 1% dos dias | 3% dos dias | PR-AUC diária | Falsos/ano/UF a 1% | Alarme no teste a 1% |
|---|---|---|---|---|---|---|
| Limiar de chuva acumulada | 1 | **32,4%** | 35,1% | **0,323** | 6,6 | 4,53% |
| PCA | 1 | 16,2% | 32,4% | 0,231 | 6,1 | 3,00% |
| Autoencoder, gargalo 13 (principal) | 5 | 21,1% ± 4,4 | 33,0% ± 5,2 | 0,197 ± 0,026 | 5,8 | 2,85% |
| Autoencoder, gargalo 3 (ablação) | 5 | 29,2% ± 2,3 | 47,0% ± 5,6 | 0,275 ± 0,016 | 7,4 | 4,87% |
| Isolation Forest | 5 | 29,7% ± 1,9 | 41,6% ± 2,4 | 0,324 ± 0,005 | 6,8 | 5,15% |

A PR-AUC de um detector ao acaso é a prevalência de dias positivos, 0,108. A taxa de alarme na validação foi
de 0,94% no ponto de 1% e de cerca de 3% no ponto de 3%. A 3%, as taxas no teste foram: limiar 8,50%, PCA 11,09%,
autoencoder 8,23%, gargalo 3 11,40% e Isolation Forest 11,52%.

Recall do autoencoder principal por semente: 0,270, 0,162, 0,189, 0,189 e 0,243 a 1%; 0,324, 0,405, 0,351, 0,297
e 0,270 a 3%.

## Os cinco critérios de refutação

| Critério | 1% | 3% | PR-AUC | Veredito |
|---|---|---|---|---|
| 1. O autoencoder não supera o PCA de forma consistente nas 5 sementes | ocorre | ocorre | ocorre | **REFUTA** |
| 2. O escore do autoencoder não se eleva nos dias dos eventos | não ocorre | não ocorre | não ocorre | não refuta |
| 3. Nenhum modelo supera o limiar de chuva acumulada | ocorre | não ocorre | não ocorre | inconclusivo |
| 4. A variabilidade entre sementes excede a diferença AE − PCA | não ocorre | ocorre | não ocorre | inconclusivo |
| 5. O resultado não se reproduz só com o Hidroweb diário | não ocorre | ocorre | ocorre | inconclusivo |

Pela regra fixada na seção de critérios do pré-registro, basta um critério para que a hipótese seja considerada
não corroborada. O critério 1 ocorreu nas três leituras.

**Critério 2, em detalhe.** A AUC de Mann-Whitney do escore estação-dia, dias de episódio severo contra os
demais, ficou acima de 0,5 em todos os modelos, com p unilateral praticamente nulo: limiar 0,764; PCA 0,648;
autoencoder 0,644 ± 0,009; gargalo 3 0,718 ± 0,012; Isolation Forest 0,758 ± 0,003. O sinal existe.

**Critério 3, em detalhe.** A 1% dos dias, o limiar teve o maior recall. A 3%, o gargalo 3 (47,0%) e o Isolation
Forest (41,6%) passaram dele (35,1%), mas com taxa de alarme no teste também maior (11,4% e 11,5%, contra 8,5%).
Parte dessa vantagem vem de alarmar mais. Na PR-AUC, que independe de limiar, o limiar e o Isolation Forest
empataram (0,323 e 0,324).

**Critério 5, em detalhe.** Só com o Hidroweb diário, a 1%: autoencoder entre 0,135 e 0,243 nas sementes, PCA
0,135, limiar 0,297. A 3%: autoencoder entre 0,270 e 0,405, PCA 0,378, limiar 0,351. PR-AUC: autoencoder entre
0,168 e 0,240, PCA 0,250, limiar 0,355.

## O que os modelos medem

| Métrica | Valor |
|---|---|
| Spearman do escore com a chuva acumulada: PCA | 0,736 |
| idem, autoencoder principal | 0,718 |
| idem, gargalo 3 | 0,887 |
| idem, Isolation Forest | 0,972 |
| Spearman autoencoder × PCA | 0,755 |
| Jaccard do 1% mais anômalo, Isolation Forest × limiar | 0,465 |
| Jaccard do 1% mais anômalo, autoencoder × limiar | 0,131 |

Os modelos que mais detectaram (Isolation Forest e gargalo 3) são os que mais se aproximam da chuva acumulada.
O autoencoder principal ordena as janelas de modo bem diferente do limiar e detecta menos.

## Diferença entre os estados

| Recall a 1% | RS (18 episódios) | SC (19 episódios) |
|---|---|---|
| Limiar | 50,0% | 15,8% |
| PCA | 27,8% | 5,3% |
| Autoencoder | 30,0% | 12,6% |
| Gargalo 3 | 41,1% | 17,9% |
| Isolation Forest | 48,9% | 11,6% |

Todos os modelos detectam muito menos em SC. Uma explicação plausível, **não testada**, é que os episódios de SC
sejam mais locais e mais rápidos do que a resolução diária capta.

## Sensibilidades

- **Agrupamento dos episódios** (1, 2, 3 e 5 dias, com 42, 37, 35 e 30 episódios severos): a 1%, o limiar fica à frente
  do autoencoder principal e do PCA em todos os casos, e o PCA fica por último; o gargalo 3 passa do limiar com
  agrupamento de 3 e de 5 dias (0,291 contra 0,286; 0,327 contra 0,300).
- **Limiar por estação** (percentis 95, 99 e 99,5) e **alvo de alarme** (0,5% a 3%): o padrão se repete; o limiar
  de chuva fica à frente do autoencoder em todas as combinações a 1% ou menos.
- **Nível 1, limiar do treino contra o da validação**, a 1%: o mesmo recall (32,4%); taxa de alarme no teste de
  4,53% com o limiar do treino e de 5,50% com o da validação.

## O que a previsão do achado 05 antecipou

A validação caiu no período mais seco da série, e o alarme calibrado para 1% dos dias tocou entre 2,85% e 5,15%
dos dias no teste. A previsão se confirmou; a taxa observada está reportada ao lado da calibrada, sem recalibração.

## Limites desta leitura

- Duas sementes do autoencoder principal pararam cedo (épocas 5 e 6). A conclusão não depende delas: nenhuma das
  cinco sementes alcança o limiar a 1% (a melhor tem 27,0%, contra 32,4%).
- O gargalo 3 é ablação e não convergiu em 150 épocas. O desempenho dele a 3% não deve ser lido como descoberta.
- A comparação a 3% iguala a taxa de alarme na validação, não no teste.
- O teto estrutural a 1% é de cerca de 61% no RS e 58% em SC.

## O que refutaria esta conclusão

Um autoencoder que superasse o limiar de chuva acumulada com a mesma taxa de alarme no teste, de forma consistente
nas cinco sementes, ou com a janela de 30 dias da ablação pré-registrada e não executada.

## O que este achado não autoriza

Qualquer modelo novo ou ajuste testado depois deste resultado é análise exploratória. Ele pode entrar como trabalho
futuro, mas não substitui o resultado pré-registrado.
