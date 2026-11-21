# -*- coding: utf-8 -*-
"""Gera o notebook 07 — falhas e travamentos dos pluviômetros, no espaço e no tempo.

Uso:  python gerar_nb07.py [destino.ipynb]
"""
import json
import os
import sys

CELLS = []


def md(txt):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": txt.strip("\n").splitlines(True)})


def code(txt):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": txt.strip("\n").splitlines(True)})


md("""
# 07 — Onde e quando os pluviômetros travam ou falham

**Exploratório e descritivo.** Não muda o resultado da fase 1 (achado 08) nem o da fase 2 (achado 09).
Segue o pré-registro `decisoes_07_falhas.json` v1.0, de 21/11/2026, gravado antes desta execução.

**A pergunta:** os pluviômetros ficam indisponíveis (sem leitura, com leitura travada ou com o dia
descartado pelo controle de qualidade) com mais frequência justamente durante as cheias severas?

**Por que importa:** numa estação sem dado, nenhum modelo, simples ou complexo, consegue dar alarme.

**O que o notebook faz:**

1. Refaz, em lotes de estações inteiras, as marcas do nível original (travado, oscilação, limite físico,
   duplicata) e guarda, para cada estação e dia, quantas leituras caíram em cada marca. O dia é fechado
   da mesma forma que no notebook 03.
2. Mapa das estações com a porcentagem de leituras travadas ou oscilando (1995–2025).
3. Mapa de calor ano × mês e tabela por rede e ano.
4. No teste (2023–2025), compara a indisponibilidade das estações elegíveis dentro dos 37 episódios
   severos com a de janelas sorteadas fora deles (teste placebo, 1.000 sorteios).

**Se o Colab cair:** rode de novo. Cada lote terminado fica em `06_dados/_lotes_07/` e não é refeito.
""")

code(r'''
# 1. Configuração, Drive e caminhos
import os, sys, json, time, gc, glob, hashlib, platform, warnings
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
warnings.filterwarnings("ignore", category=FutureWarning)

RAIZ_TESTE = os.environ.get("NB07_RAIZ_TESTE")          # usado só nos testes locais
if RAIZ_TESTE:
    CANDIDATOS = [RAIZ_TESTE]
else:
    from google.colab import drive
    drive.mount("/content/drive")
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
ARQ_ELEG = achar("06_dados/estacoes_elegiveis.parquet")
ARQ_EVENTOS = achar("06_dados/eventos_reindesc.parquet")
ARQ_QC = achar("02_scripts/qc_uniplu.py")
ARQ_DEC = achar("02_scripts/decisoes.json")
ARQ_DEC7 = achar("02_scripts/decisoes_07_falhas.json")

PASTA_DADOS = os.path.dirname(ARQ_BRUTO)
RAIZ_DADOS = os.path.dirname(PASTA_DADOS)
PASTA_SAIDA = os.path.join(RAIZ_DADOS, "05_saidas")
PASTA_LOTES = os.path.join(PASTA_DADOS, "_lotes_07")
for p in (PASTA_SAIDA, PASTA_LOTES):
    os.makedirs(p, exist_ok=True)

sys.path.insert(0, os.path.dirname(ARQ_QC))
import qc_uniplu as ql
print("bruto:", ARQ_BRUTO)
print("saídas em:", PASTA_SAIDA)
''')

code(r'''
# 2. Pré-registros: as travas de hash
def ler_json(caminho):
    with open(caminho, "rb") as f:
        b = f.read()
    return json.loads(b), hashlib.sha256(b).hexdigest()[:16]

DEC, HASH_DEC = ler_json(ARQ_DEC)
DEC7, HASH_DEC7 = ler_json(ARQ_DEC7)
VERSOES_DEC = {"1.2": "d4c58a627755c8f9"}
VERSOES_DEC7 = {"1.0": "06f4141076313128"}
if VERSOES_DEC.get(DEC["versao"]) != HASH_DEC:
    raise SystemExit(f"decisoes.json versão {DEC['versao']} com hash {HASH_DEC}: não é a versão travada da fase 1.")
if VERSOES_DEC7.get(DEC7["versao"]) != HASH_DEC7:
    raise SystemExit(f"decisoes_07_falhas.json com hash {HASH_DEC7}: o pré-registro foi editado sem emenda.")

ANO_I, ANO_F = DEC["dados"]["ano_inicial"], DEC["dados"]["ano_final"]
UFS = DEC["dados"]["ufs"]
PASSO = DEC["resolucao"]["passo"]
DESLOC_H = int(pd.Timedelta(DEC["resolucao"]["deslocamento_fechamento_dia"]) / pd.Timedelta(hours=1))
FECHADO = DEC["resolucao"]["intervalo_fechado"]
assert pd.Timedelta(PASSO) == pd.Timedelta(hours=24), "este notebook supõe dia de 24 h"
assert FECHADO in ("left", "right")
TESTE = tuple(pd.Timestamp(x) for x in DEC["particao"]["teste"])
L = int(DEC["entrada_modelo"]["janela_dias"])
PL = DEC7["teste_placebo"]
N_SORTEIOS, SEMENTE = PL["sorteios"], PL["semente"]
MAX_LINHAS_LOTE = int(os.environ.get("NB07_MAX_LINHAS", 6_000_000))   # só logística de memória
print(f"decisoes.json {DEC['versao']} ({HASH_DEC}) | decisoes_07_falhas.json {DEC7['versao']} ({HASH_DEC7})")
print(f"dia fechado às {DESLOC_H} h, intervalo fechado à {FECHADO} | teste {TESTE[0].date()} a {TESTE[1].date()} | janela {L} dias")
''')

code(r'''
# 3. Estações, elegíveis e episódios
info = pd.read_parquet(ARQ_ESTACOES)
info.columns = [c.lower() for c in info.columns]
info = info.drop_duplicates("gauge_code").reset_index(drop=True)
info["gauge_code"] = info["gauge_code"].astype(str)
info["passo_min"] = info["time_step"].map(ql.passo_minutos)
if DEC["dados"].get("excluir_time_step_indefinido", True):
    info_uso = info[info["passo_min"].notna() & info["state"].isin(UFS)].reset_index(drop=True)
else:
    info_uso = info[info["state"].isin(UFS)].reset_index(drop=True)

EST = pd.read_parquet(ARQ_ELEG)
EST["gauge_code"] = EST["gauge_code"].astype(str)
ELEG = set(EST.loc[EST["elegivel"], "gauge_code"])

EV = pd.read_parquet(ARQ_EVENTOS)
for c in ("data_inicio", "data_fim", "janela_inicio", "janela_fim"):
    EV[c] = pd.to_datetime(EV[c])
SEV = EV[EV["severo"]].reset_index(drop=True)
print(f"estações em uso: {len(info_uso)} | elegíveis: {len(ELEG)} | episódios: {len(EV)} | severos: {len(SEV)}",
      SEV["UF"].value_counts().to_dict())
''')

code(r'''
# 4. A fronteira do dia, igual à do notebook 03 (resample de 24 h, deslocado, rótulo à direita)
def dia_do_registro(t):
    """Dia (meia-noite) ao qual o carimbo t pertence na agregação do notebook 03."""
    u = t - pd.Timedelta(hours=DESLOC_H)
    if FECHADO == "right":
        return u.dt.ceil("D")
    return u.dt.floor("D") + pd.Timedelta(days=1)

def processar_lote(codigos):
    chave = ["gauge_code", "datetime"]
    df = pd.read_parquet(ARQ_BRUTO, columns=["gauge_code", "datetime", "rain_mm"],
                         filters=[("gauge_code", "in", list(codigos))])
    df["gauge_code"] = df["gauge_code"].astype(str)
    df["datetime"] = pd.to_datetime(df["datetime"])          # carimbo em UTC (decisão de 12/11/2026)
    df = df.dropna(subset=["datetime"])
    df = df[(df["datetime"] >= pd.Timestamp(f"{ANO_I}-01-01")) & (df["datetime"] < pd.Timestamp(f"{ANO_F + 1}-01-02"))]
    # duplicatas como no notebook 03: cópia idêntica sai; valores conflitantes ficam marcados
    df = df.sort_values(chave + ["rain_mm"], na_position="last", kind="stable").reset_index(drop=True)
    df["qc_duplicata"] = False
    dup = df.duplicated(chave, keep=False)
    if dup.any():
        sub = df.loc[dup, chave + ["rain_mm"]]
        nun = sub.groupby(chave)["rain_mm"].transform("nunique")
        df.loc[sub.index[nun > 1], "qc_duplicata"] = True
        sobra = df.duplicated(chave, keep="first") & ~df["qc_duplicata"]
        df = df.loc[~sobra].reset_index(drop=True)
    info_lote = info_uso[info_uso["gauge_code"].isin(codigos)]
    df = ql.marcar_acima_limite_fisico(df, info_lote)
    df = ql.marcar_travado(df)
    df = ql.marcar_oscilacao_rapida(df)
    df["dia"] = dia_do_registro(df["datetime"])
    df["leit"] = df["rain_mm"].notna()
    ag = (df.groupby(["gauge_code", "dia"])
            .agg(n_leit=("leit", "sum"), n_trav=("qc_travado", "sum"), n_osc=("qc_oscilacao_rapida", "sum"),
                 n_lim=("qc_acima_limite_fisico", "sum"), n_dup=("qc_duplicata", "sum"))
            .reset_index())
    for c in ("n_leit", "n_trav", "n_osc", "n_lim", "n_dup"):
        ag[c] = ag[c].astype("int32")
    return ag

def montar_lotes():
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
    return lotes

LOTES = montar_lotes()
print(f"{sum(len(l) for l in LOTES)} estações em {len(LOTES)} lotes")
''')

code(r'''
# 5. Rodar os lotes, com retomada (cada lote grava um arquivo; lote pronto não é refeito)
t0 = time.time()
for i, lote in enumerate(LOTES):
    arq = os.path.join(PASTA_LOTES, f"dias_{i:04d}.parquet")
    marca = arq + ".ok"
    if os.path.exists(marca):
        with open(marca) as f:
            if f.read().strip() == ",".join(lote):
                continue
    ag = processar_lote(lote)
    ag.to_parquet(arq, index=False)
    with open(marca, "w") as f:
        f.write(",".join(lote))
    print(f"lote {i + 1}/{len(LOTES)} | {len(lote)} estações | {time.time() - t0:,.0f} s", flush=True)
DIAS = pd.concat([pd.read_parquet(os.path.join(PASTA_LOTES, f"dias_{i:04d}.parquet")) for i in range(len(LOTES))],
                 ignore_index=True)
DIAS["trav_osc"] = (DIAS["n_trav"] + DIAS["n_osc"]) > 0
print(f"estação-dias com leitura: {len(DIAS):,} | com leitura travada ou oscilando: {int(DIAS['trav_osc'].sum()):,}")
print(f"leituras: {int(DIAS['n_leit'].sum()):,} | travadas: {int(DIAS['n_trav'].sum()):,} | oscilando: {int(DIAS['n_osc'].sum()):,}")
''')

code(r'''
# 6. Onde: por estação, por rede e ano, e por ano e mês
pe = (DIAS.groupby("gauge_code")
        .agg(n_leit=("n_leit", "sum"), n_trav=("n_trav", "sum"), n_osc=("n_osc", "sum"),
             dias_com_leitura=("dia", "size"), dias_trav_osc=("trav_osc", "sum"),
             primeiro_dia=("dia", "min"), ultimo_dia=("dia", "max"))
        .reset_index())
pe["pct_leit_trav_osc"] = 100 * (pe["n_trav"] + pe["n_osc"]) / pe["n_leit"].clip(lower=1)
pe = pe.merge(info_uso[["gauge_code", "state", "network", "time_step", "lat", "long"]], on="gauge_code", how="left")
pe["elegivel"] = pe["gauge_code"].isin(ELEG)
pe.to_csv(os.path.join(PASTA_SAIDA, "07_falhas_por_estacao.csv"), index=False)

DIAS["ano"] = DIAS["dia"].dt.year
DIAS["mes"] = DIAS["dia"].dt.month
DIAS = DIAS.merge(info_uso[["gauge_code", "network", "state"]], on="gauge_code", how="left")
rede_ano = (DIAS.groupby(["network", "ano"])
              .agg(estacoes=("gauge_code", "nunique"), estacao_dias=("dia", "size"),
                   pct_dias_trav_osc=("trav_osc", "mean")).reset_index())
rede_ano["pct_dias_trav_osc"] = (100 * rede_ano["pct_dias_trav_osc"]).round(3)
rede_ano.to_csv(os.path.join(PASTA_SAIDA, "07_falhas_rede_ano.csv"), index=False)
ano_mes = DIAS.groupby(["ano", "mes"])["trav_osc"].agg(["mean", "size"]).reset_index()
ano_mes.columns = ["ano", "mes", "frac_dias_trav_osc", "estacao_dias"]
ano_mes.to_csv(os.path.join(PASTA_SAIDA, "07_falhas_ano_mes.csv"), index=False)

print("Redes, % de estação-dias com leitura travada ou oscilando (1995–2025):")
print((DIAS.groupby("network")["trav_osc"].mean() * 100).round(2).sort_values(ascending=False).to_string())
print("\nAs 10 estações com maior % de leituras travadas ou oscilando (mínimo de 1.000 leituras):")
print(pe[pe["n_leit"] >= 1000].nlargest(10, "pct_leit_trav_osc")[
    ["gauge_code", "state", "network", "n_leit", "pct_leit_trav_osc", "primeiro_dia", "ultimo_dia"]].to_string(index=False))
''')

code(r'''
# 7. No teste: indisponibilidade das estações elegíveis, dia a dia
ARQ_DIARIO = achar(f"06_dados/chuva_diaria_qc_h{DESLOC_H}.parquet")
DV = pd.read_parquet(ARQ_DIARIO, columns=["gauge_code", "dia", "qc_travado", "qc_limpo_diario"])
DV["gauge_code"] = DV["gauge_code"].astype(str)
DV["dia"] = pd.to_datetime(DV["dia"])
ini = TESTE[0] - pd.Timedelta(days=L - 1)
DV = DV[(DV["dia"] >= ini) & (DV["dia"] <= TESTE[1]) & DV["gauge_code"].isin(ELEG)]
# só as elegíveis que têm ao menos um dia válido no teste (as mesmas que pontuam no notebook 05)
ativas = DV.loc[DV["qc_limpo_diario"] & (DV["dia"] >= TESTE[0]), "gauge_code"].unique()
ESTS = sorted(ativas)
DIAS_T = pd.date_range(ini, TESTE[1], freq="D")
ix_d = pd.Index(DIAS_T); ix_e = pd.Index(ESTS)

def matriz(df, col):
    m = np.zeros((len(DIAS_T), len(ESTS)), dtype=bool)
    s = df[df[col]]
    r = ix_d.get_indexer(s["dia"]); c = ix_e.get_indexer(s["gauge_code"])
    ok = (r >= 0) & (c >= 0)
    m[r[ok], c[ok]] = True
    return m

VALIDO = matriz(DV, "qc_limpo_diario")
TRAV_D = matriz(DV, "qc_travado")
DT = DIAS[DIAS["gauge_code"].isin(ESTS) & (DIAS["dia"] >= ini) & (DIAS["dia"] <= TESTE[1])].copy()
DT["leu"] = DT["n_leit"] > 0
LEU = matriz(DT, "leu")
TRAV_N = matriz(DT, "trav_osc")

INDISP = ~VALIDO
SEM_LEIT = INDISP & ~LEU
TRAVOSC = INDISP & LEU & (TRAV_N | TRAV_D)
OUTRO = INDISP & ~SEM_LEIT & ~TRAVOSC
cs = np.vstack([np.zeros((1, len(ESTS)), int), np.cumsum(VALIDO.astype(int), axis=0)])
SEM_JAN = np.ones_like(VALIDO)
SEM_JAN[L - 1:] = (cs[L:] - cs[:-L]) < L

no_teste = DIAS_T >= TESTE[0]
uf_est = info_uso.set_index("gauge_code").loc[ESTS, "state"].to_numpy()
print(f"estações elegíveis ativas no teste: {len(ESTS)}", pd.Series(uf_est).value_counts().to_dict())
for nome, M in [("indisponível", INDISP), ("sem leitura", SEM_LEIT), ("travado/oscilando", TRAVOSC),
                ("outro motivo", OUTRO), ("sem janela completa", SEM_JAN)]:
    print(f"  {nome:22s}: {100 * M[no_teste].mean():5.2f}% dos estação-dias do teste")
''')

code(r'''
# 8. A estatística e o teste placebo (pré-registrados)
D0, D1 = TESTE[0], TESTE[1]
pos = {d: i for i, d in enumerate(DIAS_T)}
MATS = {"T_indisp": INDISP, "T_travado": TRAVOSC, "T_sem_janela": SEM_JAN, "T_sem_leitura": SEM_LEIT}
SOMA = {k: {u: M[:, uf_est == u].sum(axis=1) for u in UFS} for k, M in MATS.items()}
N_U = {u: int((uf_est == u).sum()) for u in UFS}

def mascara(janelas):
    """janelas: lista de (uf, início, fim). Devolve, por UF, o vetor booleano de dias cobertos."""
    m = {u: np.zeros(len(DIAS_T), bool) for u in UFS}
    for u, a, b in janelas:
        m[u][pos[a]:pos[b] + 1] = True
    return m

def estat(m):
    out = {}
    for k in MATS:
        num = sum(SOMA[k][u][m[u]].sum() for u in UFS)
        den = sum(m[u].sum() * N_U[u] for u in UFS)
        out[k] = num / den if den else np.nan
    return out

JAN_OBS = [(r.UF, max(r.janela_inicio, D0), min(r.data_fim, D1)) for r in SEV.itertuples()
           if r.UF in UFS and r.data_fim >= D0 and r.janela_inicio <= D1]
M_OBS = mascara(JAN_OBS)
OBS = estat(M_OBS)
OCUP = mascara([(r.UF, max(r.janela_inicio, D0), min(r.data_fim, D1)) for r in EV.itertuples()
                if r.UF in UFS and r.data_fim >= D0 and r.janela_inicio <= D1])

rng = np.random.default_rng(SEMENTE)
offsets = np.array([s for s in range(-365, 366) if abs(s) >= 30])
PLAC, perdidos = [], 0
for _ in range(N_SORTEIOS):
    jan = []
    for u, a, b in JAN_OBS:
        for _t in range(200):
            s = pd.Timedelta(days=int(rng.choice(offsets)))
            a2, b2 = a + s, b + s
            if a2 < D0 or b2 > D1 or OCUP[u][pos[a2]:pos[b2] + 1].any():
                continue
            jan.append((u, a2, b2)); break
        else:
            perdidos += 1
    PLAC.append(estat(mascara(jan)))
PLAC = pd.DataFrame(PLAC)
res = []
for k in MATS:
    p = (1 + (PLAC[k] >= OBS[k]).sum()) / (1 + len(PLAC))
    res.append({"estatistica": k, "observado_pct": 100 * OBS[k], "placebo_mediana_pct": 100 * PLAC[k].median(),
                "placebo_p95_pct": 100 * PLAC[k].quantile(0.95), "razao_obs_mediana": OBS[k] / PLAC[k].median(),
                "p_valor": p})
RES = pd.DataFrame(res)
RES.to_csv(os.path.join(PASTA_SAIDA, "07_teste_placebo.csv"), index=False)
PLAC.to_csv(os.path.join(PASTA_SAIDA, "07_placebo_sorteios.csv"), index=False)
print(f"janelas severas no teste: {len(JAN_OBS)} | episódios que não acharam lugar em algum sorteio: {perdidos}")
print(RES.round(4).to_string(index=False))

# por UF e por estação (para o mapa): dentro x fora dos episódios severos
linhas = []
for j, g in enumerate(ESTS):
    u = uf_est[j]
    dentro = M_OBS[u] & no_teste
    fora = ~M_OBS[u] & no_teste
    linhas.append({"gauge_code": g, "state": u,
                   "pct_indisp_dentro": 100 * INDISP[dentro, j].mean() if dentro.any() else np.nan,
                   "pct_indisp_fora": 100 * INDISP[fora, j].mean(),
                   "pct_trav_dentro": 100 * TRAVOSC[dentro, j].mean() if dentro.any() else np.nan,
                   "pct_trav_fora": 100 * TRAVOSC[fora, j].mean()})
PEV = pd.DataFrame(linhas)
PEV["excesso_pp"] = PEV["pct_indisp_dentro"] - PEV["pct_indisp_fora"]
PEV = PEV.merge(info_uso[["gauge_code", "network", "lat", "long"]], on="gauge_code", how="left")
PEV.to_csv(os.path.join(PASTA_SAIDA, "07_episodios_por_estacao.csv"), index=False)
print("\nPor UF, % de estação-dias indisponíveis, dentro e fora dos episódios severos:")
print(PEV.groupby("state")[["pct_indisp_dentro", "pct_indisp_fora", "pct_trav_dentro", "pct_trav_fora"]].mean().round(2).to_string())

# por episódio: fração das estações da UF sem janela completa no pior dia do episódio
ep = []
for r in SEV.itertuples():
    if r.UF not in UFS or r.data_fim < D0:
        continue
    a, b = pos[max(r.janela_inicio, D0)], pos[min(r.data_fim, D1)]
    cols = uf_est == r.UF
    fr = SEM_JAN[a:b + 1][:, cols].mean(axis=1)
    ep.append({"id_evento": r.id_evento, "UF": r.UF, "data_inicio": r.data_inicio.date(),
               "pct_sem_janela_pior_dia": round(100 * fr.max(), 1), "pct_sem_janela_media": round(100 * fr.mean(), 1)})
EPI = pd.DataFrame(ep)
EPI.to_csv(os.path.join(PASTA_SAIDA, "07_episodios_sem_janela.csv"), index=False)
print("\nEpisódios severos em que a UF mais perdeu janelas completas:")
print(EPI.nlargest(8, "pct_sem_janela_pior_dia").to_string(index=False))
''')

code(r'''
# 9. Figuras
import matplotlib
matplotlib.use("Agg") if RAIZ_TESTE else None
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.formatter.use_locale": False})
virg = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")

CONTORNO = None
if not RAIZ_TESTE:
    try:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "geobr"], check=False)
        import geobr
        CONTORNO = geobr.read_state(year=2020)
        CONTORNO = CONTORNO[CONTORNO["abbrev_state"].isin(UFS)]
    except Exception as e:
        print("Sem contorno dos estados (o mapa sai só com os pontos):", type(e).__name__)

def contorno(ax):
    if CONTORNO is not None:
        CONTORNO.boundary.plot(ax=ax, color="#8A96A3", linewidth=0.8)
    ax.set_aspect("equal"); ax.set_xlabel("longitude"); ax.set_ylabel("latitude")

# Figura 1: onde as leituras travam (1995–2025)
fig, ax = plt.subplots(figsize=(8, 7.5))
contorno(ax)
z = pe[pe["n_leit"] >= 1000]
zero = z[z["pct_leit_trav_osc"] == 0]
pos_ = z[z["pct_leit_trav_osc"] > 0].sort_values("pct_leit_trav_osc")
ax.scatter(zero["long"], zero["lat"], s=6, c="#C9D2D8", label=f"sem leitura travada ({len(zero)})")
sc = ax.scatter(pos_["long"], pos_["lat"], s=14, c=pos_["pct_leit_trav_osc"].clip(upper=5), cmap="Oranges",
                vmin=0, vmax=5, edgecolors="#6B3A0A", linewidths=0.3, label=f"com leitura travada ({len(pos_)})")
cb = fig.colorbar(sc, ax=ax, shrink=0.7); cb.set_label("% das leituras travadas ou oscilando (teto de 5%)")
ax.set_title("Onde os pluviômetros travam: RS e SC, 1995–2025", loc="left", fontweight="bold")
ax.legend(loc="lower right", frameon=False, fontsize=9)
fig.text(0.01, 0.01, "Estações com ao menos 1.000 leituras. Fonte: elaboração própria, UNIPLU-BR, notebook 07.", fontsize=8, color="#4A5568")
fig.tight_layout(); fig.savefig(os.path.join(PASTA_SAIDA, "07_mapa_travamento.png"), dpi=200); plt.show() if not RAIZ_TESTE else None

# Figura 2: quando (mapa de calor ano x mês)
hm = ano_mes.pivot(index="ano", columns="mes", values="frac_dias_trav_osc") * 100
fig, ax = plt.subplots(figsize=(8, 8))
im = ax.imshow(hm.values, aspect="auto", cmap="Oranges", vmin=0)
ax.set_xticks(range(12)); ax.set_xticklabels(["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"])
ax.set_yticks(range(len(hm.index))); ax.set_yticklabels(hm.index, fontsize=8)
cb = fig.colorbar(im, ax=ax, shrink=0.7); cb.set_label("% das estação-dias com leitura travada ou oscilando")
ax.set_title("Quando os pluviômetros travam", loc="left", fontweight="bold")
fig.text(0.01, 0.01, "Fonte: elaboração própria, UNIPLU-BR, notebook 07.", fontsize=8, color="#4A5568")
fig.tight_layout(); fig.savefig(os.path.join(PASTA_SAIDA, "07_calor_ano_mes.png"), dpi=200); plt.show() if not RAIZ_TESTE else None

# Figura 3: o teste, dia a dia, com os episódios severos sombreados
fig, axs = plt.subplots(len(UFS), 1, figsize=(11, 3.2 * len(UFS)), sharex=True)
axs = np.atleast_1d(axs)
for ax, u in zip(axs, UFS):
    col = uf_est == u
    serie = pd.Series(100 * INDISP[:, col].mean(axis=1), index=DIAS_T)[no_teste]
    trav = pd.Series(100 * TRAVOSC[:, col].mean(axis=1), index=DIAS_T)[no_teste]
    for uu, a, b in JAN_OBS:
        if uu == u:
            ax.axvspan(a, b + pd.Timedelta(days=1), color="#2a78d6", alpha=0.18, lw=0)
    ax.plot(serie.index, serie.values, color="#14213D", lw=0.9, label="indisponível (qualquer motivo)")
    ax.plot(trav.index, trav.values, color="#eb6834", lw=0.9, label="travado ou oscilando")
    ax.set_ylabel("% das estações"); ax.set_title(f"{u}: {N_U[u]} estações elegíveis", loc="left", fontweight="bold")
axs[0].legend(loc="upper left", frameon=False, fontsize=9)
fig.text(0.01, 0.005, "Faixas azuis: episódios severos do REInDesC (de 3 dias antes ao fim). Fonte: elaboração própria, notebook 07.", fontsize=8, color="#4A5568")
fig.tight_layout(); fig.savefig(os.path.join(PASTA_SAIDA, "07_serie_teste.png"), dpi=200); plt.show() if not RAIZ_TESTE else None

# Figura 4: mapa do excesso de indisponibilidade nos episódios severos
fig, ax = plt.subplots(figsize=(8, 7.5))
contorno(ax)
q = PEV.dropna(subset=["excesso_pp"]).sort_values("excesso_pp", key=abs)
lim = max(5.0, float(np.nanpercentile(np.abs(q["excesso_pp"]), 95))) if len(q) else 5.0
sc = ax.scatter(q["long"], q["lat"], s=16, c=q["excesso_pp"], cmap="RdBu_r",
                norm=TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim), edgecolors="#4A5568", linewidths=0.3)
cb = fig.colorbar(sc, ax=ax, shrink=0.7); cb.set_label("indisponível nos episódios − fora deles (pontos percentuais)")
ax.set_title("Quem some justo nas cheias severas (2023–2025)", loc="left", fontweight="bold")
fig.text(0.01, 0.01, "Vermelho: mais falha nos episódios que no resto do teste. Fonte: elaboração própria, notebook 07.", fontsize=8, color="#4A5568")
fig.tight_layout(); fig.savefig(os.path.join(PASTA_SAIDA, "07_mapa_excesso_episodios.png"), dpi=200); plt.show() if not RAIZ_TESTE else None

# Figura 5: o teste placebo
fig, axs = plt.subplots(1, 3, figsize=(12, 3.6))
for ax, k, t in zip(axs, ["T_indisp", "T_travado", "T_sem_janela"],
                    ["indisponível", "travado ou oscilando", "sem janela completa"]):
    ax.hist(100 * PLAC[k], bins=30, color="#C9D2D8")
    ax.axvline(100 * OBS[k], color="#eb6834", lw=2)
    p = float(RES.set_index("estatistica").loc[k, "p_valor"])
    ax.set_title(f"{t}\nobservado {virg(100 * OBS[k], 2)}% | p = {virg(p, 3)}", loc="left", fontsize=10)
    ax.set_xlabel("% dos estação-dias nos episódios")
axs[0].set_ylabel("sorteios placebo")
fig.tight_layout(); fig.savefig(os.path.join(PASTA_SAIDA, "07_placebo.png"), dpi=200); plt.show() if not RAIZ_TESTE else None
''')

code(r'''
# 10. Registro da execução e o resumo para mandar ao Claude
r = RES.set_index("estatistica")
p = float(r.loc["T_indisp", "p_valor"])
LEITURA = ("há indício de que a indisponibilidade aumenta durante as cheias severas (p < 0,05); é associação, não causa"
           if p < 0.05 else "não há evidência de que a indisponibilidade aumente durante as cheias severas (p >= 0,05)")
log = {"executado_em": pd.Timestamp.now().isoformat(timespec="seconds"), "python": platform.python_version(),
       "pandas": pd.__version__, "hash_decisoes": HASH_DEC, "hash_decisoes_07": HASH_DEC7,
       "lotes": len(LOTES), "estacao_dias": int(len(DIAS)), "leituras": int(DIAS["n_leit"].sum()),
       "leituras_travadas": int(DIAS["n_trav"].sum()), "leituras_oscilando": int(DIAS["n_osc"].sum()),
       "estacoes_teste": len(ESTS), "janelas_severas": len(JAN_OBS), "episodios_sem_lugar_no_placebo": perdidos,
       "resultado": RES.to_dict(orient="records"), "leitura": LEITURA}
with open(os.path.join(PASTA_SAIDA, "07_log_execucao.json"), "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=1, default=str)
print("=" * 70)
print("MANDE ESTA SAÍDA AO CLAUDE")
print(json.dumps({k: log[k] for k in ("hash_decisoes_07", "leituras", "leituras_travadas", "leituras_oscilando",
                                       "estacoes_teste", "janelas_severas", "episodios_sem_lugar_no_placebo")},
                 ensure_ascii=False))
print(RES.round(4).to_string(index=False))
print("LEITURA:", LEITURA)
print("Arquivos em 05_saidas: 07_*.csv, 07_*.png e 07_log_execucao.json")
''')

md("""
## Sensibilidades — NÃO pré-registradas

Decididas em 21/11/2026, **depois** de ver o resultado da célula 8. Por isso não substituem o teste
pré-registrado; servem para saber se ele está contaminado.

- **S1, corte no fim da série.** A série Hidroweb diário do UNIPLU-BR termina em 30/09/2025 (é a maior
  rede entre as elegíveis). Depois disso a indisponibilidade salta por falta de dado na base, não por
  falha de aparelho, e vários episódios severos caem nesse trecho. S1 refaz o mesmo teste só até o corte.
- **S2, a rede do Cemaden.** Quase todo o travamento está nela, mas ela não é elegível, então ficou fora
  do teste pré-registrado. S2 pergunta se as estações do Cemaden travam mais nos episódios severos:
  leituras travadas ou oscilando, sobre as estação-dias com leitura.
""")

code(r"""
# 11. Sensibilidades S1 e S2 (não pré-registradas)
D1C = pd.Timestamp(os.environ.get("NB07_CORTE", "2025-09-30"))

def placebo(janelas, NUM, DEN, fim, n=N_SORTEIOS, semente=SEMENTE):
    rng = np.random.default_rng(semente)
    def est(m):
        num = sum(NUM[u][m[u]].sum() for u in UFS)
        den = sum(DEN[u][m[u]].sum() for u in UFS)
        return num / den if den else np.nan
    obs = est(mascara(janelas))
    vals = []
    for _ in range(n):
        jan = []
        for u, a, b in janelas:
            for _t in range(200):
                s = pd.Timedelta(days=int(rng.choice(offsets)))
                a2, b2 = a + s, b + s
                if a2 < D0 or b2 > fim or OCUP[u][pos[a2]:pos[b2] + 1].any():
                    continue
                jan.append((u, a2, b2)); break
        vals.append(est(mascara(jan)))
    vals = np.array(vals, dtype=float)
    ok = ~np.isnan(vals)
    p = (1 + (vals[ok] >= obs).sum()) / (1 + ok.sum()) if ok.any() and not np.isnan(obs) else np.nan
    return obs, vals, p

linhas = []
J1 = [(u, a, b) for (u, a, b) in JAN_OBS if b <= D1C]
DEN_E = {u: np.full(len(DIAS_T), N_U[u], dtype=float) for u in UFS}
print(f"S1: episódios severos até {D1C.date()}: {len(J1)} de {len(JAN_OBS)}")
for k in MATS:
    o, v, p = placebo(J1, SOMA[k], DEN_E, D1C)
    linhas.append({"sensibilidade": "S1_corte_" + str(D1C.date()), "estatistica": k, "observado_pct": 100 * o,
                   "placebo_mediana_pct": 100 * np.nanmedian(v), "placebo_p95_pct": 100 * np.nanpercentile(v, 95),
                   "p_valor": p})

C = DIAS[(DIAS["network"] == "CEMADEN") & (DIAS["dia"] >= D0) & (DIAS["dia"] <= D1) & (DIAS["n_leit"] > 0)]
if len(C):
    g = C.groupby(["state", "dia"]).agg(n=("gauge_code", "size"), t=("trav_osc", "sum")).reset_index()
    NUMC = {u: np.zeros(len(DIAS_T)) for u in UFS}
    DENC = {u: np.zeros(len(DIAS_T)) for u in UFS}
    for u in UFS:
        gu = g[g["state"] == u]
        ii = ix_d.get_indexer(gu["dia"])
        NUMC[u][ii[ii >= 0]] = gu["t"].to_numpy()[ii >= 0]
        DENC[u][ii[ii >= 0]] = gu["n"].to_numpy()[ii >= 0]
    print(f"S2: estações do Cemaden com leitura no teste: {C['gauge_code'].nunique()}")
    for nome, jan, fim in (("S2_cemaden_teste_todo", JAN_OBS, D1), ("S2_cemaden_ate_corte", J1, D1C)):
        o, v, p = placebo(jan, NUMC, DENC, fim)
        linhas.append({"sensibilidade": nome, "estatistica": "travado_ou_oscilando", "observado_pct": 100 * o,
                       "placebo_mediana_pct": 100 * np.nanmedian(v), "placebo_p95_pct": 100 * np.nanpercentile(v, 95),
                       "p_valor": p})
else:
    print("S2: nenhuma estação do Cemaden com leitura no teste; S2 não se aplica.")
SENS = pd.DataFrame(linhas)
SENS.to_csv(os.path.join(PASTA_SAIDA, "07_sensibilidades.csv"), index=False)
print("=" * 70)
print("SENSIBILIDADES (NÃO pré-registradas) — MANDE AO CLAUDE")
print(SENS.round(4).to_string(index=False))
""")

NB = {"cells": CELLS, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                   "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                             "07_falhas_dos_sensores.ipynb")
with open(destino, "w", encoding="utf-8") as f:
    json.dump(NB, f, ensure_ascii=False, indent=1)
print("gravado:", destino, "|", len(CELLS), "células")
