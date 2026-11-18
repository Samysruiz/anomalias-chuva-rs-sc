# Proposta de decisão sobre o limiar — para o grupo aprovar antes do notebook 05

**Situação:** PROPOSTA, redigida em 18/11/2026. Só vale depois que o grupo concordar e preencher a data
na célula 2 do notebook 05. Nenhum escore foi comparado com rótulo até aqui.

São duas decisões. Cada uma tem as opções, o que custa, a sugestão e o que faria a sugestão mudar.

---

## Decisão 1 — Aplicar ou não a emenda do limiar no treino

**O problema (achado 05):** o limiar de cada estação e a fração regional **f** são calibrados na
validação (2020–2022), que é o período mais seco dos 31 anos. O teste (2023–2025) é mais chuvoso. Na
rodada de 17/11, a mediana dos escores no teste ficou entre 5% (Isolation Forest) e 61% (autoencoder)
acima da validação. Com isso, a taxa de alarme no teste deve passar de 1%.

| | A. Rejeitar a emenda | B. Aplicar a emenda |
|---|---|---|
| O que muda | Nada no pré-registro, que continua na v1.2 | Pré-registro v1.3, com sensibilidade usando o P99 de cada modelo **no treino** |
| Trabalho extra | Nenhum | Pontuar as janelas de treino de todos os modelos antes do 05: refazer o PCA e o Isolation Forest com a mesma amostra (é determinístico, como mostrou a reprodução de 13/11 e 17/11) e reler os melhores checkpoints do autoencoder. Estimativa: um notebook novo e uma execução de cerca de 30 minutos na GPU, mais o teste. Não verificado |
| O que o relatório mostra | A taxa de alarme observada no teste ao lado da calibrada (obrigatória nos dois casos), os pontos de 1% e 3%, e o **nível 1 com limiar do treino contra limiar da validação**, que o pré-registro já prevê | Tudo o que a opção A mostra, mais a mesma comparação treino × validação para os quatro modelos |
| Risco | A banca perguntar "e se calibrassem no treino?" para os modelos 2 a 4, e a resposta ficar restrita ao nível 1 | Código novo a menos de duas semanas da entrega; mais resultados para interpretar; mais um grau de liberdade para justificar |

**Sugestão: A, rejeitar a emenda.** Três motivos:

1. **O ponto central já está coberto.** A comparação treino × validação existe para o nível 1, porque o
   pré-registro define o limiar dele no treino. Ela mostra, com o modelo mais simples, quanto o período
   de calibração muda o resultado.
2. **A taxa de alarme observada no teste é relatada de qualquer jeito.** É isso que expõe o efeito do
   período seco, para todos os modelos, sem recalibrar nada.
3. **O 3% é um segundo ponto de operação já pré-registrado.** Se a 1% o teto estrutural limitar tudo,
   o 3% mostra o comportamento com folga.

**O que faria a sugestão mudar para B:** se o grupo considerar que a comparação treino × validação só
no nível 1 não basta para defender o trabalho na banca, e houver tempo para o notebook extra (sugestão de prazo: 25/11).
Nesse caso, a emenda precisa ser aplicada **antes** de rodar o 05, nunca depois de ver o resultado.

---

## Decisão 2 — Qual limiar é o principal para o nível 1

O pré-registro tem duas regras: `modelos.nivel_1` diz "percentil 99 por estação **no treino**";
`pontuacao_e_alarme.limiar_estacao` diz "percentil 99 do escore **na validação**".

**Sugestão: o treino é o principal para o nível 1, e a validação sai como sensibilidade.** A regra
específica do nível 1 prevalece sobre a regra geral, e o notebook 05 calcula as duas de qualquer forma.
Isso não exige emenda, só registro.

---

## Como registrar, se o grupo aprovar as duas sugestões

1. Na célula 2 do notebook 05: `DECISAO_EMENDA_LIMIAR = "rejeitada"` e `DATA_DECISAO_GRUPO` com a data
   da aprovação. A versão de sugestão do notebook já traz a primeira linha preenchida e a data vazia.
2. Neste arquivo: trocar a situação para APROVADA e preencher abaixo.
3. O `decisoes.json` continua na v1.2. O script `aplicar_emenda_limiar.py` **não** deve ser rodado.
4. Não apagar `emenda-proposta-2026-11-13-limiar.md`: ele fica como registro de que a emenda foi
   proposta e rejeitada antes da avaliação.

**Aprovado em:** ____/____/2026 — **por:** __________________________________________

---

## O que refutaria esta decisão

Se a taxa de alarme observada no teste ficar muito acima da calibrada (por exemplo, perto de 3% num
ponto calibrado para 1%) e os resultados dos modelos 2 a 4 mudarem de ordem entre o ponto de 1% e o de
3%, a conclusão sobre os modelos depende do período de calibração. Isso entra no relatório como
limitação, **não** como motivo para recalibrar depois.
