# Achado 4 — Primeira execução sobre os dados reais

**Data:** 12 de novembro de 2026. Execução completa do pré-processamento sobre 118.759.267 registros
de 2.132 estações do RS e de SC, 1995–2025. Nenhum modelo treinado.

Dados de apoio: `dados/auditoria_por_criterio.csv` e `dados/auditoria_por_rede.csv`.

## O controle de qualidade na resolução original funcionou

99,70% dos registros passaram limpos. Nenhum valor ausente, nenhum negativo. Os critérios marcaram:

| Critério | Registros | % |
|---|---|---|
| Sensor travado (24 leituras) | 278.894 | 0,236 |
| Oscilação rápida | 43.357 | 0,037 |
| Estação plana | 29.225 | 0,025 |
| Cópias idênticas descartadas | 58.169 | 0,049 |
| Pares de duplicata conflitante | 2.475 | 0,002 |
| Acima do limite físico | 271 | 0,0002 |

No nível diário, 97,47% dos dias ficaram limpos. O critério espacial de zero suspeito marcou 1,98%
dos dias, e o de pico isolado 0,51%. Ambos usam **valores iniciais não calibrados**, e esses
números são o ponto de partida da calibração, não um resultado.

## O problema sério: a rede CEMADEN ficou inteiramente de fora

**Zero das 935 estações CEMADEN são elegíveis.** A causa está na coluna de cobertura:

| Rede | Estações | Elegíveis | Dias com cobertura suficiente |
|---|---|---|---|
| CEMADEN | 935 | **0** | **0,7%** |
| Hidroweb diário | 518 | 479 | 95,1% |
| Telemetria | 527 | 214 | 78,3% |
| INMET sub-diário | 94 | 64 | 88,5% |
| INMET diário | 44 | 33 | 96,2% |
| ICEA | 14 | 4 | 20,5% |

A cobertura é calculada contra o passo **declarado** na tabela de estações. O CEMADEN declara 10
minutos, o que exige 130 das 144 leituras diárias esperadas. A contagem real é outra: 57.973.474
registros em 2.148.008 dias de estação dão cerca de **27 leituras por dia**, ou uma a cada 53
minutos.

A auditoria confirma a origem: **909 das 935 estações CEMADEN têm passo real diferente do
declarado**, contra 19 na Telemetria e nenhuma nas demais.

A explicação provável é o regime de transmissão da rede: as plataformas de coleta do CEMADEN
transmitem a cada 10 minutos durante chuva e com intervalo maior em período seco. O passo declarado
é o intervalo mínimo, não o regular. Para essa rede, o critério de cobertura como implementado não
mede o que pretende medir.

### Três caminhos, com o custo de cada um

**A. Manter como está.** O CEMADEN fica fora, declarado e justificado. O estudo roda com 794
estações, das quais 479 são pluviômetros diários do Hidroweb com histórico de 1995 a 2025. Não
introduz nenhum parâmetro novo e não toca no pré-registro. Custo: perde a rede mais densa, embora
ela só cubra 2014 em diante.

**B. Usar o passo real por estação no denominador.** Parece a correção natural, mas é uma
armadilha: numa rede acionada por chuva, o passo mediano reflete o regime seco, a cobertura passa a
valer aproximadamente 1 em quase todos os dias e o critério deixa de filtrar qualquer coisa.
**Não recomendado.**

**C. Trocar o critério por lacuna máxima dentro do dia** para as redes sub-diárias, exigindo que o
maior intervalo sem leitura seja inferior a um limite. É mais fiel ao propósito do critério, que é
evitar somar um dia parcialmente observado. Custo: parâmetro novo, não pré-registrado, a declarar.

Escolha adotada: **A**, por não exigir parâmetro novo e por manter o pré-registro intacto. A
exclusão do CEMADEN passa a ser decisão declarada, não acidente de implementação.

## A rede ICEA deve sair também

Quatro estações ICEA ficaram elegíveis. Pelo achado 1, o perfil de disponibilidade do ICEA aponta
para horário local, enquanto as demais redes foram tratadas como UTC. Manter quatro estações
possivelmente em outra base de tempo contamina o agregado regional por um ganho desprezível.

Decisão: excluir a rede ICEA inteira, e não apenas as estações com resolução indeterminada.
Declarada como decisão posterior ao pré-registro.

## O deslocamento do dia não se confirmou

Ver o achado 2, seção de confirmação. Resumo: o segundo conjunto não reproduziu o ganho, e o valor
de 20 h chega a ser **pior** que o pré-registrado em SC. O deslocamento de 12 h é mantido.

## O teto de recall foi confirmado nos dados reais

| Ponto de operação | Dias de alarme por ano | Eventos severos por ano | Teto de recall |
|---|---|---|---|
| 1% dos dias | 3,7 | RS 6,0 | 61% |
| 1% dos dias | 3,7 | SC 6,3 | 58% |
| 3% dos dias | 11,0 | RS 6,0 | 100% |
| 3% dos dias | 11,0 | SC 6,3 | 100% |

Confirma o que o achado 3 previu a partir das contagens. Os dois pontos de operação permanecem.

## Partições e contagens finais

| Conjunto | Dias de estação válidos |
|---|---|
| Treino (1995–2019) | 4.199.979 |
| Validação (2020–2022) | 749.935 |
| Teste (2023–2025) | 724.993 |
| Fora das partições | 12 |

Valor extremo pelo critério interquartil, com limiar calculado só no treino: 46.473 dias, 0,82%.
É descritivo e não exclui nada.

## Pendência encontrada no próprio pré-registro

O arquivo `decisoes.json` **não contém** a janela de detecção. O texto do pré-registro fixa três
dias antes do início do evento, e o código caiu no valor padrão com aviso impresso. Texto e arquivo
precisam ser sincronizados, com a alteração registrada como correção de sincronia, não como mudança
de parâmetro.

## O que ainda não foi feito

- Calibração dos limiares espaciais, que hoje usam valores iniciais.
- Verificação das condições de uso do REInDesC.
- Nenhum modelo foi treinado, e nenhuma pontuação existe.
