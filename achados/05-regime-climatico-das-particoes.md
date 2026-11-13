# Achado 5 — A validação cai no período mais seco de 31 anos

**Data:** 13 de novembro de 2026. **Estado:** medido, com a rede fixa. **Consequência:** a calibração
do limiar está sendo feita num período atípico. Decisão sobre emenda em aberto.

## Como apareceu

A rodada de demonstração do notebook 04 imprimiu a mediana da chuva acumulada em 15 dias por
partição, no nível 1 (soma em milímetros, sem modelo):

| Conjunto | Mediana do acumulado de 15 dias |
|---|---|
| Validação 2020–2022 | 42,3 mm |
| Teste 2023–2025 | 58,4 mm |

Trinta e oito por cento de diferença. Esse número é calculado sobre **todas** as janelas de cada
partição, sem treino, sem amostragem e sem modelo: não é número de demonstração, é definitivo.

Mediana não se desloca por cauda, de modo que a hipótese de que fosse efeito do evento de maio de
2024 estava descartada desde o início.

## As duas explicações possíveis, e o teste que as separa

1. **Regime climático real.** Os períodos simplesmente diferem.
2. **Artefato de composição de rede.** A validação e o teste têm 659 e 629 estações, e a mistura de
   redes muda ao longo da série (achado 4). Se as estações presentes mudarem de lugar, a mediana
   muda sem que o clima mude.

O teste que separa as duas: repetir o cálculo **só no Hidroweb diário**, a única rede com
composição estável nos 31 anos, com 479 estações elegíveis. Com a rede fixa, a explicação 2 deixa
de ser possível.

Dados: `dados/acumulado_mediano_por_ano_hidroweb.csv`. Procedimento: célula 6b do notebook 04.

## O resultado

A diferença permanece. É clima, não é artefato.

| Período | Mediana das medianas anuais | Em relação ao treino |
|---|---|---|
| Treino 1995–2019 | 50,5 mm | — |
| Validação 2020–2022 | 40,2 mm | −20% |
| Teste 2023–2025 | 54,6 mm | +8% |

E o achado é mais preciso do que a primeira leitura sugeria: **o período anômalo é a validação, não
o teste.**

| Ano | Mediana | Posto | p90 | Posto |
|---|---|---|---|---|
| 2020 | 35,0 mm | **1/31** | 111,0 mm | 3/31 |
| 2021 | 40,1 mm | 5/31 | 117,3 mm | 6/31 |
| 2022 | 45,5 mm | 9/31 | 140,3 mm | 20/31 |
| 2023 | 56,9 mm | 25/31 | 182,4 mm | **31/31** |
| 2024 | 60,1 mm | 26/31 | 165,5 mm | 29/31 |
| 2025 | 46,8 mm | 12/31 | 137,8 mm | 16/31 |

2020 é o ano mais seco da série e 2021 é o quinto. O teste é chuvoso, mas dentro da faixa
histórica: 1998, 2015, 2002 e 2014 tiveram medianas maiores que as de 2023 e 2024.

Na cauda o quadro piora. **2023 tem o percentil 90 mais alto de toda a série** e 2024 o terceiro,
enquanto 2020 tem o terceiro mais baixo.

## Por que isso é um problema de método, não uma curiosidade

O limiar por estação é o **percentil 99** do escore na validação. O `f` do alarme regional é
calibrado para que no máximo 1% dos **dias de validação** entrem em alarme.

Ou seja: os dois parâmetros que governam a taxa de alarme estão sendo estimados nos anos de cauda
mais fraca da série e aplicados aos anos de cauda mais forte. O efeito previsível é que, no teste,
muito mais que 1% dos dias entrem em alarme. O recall sobe pelo motivo errado, e os alarmes falsos
sobem junto.

**Uma hipótese não testada** para a causa climática: o período 2020–2022 coincide com La Niña
sucessiva e 2023–2024 com El Niño, padrão conhecido de influência sobre a precipitação no Sul do
Brasil. Isso **não** é afirmado aqui como fato do trabalho: exige fonte citável e não foi
verificado. O que está medido é a diferença de regime, não a sua causa.

## O que não fazer

Recalibrar o limiar depois de ver isto seria o ajuste pós-resultado que o pré-registro existe para
impedir.

## O que fazer

Obrigatório, qualquer que seja a decisão: **reportar a taxa de alarme efetivamente observada no
teste ao lado do 1% calibrado.** Se ela vier muito acima, o número fala por si, e a limitação fica
documentada com evidência.

Em aberto, decisão do grupo, com a janela fechando no instante em que a primeira avaliação rodar:

1. **Não emendar.** O limiar continua sendo o P99 da validação, como pré-registrado, e a distorção
   entra como limitação declarada.
2. **Emendar agora, com data**, acrescentando uma análise de sensibilidade com o limiar calibrado
   sobre o treino de 25 anos, que não é um período atípico. Não cria vazamento novo, porque o
   treino já fornece a média e o desvio da normalização. O ponto principal continuaria sendo o
   pré-registrado.

O texto pronto da emenda está em `pre-registro/emenda-proposta-2026-11-13-limiar.md`, não aplicado.

## O que refutaria este achado

- O cálculo por ano no Hidroweb diário mostrando 2020–2022 dentro da faixa normal da série, o que
  indicaria erro na agregação por partição;
- a taxa de alarme observada no teste ficando próxima de 1%, o que indicaria que o efeito não se
  propaga até o alarme;
- uma fonte climatológica mostrando que o período 2020–2022 não foi anômalo em RS e SC.
