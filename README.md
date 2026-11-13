# Detecção não supervisionada de anomalias de precipitação associadas a cheias no RS e em SC

Projeto final da disciplina Aprendizado Não Supervisionado, curso de Inteligência Artificial da
Faculdade Donaduzzi (Toledo, PR). Orientação: Prof. Wagner.

**Grupo:** Felipe Fernandes Clivati, Juan Carlos Guatierri Alves, Leonardo Secco Silva,
Rafael Lazarin Lobo de Almeida, Samara Ruiz Silva e Victor Hugo Stein Blauth.

Seleção, pré-processamento, transformação e este registro foram conduzidos por Samara Ruiz Silva
entre 10 e 13 de novembro de 2026. A modelagem está dividida em quatro frentes independentes que
partem da mesma entrada — limiar acumulado, PCA, autoencoder e Isolation Forest — e a atribuição
de cada uma é registrada no histórico de commits à medida que for assumida.

## O que está neste repositório

Este repositório é o registro público e datado do trabalho. Ele existe para que as decisões
metodológicas possam ser verificadas por terceiros na ordem em que foram tomadas, e para que o
pré-registro das hipóteses seja auditável.

| Pasta | Conteúdo |
|---|---|
| `pre-registro/` | Parâmetros fixados antes de qualquer treinamento, com hash, e o registro de emendas |
| `achados/` | Cada investigação, com o que foi tentado, o que falhou e os dados de apoio |
| `codigo/` | Módulo de controle de qualidade, notebooks 03 e 04 e os seus testes |
| `dados/` | Procedência dos dados e instruções de obtenção. Os dados brutos não estão aqui |
| `declaracao-uso-de-ia.md` | O que foi assistido por IA, o que foi verificado e por quem |

Os achados, em ordem:

| Achado | Pergunta | Estado |
|---|---|---|
| 01 | Em que base de tempo estão os carimbos? | UTC, com ressalva declarada |
| 02 | Onde fechar o dia agregado? | 12 h mantido; a confirmação falhou em SC |
| 03 | O que conta como evento no REInDesC? | episódio por agrupamento, severidade pela fonte |
| 04 | O que a primeira execução sobre os dados reais mostrou? | 790 estações elegíveis; CEMADEN e ICEA fora |
| 05 | Por que o teste parece mais chuvoso que a validação? | é clima: a validação contém o ano mais seco de 31 |

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

## Quatro critérios de refutação, fixados de antemão

A hipótese é considerada não corroborada se qualquer um deles ocorrer:

1. o autoencoder não superar a análise de componentes principais de forma consistente nas cinco sementes;
2. o erro de reconstrução não se elevar nas janelas correspondentes a eventos de cheia;
3. nenhum modelo superar o limiar de precipitação acumulada;
4. a variabilidade entre sementes exceder a diferença entre modelos.

Qualquer desses resultados será publicado como resultado.

## Estado

Pré-processamento escrito e testado com dados sintéticos; execução sobre os dados reais pendente.
Nenhum modelo treinado. Nenhuma pontuação de modelo obtida. A data de entrega é 1 ou 2 de
dezembro de 2026.

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
