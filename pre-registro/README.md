# Pré-registro

`decisoes.json` contém os parâmetros fixados **antes** de qualquer treinamento. O notebook de
pré-processamento lê esse arquivo e não aceita nenhum valor digitado por fora: se um parâmetro
registrado mudar, o código quebra em vez de continuar em silêncio.

| Campo | Valor |
|---|---|
| Versão | 1.0 |
| `sha256` (16 primeiros dígitos) | `9e95c5fe56841bf7` |

Confira o hash antes de confiar em qualquer resultado:

```bash
python -c "import hashlib;print(hashlib.sha256(open('decisoes.json','rb').read()).hexdigest()[:16])"
```

## O que está fixado

Partição temporal (treino 1995–2019, validação 2020–2022, teste 2023–2025), passo e fronteira do
dia, cobertura mínima, critérios de controle de qualidade, estações elegíveis, os quatro modelos,
as cinco sementes, a calibração do alarme regional, a definição de detecção, as métricas e os
quatro critérios de refutação.

## Emendas

Toda alteração entra aqui com data, motivo e o que a sustenta. Uma emenda só é legítima se foi
decidida **antes** de qualquer pontuação de modelo existir, e isso precisa estar dito.

### 12/11/2026 — Consulta aos rótulos de evento

Os rótulos do REInDesC para o período de teste (2023–2025, RS e SC) foram exportados e inspecionados
nesta data. Nenhum modelo havia sido treinado e nenhuma pontuação existia. Registrado por
transparência, porque o pré-registro original afirmava que nenhum evento havia sido inspecionado.

### 12/11/2026 — Definição de evento

Fixada a regra descrita em `achados/03-rotulos-reindesc.md`: episódio por agrupamento de até 2 dias
por UF; conjunto principal com ao menos uma ocorrência de grande ou médio porte; estratificação por
extensão territorial. Os parâmetros de agrupamento e o limiar de 5 municípios **não constavam** do
pré-registro original e ficam declarados como posteriores.

### 12/11/2026 — Segundo ponto de operação do alarme regional

Acrescentado o ponto de 3% dos dias ao de 1% já registrado. Motivo: o ponto de 1% permite cerca de
3,7 dias de alarme por ano, contra cerca de 6 eventos severos por estado por ano, o que impõe teto
de recall de aproximadamente 61% independentemente do modelo. O teto está demonstrado em
`achados/03-rotulos-reindesc.md`. Decidido antes da obtenção de qualquer pontuação.

### 12/11/2026 — Base de tempo dos carimbos

Adotado o tempo universal coordenado, com a ressalva descrita em `achados/01-base-de-tempo.md`.
Não altera parâmetro registrado; fixa a interpretação de um campo cuja base a documentação da fonte
não esclarece.

### 12/11/2026 — Fronteira do dia: medição registrada, parâmetro mantido

A medição de `achados/02-fronteira-do-dia.md` indica 20 h como fechamento ótimo, contra as 12 h
pré-registradas. **O parâmetro principal continua sendo 12 h.** A agregação é feita nos dois
deslocamentos na mesma passagem, e a troca depende de confirmação em segundo estado e ano. Se
confirmada, entra aqui como emenda nova, com data.

## Parâmetros usados que o pré-registro não fixa

O notebook imprime a lista completa ao final da execução. São decisões de implementação, e estão
declaradas para que não sejam confundidas com parâmetros registrados: tamanho do lote de leitura,
mínimo de dias válidos para um ano contar no treino, multiplicador do critério interquartil, valores
iniciais não calibrados dos limiares espaciais, nível em que o controle espacial é aplicado,
fração de zeros para estação plana, agrupamento temporal das ocorrências e limiar de extensão
territorial.
