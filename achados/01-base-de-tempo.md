# Achado 1 — Em que base de tempo estão os carimbos do UNIPLU-BR

**Data:** 12 de novembro de 2026. **Decisão:** tempo universal coordenado (UTC), com ressalva.

## Por que importa

A coluna de carimbo temporal pode estar em UTC ou em hora local. A diferença de três horas desloca
a fronteira de cada dia agregado e, com isso, muda a qual dia é atribuída a chuva de um episódio.
Como o alarme é diário e os rótulos de evento do REInDesC são datas civis locais, um erro aqui
desloca sistematicamente a comparação.

A documentação dos autores não fecha a questão. Ela diz que houve ajuste de fuso, com os carimbos
padronizados com base na localização geográfica da estação. Essa formulação é compatível tanto com
a conversão para UTC quanto com a conversão para hora local.

## Os cinco procedimentos, na ordem em que foram feitos

### 1. Perfil diurno por rede, ponderado por precipitação

Dados: `dados/perfil_diurno_por_rede.csv`. Amostra de até 30 estações por rede, período de
treinamento (2014–2019), só registros com chuva positiva abaixo de 200 mm.

Máximos: 21 h no CEMADEN, 20 h no INMET sub-diário, 20 h na Telemetria, 8 h no ICEA.

**Conclusão:** as três redes principais estão na mesma base de tempo. Isso descarta a hipótese
pior, de bases misturadas entre redes. Não identifica qual é a base.

### 2. Hora do carimbo das estações diárias

Hipótese: um pluviômetro convencional lido às 7 h locais apareceria às 7 h se o carimbo fosse
local, e às 10 h se fosse UTC.

Resultado: Hidroweb diário e INMET diário estão 100% em 00:00. **Inconclusivo**, porque não há
informação horária para discriminar.

Dois subprodutos que valeram o procedimento:

- Os registros diários **não** estariam em 00:00 se um carimbo de meia-noite local tivesse sido
  convertido para UTC; estariam em 03:00. Logo, as séries diárias não sofreram conversão.
- Com qualquer deslocamento entre 1 h e 24 h, a janela de agregação contém o 00:00 do próprio dia,
  de modo que a estação diária conserva a sua data original. A agregação não as distorce.

### 3. Distribuição horária das leituras sub-diárias

Resultado: entre 4,0% e 4,3% em todas as 24 horas, para CEMADEN, INMET sub-diário e Telemetria.

**Procedimento inadequado, registrado como tal.** Essa distribuição mede a cadência de amostragem
do instrumento, que é fixa: um sensor de 10 minutos grava a cada 10 minutos, chova ou não. O
diagnóstico correto é o do procedimento 1, ponderado por milímetros.

### 4. Disponibilidade de observação da rede ICEA

Dados: `dados/icea_disponibilidade_rs2015.csv`. As horas 10 a 13 não constam da saída consultada e
ficam em branco no arquivo; não foram estimadas.

O ICEA não é plano: mínimo de 1,5% a 1,8% entre 1 h e 4 h, máximo de 5,1% a 5,7% entre 9 h e 18 h.
Isso é horário de funcionamento de aeródromo.

- Lido como hora local, descreve operação das 6 h às 19 h, com queda às 20 h. Escala típica.
- Lido como UTC, descreveria um aeródromo aberto das 3 h às 16 h locais. Não existe.

**Aponta para hora local, mas não decide.** O ICEA é a rede pior tratada do conjunto: das 25
estações com resolução temporal indeterminada, 22 ficaram sem classificação, com intervalos modais
misturando 45, 60, 75 e 930 minutos na mesma estação (PINELO, 2026,
`output/qc_reports/indefinido_investigation.md`). É plausível que a conversão de fuso tenha falhado
apenas nessa rede. E o ICEA já está excluído do trabalho pela regra pré-registrada do `time_step`
indeterminado.

### 5. Pareamento entre estação diária e sub-diária vizinha

Ver o achado 2. Rejeita a convenção das 7 h locais nas duas bases possíveis, e fixa a fronteira
ótima do dia, mas não identifica a base.

## Evidência documental

| Fonte | O que diz | Peso |
|---|---|---|
| Zenodo, descrição do UNIPLU-BR | Houve ajuste de fuso com base na localização da estação | Ambíguo |
| `AIRCentre/UNIPLU-BR`, `docs/processing_log.md` | Carimbos já em UTC; nenhuma conversão aplicada na importação | Favorável a UTC |
| `AIRCentre/UNIPLU-BR`, `output/qc_reports/utc_verification.md` | Zona UTC−5 consistente com UTC; UTC−4 ambígua; **UTC−3 inconclusiva** | Parcial |

A ressalva é importante e não está no resumo da fonte: a zona UTC−3, marcada como inconclusiva no
relatório original, reúne 3.325 das estações analisadas e cerca de 5,2 milhões das 5,4 milhões de
observações com chuva do teste. A conclusão geral se apoia na zona UTC−5, com dez estações.

## Decisão e fundamentos

`FUSO_CONFIRMADO = "UTC"`.

1. Os autores do UNIPLU-BR afirmam que os carimbos são ajustados para UTC.
2. O AIR Centre verificou de forma independente e importou sem conversão.
3. Sob UTC, o máximo do perfil diurno (20 h–21 h no carimbo) corresponde a 17 h–18 h locais, que é
   o máximo convectivo de fim de tarde da região. A decisão fica internamente coerente.

## Ressalva declarada

A verificação de terceiro é parcial, com a zona que concentra quase todos os dados marcada como
inconclusiva no relatório original, e o procedimento 4 aponta em sentido contrário. Se a decisão
estiver errada, todos os dias ficam deslocados em três horas. O efeito prático é limitado pela
janela de detecção pré-registrada, de três dias antes do início do evento até o fim, mas a
limitação consta do relatório.

## O que refutaria esta decisão

Qualquer um destes achados futuros:

- uma declaração explícita dos autores do UNIPLU-BR de que a base é local;
- um pluviômetro convencional do conjunto com carimbo em 07:00 em vez de 00:00;
- o pareamento do achado 2 apontando máximo em H ≈ 7 em vez de H ≈ 20, em mais de um estado e ano.
