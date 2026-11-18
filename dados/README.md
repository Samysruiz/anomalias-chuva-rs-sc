# Dados

**Nenhum dado bruto está neste repositório.** O arquivo de treinamento tem centenas de megabytes e
as ocorrências de avaliação não têm termos explícitos de licença. O `.gitignore` bloqueia os dois.

## Chuva, para treinamento: UNIPLU-BR

- Fonte: LEMOS, F. C. et al. *Unified Brazilian Rainfall Dataset (UNIPLU-BR)*. Zenodo, 2026.
  DOI 10.5281/zenodo.18883358.
- Licença: CC BY 4.0.
- O repositório do Zenodo disponibiliza **um único arquivo compactado**, não os arquivos por estado
  e ano separadamente. Tentar baixar `UF_ANO.zip` direto devolve HTTP 404. O caminho correto é
  consultar a interface programática do Zenodo, baixar o arquivo único e extrair só os membros de
  interesse. Cada `UF_ANO.zip` contém `table_info.parquet` (metadados das estações) e
  `table_data.parquet` (série de precipitação), ligados por `gauge_code`.
- Recorte usado: RS e SC, 1995–2025. São 118.759.267 registros de 2.132 estações.
- A coluna do fuso da estação na tabela de metadados chama-se `UTC`, **em maiúsculas**. Código que
  procure `utc` em minúsculas não a encontra.

### Aviso dos autores que motiva todo o pré-processamento

Os autores declaram que o tratamento aplicado foi apenas de padronização estrutural: não houve
avaliação qualitativa, verificação de consistência física nem filtragem de valores extremos. Os
valores estão como reportados pelas agências de origem.

Para um detector de anomalias isso é decisivo. Falha de instrumento e evento extremo são ambos
raros, e um modelo de reconstrução pontua os dois igual. Separar defeito de fenômeno é tarefa do
pré-processamento, não do modelo.

## Eventos, para avaliação: REInDesC

- Fonte: Cemaden, https://reindesc.cemaden.gov.br
- Obtenção: no painel de consulta, filtrar por UF (RS e SC) e período (2023–2025), aplicar os
  filtros e exportar a tabela de ocorrências em CSV. A plataforma também exporta em Excel, KML e
  GeoPackage.
- O arquivo exportado usa `;` como separador e codificação UTF-8. O notebook procura arquivos cujo
  nome comece por `reindesc` na pasta de dados.
- **Condições de uso verificadas em 13/11/2026:** acesso público e gratuito, sem termos explícitos de
  licenciamento na plataforma nem no manual. Por isso as ocorrências exportadas não são redistribuídas aqui. Em `achados/dados/reindesc_agregados.csv` há apenas
  contagens derivadas.

## Nível e vazão dos rios, camada complementar: HidroWebService da ANA

Camada independente de validação, usando cota e vazão, que o UNIPLU-BR não contém. O acesso foi
obtido, mas a rota de inventário devolve HTTP 406 e a documentação pública não especifica os nomes
exatos dos parâmetros obrigatórios. O projeto é executável sem essa camada.

## Referência de controle de qualidade

PINELO, J. *UNIPLU-BR: standardisation, quality control, and database import*. AIR Centre, 2026.
https://github.com/AIRCentre/UNIPLU-BR — licença MIT. Os limites físicos por resolução e vários
critérios de qualidade usados aqui vêm desse trabalho, assim como os relatórios citados nos achados.
