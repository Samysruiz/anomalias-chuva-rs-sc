# Achado 3 — Como definir um evento a partir do REInDesC

**Data:** 12 de novembro de 2026. **Importante:** os rótulos foram consultados nesta data, antes de
qualquer treinamento, e sem que existisse qualquer pontuação de modelo. A regra foi fixada aqui.

## O problema

O REInDesC registra **ocorrências** individuais, com data única. Não há início nem fim de episódio.
A avaliação em nível de evento, que é a prevista, exige construir episódios a partir das ocorrências.

## O que a exportação contém

Consulta restrita a RS e SC, 2023–2025. Agregados em `dados/reindesc_agregados.csv`. Os 706
registros brutos **não** são redistribuídos aqui, porque as condições de uso da plataforma não
foram verificadas.

- 706 ocorrências: 325 no RS, 381 em SC, de 03/01/2023 a 31/12/2025.
- Todas de tipologia hidrológica. Nenhuma geológica. A escolha de trabalhar só com hidrológico já
  estava dada pelos dados.
- Magnitude: 47 de grande porte (GP), 151 de médio porte (MP), 508 de pequeno porte (PP).
- 228 dias distintos com ocorrência (104 no RS, 124 em SC).

## Primeiro critério, descartado: só grande porte

Produz 6 episódios (RS 4, SC 2). Descartado por dois motivos:

1. **Número insuficiente.** Com 6 eventos, cada erro move o recall em 17 pontos percentuais.
2. **Não é estacionário.** O RS tem 18 ocorrências GP em 2023, 26 em 2024 e 1 em 2025. SC tem 2 em
   2023, 0 em 2024 e 0 em 2025. Um rótulo que desaparece de um estado por dois anos seguidos não
   serve de base para comparar modelos ao longo do período de teste.

## Segundo critério, também descartado: extensão territorial

Episódio com pelo menos 5 municípios distintos produz 32 episódios, número razoável. **Descartado
como critério principal** por um motivo metodológico: o limiar de 5 foi escolhido *depois* de
inspecionar a distribuição das contagens. É escolha pós-hoc, e um avaliador tem razão em apontá-la.

Permanece apenas como **estratificação**, não como filtro.

## Critério adotado: magnitude da fonte

Episódio com pelo menos uma ocorrência classificada pelo Cemaden como GP ou MP.

| Critério | Episódios | RS | SC |
|---|---|---|---|
| Com ocorrência GP | 6 | 4 | 2 |
| **Com ocorrência GP ou MP (principal)** | **37** | **18** | **19** |
| Todos os episódios (secundário) | 121 | 52 | 69 |

A vantagem é que a magnitude vem da fonte, com definição publicada no manual da plataforma, e não
de uma inspeção da distribuição feita por quem vai ser avaliado.

Distribuição dos 37 ao longo do tempo: RS 9/3/6 e SC 6/7/6 em 2023, 2024 e 2025. Mediana de 2 dias
e de 6 municípios. Estratificação: 24 extensos (≥ 5 municípios) e 13 locais.

Sensibilidade ao agrupamento temporal: com intervalo de 1, 2, 3 e 5 dias, o conjunto severo tem 42,
37, 35 e 30 episódios. A contagem não é frágil.

## Regra completa, fixada em 12/11/2026

1. **Episódio:** ocorrências da mesma UF com intervalo de até 2 dias entre dias consecutivos.
2. **Conjunto principal:** episódio com ao menos uma ocorrência GP ou MP. São 37.
3. **Estratificação:** extensos (≥ 5 municípios, 24) e locais (< 5, 13). O alarme é regional, então
   um evento de um município só pode ser indetectável por construção; reportar separado evita
   atribuir ao modelo uma limitação do desenho.
4. **Conjunto secundário:** os 121 episódios, sem filtro de magnitude.
5. **Descritivo apenas:** os 6 episódios com GP, sem estimativa de recall.
6. **Sensibilidade:** intervalo de 1, 2, 3 e 5 dias.
7. **Janela de detecção:** a pré-registrada, de 3 dias antes do início até o fim.

Os parâmetros do item 1 e o limiar de 5 municípios do item 3 **não constam do pré-registro
original** e estão declarados como tais.

## Problema estrutural encontrado no pré-registro

Os 37 episódios severos em 3 anos e 2 estados dão cerca de **6 por estado por ano**. O alarme
regional pré-registrado é limitado a **1% dos dias**, isto é, cerca de 3,7 dias de alarme por ano.

Como cada dia de alarme detecta no máximo um episódio, o recall tem **teto de aproximadamente 61%**,
qualquer que seja o modelo. Um autoencoder perfeito não passa disso nesse ponto de operação.

**Correção, fixada antes de ver qualquer pontuação:** dois pontos de operação, 1% e 3% dos dias. O
segundo equivale a cerca de 11 dias por ano e tem teto próximo de 100% para 6 eventos anuais,
continuando a ser restrição real. Ambos serão reportados, junto com a PR-AUC diária, que não
depende de limiar. A inclusão do segundo ponto é emenda ao pré-registro.

Declarar o teto antes é rigor. Declarar depois seria desculpa.

## A precisão temporal não permite escala sub-diária

Dos 706 registros: 204 sem horário, 303 de baixa precisão, 192 de média, 7 de alta. E o manual da
plataforma define média precisão como podendo ser o **horário de atendimento das equipes de
resgate**, não o da inundação.

O passo diário pré-registrado está correto, e o tempo de antecedência só pode ser medido em dias.

## Vieses do rótulo, a declarar no relatório

O inventário é **por impacto, não por chuva**. Entram apenas ocorrências com dano humano ou com
dano em construções, infraestrutura ou veículos, ou interrupção prolongada de tráfego, em
municípios monitorados pelo Cemaden. Alagamentos rápidos e rasos sem impacto relevante ficam fora,
assim como vendavais e tempestades convectivas.

Daí decorrem três vieses:

1. chuva extrema sem dano não é evento registrado, e conta como falso alarme;
2. dano causado por chuva a montante é evento sem chuva local, e conta como falha de detecção;
3. a cobertura espacial é só dos municípios monitorados.

## Pendência

As condições de uso do REInDesC não foram verificadas. O manual institucional não as apresenta.
Até a verificação, os registros brutos não são redistribuídos neste repositório.
