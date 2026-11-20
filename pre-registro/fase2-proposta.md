# Fase 2 — proposta de pré-registro (rascunho para aprovação do grupo)

**Situação em 20/11/2026: proposta, não aprovada e não executada.** Na avaliação feita no mesmo dia, a
recomendação foi não executar a fase 2 completa antes da entrega (1 ou 2/12/2026), pelo risco de prazo (erro 406 da
ANA, download grande do ERA5-Land, dezenas de treinos) e por ela só poder produzir resultado exploratório. A
alternativa registrada é uma versão mínima opcional, só com a entrada E1, com data-limite de 26/11/2026, ou a fase 2
completa depois da entrega, com um período de teste ainda não visto. A decisão é do grupo.

**Origem:** rascunho de 20/11/2026, escrito **depois** do resultado da fase 1 (achado 08) e **antes** de qualquer
ajuste ou dado novo. Só vale depois de aprovado pelo grupo, com data, e convertido em `decisoes_fase2.json` com
hash. Nada da fase 1 muda: o resultado pré-registrado continua sendo o do achado 08.

## Pergunta

Dar ao autoencoder informação que a chuva de um ponto não tem (chuva da vizinhança, umidade do solo e nível do
rio) faz com que ele supere o limiar de chuva acumulada na detecção dos episódios severos?

## Natureza

**Exploratória.** O período de teste (2023–2025) já foi visto na fase 1. Para reduzir esse problema, nenhuma
escolha da fase 2 usa os rótulos do teste: o ajuste usa rótulos do REInDesC de 2020–2022 (validação), e o teste é
usado uma única vez, no fim, com todas as configurações já congeladas.

## Escada de entradas

| Entrada | O que o modelo vê por janela de 15 dias | Fonte | Condição para entrar |
|---|---|---|---|
| E0 | chuva diária da estação (como na fase 1) | UNIPLU-BR | sempre |
| E1 | E0 + chuva média das estações elegíveis a até 50 km | UNIPLU-BR | sempre |
| E2 | E1 + umidade do solo diária no ponto da estação | ERA5-Land (Copernicus) | dados baixados até 24/11/2026 |
| E3 | E2 + cota diária da estação fluviométrica mais próxima | HidroWebService (ANA) | erro 406 resolvido até 25/11/2026 |

Cada variável é normalizada por estação com média e desvio do treino, como na fase 1. Uma entrada cuja condição
não for cumprida no prazo é registrada como **não executada**, sem substituto.

## Modelos comparados em cada entrada

Limiar de chuva acumulada (fixo, igual à fase 1, como referência), PCA, autoencoder e Isolation Forest, com as
mesmas cinco sementes.

## Ajuste (o "tunar")

- Grade fixa e igual para todas as entradas, para que nenhuma receba mais tentativas que outra:
  gargalo {3, 8, igual ao PCA}; taxa de aprendizado {10⁻³, 3 × 10⁻⁴}; paciência de 30 épocas; até 300 épocas.
- Critério de escolha: PR-AUC diária média nas 5 sementes, na **validação 2020–2022**, com os rótulos do REInDesC
  de 2020–2022 construídos pela mesma regra de episódio da fase 1.
- Checkpoint a cada época e melhor modelo pela perda de validação, como na fase 1.
- Alarme: mesma regra da fase 1 (limiar P99 por estação na validação; f calibrado para 1% e 3% dos dias).

## Critério de sucesso, fixado antes

A informação nova ajudou se, no teste, para alguma entrada E1 a E3:

1. o autoencoder superar o limiar de chuva acumulada em recall a 1% **e** em PR-AUC, nas 5 sementes; **e**
2. superar o autoencoder E0 ajustado nas mesmas duas medidas, nas 5 sementes.

## O que refuta

- Nenhuma entrada cumpre os itens 1 e 2: a informação adicional, nesta forma, não ajudou o autoencoder.
- O ganho aparece também no PCA e no Isolation Forest com a mesma entrada: o ganho é da fonte nova, não da não
  linearidade (deve ser reportado assim).
- O ganho não se reproduz só no Hidroweb diário.

## Reporte

Todas as entradas e configurações, inclusive as que não melhoraram, com a taxa de alarme no teste ao lado da
calibrada, e a marcação de exploratório em toda tabela.
