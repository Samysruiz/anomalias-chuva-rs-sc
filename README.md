# Detecção não supervisionada de anomalias de precipitação associadas a cheias no RS e em SC

Projeto final da disciplina Aprendizado Não Supervisionado, curso de Inteligência Artificial da
Faculdade Donaduzzi (Toledo, PR). Orientação: Prof. Wagner.

**Grupo:** Felipe Fernandes Clivati, Juan Carlos Guatierri Alves, Leonardo Secco Silva,
Rafael Lazarin Lobo de Almeida, Samara Ruiz Silva e Victor Hugo Stein Blauth.

Seleção, pré-processamento, transformação e este registro foram conduzidos por Samara Ruiz Silva
entre 10 e 20 de novembro de 2026. O treinamento dos modelos ficou a cargo de Felipe Fernandes Clivati.

## O que está neste repositório

Este repositório é o registro público e datado do trabalho. Ele existe para que as decisões
metodológicas possam ser verificadas por terceiros na ordem em que foram tomadas, e para que o
pré-registro das hipóteses seja auditável.

| Pasta | Conteúdo |
|---|---|
| `pre-registro/` | Parâmetros fixados antes de qualquer treinamento, com hash, e o registro de emendas |
| `achados/` | Cada investigação, com o que foi tentado, o que falhou e os dados de apoio |
| `codigo/` | Módulo de controle de qualidade, notebooks 03, 04 e 05 e os seus testes |
| `dados/` | Procedência dos dados e instruções de obtenção. Os dados brutos não estão aqui |
| `declaracao-uso-de-ia.md` | O que foi assistido por IA, o que foi verificado e por quem |

Os achados, em ordem:

| Achado | Pergunta | Estado |
|---|---|---|
| 01 | Em que base de tempo estão os carimbos? | UTC, com ressalva declarada (resolvida no achado 07) |
| 02 | Onde fechar o dia agregado? | 12 h mantido; a confirmação falhou em SC |
| 03 | O que conta como evento no REInDesC? | episódio por agrupamento, severidade pela fonte |
| 04 | O que a primeira execução sobre os dados reais mostrou? | 790 estações elegíveis; CEMADEN e ICEA fora |
| 05 | Por que o teste parece mais chuvoso que a validação? | é clima: a validação contém o ano mais seco de 31 |
| 06 | O projeto está consistente antes da avaliação? | sim, com duas decisões pendentes e oito correções listadas |
| 07 | O carimbo do UNIPLU-BR está mesmo em UTC? | sim: pico de correlação com a NOAA em 0 h, em 117 pares |
| 08 | O autoencoder detecta as cheias melhor que as referências? | não: hipótese não corroborada (critério 1); o limiar simples lidera a 1% |
| 09 | (Exploratório) A chuva das vizinhas ajuda o autoencoder? | não (S1 e S2 não ocorrem); o PCA com a vizinhança melhora, mas alarmando o dobro no teste |
| 10 | (Exploratório) Os pluviômetros travam ou falham nas cheias? | travamento: não nas estações do modelo (p = 0,994), e 99,5% dele é do Cemaden; falta de dado: maior nos episódios, mas confundida com o fim da série Hidroweb em 30/09/2025 (sensibilidade pendente) |

## A pergunta

Um autoencoder treinado apenas com chuva diária de estações pluviométricas do Rio Grande do Sul
e de Santa Catarina atribui erro de reconstrução mais alto a janelas que contêm eventos de cheia
do que a janelas de comportamento habitual? E esse ganho, se existir, vem da não linearidade, ou
já é obtido por uma referência linear ou por um limiar simples de precipitação acumulada?

## O desenho

Quatro níveis de comparação, do mais simples ao mais elaborado: limiar de precipitação acumulada,
análise de componentes principais, autoencoder e Isolation Forest. O mesmo particionamento
temporal, o mesmo pré-processamento e as mesmas cinco sementes para todos.

Os rótulos de evento vêm do REInDesC, do Cemaden, e são usados **somente na avaliação**. Nenhum
rótulo entra no treinamento.

## Cinco critérios de refutação, fixados de antemão

A hipótese é considerada não corroborada se qualquer um deles ocorrer:

1. o autoencoder não superar a análise de componentes principais de forma consistente nas cinco sementes;
2. o erro de reconstrução não se elevar nas janelas correspondentes a eventos de cheia;
3. nenhum modelo superar o limiar de precipitação acumulada;
4. a variabilidade entre sementes exceder a diferença entre modelos;
5. o resultado não se reproduzir na replicação restrita ao Hidroweb diário (emenda de 12/11/2026).

Qualquer desses resultados será publicado como resultado.

## Estado

- Notebook 03 (qualidade e preparo): executado nos dados reais em 13/11/2026.
- Notebook 03b (verificação de fuso com a NOAA): executado em 19/11/2026; UTC confirmado.
- Notebook 04 (janelas e modelos): rodada definitiva em 17/11/2026; escores gravados e travados.
- Notebook 06 (fase 2, exploratória, versão mínima): executado em 21/11/2026; resultado no achado 09.
- Notebook 07 (falhas dos sensores, exploratório): executado em 21/11/2026; resultado no achado 10; sensibilidades S1 e S2 pendentes.
- Notebook 05 (avaliação): executado em 20/11/2026, com a emenda do limiar rejeitada e o nível 1 calibrado
  O arquivo executado é `codigo/05_avaliacao_sugestao.ipynb` (gerado por `gerar_nb05.py --sugestao`, com a emenda do limiar marcada como rejeitada, decisão do grupo de 20/11/2026); `codigo/05_avaliacao.ipynb` é a versão em branco, que para até a decisão ser preenchida. No Drive, o executado se chama `05_avaliacao_EXECUTADO_20-11.ipynb`.
  no treino, decisões registradas pelo grupo antes da execução. Auditoria com 0 falhas.

## Resultado

**A hipótese não foi corroborada.** O critério 1 ocorreu nas três leituras: o autoencoder não supera o PCA de
forma consistente nas cinco sementes. Com alarme em 1% dos dias, o limiar simples de chuva acumulada detectou
32,4% dos 37 episódios severos; o autoencoder principal, 21,1% ± 4,4; o PCA, 16,2%. O escore sobe nos dias de
cheia em todos os modelos (AUC de 0,64 a 0,76), mas os modelos que mais detectam são os que mais se aproximam
da chuva acumulada. Detalhes, sensibilidades e limites no achado 08.

A data de entrega é 1 ou 2 de dezembro de 2026.

## Procedência dos dados

- **Treinamento:** UNIPLU-BR (LEMOS et al., 2026), Zenodo, DOI 10.5281/zenodo.18883358, licença CC BY 4.0.
- **Rótulos de avaliação:** REInDesC, Cemaden, https://reindesc.cemaden.gov.br, acesso em
  13 nov. 2026. Base descrita em BERNARDES, T. et al., *International Journal of Disaster Risk
  Reduction*, v. 137, art. 106099, 2026 (acesso aberto). Acesso público e gratuito, **sem termos
  explícitos de licenciamento**, razão pela qual as ocorrências exportadas não são redistribuídas aqui.
- **Referência de controle de qualidade:** pipeline do AIR Centre (PINELO, 2026),
  https://github.com/AIRCentre/UNIPLU-BR, licença MIT.

## Licença

Código em `codigo/` sob licença MIT (ver `LICENSE`). Textos em `achados/` e `pre-registro/` sob
Creative Commons Atribuição 4.0 Internacional.
