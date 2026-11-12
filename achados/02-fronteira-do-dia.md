# Achado 2 — Onde fechar o dia agregado

**Data:** 12 de novembro de 2026. **Estado:** medido em dois estados e dois anos. **A confirmação
falhou.** O deslocamento pré-registrado de 12 h é mantido. Ver a seção final.

## O método

Para cada par formado por uma estação diária e a estação sub-diária mais próxima a menos de 10 km,
compara-se a série diária do pluviômetro convencional com a série sub-diária do vizinho, agregada
em janelas de 24 horas. Varre-se a hora de fechamento `h` de 0 a 23 e a defasagem de −1 a +1 dia,
e mede-se a correlação média entre as duas séries.

A medição é feita no **carimbo bruto**, sem conversão, de modo que o resultado **independe** da
base de tempo discutida no achado 1.

Dados: `dados/varredura_fechamento_dia_rs2015.csv`. Execução: RS, 2015, 16 pares, mínimo de 150
dias em comum por par.

## O resultado

As 72 combinações colapsam numa curva única e unimodal no eixo contínuo `H = h + 24 × (−defasagem)`:

| H | −24 | −12 | 0 | 8 | 14 | **20** | 26 | 32 | 44 | 47 |
|---|---|---|---|---|---|---|---|---|---|---|
| correlação | 0,023 | 0,078 | 0,351 | 0,536 | 0,679 | **0,722** | 0,670 | 0,541 | 0,162 | 0,101 |

A curva é simétrica em torno do máximo: 0,679 e 0,670 a seis horas de distância de cada lado;
0,536 e 0,541 a doze horas. Essa simetria é a verificação de consistência interna do procedimento,
e ela passa.

## O que o resultado rejeita

A convenção pluviométrica brasileira, que fecha o dia às 7 h locais, nas duas bases possíveis:

| Hipótese | `h` correspondente | Correlação |
|---|---|---|
| Carimbo local, dia fechando às 7 h locais | 7 | 0,513 |
| Carimbo UTC, dia fechando às 7 h locais | 10 | 0,588 |
| Máximo observado | 20 | **0,722** |

Janelas que fecham de manhã são as piores de toda a varredura. A convenção não descreve estas séries.

Também não é artefato de corte de evento. Se fosse, a melhor janela fecharia no horário de menos
chuva, que pelo achado 1 é da madrugada ao começo da manhã. O observado é o contrário.

## O que o resultado fixa

O deslocamento que melhor alinha as redes diária e sub-diária é de 20 horas. O pré-registrado, de
12 horas, está em 0,648.

Com carimbo em UTC, 12 h fecha o dia às 9 h locais e 20 h o fecha às 17 h locais. A segunda opção
retém a madrugada e a manhã do próprio dia civil, que é quando ocorrem as inundações registradas
na data D do REInDesC. Melhora nos dois critérios ao mesmo tempo.

## Procedimento adotado, para não contaminar o pré-registro

Uma medição em um estado e um ano, com 16 pares, não sustenta alteração de parâmetro pré-registrado.
Por isso:

1. o pré-processamento agrega a chuva diária nos **dois** deslocamentos, 12 h e 20 h, na mesma
   passagem de controle de qualidade, que é a etapa computacionalmente custosa;
2. o deslocamento **principal** continua sendo o de 12 h, por ser o do pré-registro;
3. a troca do principal depende da confirmação do máximo em segundo estado e segundo ano, e
   constituirá emenda datada, registrada em `pre-registro/`;
4. o deslocamento não adotado permanece gravado como análise de sensibilidade.

Essa ordem importa: a decisão é de alinhamento de dados, tomada antes de qualquer pontuação de
modelo, e documentada com a medição que a sustenta.

## A confirmação em SC/2020 não reproduziu o ganho

Dados: `dados/varredura_fechamento_dia_sc2020.csv`. Mesmo procedimento, 20 pares.

| | RS/2015 | SC/2020 |
|---|---|---|
| Máximo do grid | H = 20 | H = 18 |
| Correlação no máximo | 0,722 | 0,717 |
| Correlação em h = 12 (pré-registrado) | 0,648 | **0,714** |
| Ganho do máximo sobre o pré-registrado | +0,074 | **+0,003** |
| Correlação em h = 20 | 0,722 | **0,701** |

Os dois máximos caem na faixa de 18 h a 22 h, que era o critério que eu havia fixado de antemão
para justificar a emenda. **Mesmo assim a emenda não se faz**, por um motivo que o critério, escrito
antes de ver o segundo conjunto, não previa: em SC, adotar 20 h produz 0,701, que é **pior** que os
0,714 do valor pré-registrado. Uma regra que, cumprida à risca, piora metade da evidência é uma
regra mal escrita. Fica o registro do erro.

Em SC a curva é quase plana de h = 11 a h = 19, variando entre 0,707 e 0,717. Em RS ela tem
inclinação forte. O ganho medido em RS, portanto, não é propriedade geral da convenção das estações
diárias.

**Hipótese para a diferença, não testada:** o parceiro sub-diário de cada par muda entre os dois
conjuntos. Pelo achado 4, as estações CEMADEN transmitem cerca de 27 leituras por dia, e não as 144
que o passo declarado faz esperar. Se os pares de RS/2015 forem dominados por parceiros CEMADEN com
amostragem esparsa, a curva observada ali pode refletir o regime de transmissão da rede, e não a
fronteira do dia do pluviômetro convencional.

**Decisão:** mantém-se o deslocamento pré-registrado de 12 h. O agregado de 20 h continua gravado e
entra apenas como análise de sensibilidade. Nenhuma emenda é feita. A perda de alinhamento em RS
fica declarada como limitação.

Um valor intermediário, h = 18, é o melhor dos dois conjuntos em conjunto, mas seria escolhido
depois de ver as duas curvas, e exigiria repetir a passagem de controle de qualidade. Não é adotado.
