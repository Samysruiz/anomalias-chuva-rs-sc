# Achado 6 — Auditoria do projeto antes da avaliação

**Data:** 17 de novembro de 2026, depois da rodada definitiva do notebook 04 e antes de qualquer
comparação de escore com rótulo. Foram cruzados o repositório, a pasta do Drive (`02_scripts`,
`03_notebooks`, `05_saidas`, `06_dados`, `01_documentacao`), o `decisoes.json`, os registros de
execução dos notebooks 03 e 04 e o Registro do processo KDD.

## O que bate

- O `decisoes.json` do Drive e o do repositório são o mesmo arquivo (v1.2, `d4c58a627755c8f9`).
- O notebook 04 rodou fora do modo demonstração, com a v1.2 (`04_log_execucao.json`, 17/11/2026).
- Partições, janelas e estações batem entre o notebook 04, a demonstração e os arquivos de auditoria:
  2.937.487 / 445.963 / 356.567 janelas; 790 estações elegíveis (461 no RS, 329 em SC); 479 no
  subconjunto Hidroweb.
- Os rótulos batem com o achado 3: 121 episódios, 37 severos (RS 18, SC 19), 24 extensos e 13 locais,
  todos entre 03/01/2023 e 31/12/2025.
- A tabela por critério do controle de qualidade bate com o registro do notebook 03:
  118.016.773 / 118.373.471 = 99,6987%.

## O que precisa de decisão antes do notebook 05

**1. A emenda do limiar não é executável sem um passo a mais.** A emenda proposta em 13/11 pede o
percentil 99 de cada modelo **no treino**. O notebook 04 grava escores só de validação e teste. Para
aplicar a emenda é preciso pontuar as janelas de treino antes da avaliação. O notebook 05 para se a
emenda for marcada como aplicada e o arquivo `p99_treino_por_modelo.parquet` não existir.

Para o nível 1 isso não falta: o pré-registro já define o limiar dele no treino e o notebook 04
gravou esse limiar. A decisão continua sendo do grupo.

**2. O pré-registro tem duas regras de limiar para o nível 1.** `modelos.nivel_1` diz "percentil 99
por estação no treino"; `pontuacao_e_alarme.limiar_estacao` diz "percentil 99 do escore na
validação". O notebook 05 usa a regra específica (treino) como principal para o nível 1 e relata a
outra ao lado. O grupo deve confirmar antes de rodar.

## Inconsistências encontradas

| # | Onde | O que está errado | Correção |
|---|---|---|---|
| 1 | Slides, Dossiê | "385.760 registros (0,33%) sem explicação" | O número certo é 385.796, e a maior parte está explicada (abaixo). Slides corrigidos; **Dossiê a corrigir** |
| 2 | README | "Quatro critérios de refutação" e "execução sobre os dados reais pendente" | Corrigido neste commit: são cinco, e os notebooks 03 e 04 já rodaram |
| 3 | `dados/README.md`, achado 3 | "condições de uso não verificadas" | Verificadas em 13/11 (KDD, seção 2.5): acesso público, sem termos explícitos de licença. Corrigido neste commit |
| 4 | Registro KDD (versão de 13/11) | Seção 6.2 com quatro critérios; seções 3.5 e 8b dizem que a execução nos dados reais está pendente; Quadro 4 sem a exclusão do CEMADEN, a emenda de autoria, a rodada descartada de 13/11 e a rodada de 17/11; sem o achado 5; sem a declaração de uso de IA | **A atualizar no Google Doc** |
| 5 | Registro KDD, seção 2.2 | O texto fala em "cinco redes" e a Tabela 1 lista seis | **A corrigir** (INMET diário e sub-diário são redes distintas no UNIPLU-BR) |
| 6 | Registro KDD, seção 4.2 | "O limiar de decisão será estabelecido exclusivamente sobre o conjunto de validação" | Conflita com o nível 1 no treino (item 2 acima). **A ajustar** quando o grupo confirmar |
| 7 | Logs dos notebooks | O 03 rodou com `decisoes.json` v1.1 e o 04 com v1.2 | Pelo campo `_sobre`, a diferença é só a emenda de autoria. Declarar. O arquivo v1.1 não foi arquivado, então isso não pode ser conferido byte a byte |
| 8 | Drive | `escores_04.parquet` tem data de modificação (18:09 UTC) anterior ao registro do 04 (19:21 UTC) | **Resolvido em 18/11.** A cópia do Felipe guarda o registro da rodada de 13/11/2026 (versão 1 do notebook). As 10 melhores épocas e perdas de validação do autoencoder são idênticas às da rodada de 17/11, e a variância do PCA difere só na 8ª casa (0,90704268 contra 0,90704262): a rodada de 17/11 reproduziu a de 13/11. O notebook 05 continua conferindo as medianas antes de avaliar |

### A diferença entre o arquivo bruto e o processado

| Parcela | Registros |
|---|---|
| Arquivo bruto de RS e SC, 1995–2025 | 118.759.267 |
| Lidos nas 2.127 estações auditadas | 118.431.640 |
| — cópias idênticas descartadas | 58.169 |
| — registros processados | 118.373.471 |
| **Não pertencem a nenhuma das 2.127 estações auditadas** | **327.627 (0,28%)** |

Das 2.132 estações da tabela, 5 não aparecem na auditoria (83879, 83892, 83917, 83994 e 83882,
todas do INMET diário e nenhuma elegível). Os 327.627 registros pertencem a elas (por exemplo, com todas as
leituras fora de 1995–2025) ou a códigos sem entrada na tabela de estações. **Nenhuma das 790 estações elegíveis é
afetada.** Para fechar a conta, rode no Colab:

```python
import pandas as pd
b = pd.read_parquet(ARQ_BRUTO, columns=["gauge_code", "datetime"])
b["gauge_code"] = b["gauge_code"].astype(str)
aud = set(pd.read_csv(os.path.join(PASTA_SAIDA, "03_auditoria_por_estacao.csv"))["gauge_code"].astype(str))
fora = b[~b["gauge_code"].isin(aud)]
print(len(fora)); print(fora.groupby("gauge_code")["datetime"].agg(["size", "min", "max"]))
```

## Lacunas que não bloqueiam, mas entram nas limitações

1. **Limiares espaciais do controle de qualidade não calibrados.** O pré-registro manda calibrar no
   treino; foram usados os valores de partida (raio 50 km, mínimo de 2 vizinhos, 20 mm, razão 0,1,
   10 mm). Isso é um desvio do pré-registro e precisa ser declarado como tal.
2. **Sensor travado no nível diário** ficou em 7 dias, sem a calibração prevista no treino.
3. **Ablação de janela de 7 e 30 dias** pré-registrada e não executada: exige retreinar no notebook 04.
4. **Camada secundária da ANA:** o erro 406 da HidroWebService continua sem solução.
5. **Referências pendentes:** MEIRA et al. (2022) e as demais da seção 9.1 do KDD não foram consultadas.
6. **Instabilidade do autoencoder:** sementes 0 e 1 pararam nas épocas 5 e 6, com perda cerca de 70%
   maior; a ablação de gargalo 3 não convergiu em 150 épocas.
7. **Data da ocorrência e fronteira do dia:** o REInDesC registra a data da ocorrência, e o dia de chuva
   fecha às 12 h UTC (9 h local). A janela de detecção de 3 dias antes do início absorve esse
   descompasso, mas ele precisa ser citado.

## O que refutaria esta auditoria

Se o comando acima mostrar que os 327.627 registros pertencem a alguma das 790 estações elegíveis, a
conclusão "nenhuma estação elegível é afetada" cai e o notebook 03 precisa ser revisto. Se a
conferência de medianas do notebook 05 falhar, o `escores_04.parquet` do Drive não é o da rodada de
17/11 e a avaliação não deve seguir.

## Atualização de 18/11/2026: cópia do Felipe e notebook 04 versão 3

A pasta do Felipe é uma cópia de 16/11 da pasta do projeto, reorganizada (testes em `04_testes/testes` e
`04_testes/auxiliares`, gerador do notebook 03 em `02_scripts/_ferramentas`, LEIA-ME novo). O pré-registro
é o mesmo (`d4c58a627755c8f9`). O notebook 04 dele difere do oficial em duas coisas, ambas incorporadas na
**versão 3**:

1. a célula 6b, com a mediana anual da chuva acumulada no Hidroweb (o diagnóstico do achado 05);
2. no modo de demonstração, as saídas vão para subpastas `_demo` de `05_saidas`, `06_dados` e `_modelos_04`.

A rodada real da versão 3 é idêntica à da versão 2: o código das células é o mesmo do Felipe, exceto o
número da versão no registro. O teste sintético do notebook 04 passou nos dois modos, incluindo a
verificação de que a demonstração não grava nada nas pastas definitivas.

**Reprodutibilidade:** o registro de 13/11 na cópia do Felipe e o de 17/11 na pasta oficial têm as mesmas
melhores épocas e perdas de validação nos 10 treinos do autoencoder. Duas execuções separadas por quatro
dias deram o mesmo resultado.
