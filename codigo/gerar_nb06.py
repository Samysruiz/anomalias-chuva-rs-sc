# -*- coding: utf-8 -*-
"""Gera o notebook 06 — fase 2, versão mínima: autoencoder ajustado e chuva das vizinhas.

Uso:  python gerar_nb06.py [destino.ipynb]
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
# 06 — Fase 2, versão mínima: o autoencoder ajustado e a chuva das vizinhas

**Exploratório.** O período de teste (2023–2025) já foi visto na fase 1, cujo resultado pré-registrado
(achado 08) não muda. Este notebook segue o pré-registro `decisoes_fase2.json` v1.0, de 20/11/2026,
gravado antes de qualquer ajuste.

**A pergunta:** dar ao autoencoder a chuva média das estações vizinhas (até 50 km) faz com que ele supere
o limiar de chuva acumulada?

**Duas entradas, a mesma grade de ajuste:**

| Entrada | O que o modelo vê por janela |
|---|---|
| E0 | 15 dias da chuva da própria estação (como na fase 1) |
| E1 | E0 + 15 dias da chuva média das vizinhas elegíveis a até 50 km |

**Regras que impedem trapaça:**

1. O ajuste do autoencoder escolhe a configuração pela PR-AUC diária **na validação 2020–2022**, com
   rótulos do REInDesC de 2020–2022. Os rótulos do teste não participam de nenhuma escolha.
2. E0 e E1 recebem a mesma grade (gargalo 3, 8 ou igual ao PCA; taxa de aprendizado 10⁻³ ou 3 × 10⁻⁴).
3. Todas as comparações usam o mesmo conjunto de janelas: as completas em E1.
4. O teste é pontuado uma única vez, no fim, com tudo congelado.
5. Os critérios de sucesso S1 e S2 estão fixados no pré-registro.

**Antes de rodar:** exporte do REInDesC as ocorrências de RS e SC de **2020 a 2022** e grave em
`06_dados/` com nome começando por **`validacao_reindesc`** (por exemplo `validacao_reindesc_2020_2022.csv`).
O nome **não** pode começar por `reindesc`, senão o notebook 03 misturaria esses rótulos com os do teste.

**Se o Colab cair:** rode de novo. Cada treino terminado fica gravado em `06_dados/_modelos_06/` e é
reaproveitado, sem treinar outra vez.
""")

code(r'''
# 1. Configuração, Drive e caminhos
import os, sys, json, time, gc, glob, hashlib, platform, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 220)

RAIZ_TESTE = os.environ.get("NB06_RAIZ_TESTE")
if RAIZ_TESTE:
    RAIZ = RAIZ_TESTE
else:
    from google.colab import drive
    drive.mount("/content/drive", force_remount=False)
    BASE = "/content/drive/MyDrive"
    candidatos = [
        os.path.join(BASE, "NÃO SUPERVISIONADO", "PROJETO FINAL WAG"),
        os.path.join(BASE, "NÃOSUPERVISIONADO", "PROJETO FINAL WAG"),
        os.path.join(BASE, "PROJETO FINAL WAG"),
    ]
    achados = [c for c in candidatos if os.path.isdir(c)]
    if not achados:
        raise SystemExit("não achei a pasta PROJETO FINAL WAG. Candidatos testados:\n  " + "\n  ".join(candidatos))
    RAIZ = achados[0]

PASTA_DADOS = os.path.join(RAIZ, "06_dados")
PASTA_SAIDA = os.path.join(RAIZ, "05_saidas")
PASTA_SCRIPTS = os.path.join(RAIZ, "02_scripts")
PASTA_MODELOS = os.path.join(PASTA_DADOS, "_modelos_06")
os.makedirs(PASTA_SAIDA, exist_ok=True)
os.makedirs(PASTA_MODELOS, exist_ok=True)
print("raiz    :", RAIZ)
print("modelos :", PASTA_MODELOS)
''')

code(r'''
# 2. Pré-registros: fase 1 (v1.2) e fase 2 (v1.0). Qualquer divergência de hash para o notebook.
def le_com_hash(caminho):
    with open(caminho, "rb") as f:
        b = f.read()
    return json.loads(b.decode("utf-8")), hashlib.sha256(b).hexdigest()[:16]

DEC, HASH_DEC = le_com_hash(os.path.join(PASTA_SCRIPTS, "decisoes.json"))
DEC2, HASH_DEC2 = le_com_hash(os.path.join(PASTA_SCRIPTS, "decisoes_fase2.json"))

HASH_FASE1 = {"1.2": "d4c58a627755c8f9"}
HASH_FASE2 = {"1.0": "c0e7df1aded21cd7"}
if HASH_FASE1.get(DEC["versao"]) != HASH_DEC:
    raise SystemExit(f"decisoes.json versão {DEC['versao']} com hash {HASH_DEC}: esperado o da v1.2 "
                     f"(d4c58a627755c8f9). Copie o arquivo do GitHub para 02_scripts.")
if HASH_FASE2.get(DEC2["versao"]) != HASH_DEC2:
    raise SystemExit(f"decisoes_fase2.json versão {DEC2['versao']} com hash {HASH_DEC2}: esperado c0e7df1aded21cd7. "
                     f"O arquivo foi alterado sem nova versão. Copie o do GitHub para 02_scripts.")

# --- fase 1, herdado sem mudança ---
JANELA = int(DEC["entrada_modelo"]["janela_dias"])
PART = {k: (pd.Timestamp(v[0]), pd.Timestamp(v[1])) for k, v in DEC["particao"].items()
        if isinstance(v, list) and len(v) == 2}
DESLOC_PRINCIPAL = 12
DIAS_ANTES = int(DEC["avaliacao"]["dias_antes_do_inicio"])

# --- fase 2, tudo lido do pré-registro ---
VIZ = DEC2["vizinhanca"]
RAIO_KM = float(VIZ["raio_km"])
MIN_VIZINHAS = int(VIZ["minimo_vizinhas_com_dado_no_dia"])
AJ = DEC2["ajuste_autoencoder"]
GRADE_GARGALO = list(AJ["grade"]["gargalo"])
GRADE_LR = [float(x) for x in AJ["grade"]["taxa_aprendizado"]]
AE_LOTE = int(AJ["lote"])
AE_EPOCAS = int(os.environ.get("NB06_EPOCAS", AJ["epocas_maximas"]))
AE_PACIENCIA = int(AJ["paciencia"])
SEMENTE_AJUSTE = int(AJ["semente_do_ajuste"])
MF = DEC2["modelos_finais"]
SEMENTES = list(MF["sementes"])
VAR_PCA = 0.90
IF_ARVORES = int(MF["isolation_forest"]["arvores"])
IF_AMOSTRA = int(MF["isolation_forest"]["amostra"])
MAX_JANELAS_TREINO = int(os.environ.get("NB06_MAX_TREINO", DEC2["teto_janelas_treino"]))
SEMENTE_AMOSTRA = int(DEC2["semente_amostra_treino"])
PERIODO_VAL_ROTULOS = tuple(pd.Timestamp(x) for x in DEC2["rotulos_validacao"]["periodo"])
DATA_LIMITE = pd.Timestamp(DEC2["data_limite"])

# --- NÃO pré-registrado: implementação, igual à fase 1 onde existia ---
GAP_EPISODIO_DIAS = 2            # regra do notebook 03
MIN_JANELAS_VALIDACAO = 100      # regra do notebook 05
Q_LIMIAR = 0.99
ALVOS = (0.01, 0.03)
DESVIO_MINIMO = 1e-6
NAO_PREREGISTRADOS = {
    "arquitetura do autoencoder": "entrada → (entrada+gargalo)//2 → gargalo → (entrada+gargalo)//2 → entrada, ReLU entre camadas, como na fase 1",
    "mínimo de janelas de validação para a estação ter limiar": MIN_JANELAS_VALIDACAO,
    "f calibrado por UF": True,
    "piso do desvio na normalização": DESVIO_MINIMO,
    "reaproveitamento de treinos já terminados quando o notebook é rodado de novo": True,
}
if AE_EPOCAS != int(AJ["epocas_maximas"]) or MAX_JANELAS_TREINO != int(DEC2["teto_janelas_treino"]):
    NAO_PREREGISTRADOS["ATENÇÃO: execução reduzida por variável de ambiente (só teste)"] = (AE_EPOCAS, MAX_JANELAS_TREINO)

print(f"decisoes.json v{DEC['versao']} ({HASH_DEC}) | decisoes_fase2.json v{DEC2['versao']} ({HASH_DEC2})")
print("escopo:", DEC2["escopo"])
print(f"vizinhança: {RAIO_KM} km, mínimo {MIN_VIZINHAS} vizinhas com dado no dia")
print(f"grade: gargalo {GRADE_GARGALO} × taxa {GRADE_LR} | {AE_EPOCAS} épocas, paciência {AE_PACIENCIA}")
hoje = pd.Timestamp.now().normalize()
if hoje > DATA_LIMITE:
    print(f"\nATENÇÃO: hoje ({hoje.date()}) passou da data-limite pré-registrada ({DATA_LIMITE.date()}). "
          f"Pelo pré-registro, a fase 2 sai da entrega.")
print("\nNÃO PRÉ-REGISTRADOS:")
for k, v in NAO_PREREGISTRADOS.items():
    print(" -", k, "=", v)
''')

code(r'''
# 3. Entradas: chuva, estações, rótulos do teste e rótulos da validação
arq_chuva = os.path.join(PASTA_DADOS, f"chuva_diaria_qc_h{DESLOC_PRINCIPAL}.parquet")
for c in (arq_chuva, os.path.join(PASTA_DADOS, "estacoes_elegiveis.parquet"),
          os.path.join(PASTA_DADOS, "eventos_reindesc.parquet")):
    if not os.path.exists(c):
        raise SystemExit(f"não achei {c}. Rode o notebook 03 antes.")

D = pd.read_parquet(arq_chuva)
EST = pd.read_parquet(os.path.join(PASTA_DADOS, "estacoes_elegiveis.parquet"))
EV_TESTE = pd.read_parquet(os.path.join(PASTA_DADOS, "eventos_reindesc.parquet"))
D["dia"] = pd.to_datetime(D["dia"])
EST_EL = EST[EST["elegivel"]].copy()
D = D[D["gauge_code"].isin(set(EST_EL["gauge_code"])) & D["qc_limpo_diario"]].copy()
HIDROWEB = set(EST_EL.loc[EST_EL["subconjunto_hidroweb"], "gauge_code"])
UF_DE = EST_EL.set_index("gauge_code")["state"]
print(f"estações elegíveis: {len(EST_EL)} | dias limpos: {len(D):,}")
print(f"episódios do teste: {len(EV_TESTE)}, severos {int(EV_TESTE['severo'].sum())}")

def episodios(oc):
    """Mesma regra do notebook 03, célula 19."""
    oc = oc.sort_values(["UF", "Data"]).reset_index(drop=True)
    dif = oc.groupby("UF")["Data"].diff()
    oc["_novo"] = (dif.dt.days > GAP_EPISODIO_DIAS) | dif.isna()
    oc["id_evento"] = oc["UF"] + "_" + oc.groupby("UF")["_novo"].cumsum().astype(str).str.zfill(3)
    ev = oc.groupby(["UF", "id_evento"]).agg(
        data_inicio=("Data", "min"), data_fim=("Data", "max"),
        n_ocorrencias=("ID ocorrência", "size"), n_municipios=("Município", "nunique")).reset_index()
    mag = pd.crosstab(oc["id_evento"], oc["Magnitude"]).reindex(columns=["GP", "MP", "PP"], fill_value=0)
    ev = ev.merge(mag.rename(columns={"GP": "n_gp", "MP": "n_mp", "PP": "n_pp"}), on="id_evento", how="left")
    ev["severo"] = ev[["n_gp", "n_mp"]].sum(axis=1) >= 1
    ev["extenso"] = ev["n_municipios"] >= 5
    ev["janela_inicio"] = ev["data_inicio"] - pd.Timedelta(days=DIAS_ANTES)
    ev["janela_fim"] = ev["data_fim"]
    return ev

arqs_val = sorted(glob.glob(os.path.join(PASTA_DADOS, "validacao_reindesc*.csv")))
if not arqs_val:
    raise SystemExit("faltam os rótulos da validação: exporte do REInDesC as ocorrências de RS e SC de "
                     "2020 a 2022 e grave em 06_dados/ como validacao_reindesc_2020_2022.csv")
OCV = pd.concat([pd.read_csv(a, sep=";", encoding="utf-8-sig") for a in arqs_val], ignore_index=True)   # a exportação vem com BOM
OCV.columns = [c.strip() for c in OCV.columns]
OCV["Data"] = pd.to_datetime(OCV["Data"])
OCV = OCV.drop_duplicates("ID ocorrência")
fora = ~OCV["Data"].between(*PERIODO_VAL_ROTULOS)
if fora.any():
    print(f"ATENÇÃO: {int(fora.sum())} ocorrências fora de 2020–2022 descartadas")
OCV = OCV[~fora & OCV["UF"].isin(["RS", "SC"])]
EV_VAL = episodios(OCV)
print(f"\nvalidação: {len(OCV)} ocorrências → {len(EV_VAL)} episódios, {int(EV_VAL['severo'].sum())} severos")
print(pd.crosstab(EV_VAL["UF"], EV_VAL["severo"]).to_string())
if int(EV_VAL["severo"].sum()) < 5:
    print("ATENÇÃO: menos de 5 episódios severos na validação; o ajuste fica pouco informativo (registrar).")
''')

md("""
## As duas entradas

A chuva das vizinhas de cada estação, em cada dia, é a média das **outras** estações elegíveis a até 50 km
que têm dado limpo naquele dia, exigindo pelo menos 2 delas. Abaixo disso, o dia fica ausente e a janela
que o contiver é descartada. Cada série (própria e vizinhas) é padronizada por estação com média e desvio
**só do treino**.
""")

code(r'''
# 4. Matriz de chuva própria e da vizinhança
from numpy.lib.stride_tricks import sliding_window_view

M = D.pivot_table(index="dia", columns="gauge_code", values="rain_mm", aggfunc="first").sort_index()
M = M.reindex(pd.date_range(M.index.min(), M.index.max(), freq="D"))
dias = M.index.to_numpy()
estacoes = M.columns.to_numpy()
A = M.to_numpy(dtype="float32")

coord = EST_EL.set_index("gauge_code").loc[estacoes, ["lat", "long"]].to_numpy(dtype="float64")
la, lo = np.radians(coord[:, 0]), np.radians(coord[:, 1])
dlat = la[:, None] - la[None, :]
dlon = lo[:, None] - lo[None, :]
h = np.sin(dlat / 2) ** 2 + np.cos(la)[:, None] * np.cos(la)[None, :] * np.sin(dlon / 2) ** 2
DIST = 2 * 6371.0 * np.arcsin(np.sqrt(h))
ADJ = ((DIST <= RAIO_KM) & ~np.eye(len(estacoes), dtype=bool)).astype("float32")
print(f"vizinhas por estação (até {RAIO_KM:.0f} km): mediana {np.median(ADJ.sum(1)):.0f}, "
      f"sem nenhuma: {int((ADJ.sum(1) == 0).sum())}")

tem = (~np.isnan(A)).astype("float32")
soma = np.nan_to_num(A) @ ADJ
cont = tem @ ADJ
V = np.where(cont >= MIN_VIZINHAS, soma / np.maximum(cont, 1), np.nan).astype("float32")
print(f"dias-estação com vizinhança válida: {np.isfinite(V).mean() * 100:.1f}%")

def padroniza(X):
    ini, fim = PART["treino"]
    m = (dias >= np.datetime64(ini)) & (dias <= np.datetime64(fim))
    mu, sd = np.nanmean(X[m], axis=0), np.nanstd(X[m], axis=0)
    ruim = ~np.isfinite(mu) | ~np.isfinite(sd) | (sd < DESVIO_MINIMO)
    Z = ((X - np.where(ruim, 0, mu)) / np.where(ruim, 1, sd)).astype("float32")
    Z[:, ruim] = np.nan
    return Z, int(ruim.sum())

Z_prop, r1 = padroniza(A)
Z_viz, r2 = padroniza(V)
print(f"estações sem estatística de treino: própria {r1}, vizinhança {r2} (excluídas da entrada correspondente)")

W_prop = sliding_window_view(Z_prop, JANELA, axis=0)
W_viz = sliding_window_view(Z_viz, JANELA, axis=0)
W_mm = sliding_window_view(A, JANELA, axis=0)
dias_rotulo = dias[JANELA - 1:]
valida = ~np.isnan(W_prop).any(axis=2) & ~np.isnan(W_viz).any(axis=2)
valida_e0 = ~np.isnan(W_prop).any(axis=2)
print(f"janelas completas em E0: {int(valida_e0.sum()):,} | completas em E0 e E1 (usadas): {int(valida.sum()):,} "
      f"({100 * valida.sum() / max(valida_e0.sum(), 1):.1f}%)")
''')

code(r'''
# 5. Partição (mesma regra da fase 1) e amostra de treino
def faixa(nome):
    ini, fim = (np.datetime64(x) for x in PART[nome])
    primeiro = dias_rotulo - np.timedelta64(JANELA - 1, "D")
    dentro = (primeiro >= ini) & (dias_rotulo <= fim)
    if nome in ("treino", "validacao"):
        dentro &= dias_rotulo <= (fim - np.timedelta64(JANELA, "D"))
    return dentro

IDX = {}
for nome in ("treino", "validacao", "teste"):
    i_dia, i_est = np.where(valida & faixa(nome)[:, None])
    IDX[nome] = (i_dia, i_est)
    print(f"{nome:10s}: {len(i_dia):>9,} janelas | {len(np.unique(i_est)):>4} estações")

i_d, i_e = IDX["treino"]
if len(i_d) > MAX_JANELAS_TREINO:
    sel = np.sort(np.random.default_rng(SEMENTE_AMOSTRA).choice(len(i_d), MAX_JANELAS_TREINO, replace=False))
    IDX["treino"] = (i_d[sel], i_e[sel])
    print(f"treino amostrado: {MAX_JANELAS_TREINO:,} janelas (semente {SEMENTE_AMOSTRA})")

def monta(nome, entrada):
    i_dia, i_est = IDX[nome]
    X = W_prop[i_dia, i_est, :]
    if entrada == "E1":
        X = np.concatenate([X, W_viz[i_dia, i_est, :]], axis=1)
    return np.ascontiguousarray(X, dtype="float32")

def quadro(nome):
    i_dia, i_est = IDX[nome]
    g = estacoes[i_est]
    return pd.DataFrame({"gauge_code": g, "uf": pd.Series(g).map(UF_DE).to_numpy(),
                         "dia": pd.to_datetime(dias_rotulo[i_dia])})

Q = {n: quadro(n) for n in ("validacao", "teste")}
assert Q["validacao"]["uf"].notna().all() and Q["teste"]["uf"].notna().all(), "estação sem UF"
''')

code(r'''
# 6. Funções de alarme e avaliação (iguais às do notebook 05)
from sklearn.metrics import average_precision_score

def limiares(df, q=Q_LIMIAR):
    g = df.groupby("gauge_code")["escore"]
    return g.quantile(q)[g.size() >= MIN_JANELAS_VALIDACAO]

def fracao_diaria(df, thr):
    t = df["gauge_code"].map(thr)
    m = t.notna().to_numpy()
    d = pd.DataFrame({"uf": df["uf"].to_numpy()[m], "dia": df["dia"].to_numpy()[m],
                      "acima": df["escore"].to_numpy()[m] > t.to_numpy()[m]})
    r = d.groupby(["uf", "dia"])["acima"].agg(ativas="size", acima="sum").reset_index()
    r["frac"] = r["acima"] / r["ativas"]
    return r

def calibrar_f(v, alvo):
    v = np.sort(np.asarray(v)); n = len(v)
    for c in np.unique(v[v > 0]):
        taxa = (n - np.searchsorted(v, c, side="left")) / n
        if taxa <= alvo:
            return float(c), float(taxa)
    return float(v.max() + 1e-9), 0.0

def janelas_de(ev, so_severos):
    s = set()
    for e in ev[ev["severo"]].itertuples(index=False) if so_severos else ev.itertuples(index=False):
        for d in pd.date_range(e.janela_inicio, e.janela_fim, freq="D"):
            s.add((e.UF, d))
    return s

JAN_VAL_SEV = janelas_de(EV_VAL, True)
JAN_TE_SEV, JAN_TE_TODOS = janelas_de(EV_TESTE, True), janelas_de(EV_TESTE, False)

def pr_auc(F, janelas):
    y = np.array([k in janelas for k in zip(F["uf"], F["dia"])])
    if y.sum() == 0:
        return np.nan
    return float(average_precision_score(y, F["frac"]))

def avalia_teste(va, te, thr):
    """Recall dos severos, falsos por ano e PR-AUC no teste, para 1% e 3% dos dias."""
    Fv, Ft = fracao_diaria(va, thr), fracao_diaria(te, thr)
    out = {"pr_auc": pr_auc(Ft, JAN_TE_SEV)}
    sev = EV_TESTE[EV_TESTE["severo"]]
    for alvo in ALVOS:
        fs = {uf: calibrar_f(g["frac"], alvo)[0] for uf, g in Fv.groupby("uf")}
        a = Ft.assign(alarme=Ft["frac"] >= Ft["uf"].map(fs))
        dias_al = {uf: set(g.loc[g["alarme"], "dia"]) for uf, g in a.groupby("uf")}
        det = [any(d in dias_al.get(e.UF, set()) for d in pd.date_range(e.janela_inicio, e.janela_fim))
               for e in sev.itertuples(index=False)]
        anos = {uf: g["dia"].nunique() / 365.25 for uf, g in a.groupby("uf")}
        falso = a["alarme"].to_numpy() & np.array([k not in JAN_TE_TODOS for k in zip(a["uf"], a["dia"])])
        tag = f"{int(round(alvo * 100))}%"
        out[f"recall_{tag}"] = float(np.mean(det))
        out[f"falsos_ano_uf_{tag}"] = float(np.mean([falso[(a["uf"] == uf).to_numpy()].sum() / anos[uf] for uf in anos]))
        out[f"alarme_teste_{tag}"] = float(a["alarme"].mean())
    return out

print(f"episódios severos: validação {int(EV_VAL['severo'].sum())}, teste {int(EV_TESTE['severo'].sum())}")
''')

code(r'''
# 7. Peças dos modelos: PCA, autoencoder com checkpoint e retomada, Isolation Forest
import torch
import torch.nn as nn
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest

DISPOSITIVO = "cuda" if torch.cuda.is_available() else "cpu"
print("dispositivo:", DISPOSITIVO)

def camadas_de(dim, gargalo):
    meio = (dim + gargalo) // 2
    seq = [dim, meio, gargalo, meio, dim]
    return [c for i, c in enumerate(seq) if i in (0, 2, 4) or (c != gargalo and c != dim)]

def monta_ae(camadas):
    blocos = []
    for i in range(len(camadas) - 1):
        blocos.append(nn.Linear(camadas[i], camadas[i + 1]))
        if i < len(camadas) - 2:
            blocos.append(nn.ReLU())
    return nn.Sequential(*blocos)

def erro_ae(modelo, X, lote=8192):
    modelo.eval()
    out = np.empty(len(X), dtype="float32")
    with torch.no_grad():
        for i in range(0, len(X), lote):
            b = torch.from_numpy(X[i:i + lote]).to(DISPOSITIVO)
            out[i:i + lote] = ((modelo(b) - b) ** 2).mean(dim=1).cpu().numpy()
    return out

HIST = []

def treina_ae(entrada, gargalo, lr, semente, X_tr, X_va):
    """Treina (ou retoma) um autoencoder. Checkpoint a cada época; melhor modelo pela perda de validação."""
    camadas = camadas_de(X_tr.shape[1], gargalo)
    marca = f"{entrada}_g{gargalo}_lr{lr:g}_s{semente}"
    arq_melhor = os.path.join(PASTA_MODELOS, f"{marca}_melhor.pt")
    arq_fim = os.path.join(PASTA_MODELOS, f"{marca}_fim.json")
    modelo = monta_ae(camadas).to(DISPOSITIVO)
    if os.path.exists(arq_fim) and os.path.exists(arq_melhor):
        info = json.load(open(arq_fim))
        modelo.load_state_dict(torch.load(arq_melhor, map_location=DISPOSITIVO)["estado"])
        print(f"  {marca}: reaproveitado (melhor época {info['melhor_epoca']}, perda {info['melhor_perda']:.5f})")
        return modelo, info
    torch.manual_seed(semente); np.random.seed(semente)
    otim = torch.optim.Adam(modelo.parameters(), lr=lr)
    perda_fn = nn.MSELoss()
    Xt = torch.from_numpy(X_tr)
    melhor, melhor_ep, sem = np.inf, 0, 0
    for ep in range(1, AE_EPOCAS + 1):
        modelo.train()
        ordem = torch.randperm(len(Xt))
        s, n = 0.0, 0
        for i in range(0, len(ordem), AE_LOTE):
            b = Xt[ordem[i:i + AE_LOTE]].to(DISPOSITIVO)
            otim.zero_grad()
            perda = perda_fn(modelo(b), b)
            perda.backward()
            otim.step()
            s += float(perda.detach()) * len(b); n += len(b)
        pva = float(np.mean(erro_ae(modelo, X_va)))
        HIST.append({"entrada": entrada, "gargalo": gargalo, "lr": lr, "semente": semente, "epoca": ep,
                     "perda_treino": s / max(n, 1), "perda_validacao": pva})
        estado = {"epoca": ep, "estado": modelo.state_dict(), "perda_validacao": pva}
        torch.save(estado, os.path.join(PASTA_MODELOS, f"{marca}_ultima_epoca.pt"))   # checkpoint por época
        if pva < melhor - 1e-6:
            melhor, melhor_ep, sem = pva, ep, 0
            torch.save(estado, arq_melhor)
        else:
            sem += 1
            if sem >= AE_PACIENCIA:
                break
    modelo.load_state_dict(torch.load(arq_melhor, map_location=DISPOSITIVO)["estado"])
    info = {"camadas": camadas, "melhor_epoca": melhor_ep, "melhor_perda": melhor, "epocas_rodadas": ep,
            "no_teto": melhor_ep == AE_EPOCAS}
    json.dump(info, open(arq_fim, "w"))
    aviso = "  <-- melhor época no teto" if info["no_teto"] else ""
    print(f"  {marca}: melhor época {melhor_ep}, perda {melhor:.5f}{aviso}")
    return modelo, info

def pr_auc_validacao(esc_va):
    va = Q["validacao"].assign(escore=esc_va)
    return pr_auc(fracao_diaria(va, limiares(va)), JAN_VAL_SEV)

X = {e: {n: monta(n, e) for n in ("treino", "validacao", "teste")} for e in ("E0", "E1")}
PCAS = {e: PCA(n_components=VAR_PCA, svd_solver="full", random_state=0).fit(X[e]["treino"]) for e in X}
for e, p in PCAS.items():
    print(f"{e}: entrada {X[e]['treino'].shape[1]} dims | PCA retém {p.n_components_} componentes "
          f"({p.explained_variance_ratio_.sum() * 100:.1f}%)")
''')

md("""
## Parte 1 — O ajuste, só na validação

Seis configurações por entrada, a mesma grade para E0 e E1, todas com a semente 0. A escolha é pela maior
PR-AUC diária na validação, com os rótulos de 2020–2022. **Nenhum número do teste aparece nesta parte.**
""")

code(r'''
# 8. Ajuste: grade igual para E0 e E1, escolha pela PR-AUC na validação
t0 = time.time()
AJUSTE = []
for e in ("E0", "E1"):
    print(f"\n=== {e} ===")
    for g in GRADE_GARGALO:
        gargalo = int(PCAS[e].n_components_) if g == "igual_ao_pca" else int(g)
        for lr in GRADE_LR:
            modelo, info = treina_ae(e, gargalo, lr, SEMENTE_AJUSTE, X[e]["treino"], X[e]["validacao"])
            ap = pr_auc_validacao(erro_ae(modelo, X[e]["validacao"]))
            AJUSTE.append({"entrada": e, "gargalo_grade": g, "gargalo": gargalo, "lr": lr,
                           "melhor_epoca": info["melhor_epoca"], "perda_validacao": info["melhor_perda"],
                           "no_teto": info["no_teto"], "pr_auc_validacao": ap})
AJUSTE = pd.DataFrame(AJUSTE)
print(f"\najuste em {time.time() - t0:.0f} s\n")
print(AJUSTE.round(4).to_string(index=False))

ESCOLHA = {}
for e, g in AJUSTE.groupby("entrada"):
    melhor = g.sort_values(["pr_auc_validacao", "perda_validacao"], ascending=[False, True]).iloc[0]
    ESCOLHA[e] = (int(melhor["gargalo"]), float(melhor["lr"]))
    print(f"{e}: escolhido gargalo {ESCOLHA[e][0]}, taxa {ESCOLHA[e][1]:g} "
          f"(PR-AUC na validação {melhor['pr_auc_validacao']:.3f})")
AJUSTE.to_csv(os.path.join(PASTA_SAIDA, "06_ajuste_validacao.csv"), index=False)
''')

md("""
## Parte 2 — Modelos finais e o teste, uma única vez

Com as configurações congeladas, cada entrada recebe: autoencoder escolhido nas 5 sementes, PCA e
Isolation Forest nas 5 sementes. O limiar de chuva acumulada é o mesmo da fase 1, sobre as mesmas janelas.
""")

code(r'''
# 9. Treinos finais e escores de validação e teste
ESC = {}   # (entrada, modelo, semente) -> {"validacao": array, "teste": array}
t0 = time.time()

i_dia, i_est = IDX["treino"]
acum_tr = W_mm[i_dia, i_est, :].sum(axis=1)
P99_N1 = (pd.DataFrame({"g": estacoes[i_est], "a": acum_tr}).groupby("g")["a"].quantile(Q_LIMIAR))
for n in ("validacao", "teste"):
    i_dia, i_est = IDX[n]
    ESC.setdefault(("—", "limiar_acumulado", -1), {})[n] = W_mm[i_dia, i_est, :].sum(axis=1)

for e in ("E0", "E1"):
    p = PCAS[e]
    def erro_pca(Xm):
        return ((Xm - p.inverse_transform(p.transform(Xm))) ** 2).mean(axis=1)
    ESC[(e, "pca", -1)] = {n: erro_pca(X[e][n]) for n in ("validacao", "teste")}
    gargalo, lr = ESCOLHA[e]
    for s in SEMENTES:
        modelo, _ = treina_ae(e, gargalo, lr, s, X[e]["treino"], X[e]["validacao"])
        ESC[(e, "autoencoder", s)] = {n: erro_ae(modelo, X[e][n]) for n in ("validacao", "teste")}
        iso = IsolationForest(n_estimators=IF_ARVORES, max_samples=IF_AMOSTRA, random_state=s, n_jobs=-1).fit(X[e]["treino"])
        ESC[(e, "isolation_forest", s)] = {n: -iso.score_samples(X[e][n]) for n in ("validacao", "teste")}
print(f"\nmodelos finais em {time.time() - t0:.0f} s")
if HIST:
    pd.DataFrame(HIST).to_csv(os.path.join(PASTA_SAIDA, "06_historico_autoencoder.csv"), index=False)
''')

code(r'''
# 10. Avaliação no teste (todas as estações e só Hidroweb diário)
LIN = []
for grupo in ("todas", "hidroweb"):
    for (e, modelo, s), d in ESC.items():
        va = Q["validacao"].assign(escore=d["validacao"])
        te = Q["teste"].assign(escore=d["teste"])
        if grupo == "hidroweb":
            va, te = va[va["gauge_code"].isin(HIDROWEB)], te[te["gauge_code"].isin(HIDROWEB)]
        thr = P99_N1 if modelo == "limiar_acumulado" else limiares(va)
        if grupo == "hidroweb" and modelo == "limiar_acumulado":
            thr = thr[thr.index.isin(HIDROWEB)]
        r = avalia_teste(va, te, thr)
        r.update({"grupo": grupo, "entrada": e, "modelo": modelo, "semente": s})
        LIN.append(r)
R = pd.DataFrame(LIN)
R.to_csv(os.path.join(PASTA_SAIDA, "06_metricas_teste.csv"), index=False)
col = ["recall_1%", "recall_3%", "pr_auc", "falsos_ano_uf_1%", "alarme_teste_1%"]
res = (R[R["grupo"] == "todas"].groupby(["entrada", "modelo"])[col].agg(["mean", "std"]).round(3))
print("TODAS AS ESTAÇÕES (média e desvio nas sementes):")
print(res.to_string())
''')

code(r'''
# 11. Critérios pré-registrados S1 e S2, e a leitura
def valores(grupo, e, modelo, medida):
    g = R[(R["grupo"] == grupo) & (R["entrada"] == e) & (R["modelo"] == modelo)].sort_values("semente")
    return g.set_index("semente")[medida]

VEREDITOS = {}
for grupo in ("todas", "hidroweb"):
    lim = R[(R["grupo"] == grupo) & (R["modelo"] == "limiar_acumulado")].iloc[0]
    s1 = s2 = True
    for medida in ("recall_1%", "pr_auc"):
        e1 = valores(grupo, "E1", "autoencoder", medida)
        e0 = valores(grupo, "E0", "autoencoder", medida)
        s1 &= bool((e1 > lim[medida]).all())
        s2 &= bool((e1 > e0.reindex(e1.index)).all())
        print(f"[{grupo}] {medida}: limiar {lim[medida]:.3f} | AE E0 {e0.round(3).tolist()} | AE E1 {e1.round(3).tolist()}")
    ganho = {}
    for m in ("pca", "isolation_forest"):
        for medida in ("recall_1%", "pr_auc"):
            ganho[f"{m} {medida}"] = round(float(valores(grupo, "E1", m, medida).mean() - valores(grupo, "E0", m, medida).mean()), 3)
    VEREDITOS[grupo] = {"S1": s1, "S2": s2, "ganho_E1_menos_E0_outros_modelos": ganho}
    print(f"[{grupo}] S1 (AE E1 supera o limiar nas 5 sementes): {s1} | S2 (AE E1 supera AE E0 nas 5 sementes): {s2}")
    print(f"[{grupo}] ganho médio de E0 para E1 nos outros modelos: {ganho}\n")

v = VEREDITOS["todas"]
if v["S1"] and v["S2"]:
    LEITURA = "S1 e S2: a chuva das vizinhas ajudou o autoencoder a superar o limiar (exploratório)."
elif v["S2"]:
    LEITURA = "S2 sem S1: a vizinhança ajudou o autoencoder, mas não o bastante para superar o limiar."
else:
    LEITURA = "Nem S1 nem S2: a chuva das vizinhas, nesta forma, não ajudou o autoencoder (refutação pré-registrada)."
if (v["S1"] or v["S2"]) and not (VEREDITOS["hidroweb"]["S1"] or VEREDITOS["hidroweb"]["S2"]):
    LEITURA += " O ganho não se repete só no Hidroweb diário: atribuído à mistura de redes."
print("LEITURA:", LEITURA)
print("Lembrete: resultado exploratório; não substitui o resultado pré-registrado da fase 1 (achado 08).")
''')

code(r'''
# 12. Registro da execução
log = {
    "notebook": "06_fase2_vizinhanca", "versao_notebook": "1",
    "data_execucao": pd.Timestamp.now().isoformat(),
    "decisoes_fase1": {"versao": DEC["versao"], "sha256_16": HASH_DEC},
    "decisoes_fase2": {"versao": DEC2["versao"], "sha256_16": HASH_DEC2},
    "natureza": DEC2["natureza"],
    "janelas": {n: int(len(IDX[n][0])) for n in IDX},
    "episodios_severos": {"validacao": int(EV_VAL["severo"].sum()), "teste": int(EV_TESTE["severo"].sum())},
    "pca_componentes": {e: int(p.n_components_) for e, p in PCAS.items()},
    "escolha_ajuste": {e: {"gargalo": g, "lr": lr} for e, (g, lr) in ESCOLHA.items()},
    "vereditos": VEREDITOS, "leitura": LEITURA,
    "nao_preregistrados": NAO_PREREGISTRADOS,
    "epocas_maximas_usadas": AE_EPOCAS, "teto_janelas_treino_usado": MAX_JANELAS_TREINO,
    "python": platform.python_version(), "pandas": pd.__version__,
}
_partes = []
for (e, modelo, s), d in ESC.items():
    for n in ("validacao", "teste"):
        _partes.append(Q[n].assign(entrada=e, modelo=modelo, semente=np.int16(s), conjunto=n,
                                   escore=np.asarray(d[n], dtype="float32")))
pd.concat(_partes, ignore_index=True).to_parquet(os.path.join(PASTA_DADOS, "escores_06.parquet"), index=False)
del _partes
with open(os.path.join(PASTA_SAIDA, "06_log_execucao.json"), "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2, default=str)
print("gravado: 06_ajuste_validacao.csv, 06_metricas_teste.csv, 06_historico_autoencoder.csv, 06_log_execucao.json e 06_dados/escores_06.parquet")
''')


def nb():
    return {"cells": CELLS, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4"}}, "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "06_fase2_vizinhanca.ipynb")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(nb(), f, ensure_ascii=False, indent=1)
    print("ok", len(CELLS), "celulas ->", destino)
