# Figuras

Contagens de estações por ano e rede. Não contêm dado bruto de chuva nem dado pessoal.

| Arquivo | O que mostra |
|---|---|
| `estacoes_por_ano_rede_todas_e_elegiveis.png` | Painel superior: todas as estações com dia válido. Painel inferior: as 790 estações elegíveis. |
| `estacoes_ativas_por_ano_rede_apos_qc.png` | Estações com pelo menos um dia válido por ano, após o controle de qualidade. |

## Leitura com cuidado

- **As cores não são as mesmas entre os painéis.** No painel superior, o azul é CEMADEN e o laranja é
  Hidroweb diário. No painel inferior, o azul é Hidroweb diário. Leia sempre a legenda de cada painel.
- **A segunda figura mostra o ano de 2026** com uma barra mínima, o que indica um ano incompleto.
  A primeira figura vai só até 2025. Esse ano não entra nas partições (treino 1995–2019,
  validação 2020–2022, teste 2023–2025).
- O painel inferior da primeira figura teve o título refeito para "Somente as 790 estações
  elegíveis". O resto da imagem é o gráfico original do notebook.
- Estas figuras são derivadas das contagens do pré-processamento. Se o notebook for reexecutado,
  elas devem ser regeneradas pelo código, não editadas.
