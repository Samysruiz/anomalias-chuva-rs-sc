"""Gera 03_qualidade_e_preparo.ipynb (celulas escritas como texto)."""
import json

C = []  # (tipo, fonte)


def md(t):
    C.append(("markdown", t.strip("\n")))


def code(t):
    C.append(("code", t.strip("\n")))


md("""
# 03 — Qualidade e preparo dos dados

Projeto final — Aprendizado Não Supervisionado (Wagner). Trabalho do grupo: Felipe Fernandes
Clivati, Juan Carlos Guatierri Alves, Leonardo Secco Silva, Rafael Lazarin Lobo de Almeida,
Samara Ruiz Silva e Victor Hugo Stein Blauth.

**Versão 2, 12/11/2026.** A versão 1 foi escrita de manhã e testada só com dados sintéticos.
Esta versão incorpora os diagnósticos rodados nos dados reais ao longo do dia 12/11 e
registra, abaixo, **todo** o percurso: o que funcionou, o que não funcionou e o que
continua em aberto. Nada foi omitido de propósito.

## O que este notebook faz

1. Lê `decisoes.json` (pré-registro). Nenhum parâmetro registrado é digitado aqui.
2. Roda três diagnósticos de fuso horário e de fronteira do dia, e grava as saídas.
3. Em lotes de estações, na resolução original: remove cópias idênticas, marca duplicatas conflitantes,
   valores negativos, valores acima do limite físico, sensor travado, oscilação rápida e estação plana.
4. Agrega em dias, **com dois deslocamentos ao mesmo tempo** (o pré-registrado e o medido), usando
   só registros limpos e exigindo cobertura mínima.
5. No nível diário: sensor travado (7 dias), coerência espacial entre vizinhas, valor extremo (limiar só do treino).
6. Define as partições, as estações elegíveis e grava as tabelas de auditoria.
7. Monta a tabela de eventos do REInDesC, que o notebook de avaliação vai usar como rótulo.

## O que este notebook NÃO faz

- **Não calibra** os limiares espaciais. Usa os valores iniciais do módulo `qc_uniplu.py`
  e, se você ligar a célula opcional, produz a tabela de sensibilidade **só no treino**, para a calibração.
- Não normaliza nem cria janelas. Isso é do notebook 04.
- Não treina nada e **não olha o conjunto de teste para nenhuma decisão**.

## Regra de vazamento

O conjunto de teste (2023–2025) passa pelo mesmo QC e pela mesma agregação, porque os dados
precisam ser limpos igualmente. Mas nenhum limiar, estatística ou decisão é calculado com ele.
O único uso do teste aqui é a contagem agregada de registros marcados na tabela de auditoria,
o que já está declarado no pré-registro.

Exceção declarada: os **rótulos de evento** do REInDesC de 2023–2025 foram consultados em
12/11/2026, antes de qualquer treinamento e sem que nenhuma pontuação de modelo existisse.
A regra de evento foi fixada nessa data. Isso está na Parte 6 e precisa constar como emenda
datada no pré-registro.

---

# Registro da investigação do fuso horário e da fronteira do dia

A coluna `datetime` pode estar em hora local ou em UTC. Isso muda a fronteira de cada dia e,
com o deslocamento do pré-registro, muda **qual dia recebe a chuva**. Foram cinco tentativas.

### Tentativa 1 — perfil diurno ponderado por chuva, por rede (célula 4)

Resultado em 12/11: picos em 21h (CEMADEN), 20h (INMET subdiário), 20h (Telemetria) e
8h/16h (ICEA). **Conclusão:** as três redes principais estão na **mesma** base de tempo,
o que descarta a hipótese pior, de bases misturadas. O ICEA destoa. Um perfil sozinho
não diz **qual** é a base.

### Tentativa 2 — hora do carimbo das estações diárias (célula 5)

Hipótese: um pluviômetro convencional lido às 07h local apareceria às 07h se o carimbo
fosse local e às 10h se fosse UTC. **Resultado: inconclusivo.** Hidroweb diário e INMET
diário estão 100% em 00:00. Não há hora para discriminar.

Dois subprodutos úteis, e por isso a célula ficou:
- Não estão em 03:00, que é onde apareceriam se um carimbo de meia-noite local tivesse sido
  convertido para UTC. Os registros diários **não sofreram conversão**.
- Com qualquer deslocamento entre 1h e 24h, a janela contém 00:00 do próprio dia, então a
  estação diária **mantém a data original**. A agregação não distorce o Hidroweb.

### Tentativa 3 — contagem de leituras por hora nas redes subdiárias (célula 5)

**Resultado: inútil para fuso, e registrado como tal.** Deu praticamente plano (4,0% a 4,3%
em todas as horas) porque mede a cadência do sensor, não a chuva: um sensor de 10 minutos
grava a cada 10 minutos, chova ou não. O diagnóstico correto é o da tentativa 1, ponderado
por milímetros.

### Tentativa 4 — perfil de operação do ICEA

O ICEA não é plano: mínimo de 1,5% a 1,8% entre 01h e 04h, máximo de 5,1% a 5,7% entre
09h e 18h. Isso é horário de funcionamento de aeródromo. Lido como **local**, descreve uma
escala das 06h às 19h com queda às 20h, que é típica. Lido como UTC, descreveria um
aeródromo aberto das 03h às 16h local, o que não existe.

**Mas o ICEA não decide.** É a rede pior tratada do UNIPLU-BR: dos 25 registros com
`time_step` indefinido, 22 ficaram sem resolução, com intervalos modais misturando 45, 60,
75 e 930 minutos na mesma estação (relatório `indefinido_investigation.md` do repositório
`AIRCentre/UNIPLU-BR`). É plausível que a conversão de fuso tenha falhado só nela. E o ICEA
já está **excluído** deste trabalho pela regra pré-registrada do `time_step` indefinido.

### Tentativa 5 — pareamento estação diária × estação subdiária vizinha (célula 6)

A que funcionou. Para cada par de estações a menos de 10 km, varre a hora de fechamento h
de 0 a 23 e a defasagem de −1, 0 e +1 dia, e mede a correlação entre a série diária e a
subdiária agregada naquela janela.

Resultado em RS/2015, 16 pares: as 72 células colapsam numa **única curva unimodal e
simétrica**, com máximo bem definido em **H = 20** (0,722) e simetria em torno dele
(0,679 e 0,670 a seis horas de distância; 0,536 e 0,541 a doze horas).

O que isso **rejeita**: a convenção das 07h local, nas duas bases possíveis. Ela daria
h = 7 (0,513) se o carimbo fosse local e h = 10 (0,588) se fosse UTC. São das piores
posições do grid inteiro.

O que isso **fixa**: a janela que melhor alinha as redes diária e subdiária fecha às 20h
do carimbo. Isso é medido no carimbo bruto e **independe do fuso**.

O que isso **não resolve**: qual é a base. Nem 20h local nem 17h local (20h UTC) correspondem
a uma convenção pluviométrica documentada.

### Evidência documental

- **Zenodo (UNIPLU-BR, DOI 10.5281/zenodo.18883358):** diz que houve "Time Zone Adjustment"
  com os carimbos padronizados com base na localização geográfica da estação. Redação
  ambígua. Licença CC BY 4.0. A coluna `UTC` da tabela de estações é o fuso da estação,
  não a base do carimbo.
- **Repositório `AIRCentre/UNIPLU-BR`:** afirma que os carimbos já estão em UTC e importou
  os dados **sem conversão**. Mas o relatório próprio deles, `utc_verification.md`, testa o
  ciclo diurno por zona de fuso e marca a zona UTC−3 como **inconclusiva** — e essa zona
  concentra 3.325 das 3.440 estações e 5,2 milhões das 5,4 milhões de observações chuvosas
  do teste. A conclusão geral deles se apoia nas 10 estações da zona UTC−5.

### Decisão tomada em 12/11/2026

`FUSO_CONFIRMADO = "UTC"`, por três fundamentos: a afirmação dos autores do UNIPLU-BR, a
verificação independente do AIR Centre e o carregamento sem conversão na base de produção deles.

**Ressalva que precisa constar no relatório:** a verificação do AIR Centre é parcial, com a
zona que concentra quase todos os dados marcada como inconclusiva no relatório original, e o
perfil do ICEA aponta em sentido contrário. Se o fuso estiver errado, todo dia fica deslocado
em 3 horas. O efeito prático é limitado pela janela de detecção pré-registrada, que vai de
3 dias antes do início do evento até o fim, mas a limitação fica declarada.

Com a decisão de UTC, o pico da tentativa 1 (20h–21h no carimbo) vira 17h–18h local, que é o
máximo convectivo de fim de tarde. Fecha com a climatologia da região.

### Em aberto: o deslocamento do dia

O pré-registro fixa deslocamento de 12 h, que com carimbo UTC fecha o dia às 09h local.
A medição da tentativa 5 aponta 20 h, que fecha às 17h local, com correlação 0,722 contra
0,648 dos 12 h.

Este notebook **não decide sozinho**. Ele agrega nos **dois** deslocamentos na mesma passagem
cara de QC, usa o pré-registrado (12 h) como principal e deixa o outro gravado para a análise
de sensibilidade. A troca só vale como **emenda datada** se a célula 6 confirmar o ótimo em
um segundo estado e ano (SC/2020), o que ela faz automaticamente.

---

# Registro da investigação dos rótulos de evento (REInDesC)

Consultado em 12/11/2026, antes de qualquer treinamento.

- Exportação de RS e SC, 2023–2025: **706 ocorrências**, todas de tipologia hidrológica,
  nenhuma geológica. RS 325, SC 381.
- Magnitude, pelos critérios publicados do Cemaden: PP 508, MP 151, GP 47.
- **Critério GP sozinho foi rejeitado:** só 6 episódios, e não estacionário. O RS teve 18
  ocorrências GP em 2023, 26 em 2024 e 1 em 2025; SC teve 2 em 2023, 0 em 2024 e 0 em 2025.
  Seis eventos dariam recall com 17 pontos de incerteza por acerto.
- **Critério adotado: episódio com pelo menos uma ocorrência GP ou MP.** São 37 episódios
  (RS 18, SC 19), distribuídos 9/3/6 e 6/7/6 pelos três anos. Mediana de 2 dias e 6 municípios.
- O limiar de "5 municípios" que eu tinha cogitado foi **descartado** por ter sido escolhido
  depois de ver a distribuição. A magnitude vem da fonte, com definição publicada, e não
  sofre dessa crítica. Os 5 municípios voltam só como **estratificação** (24 extensos, 13 locais).
- **Problema estrutural encontrado no pré-registro:** 37 episódios em 3 anos e 2 estados dão
  cerca de 6 por estado por ano. O alarme regional pré-registrado é limitado a 1% dos dias,
  cerca de 3,7 dias por ano. Como cada dia de alarme detecta no máximo um episódio, o recall
  tem teto de aproximadamente 61% **qualquer que seja o modelo**. Por isso foram fixados
  **dois pontos de operação**, 1% e 3%, antes de ver qualquer pontuação.
- **Precisão temporal inutilizável:** dos 706 registros, 204 sem horário e 303 de baixa
  precisão; apenas 7 de alta. E o manual define média precisão como podendo ser o horário de
  atendimento das equipes de resgate. O passo diário pré-registrado está certo, e o lead time
  só pode ser medido em dias.
- **Vieses a declarar:** o inventário é por impacto, não por chuva. Entram apenas ocorrências
  com dano humano ou material relevante, em municípios monitorados pelo Cemaden. Logo: chuva
  extrema sem dano não é evento; dano causado por chuva a montante é evento sem chuva local;
  e a cobertura espacial é só dos municípios monitorados.
- **Pendente:** a licença de uso do REInDesC não foi verificada. O manual institucional não a
  traz. Está no painel "Sobre o REInDesC" do portal.

---

# Outros achados registrados

- **Armadilha do pandas 3:** `resample("1D", offset=...)` ignora o deslocamento **em silêncio**,
  porque "1D" virou período de calendário. A célula 2 converte o passo para horas (`FREQ_DIA`)
  e trava com `assert` se o passo não for um número inteiro de horas.
- **A coluna do fuso na tabela de estações chama `UTC`, maiúscula.** A célula 3 normaliza
  todos os nomes para minúsculas antes de usar; código avulso que procure `utc` direto falha.
- O arquivo bruto tem 118.759.267 registros e 2.132 estações em RS e SC, de 1995 a 2025.

## Tempo e memória

Não medi o tempo nos dados reais. A leitura é feita em lotes (por número de linhas), com
checkpoint por lote: se o Colab desconectar, execute de novo e ele retoma do último lote concluído.
Os diagnósticos das células 5 e 6 leem um zip de um ano por vez e são rápidos.
""")

code(r'''
# 1. Configuração, Drive e localização dos arquivos
import os, sys, json, time, gc, glob, hashlib, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore", category=FutureWarning)

RAIZ_TESTE = os.environ.get("NB03_RAIZ_TESTE")  # usado só nos testes locais
if RAIZ_TESTE:
    CANDIDATOS = [RAIZ_TESTE]
else:
    from google.colab import drive
    drive.mount("/content/drive")
    # A pasta do projeto existe em mais de um lugar (a do Colab guarda os dados,
    # a oficial guarda scripts e documentos). Procura cada arquivo nos dois.
    CANDIDATOS = [
        "/content/drive/MyDrive/NÃOSUPERVISIONADO/PROJETO FINAL WAG",
        "/content/drive/MyDrive/NÃO SUPERVISIONADO/PROJETO FINAL WAG",
        "/content/drive/MyDrive/PROJETO FINAL WAG",
    ]

def achar(relativo, obrigatorio=True):
    for base in CANDIDATOS:
        p = os.path.join(base, relativo)
        if os.path.exists(p):
            return p
    if obrigatorio:
        raise SystemExit(f"Não encontrei '{relativo}' em nenhuma destas pastas:\n  " + "\n  ".join(CANDIDATOS))
    return None

ARQ_BRUTO = achar("06_dados/chuva_rs_sc_bruto.parquet")
ARQ_ESTACOES = achar("06_dados/estacoes_rs_sc.parquet")
ARQ_QC = achar("02_scripts/qc_uniplu.py")
ARQ_DECISOES = achar("02_scripts/decisoes.json")

RAIZ_DADOS = os.path.dirname(os.path.dirname(ARQ_BRUTO))
PASTA_DADOS = os.path.join(RAIZ_DADOS, "06_dados")
PASTA_SAIDA = os.path.join(RAIZ_DADOS, "05_saidas")
PASTA_LOTES = os.path.join(PASTA_DADOS, "_lotes_03")
for p in (PASTA_SAIDA, PASTA_LOTES):
    os.makedirs(p, exist_ok=True)

sys.path.insert(0, os.path.dirname(ARQ_QC))
import qc_uniplu as ql

print("bruto    :", ARQ_BRUTO)
print("estações :", ARQ_ESTACOES)
print("módulo QC:", ARQ_QC)
print("decisões :", ARQ_DECISOES)
print("saídas em:", PASTA_DADOS, "e", PASTA_SAIDA)
''')

code(r'''
# 2. Ler o pré-registro e declarar o que NÃO está nele
with open(ARQ_DECISOES, "rb") as f:
    _bytes = f.read()
DEC = json.loads(_bytes)
HASH_DECISOES = hashlib.sha256(_bytes).hexdigest()[:16]

# Versões aceitas e os seus hashes. Se o arquivo mudar sem passar por aqui, o notebook para.
# 1.0 = pré-registro original, congelado em decisoes_v1.0_original.json.
# 1.1 = emendas de 12/11/2026, todas anteriores a qualquer treinamento (bloco "emendas" do arquivo).
VERSOES_ACEITAS = {"1.0": "9e95c5fe56841bf7", "1.1": "ecb0a097f983665c", "1.2": "d4c58a627755c8f9"}
assert DEC["versao"] in VERSOES_ACEITAS, (
    f"versão {DEC['versao']} do decisoes.json não reconhecida; registre a emenda antes de seguir")
if HASH_DECISOES != VERSOES_ACEITAS[DEC["versao"]]:
    print(f"ATENÇÃO: o hash do decisoes.json ({HASH_DECISOES}) não bate com o registrado para a "
          f"versão {DEC['versao']} ({VERSOES_ACEITAS[DEC['versao']]}). O arquivo foi editado sem "
          f"registrar a emenda. Confira antes de usar qualquer resultado.")
for _e in DEC.get("emendas", []):
    print(f"  emenda {_e['data']}: {_e['item']}")
UFS = DEC["dados"]["ufs"]
ANO_I, ANO_F = DEC["dados"]["ano_inicial"], DEC["dados"]["ano_final"]
PASSO = DEC["resolucao"]["passo"]
OFFSET = DEC["resolucao"]["deslocamento_fechamento_dia"]
FECHADO = DEC["resolucao"]["intervalo_fechado"]
COB_MIN = DEC["resolucao"]["cobertura_minima"]
MIN_REP_DIAS = DEC["qc"]["min_repeticoes_travado_dias"]
TREINO = tuple(pd.Timestamp(x) for x in DEC["particao"]["treino"])
VALID = tuple(pd.Timestamp(x) for x in DEC["particao"]["validacao"])
TESTE = tuple(pd.Timestamp(x) for x in DEC["particao"]["teste"])
ANOS_MIN_TREINO = DEC["estacoes"]["anos_minimos_no_treino"]

# "1D" é um período de calendário nas versões novas do pandas, e nele o deslocamento (offset) é
# ignorado em silêncio. Convertido para horas, o intervalo passa a ser de duração fixa e o offset vale.
_h = pd.Timedelta(PASSO) / pd.Timedelta(hours=1)
assert _h == int(_h), "o passo do pré-registro precisa ser um número inteiro de horas"
FREQ_DIA = f"{int(_h)}h"

# --- Parâmetros usados aqui que o pré-registro NÃO fixa. Entram na lista final. ---
MAX_LINHAS_LOTE = int(os.environ.get("NB03_MAX_LINHAS", 6_000_000))   # só logística de memória
DIAS_VALIDOS_MIN_POR_ANO = 183       # um ano "conta" para as 3 do treino se tiver >= 183 dias válidos
K_IQR = ql.K_IQR                      # 3,0, da fonte (PINELO, 2026)
ESPACIAIS_INICIAIS = dict(raio_km=50.0, minimo_vizinhos=2, limiar_mm=20.0,
                          razao_maxima=0.10, limiar_vizinhos_mm=10.0)  # valores iniciais, NÃO calibrados
NAO_PREREGISTRADOS = {
    "MAX_LINHAS_LOTE": MAX_LINHAS_LOTE,
    "DIAS_VALIDOS_MIN_POR_ANO": DIAS_VALIDOS_MIN_POR_ANO,
    "K_IQR (fonte: PINELO, 2026)": K_IQR,
    "ESPACIAIS_INICIAIS (a calibrar no treino)": ESPACIAIS_INICIAIS,
    "limite_fisico por resolução e 24 repetições no nível original (fonte: PINELO, 2026)": "qc_uniplu.py v2.1",
    "QC espacial aplicado no nível DIÁRIO (não no original)": "decisão de implementação",
    "fração de zeros 0,99 para estação plana, no nível original (fonte: PINELO, 2026)": ql.FRACAO_ZEROS_PLANA,
    "FUSO_CONFIRMADO (célula 7, decisão de 12/11/2026, com ressalva declarada)": "ver célula 7",
    "deslocamento alternativo agregado além do pré-registrado (célula 8)": "20 h, medido na célula 6",
    "GAP_EPISODIO_DIAS do REInDesC (célula 19)": 2,
    "MIN_MUNICIPIOS_EXTENSO do REInDesC (célula 19, só estratifica)": 5,
    "segundo ponto de operação do alarme regional (3% dos dias)": "emenda de 12/11/2026",
}
print("decisoes.json versão", DEC["versao"], "| sha256", HASH_DECISOES)
print("UFs", UFS, "| anos", ANO_I, "a", ANO_F, "| passo", PASSO, f"(usado como {FREQ_DIA})", "| offset", OFFSET, "| fechado", FECHADO)
print("treino", [str(x.date()) for x in TREINO], "| validação", [str(x.date()) for x in VALID],
      "| teste", [str(x.date()) for x in TESTE])
''')

md("""
## Parte 1 — Estações, fuso horário e fronteira do dia

As células 4, 5 e 6 são as tentativas 1, 2+3 e 5 descritas no registro do cabeçalho. Elas ficam
no notebook mesmo quando o resultado foi inconclusivo, porque a auditoria do trabalho precisa
mostrar o que foi tentado, não só o que deu certo. Rode todas e guarde as saídas: elas vão para
o anexo do relatório.

A decisão de fuso já está tomada (célula 7). A do deslocamento depende da célula 6.
""")

code(r'''
# 3. Estações: filtros e tabelas de contagem
info = pd.read_parquet(ARQ_ESTACOES)
info.columns = [c.lower() for c in info.columns]
info = info.drop_duplicates("gauge_code").reset_index(drop=True)
info["passo_min"] = info["time_step"].map(ql.passo_minutos)

col_utc = "utc" if "utc" in info.columns else None
print("estações na tabela:", len(info), "| UFs:", info["state"].value_counts().to_dict())

print("\nrede × passo declarado (min):")
print(pd.crosstab(info["network"], info["time_step"].astype(str)))
if col_utc:
    print("\nrede × coluna utc da tabela de estações:")
    print(pd.crosstab(info["network"], info[col_utc].astype(str)))

n_indef = int(info["passo_min"].isna().sum())
print(f"\nestações com time_step indefinido: {n_indef} (excluídas, conforme decisoes.json)")
if DEC["dados"]["excluir_time_step_indefinido"]:
    info_uso = info[info["passo_min"].notna() & info["state"].isin(UFS)].reset_index(drop=True)
else:
    info_uso = info[info["state"].isin(UFS)].reset_index(drop=True)
print("estações em uso:", len(info_uso))
''')

code(r'''
# 4. Diagnóstico do fuso: em que hora do carimbo a chuva se concentra, por rede?
# Usa uma amostra de estações sub-horárias e o período do TREINO (2014–2019), nunca o teste.
import pyarrow.parquet as pq

sub = info_uso[info_uso["passo_min"] <= 60]
rng = np.random.default_rng(0)
amostra = []
for rede, g in sub.groupby("network"):
    cods = g["gauge_code"].to_numpy()
    amostra += list(rng.choice(cods, size=min(30, len(cods)), replace=False))

d = pd.read_parquet(ARQ_BRUTO, columns=["gauge_code", "datetime", "rain_mm"],
                    filters=[("gauge_code", "in", amostra)])
d["datetime"] = pd.to_datetime(d["datetime"])
d = d[(d["datetime"] >= pd.Timestamp("2014-01-01")) & (d["datetime"] <= TREINO[1]) & (d["rain_mm"] > 0)
      & (d["rain_mm"] < 200)]
d = d.merge(sub[["gauge_code", "network"]], on="gauge_code")
d["hora"] = d["datetime"].dt.hour

perfil = (d.groupby(["network", "hora"])["rain_mm"].sum().unstack(fill_value=0))
perfil = (perfil.div(perfil.sum(axis=1), axis=0) * 100).round(1)
print("Participação (%) de cada hora do carimbo na chuva total, por rede:\n")
print(perfil.to_string())
print("\nHora do pico por rede:", perfil.idxmax(axis=1).to_dict())
print("\nComo ler: redes que gravam na mesma base de tempo devem ter picos próximos.")
print("Uma diferença de cerca de 3 horas entre redes sugere bases diferentes (local e UTC).")
print("Um perfil sozinho não diz qual é qual. MANDE ESTA SAÍDA AO CLAUDE ANTES DE PREENCHER A CÉLULA 5.")
del d; gc.collect()
''')

code(r'''
# 5. Diagnóstico B — hora do carimbo por rede, num zip de um ano (tentativas 2 e 3 do registro).
# Mantido no notebook mesmo sendo inconclusivo para o fuso: a auditoria precisa do que foi tentado.
import zipfile, io

PASTA_ZIPS = os.path.join(PASTA_DADOS, "uniplu_rs_sc")

def ler_zip_ano(uf, ano):
    """Lê um zip UF_ANO do UNIPLU-BR e devolve (tabela de estações, tabela de dados)."""
    alvo = os.path.join(PASTA_ZIPS, f"{uf}_{ano}.zip")
    if not os.path.exists(alvo):
        disp = sorted(os.path.basename(z) for z in glob.glob(os.path.join(PASTA_ZIPS, f"{uf}_*.zip")))
        raise FileNotFoundError(f"não achei {uf}_{ano}.zip em {PASTA_ZIPS}. Disponíveis: {disp[:12]}")
    with zipfile.ZipFile(alvo) as z:
        ni = [n for n in z.namelist() if n.endswith("table_info.parquet")][0]
        nd = [n for n in z.namelist() if n.endswith("table_data.parquet")][0]
        i = pd.read_parquet(io.BytesIO(z.read(ni)))
        d = pd.read_parquet(io.BytesIO(z.read(nd)))
    i.columns = [c.lower() for c in i.columns]   # a coluna do fuso vem como "UTC", maiúscula
    d["datetime"] = pd.to_datetime(d["datetime"])
    return i.drop_duplicates("gauge_code"), d

def diagnostico_b(uf, ano):
    inf1, dad1 = ler_zip_ano(uf, ano)
    m = dad1.merge(inf1[["gauge_code", "network", "time_step"]], on="gauge_code", how="left")
    print(f"{uf}_{ano}: {len(m):,} leituras\n")
    print("passo declarado por rede:")
    print(pd.crosstab(m["network"], m["time_step"]).to_string())
    if "utc" in inf1.columns:
        print("\nrede × coluna UTC da tabela de estações (fuso da estação, não base do carimbo):")
        print(pd.crosstab(inf1["network"], inf1["utc"].astype(str)).to_string())
    print("\nhora do carimbo por rede (% das LEITURAS, não da chuva):")
    print((pd.crosstab(m["network"], m["datetime"].dt.hour, normalize="index") * 100).round(1).to_string())
    del dad1, m; gc.collect()

UF_DIAG, ANO_DIAG = "RS", "2015"
try:
    diagnostico_b(UF_DIAG, ANO_DIAG)
    DIAG_ZIPS_OK = True
except FileNotFoundError as e:
    DIAG_ZIPS_OK = False
    print("DIAGNÓSTICO B NÃO RODOU:", e)
    print("Os zips por ano do UNIPLU-BR precisam estar em 06_dados/uniplu_rs_sc/.")

print("""
Como ler (ver o registro no cabeçalho):
 - redes diárias em 100% na hora 00 -> sem informação horária, não discriminam o fuso; e não
   sofreram conversão, pois estariam em 03:00 se tivessem ido de local para UTC;
 - redes subdiárias praticamente planas -> isto mede a cadência do sensor, não a chuva;
 - ICEA não plano -> é horário de operação de aeródromo e aponta para horário local, mas o
   ICEA está excluído pela regra pré-registrada do time_step indefinido.""")
''')

code(r'''
# 6. Diagnóstico C — pareamento estação diária × subdiária vizinha (tentativa 5 do registro).
# É o teste que decide o DESLOCAMENTO do dia. Roda em dois estados e dois anos para ver se o
# ótimo é estável. Mede no carimbo bruto, portanto independe do fuso.
RAIO_PAR_KM = 10.0
MAX_PARES = 20
MIN_DIAS_PAR = 150
CONJUNTOS_DIAG = [("RS", "2015"), ("SC", "2020")]
REDES_DIARIAS = ["Hidroweb diário", "INMET diário"]
REDES_SUBDIARIAS = ["CEMADEN", "Telemetria", "INMET subdiário"]

def varrer_fechamento(uf, ano):
    inf, dad = ler_zip_ano(uf, ano)
    inf = inf.set_index("gauge_code")
    dia_est = inf[inf["network"].isin(REDES_DIARIAS)]
    sub_est = inf[inf["network"].isin(REDES_SUBDIARIAS)]
    pares = []
    for gd, rd in dia_est.iterrows():
        dx = (sub_est["long"] - rd["long"]) * 111.32 * np.cos(np.radians(rd["lat"]))
        dy = (sub_est["lat"] - rd["lat"]) * 110.57
        dist = np.sqrt(dx ** 2 + dy ** 2)
        if len(dist) and dist.min() <= RAIO_PAR_KM:
            pares.append((gd, dist.idxmin(), float(dist.min())))
    pares = sorted(pares, key=lambda p: p[2])[:MAX_PARES]
    usados = {p[0] for p in pares} | {p[1] for p in pares}
    serie = {g: s.set_index("datetime")["rain_mm"].sort_index()
             for g, s in dad[dad["gauge_code"].isin(usados)].groupby("gauge_code")}
    linhas = []
    for h in range(24):
        acc = {-1: [], 0: [], 1: []}
        for gd, gs, _ in pares:
            if gd not in serie or gs not in serie:
                continue
            a = serie[gd]
            a = a.groupby(a.index.normalize()).sum()
            b = serie[gs].resample("24h", offset=f"{h}h", closed="right", label="right").sum()
            b.index = b.index.normalize()
            for lag in (-1, 0, 1):
                c = b.copy()
                c.index = c.index + pd.Timedelta(days=lag)
                j = pd.concat([a.rename("d"), c.rename("s")], axis=1, join="inner").dropna()
                if len(j) >= MIN_DIAS_PAR and j["d"].std() > 0 and j["s"].std() > 0:
                    acc[lag].append(j["d"].corr(j["s"]))
        for lag in (-1, 0, 1):
            if acc[lag]:
                linhas.append({"uf": uf, "ano": ano, "h": h, "defasagem": lag, "H": h + 24 * (-lag),
                               "corr": float(np.mean(acc[lag])), "pares": len(acc[lag])})
    del dad, serie; gc.collect()
    return pd.DataFrame(linhas), len(pares)

partes = []
for uf, ano in CONJUNTOS_DIAG:
    try:
        r, npares = varrer_fechamento(uf, ano)
    except FileNotFoundError as e:
        print(f"DIAGNÓSTICO C não rodou para {uf}/{ano}:", e)
        continue
    if not len(r):
        print(f"DIAGNÓSTICO C sem pares utilizáveis em {uf}/{ano} (precisa de estação diária e subdiária a menos de {RAIO_PAR_KM:.0f} km)")
        continue
    partes.append(r)
    melhor = r.loc[r["corr"].idxmax()]
    linha12 = r[(r["h"] == 12) & (r["defasagem"] == 0)]["corr"]
    print(f"\n=== {uf}/{ano} — {npares} pares a até {RAIO_PAR_KM:.0f} km ===")
    print("correlação por h (defasagem 0):")
    print(r[r["defasagem"] == 0].set_index("h")["corr"].round(3).to_string())
    print(f"máximo do grid: H={int(melhor['H'])} (h={int(melhor['h'])}, defasagem={int(melhor['defasagem'])}), corr={melhor['corr']:.3f}")
    if len(linha12):
        print(f"pré-registrado h=12, defasagem 0: corr={float(linha12.iloc[0]):.3f}")

otimos = pd.DataFrame(columns=["uf", "ano", "H", "corr"])
if partes:
    DIAG_C = pd.concat(partes, ignore_index=True)
    DIAG_C.to_csv(os.path.join(PASTA_SAIDA, "03_diagnostico_fechamento_dia.csv"), index=False)
    otimos = DIAG_C.loc[DIAG_C.groupby(["uf", "ano"])["corr"].idxmax(), ["uf", "ano", "H", "corr"]]
    print("\nótimo por conjunto:")
    print(otimos.to_string(index=False))
else:
    print("\nNenhum conjunto rodou. O deslocamento fica como está no pré-registro.")
print("""
Como ler: as 72 células de cada conjunto devem colapsar numa curva única e unimodal em
H = h + 24*(-defasagem). Se os dois conjuntos derem máximo entre H=18 e H=22, o ótimo é
estável e a emenda do deslocamento para 20 h se justifica. Se derem máximos distantes,
fique com os 12 h pré-registrados e declare a perda de alinhamento como limitação.
MANDE ESTA SAÍDA AO CLAUDE ANTES DE MUDAR O DESLOCAMENTO PRINCIPAL.""")
''')

code(r'''
# 7. Fuso horário. Decidido em 12/11/2026 — ver "Registro da investigação" no cabeçalho.
#    "UTC"   -> os carimbos já estão em UTC; nada é convertido.
#    "local" -> os carimbos estão em hora de Brasília; são convertidos para UTC (America/Sao_Paulo,
#               com o horário de verão que existia até 2019) antes de agregar em dias.
#
# Fundamentos de "UTC": (a) os autores do UNIPLU-BR afirmam que os carimbos são ajustados para UTC;
# (b) o AIR Centre verificou de forma independente e importou sem conversão; (c) com UTC, o pico da
# célula 4 (20h-21h no carimbo) vira 17h-18h local, o máximo convectivo de fim de tarde da região.
# Ressalva declarada: a verificação do AIR Centre marca como inconclusiva justamente a zona UTC-3,
# que concentra quase todos os dados; e o perfil do ICEA, na célula 5, aponta para horário local.
FUSO_CONFIRMADO = "UTC"
FUSO_FUNDAMENTO = ("autores do UNIPLU-BR + verificacao independente do AIR Centre (parcial: zona "
                   "UTC-3 inconclusiva no relatorio original) + coerencia com o maximo convectivo local")
''')

code(r'''
# 8. Trava do fuso e escolha dos deslocamentos do dia
assert FUSO_CONFIRMADO in ("UTC", "local"), "FUSO_CONFIRMADO precisa ser 'UTC' ou 'local' (célula 7)."

# O pré-registro fixa 12 h. A medição da célula 6 aponta 20 h. Para não pagar duas vezes a passagem
# cara de QC, o notebook agrega nos dois deslocamentos e usa o pré-registrado como principal.
# DESLOCAMENTO_PRINCIPAL só muda por emenda datada, depois de conferir a célula 6.
DESLOC_PREREGISTRADO = int(pd.Timedelta(OFFSET) / pd.Timedelta(hours=1))
DESLOC_MEDIDO = 20
DESLOCAMENTOS = sorted({DESLOC_PREREGISTRADO, DESLOC_MEDIDO})
DESLOCAMENTO_PRINCIPAL = DESLOC_PREREGISTRADO

assert DESLOCAMENTO_PRINCIPAL in DESLOCAMENTOS
print("Fuso confirmado:", FUSO_CONFIRMADO)
print("Deslocamentos agregados:", DESLOCAMENTOS, "h")
print("Principal:", DESLOCAMENTO_PRINCIPAL, "h (pré-registrado)")
if FUSO_CONFIRMADO == "UTC":
    print("Fronteira do dia em hora local:", {d: f"{(d - 3) % 24:02d}h" for d in DESLOCAMENTOS})
''')

md("""
## Parte 2 — QC na resolução original e agregação diária, em lotes

Cada lote contém estações **inteiras**, para que todo critério temporal veja a série completa de cada estação.
Resultados parciais ficam em `06_dados/_lotes_03/`. Se o Colab cair, basta executar de novo.

Regras aplicadas (todas marcam, nenhuma apaga, exceto cópias idênticas, que o pré-registro manda descartar):

| Critério | Classe | Origem |
|---|---|---|
| duplicata com valor igual | descartada a cópia | `decisoes.json` |
| duplicata com valor diferente | FALHA nos dois | `decisoes.json` |
| negativo, acima do limite físico | FALHA | PINELO (2026) |
| travado (24 leituras), oscilação rápida, estação plana | DEFEITO | PINELO (2026) |

Só registros **sem falha e sem defeito** entram na soma diária. Um dia com cobertura menor que
a mínima do pré-registro é descartado (fica ausente), nunca preenchido.
""")

code(r'''
# 9. Funções do lote
import pyarrow.parquet as pq

COLUNAS_NATIVAS = ["qc_ausente"] + ql.COLUNAS_FALHA + ["qc_travado", "qc_oscilacao_rapida", "qc_estacao_plana"]

def para_utc(serie_dt):
    """Converte carimbos de hora de Brasília para UTC. Horas ambíguas ou inexistentes viram NaT."""
    loc = serie_dt.dt.tz_localize("America/Sao_Paulo", ambiguous="NaT", nonexistent="NaT")
    return loc.dt.tz_convert("UTC").dt.tz_localize(None)

def processar_lote(codigos):
    chave = ["gauge_code", "datetime"]
    df = pd.read_parquet(ARQ_BRUTO, columns=["gauge_code", "datetime", "rain_mm"],
                         filters=[("gauge_code", "in", list(codigos))])
    df["gauge_code"] = df["gauge_code"].astype(str)
    df["datetime"] = pd.to_datetime(df["datetime"])
    bruto_por_est = df.groupby("gauge_code").size()

    if FUSO_CONFIRMADO == "local":
        df["datetime"] = para_utc(df["datetime"])
    nat_por_est = df.loc[df["datetime"].isna()].groupby("gauge_code").size()
    df = df.dropna(subset=["datetime"])

    # Faixa de anos do pré-registro (a janela de 12 h pode puxar 1 dia para fora; tudo bem)
    df = df[(df["datetime"] >= pd.Timestamp(f"{ANO_I}-01-01")) & (df["datetime"] < pd.Timestamp(f"{ANO_F + 1}-01-02"))]

    # Duplicatas, conforme decisoes.json (valor igual: descarta a cópia; diferente: FALHA nos dois)
    df = df.sort_values(chave + ["rain_mm"], na_position="last", kind="stable").reset_index(drop=True)
    df["qc_duplicata"] = False
    copias_por_est = pd.Series(dtype="int64")
    conflitos_por_est = pd.Series(dtype="int64")
    dup = df.duplicated(chave, keep=False)
    if dup.any():
        sub = df.loc[dup, chave + ["rain_mm"]]
        nun = sub.groupby(chave)["rain_mm"].transform("nunique")
        idx_conf = sub.index[nun > 1]
        df.loc[idx_conf, "qc_duplicata"] = True
        conf = df.loc[idx_conf].drop_duplicates(chave)
        conflitos_por_est = conf.groupby("gauge_code").size()
        sobra = df.duplicated(chave, keep="first") & ~df["qc_duplicata"]
        copias_por_est = df.loc[sobra].groupby("gauge_code").size()
        df = df.loc[~sobra].reset_index(drop=True)

    # Passo real: mediana do intervalo entre carimbos distintos
    u = df.drop_duplicates(chave)
    passo_real = (u.groupby("gauge_code")["datetime"].diff().dt.total_seconds() / 60)
    passo_real = passo_real.groupby(u["gauge_code"]).median()

    info_lote = info_uso[info_uso["gauge_code"].isin(codigos)]
    df = ql.marcar_ausente(df)
    df = ql.marcar_negativo(df)
    df = ql.marcar_acima_limite_fisico(df, info_lote)
    df = ql.marcar_travado(df)                 # 24 leituras, resolução original
    df = ql.marcar_oscilacao_rapida(df)
    df = ql.marcar_estacao_plana(df)

    falha = df[ql.COLUNAS_FALHA].any(axis=1)
    defeito = df[["qc_travado", "qc_oscilacao_rapida", "qc_estacao_plana"]].any(axis=1)
    df["qc_limpo_nativo"] = ~(falha | defeito | df["qc_ausente"])

    # Auditoria por estação
    g = df.groupby("gauge_code")
    aud = g[COLUNAS_NATIVAS + ["qc_limpo_nativo"]].sum().astype("int64")
    aud["n_registros"] = g.size()
    aud["frac_zeros"] = g["rain_mm"].apply(lambda s: float((s == 0).mean()))
    aud["passo_real_min"] = passo_real.reindex(aud.index)
    aud["ano_min"] = g["datetime"].min().dt.year
    aud["ano_max"] = g["datetime"].max().dt.year
    aud["n_bruto"] = bruto_por_est.reindex(aud.index).fillna(0).astype("int64")
    aud["n_copias_identicas_descartadas"] = copias_por_est.reindex(aud.index).fillna(0).astype("int64")
    aud["n_pares_duplicata_conflitante"] = conflitos_por_est.reindex(aud.index).fillna(0).astype("int64")
    aud["n_carimbos_invalidos_fuso"] = nat_por_est.reindex(aud.index).fillna(0).astype("int64")
    aud = aud.reset_index()

    # Agregação diária só com registros limpos, em CADA deslocamento candidato (ver célula 8).
    # A parte cara é o QC acima; o resample sai barato, então os dois saem na mesma passagem.
    lim = df.loc[df["qc_limpo_nativo"], ["gauge_code", "datetime", "rain_mm"]].set_index("datetime")
    passo_decl = info_lote.set_index("gauge_code")["passo_min"]
    minutos_passo = pd.Timedelta(PASSO).total_seconds() / 60
    partes_ag = []
    for dh in (DESLOCAMENTOS if len(lim) else []):
        a = (lim.groupby("gauge_code")["rain_mm"]
                .resample(FREQ_DIA, offset=f"{dh}h", closed=FECHADO, label="right")
                .agg(["sum", "count"]).reset_index())
        a.columns = ["gauge_code", "rotulo", "rain_mm", "n_leituras"]
        a["dia"] = a["rotulo"].dt.normalize()
        a = a.drop(columns="rotulo")
        a["desloc_h"] = np.int16(dh)
        a["n_esperado"] = (minutos_passo / a["gauge_code"].map(passo_decl)).round().clip(lower=1)
        a["cobertura"] = a["n_leituras"] / a["n_esperado"]
        a["cobertura_ok"] = a["cobertura"] >= COB_MIN
        a["rain_mm"] = a["rain_mm"].astype("float32")
        partes_ag.append(a)
    ag = (pd.concat(partes_ag, ignore_index=True) if partes_ag
          else pd.DataFrame(columns=["gauge_code", "dia", "rain_mm", "n_leituras", "desloc_h",
                                     "n_esperado", "cobertura", "cobertura_ok"]))
    return ag, aud

def montar_lotes():
    """Agrupa estações inteiras em lotes de até MAX_LINHAS_LOTE linhas (contagem prévia, só da coluna do código)."""
    t = pq.read_table(ARQ_BRUTO, columns=["gauge_code"]).to_pandas()["gauge_code"].astype(str)
    cont = t.value_counts()
    del t; gc.collect()
    cont = cont.reindex(info_uso["gauge_code"]).dropna().astype(int).sort_index()
    lotes, atual, soma = [], [], 0
    for cod, n in cont.items():
        if atual and soma + n > MAX_LINHAS_LOTE:
            lotes.append(atual); atual, soma = [], 0
        atual.append(cod); soma += n
    if atual:
        lotes.append(atual)
    return lotes, cont

LOTES, CONT_LINHAS = montar_lotes()
print(f"{len(CONT_LINHAS)} estações com registros | {int(CONT_LINHAS.sum()):,} linhas | {len(LOTES)} lotes")
''')

code(r'''
# 10. Rodar os lotes (com retomada). Cada lote grava dois arquivos pequenos.
t0 = time.time()
for i, lote in enumerate(LOTES):
    a_dia = os.path.join(PASTA_LOTES, f"diario_{i:04d}.parquet")
    a_aud = os.path.join(PASTA_LOTES, f"auditoria_{i:04d}.parquet")
    if os.path.exists(a_dia) and os.path.exists(a_aud):
        continue
    ag, aud = processar_lote(lote)
    ag.to_parquet(a_dia, index=False)
    aud.to_parquet(a_aud, index=False)
    del ag, aud; gc.collect()
    print(f"lote {i + 1}/{len(LOTES)} ok | {len(lote)} estações | {time.time() - t0:,.0f} s", flush=True)
print("Todos os lotes concluídos.")
''')

md("""
## Parte 3 — Nível diário

Aqui as séries já estão todas na mesma resolução. A coerência espacial é avaliada neste nível, não
a cada 10 minutos: a chuva convectiva muda de lugar em minutos, e comparar estações a cada 10 minutos
produziria muita discordância legítima. **Esta é uma decisão de implementação, não de pré-registro**;
ela entra na lista final e deve ser registrada no relatório.
""")

code(r'''
# 11. Juntar os lotes. TODOS os deslocamentos ficam em D_TODOS; o pipeline segue só com o principal.
D_TODOS = pd.concat([pd.read_parquet(os.path.join(PASTA_LOTES, f"diario_{i:04d}.parquet")) for i in range(len(LOTES))],
                    ignore_index=True)
AUD = pd.concat([pd.read_parquet(os.path.join(PASTA_LOTES, f"auditoria_{i:04d}.parquet")) for i in range(len(LOTES))],
                ignore_index=True)
D_TODOS["dia"] = pd.to_datetime(D_TODOS["dia"])
print("linhas diárias por deslocamento:")
print(D_TODOS.groupby("desloc_h").agg(linhas=("dia", "size"), pct_cobertura_ok=("cobertura_ok", "mean")).assign(
    pct_cobertura_ok=lambda t: (100 * t["pct_cobertura_ok"]).round(1)).to_string())

D = D_TODOS[D_TODOS["desloc_h"] == DESLOCAMENTO_PRINCIPAL].reset_index(drop=True)
print(f"\nseguindo com deslocamento {DESLOCAMENTO_PRINCIPAL} h: {len(D):,} linhas diárias")
print(f"com cobertura mínima: {int(D['cobertura_ok'].sum()):,} ({100 * D['cobertura_ok'].mean():.1f}%)")

# Só dias com cobertura suficiente seguem; os demais ficam ausentes, nunca preenchidos
V = D.loc[D["cobertura_ok"], ["gauge_code", "dia", "rain_mm"]].rename(columns={"dia": "datetime"}).reset_index(drop=True)
V["rain_mm"] = V["rain_mm"].astype("float64")
print("dias válidos:", f"{len(V):,}", "| estações com pelo menos um dia válido:", V["gauge_code"].nunique())
''')

code(r'''
# 12. QC no nível diário: travado (7 dias) e coerência espacial. Valores iniciais, NÃO calibrados.
t0 = time.time()
V = ql.marcar_travado(V, min_repeticoes=MIN_REP_DIAS)
print(f"travado diário ({MIN_REP_DIAS} dias): {int(V['qc_travado'].sum()):,} dias | {time.time() - t0:,.0f} s")

e = ESPACIAIS_INICIAIS
V = ql.marcar_isolado_espacial(V, info_uso, raio_km=e["raio_km"], minimo_vizinhos=e["minimo_vizinhos"],
                               limiar_mm=e["limiar_mm"], razao_maxima=e["razao_maxima"])
print(f"isolado espacial: {int(V['qc_isolado_espacial'].sum()):,} dias | {time.time() - t0:,.0f} s")
V = ql.marcar_seco_espacial(V, info_uso, raio_km=e["raio_km"], minimo_vizinhos=e["minimo_vizinhos"],
                            limiar_vizinhos_mm=e["limiar_vizinhos_mm"])
print(f"seco espacial   : {int(V['qc_seco_espacial'].sum()):,} dias | {time.time() - t0:,.0f} s")
''')

code(r'''
# 13. Extremo (descritivo, não exclui) com limiar calculado SÓ no treino; partições
V["conjunto"] = np.select(
    [(V["datetime"] >= TREINO[0]) & (V["datetime"] <= TREINO[1]),
     (V["datetime"] >= VALID[0]) & (V["datetime"] <= VALID[1]),
     (V["datetime"] >= TESTE[0]) & (V["datetime"] <= TESTE[1])],
    ["treino", "validacao", "teste"], default="fora")

pos_treino = V[(V["conjunto"] == "treino") & (V["rain_mm"] > 0)]
q = pos_treino.groupby("gauge_code")["rain_mm"].quantile([0.25, 0.75]).unstack()
q.columns = ["q1", "q3"]
q["limiar_extremo"] = q["q3"] + K_IQR * (q["q3"] - q["q1"])
V["qc_atipico_iqr"] = (V["rain_mm"] > V["gauge_code"].map(q["limiar_extremo"])).fillna(False)

V["qc_defeito_diario"] = V[["qc_travado", "qc_isolado_espacial", "qc_seco_espacial"]].any(axis=1)
V["qc_limpo_diario"] = ~V["qc_defeito_diario"]
print(V["conjunto"].value_counts().to_string())
print(f"\nextremo (IQR, limiar do treino): {int(V['qc_atipico_iqr'].sum()):,} dias — descritivo, NÃO exclui")
''')

code(r'''
# 14. Estações elegíveis: pelo menos 3 anos com dias válidos suficientes no TREINO
tr = V[(V["conjunto"] == "treino") & V["qc_limpo_diario"]].copy()
tr["ano"] = tr["datetime"].dt.year
dias_por_ano = tr.groupby(["gauge_code", "ano"]).size().rename("dias").reset_index()
anos_ok = (dias_por_ano[dias_por_ano["dias"] >= DIAS_VALIDOS_MIN_POR_ANO]
           .groupby("gauge_code").size().rename("anos_treino_ok"))

EST = info_uso[["gauge_code", "network", "state", "city", "lat", "long", "time_step", "passo_min"]].copy()
EST = EST.merge(anos_ok, on="gauge_code", how="left")
EST["anos_treino_ok"] = EST["anos_treino_ok"].fillna(0).astype(int)
EST["atende_anos_minimos"] = EST["anos_treino_ok"] >= ANOS_MIN_TREINO

# Emenda de 12/11/2026 (decisoes.json v1.1): redes excluídas por decisão declarada.
# A exclusão é aplicada AQUI, e não antes do QC, de propósito: a auditoria das células 15 e 16
# precisa continuar mostrando os números que justificam a exclusão.
REDES_EXCLUIDAS = DEC["dados"].get("redes_excluidas", [])
EST["rede_excluida"] = EST["network"].isin(REDES_EXCLUIDAS)
EST["elegivel"] = EST["atende_anos_minimos"] & ~EST["rede_excluida"]

# Quinto critério de refutação: replicação restrita ao Hidroweb diário, única rede com
# composição estável nos 31 anos. A marcação sai aqui para o notebook de avaliação usar.
EST["subconjunto_hidroweb"] = EST["elegivel"] & (EST["network"] == "Hidroweb diário")

print("redes excluídas por emenda:", REDES_EXCLUIDAS or "(nenhuma)")
if REDES_EXCLUIDAS:
    perdidas = int((EST["atende_anos_minimos"] & EST["rede_excluida"]).sum())
    print(f"  estações que atendiam aos anos mínimos e saíram pela exclusão de rede: {perdidas}")
print(f"estações elegíveis (>= {ANOS_MIN_TREINO} anos no treino, redes excluídas fora): "
      f"{int(EST['elegivel'].sum())} de {len(EST)}")
print(f"subconjunto Hidroweb diário (5º critério de refutação): {int(EST['subconjunto_hidroweb'].sum())}")
print(EST.groupby("network")[["atende_anos_minimos", "elegivel"]].agg(["sum", "size"]).to_string())
''')

md("""
## Parte 4 — Auditoria e saídas

As tabelas abaixo vão para o relatório KDD. Elas são a auditoria de consistência: dizem quanto cada critério
removeu, por rede, e onde a cobertura é fraca. **Leia a coluna de cobertura por rede antes de confiar nos números**:
uma rede que grava só quando chove teria cobertura baixa por construção, e não por defeito.
""")

code(r'''
# 15. Tabelas de auditoria
AUD = AUD.merge(info_uso[["gauge_code", "network", "time_step"]], on="gauge_code", how="left")
tot = int(AUD["n_registros"].sum())   # registros após descartar as cópias idênticas

linhas = []
for c in COLUNAS_NATIVAS:
    n = int(AUD[c].sum())
    linhas.append({"nivel": "original", "criterio": c, "registros": n, "percentual": round(100 * n / tot, 4)})
linhas.append({"nivel": "original", "criterio": "qc_limpo_nativo", "registros": int(AUD["qc_limpo_nativo"].sum()),
               "percentual": round(100 * AUD["qc_limpo_nativo"].sum() / tot, 4)})
for c in ["n_copias_identicas_descartadas", "n_pares_duplicata_conflitante"]:
    n = int(AUD[c].sum())
    linhas.append({"nivel": "original", "criterio": c, "registros": n, "percentual": round(100 * n / tot, 4)})
for c in ["qc_travado", "qc_isolado_espacial", "qc_seco_espacial", "qc_atipico_iqr", "qc_limpo_diario"]:
    n = int(V[c].sum())
    linhas.append({"nivel": "diario", "criterio": c, "registros": n, "percentual": round(100 * n / len(V), 4)})
AUD_CRIT = pd.DataFrame(linhas)
print(AUD_CRIT.to_string(index=False))

por_rede = AUD.groupby("network").agg(estacoes=("gauge_code", "nunique"), registros=("n_registros", "sum"),
                                      limpo_nativo=("qc_limpo_nativo", "sum"))
for c in COLUNAS_NATIVAS:
    por_rede[c] = AUD.groupby("network")[c].sum()
por_rede["pct_limpo_nativo"] = (100 * por_rede["limpo_nativo"] / por_rede["registros"]).round(2)
dv = D.merge(info_uso[["gauge_code", "network"]], on="gauge_code")
por_rede["dias_com_registro"] = dv.groupby("network").size()
por_rede["pct_dias_cobertura_ok"] = (100 * dv.groupby("network")["cobertura_ok"].mean()).round(1)
por_rede["frac_zeros_mediana"] = AUD.groupby("network")["frac_zeros"].median().round(3)
print("\n", por_rede.to_string())

inc = AUD[(AUD["passo_real_min"].notna()) & (AUD["passo_real_min"] != AUD["time_step"].map(ql.passo_minutos))]
print(f"\nestações cujo passo real (mediana dos intervalos) difere do declarado: {len(inc)} de {len(AUD)}")
print(inc.groupby("network").size().to_string() if len(inc) else "nenhuma")
''')

code(r'''
# 16. Figura: estações ativas por ano e rede (apenas dias válidos)
import matplotlib
import matplotlib.pyplot as plt
ativ = V.merge(info_uso[["gauge_code", "network"]], on="gauge_code")
ativ = ativ[ativ["datetime"].dt.year <= ANO_F]   # corta o dia de fronteira que cai no ano seguinte
ativ["ano"] = ativ["datetime"].dt.year
tab = ativ.groupby(["ano", "network"])["gauge_code"].nunique().unstack(fill_value=0)
tab.to_csv(os.path.join(PASTA_SAIDA, "03_estacoes_ativas_por_ano.csv"))

# A figura do relatório é a das elegíveis: mostrar as 2.132 num trabalho que usa 790 confunde o leitor.
elegiveis = set(EST.loc[EST["elegivel"], "gauge_code"])
tab_el = (ativ[ativ["gauge_code"].isin(elegiveis)]
          .groupby(["ano", "network"])["gauge_code"].nunique().unstack(fill_value=0))
tab_el.to_csv(os.path.join(PASTA_SAIDA, "03_estacoes_elegiveis_por_ano.csv"))

fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
tab.plot(kind="bar", stacked=True, width=0.85, ax=a1, legend=True)
a1.set_title("Todas as estações com dia válido, por ano e rede")
a1.set_ylabel("Estações"); a1.set_xlabel("")
tab_el.plot(kind="bar", stacked=True, width=0.85, ax=a2, legend=True)
a2.set_title(f"Somente as {len(elegiveis)} estações elegíveis — é esta que vai para o relatório")
a2.set_ylabel("Estações"); a2.set_xlabel("Ano")
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, "03_estacoes_ativas_por_ano.png"), dpi=150)
plt.show()

print("total de elegíveis ativas por ano:")
print(tab_el.sum(axis=1).to_string())
''')

code(r'''
# 17. Gravar saídas e o registro desta execução
saida = V[["gauge_code", "datetime", "rain_mm", "conjunto", "qc_travado", "qc_isolado_espacial",
           "qc_seco_espacial", "qc_atipico_iqr", "qc_limpo_diario"]].rename(columns={"datetime": "dia"})
saida["rain_mm"] = saida["rain_mm"].astype("float32")
saida.to_parquet(os.path.join(PASTA_DADOS, f"chuva_diaria_qc_h{DESLOCAMENTO_PRINCIPAL}.parquet"), index=False)

# O deslocamento alternativo fica gravado só com a agregação, sem o QC diário, para a sensibilidade.
for dh in DESLOCAMENTOS:
    if dh == DESLOCAMENTO_PRINCIPAL:
        continue
    alt = D_TODOS[(D_TODOS["desloc_h"] == dh) & D_TODOS["cobertura_ok"]][["gauge_code", "dia", "rain_mm"]]
    alt.to_parquet(os.path.join(PASTA_DADOS, f"chuva_diaria_agregada_h{dh}.parquet"), index=False)
    print(f"deslocamento alternativo {dh} h gravado ({len(alt):,} dias) para a análise de sensibilidade")

EST.to_parquet(os.path.join(PASTA_DADOS, "estacoes_elegiveis.parquet"), index=False)
EST.to_csv(os.path.join(PASTA_SAIDA, "03_estacoes.csv"), index=False)
AUD_CRIT.to_csv(os.path.join(PASTA_SAIDA, "03_auditoria_por_criterio.csv"), index=False)
por_rede.to_csv(os.path.join(PASTA_SAIDA, "03_auditoria_por_rede.csv"))
AUD.to_csv(os.path.join(PASTA_SAIDA, "03_auditoria_por_estacao.csv"), index=False)

import platform
log = {
    "notebook": "03_qualidade_e_preparo", "versao_notebook": "2", "data_execucao": pd.Timestamp.now().isoformat(),
    "decisoes_versao": DEC["versao"], "decisoes_sha256_16": HASH_DECISOES,
    "fuso_confirmado": FUSO_CONFIRMADO, "fuso_fundamento": FUSO_FUNDAMENTO,
    "redes_excluidas": DEC["dados"].get("redes_excluidas", []),
    "subconjunto_hidroweb_estacoes": int(EST["subconjunto_hidroweb"].sum()),
    "deslocamentos_agregados_h": DESLOCAMENTOS, "deslocamento_principal_h": DESLOCAMENTO_PRINCIPAL,
    "deslocamento_otimo_medido": otimos.to_dict("records"),
    "modulo_qc": "qc_uniplu.py v2.1", "pandas": pd.__version__, "python": platform.python_version(),
    "linhas_brutas_lidas": int(AUD["n_registros"].sum()),
    "dias_validos": int(len(V)), "estacoes_elegiveis": int(EST["elegivel"].sum()),
    "parametros_nao_preregistrados": {k: (v if not isinstance(v, dict) else v) for k, v in NAO_PREREGISTRADOS.items()},
}
with open(os.path.join(PASTA_SAIDA, "03_log_execucao.json"), "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2, default=str)

print("Gravado em", PASTA_DADOS, "e", PASTA_SAIDA)
print("\nPARÂMETROS USADOS QUE O PRÉ-REGISTRO NÃO FIXA (registrar no Quadro de decisões do relatório KDD):")
for k, v in NAO_PREREGISTRADOS.items():
    print(" -", k, "=", v)
print("\nMANDE AO CLAUDE: as saídas das células 4, 5, 6, 12, 13, 14 e 15.")
''')

md("""
## Célula opcional — sensibilidade dos limiares espaciais (só treino)

Prepara a calibração (tarefa para o Opus). Roda os dois critérios espaciais em uma grade de parâmetros,
**apenas sobre dias do treino**, e mostra quantos dias cada combinação marcaria. Não grava nenhum parâmetro.
Pode levar muitos minutos; deixe desligada na primeira execução.
""")

code(r'''
# 18. (opcional) Sensibilidade no treino. Mude para True para rodar.
RODAR_SENSIBILIDADE = False
if RODAR_SENSIBILIDADE:
    import itertools
    base = V.loc[(V["conjunto"] == "treino") & (V["datetime"] >= pd.Timestamp("2014-01-01")),
                 ["gauge_code", "datetime", "rain_mm"]].reset_index(drop=True)
    saida_sens = []
    for raio, lim, razao in itertools.product([30.0, 50.0, 75.0], [20.0, 40.0, 60.0], [0.05, 0.10, 0.20]):
        r = ql.marcar_isolado_espacial(base, info_uso, raio_km=raio, limiar_mm=lim, razao_maxima=razao)
        saida_sens.append({"criterio": "isolado", "raio_km": raio, "limiar_mm": lim, "razao": razao,
                           "dias_marcados": int(r["qc_isolado_espacial"].sum())})
    for raio, viz in itertools.product([30.0, 50.0, 75.0], [10.0, 20.0, 40.0]):
        r = ql.marcar_seco_espacial(base, info_uso, raio_km=raio, limiar_vizinhos_mm=viz)
        saida_sens.append({"criterio": "seco", "raio_km": raio, "limiar_vizinhos_mm": viz,
                           "dias_marcados": int(r["qc_seco_espacial"].sum())})
    SENS = pd.DataFrame(saida_sens)
    SENS.to_csv(os.path.join(PASTA_SAIDA, "03_sensibilidade_espacial_treino.csv"), index=False)
    print(SENS.to_string(index=False))
else:
    print("Sensibilidade desligada. Mude RODAR_SENSIBILIDADE para True quando for calibrar.")
''')


md("""
## Parte 6 — Rótulos de evento (REInDesC)

Monta a tabela de eventos que o notebook de avaliação vai usar. **A regra foi fixada em
12/11/2026, antes de qualquer treinamento e sem que nenhuma pontuação de modelo existisse.**
O motivo de cada escolha está no registro do cabeçalho.

| Elemento | Regra | Origem |
|---|---|---|
| Episódio | ocorrências da mesma UF com intervalo de até 2 dias entre dias consecutivos | decisão de 12/11, **não** pré-registrada |
| Conjunto principal | episódio com pelo menos uma ocorrência GP ou MP | magnitude definida pelo Cemaden |
| Estratificação | extenso (≥ 5 municípios) × local (< 5) | decisão de 12/11, **não** pré-registrada |
| Conjunto secundário | todos os episódios, sem filtro de magnitude | — |
| Janela de detecção | de 3 dias antes do início até o fim | pré-registro |

Os arquivos `reindesc_*.csv` exportados do portal precisam estar em `06_dados/`.
""")

code(r'''
# 19. Rótulos de evento a partir das ocorrências do REInDesC
GAP_EPISODIO_DIAS = 2          # NÃO pré-registrado
MIN_MUNICIPIOS_EXTENSO = 5     # NÃO pré-registrado (só estratifica, não filtra)
MAGNITUDES_SEVERAS = ("GP", "MP")
try:
    DIAS_ANTES = int(DEC["avaliacao"]["dias_antes_do_inicio"])
except Exception:
    DIAS_ANTES = 3
    print("aviso: não achei a janela no decisoes.json; usando 3 dias, que é o valor pré-registrado no texto")

arqs = sorted(glob.glob(os.path.join(PASTA_DADOS, "reindesc*.csv")))
if not arqs:
    print(f"ATENÇÃO: nenhum CSV do REInDesC em {PASTA_DADOS} (o nome precisa começar com 'reindesc').")
    print("Sem eles não há rótulo de evento e o notebook de avaliação não roda. O resto já está gravado.")
    raise SystemExit(0)
OC = pd.concat([pd.read_csv(a, sep=";", encoding="utf-8") for a in arqs], ignore_index=True)
OC.columns = [c.strip() for c in OC.columns]
OC["Data"] = pd.to_datetime(OC["Data"])
OC = OC.drop_duplicates("ID ocorrência").sort_values(["UF", "Data"]).reset_index(drop=True)

print(f"{len(arqs)} arquivo(s) | {len(OC)} ocorrências | {OC['Data'].min().date()} a {OC['Data'].max().date()}")
print("por UF:", OC["UF"].value_counts().to_dict())
print("tipologia:", OC["Tipologia"].value_counts().to_dict())
print("magnitude:", OC["Magnitude"].value_counts().to_dict())
print("\nmagnitude por UF e ano (verificar estacionariedade do rótulo):")
print(pd.crosstab([OC["UF"], OC["Data"].dt.year], OC["Magnitude"]).to_string())

# Episódios: dias consecutivos da mesma UF separados por no máximo GAP_EPISODIO_DIAS
OC["_novo"] = (OC.groupby("UF")["Data"].diff().dt.days > GAP_EPISODIO_DIAS) | OC.groupby("UF")["Data"].diff().isna()
OC["id_evento"] = OC["UF"] + "_" + OC.groupby("UF")["_novo"].cumsum().astype(str).str.zfill(3)

EV = OC.groupby(["UF", "id_evento"]).agg(
    data_inicio=("Data", "min"), data_fim=("Data", "max"),
    n_ocorrencias=("ID ocorrência", "size"), n_municipios=("Município", "nunique")).reset_index()
mag = pd.crosstab(OC["id_evento"], OC["Magnitude"]).reindex(columns=["GP", "MP", "PP"], fill_value=0)
EV = EV.merge(mag.rename(columns={"GP": "n_gp", "MP": "n_mp", "PP": "n_pp"}), on="id_evento", how="left")
EV["duracao_dias"] = (EV["data_fim"] - EV["data_inicio"]).dt.days + 1
EV["severo"] = EV[["n_gp", "n_mp"]].sum(axis=1) >= 1
EV["extenso"] = EV["n_municipios"] >= MIN_MUNICIPIOS_EXTENSO
EV["janela_inicio"] = EV["data_inicio"] - pd.Timedelta(days=DIAS_ANTES)
EV["janela_fim"] = EV["data_fim"]

print(f"\nepisódios: {len(EV)} | severos (GP ou MP): {int(EV['severo'].sum())}")
print(pd.crosstab(EV[EV["severo"]]["UF"], EV[EV["severo"]]["data_inicio"].dt.year).to_string())
print("\nestratificação do conjunto principal:")
print(pd.crosstab(EV[EV["severo"]]["UF"], EV[EV["severo"]]["extenso"].map({True: "extenso", False: "local"})).to_string())
print("\ncom pelo menos uma ocorrência GP (descritivo, NÃO usado como conjunto principal):",
      int((EV["n_gp"] >= 1).sum()))

print("\nmaiores episódios severos:")
print(EV[EV["severo"]].nlargest(8, "n_municipios")[
    ["UF", "data_inicio", "data_fim", "duracao_dias", "n_ocorrencias", "n_municipios", "n_gp", "n_mp"]
].to_string(index=False))

# Teto estrutural do recall no ponto de operação pré-registrado
anos = (OC["Data"].max() - OC["Data"].min()).days / 365.25
for frac in (0.01, 0.03):
    dias_alarme = frac * 365.25
    for uf in sorted(EV["UF"].unique()):
        n = int(EV[(EV["UF"] == uf) & EV["severo"]].shape[0]) / anos
        print(f"alarme {frac:.0%} dos dias -> {dias_alarme:.1f} dias/ano | {uf}: {n:.1f} eventos severos/ano "
              f"| teto de recall ~ {min(1.0, dias_alarme / n):.0%}")

EV.to_parquet(os.path.join(PASTA_DADOS, "eventos_reindesc.parquet"), index=False)
OC.drop(columns="_novo").to_parquet(os.path.join(PASTA_DADOS, "ocorrencias_reindesc.parquet"), index=False)
EV.to_csv(os.path.join(PASTA_SAIDA, "03_eventos_reindesc.csv"), index=False)
print("\nGravado: eventos_reindesc.parquet, ocorrencias_reindesc.parquet e 03_eventos_reindesc.csv")
print("\nLIMITAÇÕES A DECLARAR NO RELATÓRIO (ver registro no cabeçalho):")
print(" - inventário por impacto, não por chuva: chuva extrema sem dano não é evento")
print(" - só municípios monitorados pelo Cemaden: viés de cobertura espacial")
print(" - precisão temporal inutilizável: lead time só em dias")
print(" - GAP_EPISODIO_DIAS e MIN_MUNICIPIOS_EXTENSO não são pré-registrados")
print(" - licença de uso do REInDesC ainda não verificada")
''')


def nb():
    cells = []
    for tipo, fonte in C:
        linhas = fonte.split("\n")
        src = [l + "\n" for l in linhas[:-1]] + [linhas[-1]]
        c = {"cell_type": tipo, "metadata": {}, "source": src}
        if tipo == "code":
            c["outputs"] = []
            c["execution_count"] = None
        cells.append(c)
    return {"cells": cells, "metadata": {"colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    json.dump(nb(), open("/home/claude/03_qualidade_e_preparo.ipynb", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("ok", len(C), "celulas")
