# Achado 10 — Onde e quando os pluviômetros travam, e se falham nas cheias (exploratório)

**Data:** 21/11/2026 · **Notebook:** `codigo/07_falhas_dos_sensores.ipynb` ·
**Pré-registro:** `pre-registro/decisoes_07_falhas.json` v1.0 (hash `06f4141076313128`), gravado antes da execução.

## Pergunta

Os pluviômetros ficam indisponíveis (sem leitura, com leitura travada ou com o dia descartado pelo
controle de qualidade) com mais frequência justamente durante as cheias severas? Numa estação sem dado
não há janela de 15 dias, e nenhum modelo consegue dar alarme.

## Consistência

O notebook 07 contou 118.373.471 leituras, 278.894 travadas e 43.357 oscilando: os mesmos totais do
notebook 03.

## Onde travam

| Rede | Leituras | Travadas | Oscilando | Estações com alguma |
|---|---:|---:|---:|---|
| Cemaden | 57.973.474 | 277.632 | 42.880 | 404 de 935 |
| Telemetria | 45.670.562 | 471 | 426 | 22 de 527 |
| INMET subdiário | 9.144.185 | 24 | 51 | 3 de 94 |
| ICEA | 1.270.590 | 767 | 0 | 3 de 14 |
| Hidroweb diário | 4.046.109 | 0 | 0 | 0 de 518 |
| INMET diário | 268.551 | 0 | 0 | 0 de 39 |

O Cemaden responde por 99,5% das leituras travadas e 98,9% das oscilando. Entre as 790 estações
elegíveis, só 14 têm alguma leitura marcada (306 travadas, 260 oscilando). No Cemaden, a fração de
estação-dias com travamento passou de 0,07% (2014) para 1,47% (2024). Os meses mais altos foram
outubro de 2023 e maio de 2024, mas janeiro de 2018 e julho de 2019 também; isso é descrição, não teste.

Figuras: `figuras/07_mapa_travamento.png`, `figuras/07_calor_ano_mes.png`.

## Teste pré-registrado (633 estações elegíveis ativas no teste, 37 episódios severos)

| Estatística | Nos episódios | Placebo, mediana | Placebo, P95 | p |
|---|---:|---:|---:|---:|
| Indisponível, qualquer motivo | 26,57% | 20,35% | 23,92% | 0,005 |
| Travado ou oscilando | 0,009% | 0,051% | 0,094% | 0,994 |
| Sem leitura | 20,58% | 16,84% | 20,44% | 0,047 |
| Sem janela de 15 dias completa | 53,57% | 43,00% | 45,97% | 0,001 |

- **Travamento:** refutado para as estações elegíveis (p = 0,994).
- **Indisponibilidade:** pelo critério, há indício (p = 0,005). Mas a série Hidroweb diário do
  UNIPLU-BR termina em 30/09/2025 para todas as 479 estações elegíveis da rede, e ao menos cinco
  episódios severos de outubro a dezembro de 2025 caem nesse trecho, com 74% a 87% das estações sem
  janela completa (`figuras/07_serie_teste.png`). Ali a falta de dado é o fim da base, não falha de
  aparelho. O grupo não aceita a leitura sem a sensibilidade S1.

## Sensibilidades, não pré-registradas (pendentes)

Decididas depois de ver o resultado, na célula 11 do notebook 07:

- **S1:** o mesmo teste só até 30/09/2025.
- **S2:** se as estações do Cemaden travam mais nos episódios severos.

## Efeito na fase 1

Nos episódios de outubro a dezembro de 2025, todos os modelos ficaram quase sem estação para alarmar.
A comparação entre modelos continua válida, mas o recall absoluto de todos fica subestimado.

## Limites

O REInDesC não tem coordenadas: o episódio vale para a UF inteira. O critério de travado
(PINELO, 2026) não foi calibrado e pode marcar chuva constante verdadeira. O UNIPLU-BR não informa
o motivo das falhas.

Dados: `dados/07/`.
