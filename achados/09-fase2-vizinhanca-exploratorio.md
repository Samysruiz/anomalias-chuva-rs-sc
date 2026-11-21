# Achado 09 — Fase 2 (exploratória): a chuva das vizinhas não ajudou o autoencoder

**Execução:** 21/11/2026, notebook `06_fase2_vizinhanca` (versão 1), em GPU no Colab.
**Pré-registros:** `decisoes.json` v1.2 (`d4c58a627755c8f9`) e `decisoes_fase2.json` v1.0 (`c0e7df1aded21cd7`),
este gravado no GitHub em 20/11/2026, antes do código e de qualquer ajuste.
**Natureza:** exploratória. O período de teste já havia sido visto na fase 1. Este achado não altera o resultado
pré-registrado da fase 1 (achado 08).
**Dados de apoio:** `achados/dados/06/`.

## O que foi feito

- **Entradas:** E0, a janela de 15 dias da própria estação; E1, E0 mais a janela da chuva média das estações
  elegíveis a até 50 km, com no mínimo 2 vizinhas com dado no dia.
- **Janelas:** E0 e E1 foram avaliadas no mesmo conjunto, as completas em E1: 500.000 de treino (amostra),
  435.935 de validação e 343.986 de teste.
- **Ajuste:** a mesma grade para as duas entradas (gargalo 3, 8 ou igual ao PCA; taxa de aprendizado 10⁻³ ou
  3 × 10⁻⁴). A escolha foi pela PR-AUC diária na validação 2020–2022, com os rótulos do REInDesC de 2020–2022:
  69 episódios, dos quais 16 severos (RS 4, SC 12). Os rótulos do teste não participaram da escolha.
- **Teste:** usado uma vez, com as configurações congeladas.

## O ajuste

| Entrada | Escolha | PR-AUC na validação | Observação |
|---|---|---|---|
| E0 | gargalo 3, taxa 10⁻³ | 0,203 | a configuração de menor perda (gargalo 13) teve a pior PR-AUC, 0,056 |
| E1 | gargalo 3, taxa 3 × 10⁻⁴ | 0,163 | já na validação, abaixo do melhor E0 |

As duas entradas escolheram o gargalo 3: o autoencoder que menos reconstrói é o que mais detecta. Os gargalos 3 e 8
pararam perto do teto de 300 épocas, e um deles (E1, gargalo 3, taxa 10⁻³) parou no teto.

## Resultado no teste (todas as estações)

| Modelo | Entrada | Recall a 1% | Recall a 3% | PR-AUC | Falsos/ano/UF a 1% | Alarme no teste a 1% |
|---|---|---|---|---|---|---|
| Limiar de chuva acumulada | — | 32,4% | 35,1% | 0,333 | 5,9 | 4,4% |
| Autoencoder ajustado | E0 | 29,7% ± 1,9 | 50,3% ± 2,4 | 0,281 ± 0,016 | 7,8 | 5,2% |
| Autoencoder ajustado | E1 | 31,4% ± 2,4 | 42,7% ± 3,5 | 0,271 ± 0,011 | 8,1 | 5,2% |
| PCA | E0 | 16,2% | 32,4% | 0,242 | 5,7 | 2,9% |
| PCA | E1 | **59,5%** | **70,3%** | **0,358** | 13,0 | **8,7%** |
| Isolation Forest | E0 | 30,3% ± 1,2 | 42,2% ± 3,1 | 0,324 ± 0,008 | 7,0 | 5,2% |
| Isolation Forest | E1 | 30,3% ± 2,3 | 37,8% ± 2,7 | 0,315 ± 0,004 | 5,9 | 4,7% |

Os números do limiar diferem um pouco dos do achado 08 (PR-AUC 0,333 contra 0,323) porque o conjunto de janelas é
outro: só as completas em E1.

Recall a 1% do autoencoder por semente: E0 0,270, 0,297, 0,297, 0,297 e 0,324; E1 0,324, 0,351, 0,297, 0,297 e 0,297.

## Critérios pré-registrados

| Critério | Todas as estações | Só Hidroweb diário |
|---|---|---|
| S1: autoencoder E1 supera o limiar em recall a 1% e em PR-AUC, nas 5 sementes | não | não |
| S2: autoencoder E1 supera o autoencoder E0 nas mesmas medidas, nas 5 sementes | não | não |

**Leitura pré-registrada:** nem S1 nem S2. A chuva das vizinhas, nesta forma, não ajudou o autoencoder. Em PR-AUC,
o autoencoder E1 ficou abaixo do limiar em todas as sementes e abaixo do E0 em quatro das cinco.

## O que apareceu fora dos critérios: o PCA com a vizinhança

O PCA com E1 teve o maior recall de todos (59,5% a 1%, 70,3% a 3%) e a maior PR-AUC (0,358, contra 0,333 do
limiar). Isso **não** estava nos critérios de sucesso, que tratam do autoencoder, e precisa ser lido com três
ressalvas:

1. **Ele alarma muito mais no teste.** Calibrado para 1% dos dias na validação, tocou em 8,7% dos dias do teste,
   o dobro do limiar (4,4%), com 13,0 alarmes falsos por ano por estado, contra 5,9. Boa parte do recall vem daí.
2. **Na medida que independe de limiar, o ganho é pequeno.** PR-AUC de 0,358 contra 0,333 do limiar com todas as
   estações; só com o Hidroweb diário, 0,368 contra 0,364, um empate.
3. **É um único modelo, determinístico, sem sementes, e o teste já tinha sido visto.**

Pela regra de leitura pré-registrada, quando a fonte nova melhora outro modelo, o ganho é atribuído à fonte, e não à
não linearidade. Aqui, a vizinhança melhora o PCA (PR-AUC de 0,242 para 0,358) e não melhora o autoencoder nem o
Isolation Forest. A hipótese que fica para trabalho futuro, **não testada**: um modelo que veja a coerência entre a
chuva da estação e a da vizinhança pode detectar mais, desde que a taxa de alarme no teste seja controlada.

## O ajuste também respondeu ao "tunar"

O autoencoder E0 ajustado (gargalo 3) detectou 29,7% a 1%, contra 21,1% do autoencoder principal da fase 1
(gargalo 13), e ficou próximo da ablação de gargalo 3 da fase 1 (29,2%). Ajustar ajudou, mas não o bastante para
superar o limiar a 1% (32,4%). A 3%, o autoencoder E0 chegou a 50,3%, contra 35,1% do limiar, mas alarmou em 11,4%
dos dias do teste, contra 8,5%.

## Limites

- Só 16 episódios severos na validação (4 no RS): a escolha da configuração tem muito ruído.
- Gargalos 3 e 8 pararam perto do teto de 300 épocas.
- Teste já visto na fase 1: tudo aqui é exploratório.

## O que refutaria esta leitura

Um autoencoder com a vizinhança que superasse o limiar e o E0 nas 5 sementes num período de teste novo; ou, para o
PCA, uma PR-AUC acima do limiar também só no Hidroweb diário e com a taxa de alarme no teste próxima da nominal.
