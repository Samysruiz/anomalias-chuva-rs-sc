# Achado 7 — A base de tempo é UTC: confirmação independente com a NOAA

**Data:** 19 de novembro de 2026. Notebook `03b_verificacao_utc_noaa`, executado nos dados reais antes
de qualquer comparação de escore com rótulo.

## Por que a verificação foi feita

Em 12/11/2026 o grupo adotou o tempo universal coordenado (UTC) como base dos carimbos do UNIPLU-BR,
**com ressalva** (achado 01): a verificação de terceiro (PINELO, 2026) era inconclusiva justamente para
o fuso UTC−3, e a rede ICEA apontava para hora local. Um erro nessa decisão deslocaria em três horas a
fronteira de todos os dias agregados.

## A fonte independente

A *Global Historical Climatology Network hourly* (GHCNh), da NOAA, reúne boletins horários e sinóticos
de estações meteorológicas. Os resumos diários da própria NOAA são calculados num dia de 00 a 23 UTC, ou
seja, o relógio dessa base é UTC (NCEI, 2026).

## O critério, fixado antes de olhar os dados

Para cada registro de chuva da NOAA, acumulado em P horas e terminando no instante T, somou-se a chuva
das estações sub-diárias do UNIPLU-BR a até 15 km no intervalo (T − P + L, T + L], com o deslocamento L
de −6 a +6 horas, e mediu-se a correlação.

| Pico da curva | Leitura |
|---|---|
| L = 0 | carimbo em UTC: decisão de 12/11 confirmada |
| L = −3 | carimbo em hora de Brasília: decisão de 12/11 errada |
| outro valor, ou margem menor que 0,05 sobre a correlação a 3 horas do pico | inconclusivo |

Período: 2014–2019, só treino. Redes: Telemetria e INMET subdiário, as redes sub-diárias do estudo.

## Resultado

169 estações da GHCNh na caixa do RS e de SC, todas baixadas. **117 pares** com dados suficientes.

| Deslocamento (h) | −6 | −5 | −4 | −3 | −2 | −1 | **0** | +1 | +2 | +3 | +4 | +5 | +6 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Correlação média | 0,120 | 0,139 | 0,165 | 0,204 | 0,264 | 0,402 | **0,798** | 0,417 | 0,267 | 0,208 | 0,169 | 0,143 | 0,125 |

**Veredito: CONFIRMADO.** O pico está em 0 h, com margem de 0,59 sobre a correlação a 3 horas, contra
0,05 exigido. Em −3 h, onde estaria o pico se o carimbo fosse hora de Brasília, a correlação é 0,204.

| Rede | Pares | Pico em 0 h | Pico em ±1 h | Pico em +2 h | Pico em ±3 h |
|---|---|---|---|---|---|
| INMET subdiário | 72 | 72 | 0 | 0 | 0 |
| Telemetria | 45 | 38 | 6 (4 em +1, 2 em −1) | 1 | 0 |

## Como ler, com os limites

1. **No INMET subdiário, os pares devem ser a mesma estação nas duas bases.** Os identificadores
   `BRN0000Axxx` da GHCNh correspondem, pelo código, às estações automáticas do INMET. Esses 72 pares
   mostram que o UNIPLU-BR guarda o dado no mesmo relógio da NOAA, o que responde à pergunta do fuso,
   mas não são uma comparação entre instrumentos diferentes. A correspondência pelo código é uma
   inferência e não foi conferida estação por estação.
2. **A evidência independente é a Telemetria (ANA):** 38 dos 45 pares com pico em 0 h e nenhum em ±3 h.
   Os 7 pares fora de 0 h ficam a 1 ou 2 horas, o que pode vir de cadência de leitura ou de intervalos
   de acumulação diferentes; a causa não foi investigada.
3. **Duas leituras da documentação da NOAA não foram conferidas diretamente:** que a coluna
   `precipitation` é o acumulado de 1 hora e que o valor do instante T é a chuva do período que termina
   em T. O pico do INMET em 0 h nos 72 pares é coerente com as duas: se alguma estivesse errada, o pico
   se deslocaria de 1 hora em todos eles. A conferência na documentação continua pendente.
4. **Alcance:** vale para as duas redes sub-diárias do estudo, em 2014–2019. As estações diárias são
   carimbadas à 0 h e não respondem à pergunta. CEMADEN e ICEA, já excluídas, não foram testadas.

## O que muda no projeto

- A decisão de 12/11 (UTC) fica confirmada por fonte independente. **Nenhuma emenda é necessária**, e
  os notebooks 03, 04 e 05 não mudam.
- A ressalva "verificação de terceiro parcial" sai das limitações. Entra no lugar a limitação do item 1:
  para o INMET, a confirmação é de relógio, não de instrumento.

## O que refutaria este achado

Uma documentação da NOAA mostrando que o valor do instante T se refere ao período que **começa** em T,
ou que `precipitation` não é horária, deslocaria a leitura do pico. Nesse caso o notebook precisa ser
corrigido e rodado de novo, e o veredito pode mudar.

## Arquivos

No Drive, em `05_saidas`: `03b_curvas_por_par.csv`, `03b_log_execucao.json` e
`03b_verificacao_utc_noaa.png`. Os 169 arquivos da NOAA ficam em `06_dados/noaa_ghcnh/` e não são
redistribuídos aqui.

## Referência

NATIONAL CENTERS FOR ENVIRONMENTAL INFORMATION (NCEI). **Global Historical Climatology Network hourly
(GHCNh)**. Asheville: NOAA. Disponível em:
https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly. Acesso em: 19 nov. 2026.
