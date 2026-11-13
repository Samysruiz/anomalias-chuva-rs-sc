# Emenda proposta — 13 de novembro de 2026 — limiar por estação

**Estado: PROPOSTA. Não aplicada ao `decisoes.json`.** A decisão é do grupo.

## Por que ela é legítima neste momento, e deixa de ser depois

O pré-registro só vale se as alterações forem feitas antes de ver o resultado que elas afetariam.
Nesta data:

- nenhum recall foi calculado;
- nenhuma taxa de alarme foi calculada;
- o notebook 05, que faz a avaliação, não existe.

A única execução de modelo que houve foi em modo de demonstração, com dez épocas, e os escores
dela estão marcados como descartáveis. Nenhum número de avaliação de evento existe para ser
olhado.

**A janela fecha no instante em que a primeira avaliação rodar.** Depois disso, qualquer mudança
no limiar é ajuste pós-resultado e um avaliador tem razão em apontar.

## O que a emenda faz

Acrescenta uma **análise de sensibilidade**. Não troca o ponto principal.

| | Antes | Depois |
|---|---|---|
| Limiar principal | P99 do escore na validação | **inalterado** |
| Sensibilidade do percentil | 95 e 99,5 | inalterada |
| Sensibilidade do período | não havia | **P99 calculado sobre o treino de 1995 a 2019** |

## Por que não cria vazamento

O treino já fornece a média e o desvio padrão da normalização por estação. Calcular também o
percentil 99 do escore sobre o treino não dá ao modelo nenhuma informação que ele já não tivesse.
A regra do pré-registro — "o teste não é consultado para nenhuma decisão" — continua intacta, que
é a barreira que importa.

## O motivo

Achado 5. Com a rede fixa no Hidroweb diário, a validação de 2020 a 2022 está 20% abaixo da
mediana do treino e contém o ano mais seco dos 31; o teste está 8% acima. Calibrar a taxa de
alarme num período atípico e aplicá-la a outro produz uma taxa de alarme no teste que não é a
calibrada.

## O bloco a inserir no `decisoes.json`

Em `pontuacao_e_alarme`:

```json
"sensibilidade_periodo_do_limiar": "P99 do escore calculado sobre o treino 1995-2019, alem do P99 na validacao",
"motivo_sensibilidade_periodo": "achado 5: a validacao 2020-2022 esta 20% abaixo da mediana do treino na chuva acumulada de 15 dias, com 2020 sendo o ano mais seco dos 31; calibrar a taxa de alarme nesse periodo e aplica-la ao teste produz taxa observada diferente da calibrada"
```

Em `emendas`:

```json
{
  "data": "2026-11-13",
  "item": "sensibilidade do periodo de calibracao do limiar",
  "detalhe": "acrescentada analise de sensibilidade com o P99 calculado no treino, alem do P99 na validacao pre-registrado, que continua sendo o ponto principal. Motivo no achado 5. Emenda feita antes de qualquer calculo de recall ou de taxa de alarme; o notebook 05 nao existia nesta data."
}
```

E `"versao"` passa de `"1.2"` para `"1.3"`.

## Como aplicar, se o grupo decidir que sim

```
python3 pre-registro/aplicar_emenda_limiar.py
```

O script aplica as três alterações, grava o arquivo e **imprime o novo sha256 de 16 dígitos**.
Esse valor precisa ser acrescentado a `VERSOES_ACEITAS` na célula 2 do notebook 03 e na célula 2
do notebook 04, senão a guarda de hash vai avisar que o pré-registro mudou — que é exatamente o
comportamento desejado dela.

## Obrigatório, qualquer que seja a decisão

Reportar a **taxa de alarme efetivamente observada no teste** ao lado do 1% calibrado. Isso não
depende da emenda e não é opcional.
