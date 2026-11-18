# -*- coding: utf-8 -*-
"""Teste do notebook 04 com dados sinteticos.

Constroi a saida que o notebook 03 grava, planta um evento extremo no periodo de
teste, executa as celulas de codigo do notebook e verifica vazamento, janelas,
checkpoints e se o evento plantado recebe escore mais alto.

Uso:  python testar_nb04.py
"""
import json, os, shutil, subprocess, sys
import numpy as np
import pandas as pd

RAIZ = "/tmp/nb04_teste"
AQUI = os.path.dirname(os.path.abspath(__file__))
NB = os.environ.get("NB04", os.path.join(AQUI, "..", "04_janelas_e_modelos.ipynb"))
DECISOES = os.environ.get("DECISOES", os.path.join(AQUI, "..", "..", "pre-registro", "decisoes.json"))
QC = os.path.join(AQUI, "..", "qc_uniplu.py")

FALHAS = []


def checa(nome, ok, detalhe=""):
    print(("PASSOU " if ok else "FALHOU ") + nome, detalhe if not ok else detalhe)
    if not ok:
        FALHAS.append(nome)


# ---------------------------------------------------------------- dados
shutil.rmtree(RAIZ, ignore_errors=True)
for p in ("06_dados", "05_saidas", "02_scripts"):
    os.makedirs(f"{RAIZ}/{p}", exist_ok=True)
shutil.copy(DECISOES, f"{RAIZ}/02_scripts/decisoes.json")
if os.path.exists(QC):
    shutil.copy(QC, f"{RAIZ}/02_scripts/qc_uniplu.py")

rng = np.random.default_rng(7)
dias = pd.date_range("1995-01-01", "2025-12-31", freq="D")
redes = (["Hidroweb diário"] * 20 + ["Telemetria"] * 10 + ["INMET subdiário"] * 6 + ["INMET diário"] * 4)
estacoes = [f"E{i:03d}" for i in range(len(redes))]

linhas = []
for g, rede in zip(estacoes, redes):
    # chuva: 70% de dias secos, resto exponencial
    v = rng.exponential(8.0, len(dias)).astype("float32")
    v[rng.random(len(dias)) < 0.70] = 0.0
    # Telemetria so existe de 2014 em diante, como nos dados reais
    ini = pd.Timestamp("2014-01-01") if rede == "Telemetria" else dias[0]
    m = dias >= ini
    # lacunas aleatorias de 3%
    m &= rng.random(len(dias)) > 0.03
    linhas.append(pd.DataFrame({"gauge_code": g, "dia": dias[m], "rain_mm": v[m]}))
D = pd.concat(linhas, ignore_index=True)

# EVENTO PLANTADO: 2024-05-01 a 2024-05-05, chuva muito acima do normal em todas as estacoes
EV_INI, EV_FIM = pd.Timestamp("2024-05-01"), pd.Timestamp("2024-05-05")
alvo = D["dia"].between(EV_INI, EV_FIM)
D.loc[alvo, "rain_mm"] = rng.uniform(90, 160, int(alvo.sum())).astype("float32")
print(f"evento plantado: {int(alvo.sum())} dias de estacao entre {EV_INI.date()} e {EV_FIM.date()}")

def conjunto(d):
    if d <= pd.Timestamp("2019-12-31"):
        return "treino"
    if d <= pd.Timestamp("2022-12-31"):
        return "validacao"
    return "teste"

D["conjunto"] = D["dia"].map(conjunto)
D["qc_limpo_diario"] = True
D.loc[rng.random(len(D)) < 0.01, "qc_limpo_diario"] = False   # 1% sujo
D.to_parquet(f"{RAIZ}/06_dados/chuva_diaria_qc_h12.parquet", index=False)

EST = pd.DataFrame({"gauge_code": estacoes, "network": redes})
EST["elegivel"] = True
EST["subconjunto_hidroweb"] = EST["network"] == "Hidroweb diário"
EST.to_parquet(f"{RAIZ}/06_dados/estacoes_elegiveis.parquet", index=False)

EV = pd.DataFrame([
    {"UF": "RS", "id_evento": "RS_001", "data_inicio": pd.Timestamp("2023-01-05"),
     "data_fim": pd.Timestamp("2023-01-06"), "n_municipios": 7, "severo": True},
    {"UF": "RS", "id_evento": "RS_002", "data_inicio": EV_INI, "data_fim": EV_FIM,
     "n_municipios": 30, "severo": True},
    {"UF": "SC", "id_evento": "SC_001", "data_inicio": pd.Timestamp("2025-03-02"),
     "data_fim": pd.Timestamp("2025-03-03"), "n_municipios": 2, "severo": False},
])
EV.to_parquet(f"{RAIZ}/06_dados/eventos_reindesc.parquet", index=False)
print(f"sintetico: {len(D):,} linhas, {len(estacoes)} estacoes, {len(EV)} eventos")

# ---------------------------------------------------------------- executar
nb = json.load(open(NB, encoding="utf-8"))
DEMO = os.environ.get("TESTE_DEMO") == "1"
fonte = ["import os", f"os.environ['NB04_RAIZ_TESTE'] = {RAIZ!r}",
         "os.environ['NB04_EPOCAS'] = '3'", "os.environ['NB04_MAX_TREINO'] = '20000'"]
for c in nb["cells"]:
    if c["cell_type"] == "code":
        src = "".join(c["source"])
        if not DEMO:
            src = src.replace("MODO_DEMONSTRACAO = True", "MODO_DEMONSTRACAO = False")
        fonte.append(src)
print("modo:", "DEMONSTRACAO" if DEMO else "DEFINITIVO")
script = f"{RAIZ}/nb04_exec.py"
open(script, "w", encoding="utf-8").write("\n\n".join(fonte))

r = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=3600)
print(r.stdout[-5000:])
if r.returncode != 0:
    print("STDERR:", r.stderr[-4000:])
    checa("notebook executa sem erro", False, f"retorno {r.returncode}")
    sys.exit(1)
checa("notebook executa sem erro", True)

# ---------------------------------------------------------------- verificar
SUF = "_demo" if DEMO else ""
SUB = "/_demo" if DEMO else ""          # versão 3: a demonstração grava em subpastas _demo
S = pd.read_parquet(f"{RAIZ}/06_dados{SUB}/escores_04{SUF}.parquet")
S["dia"] = pd.to_datetime(S["dia"])
log = json.load(open(f"{RAIZ}/05_saidas{SUB}/04_log_execucao{SUF}.json", encoding="utf-8"))

niveis = set(S["modelo"].unique())
esperados = {"nivel1_acumulado", "nivel2_pca", "nivel3_autoencoder", "nivel4_isolation"}
checa("quatro niveis pre-registrados pontuados", esperados <= niveis, sorted(niveis))
ablacoes = niveis - esperados
checa("ablacao de gargalo do autoencoder presente", len(ablacoes) == 1, sorted(ablacoes))
checa("so validacao e teste gravados", set(S["conjunto"]) == {"validacao", "teste"}, set(S["conjunto"]))
sem_ae = sorted(S.loc[S["modelo"] == "nivel3_autoencoder", "semente"].unique())
esperadas = [0, 1] if DEMO else [0, 1, 2, 3, 4]
checa("sementes do autoencoder", sem_ae == esperadas, sem_ae)
sem_if = sorted(S.loc[S["modelo"] == "nivel4_isolation", "semente"].unique())
checa("sementes do isolation forest", sem_if == esperadas, sem_if)

# vazamento: nenhuma janela de teste usa dia de validacao
JAN = int(log["janela_dias"])
primeiro_teste = S.loc[S["conjunto"] == "teste", "dia"].min()
checa("primeiro dia pontuavel do teste respeita a janela",
      primeiro_teste >= pd.Timestamp("2023-01-01") + pd.Timedelta(days=JAN - 1),
      f"{primeiro_teste.date()} (minimo {(pd.Timestamp('2023-01-01') + pd.Timedelta(days=JAN - 1)).date()})")
ultimo_val = S.loc[S["conjunto"] == "validacao", "dia"].max()
checa("intervalo entre validacao e teste aplicado",
      ultimo_val <= pd.Timestamp("2022-12-31") - pd.Timedelta(days=JAN),
      f"{ultimo_val.date()}")
checa("gap registrado no log", int(log["gap_entre_particoes_dias"]) == JAN, log["gap_entre_particoes_dias"])

# PCA retem variancia pedida
checa("PCA retem pelo menos 90% da variancia", log["pca_variancia_explicada"] >= 0.90,
      f"{log['pca_variancia_explicada']:.3f} com {log['pca_componentes']} componentes")

# checkpoints por epoca e melhor modelo
ck = os.listdir(f"{RAIZ}/06_dados/_modelos_04{SUB}")
por_epoca = [f for f in ck if "_epoca" in f]
melhores = [f for f in ck if f.endswith("_melhor.pt")]
checa("checkpoint gravado a cada epoca", len(por_epoca) >= 2 * len(esperadas) * 3, f"{len(por_epoca)} arquivos")
checa("melhor modelo por semente e por gargalo preservado", len(melhores) == 2 * len(esperadas),
      f"{len(melhores)} arquivos: {sorted(melhores)}")
gargalos = {f.split("_")[1] for f in melhores}
checa("dois gargalos treinados", len(gargalos) == 2, sorted(gargalos))

H = pd.read_csv(f"{RAIZ}/05_saidas{SUB}/04_historico_autoencoder{SUF}.csv")
checa("historico tem perda de treino e validacao por epoca",
      {"semente", "epoca", "perda_treino", "perda_validacao"} <= set(H.columns), list(H.columns))

# sementes produzem resultados diferentes (se nao, a semente nao esta sendo usada)
a0 = S[(S.modelo == "nivel3_autoencoder") & (S.semente == 0) & (S.conjunto == "teste")].set_index(["gauge_code", "dia"])["escore"]
a1 = S[(S.modelo == "nivel3_autoencoder") & (S.semente == 1) & (S.conjunto == "teste")].set_index(["gauge_code", "dia"])["escore"]
checa("sementes diferentes dao escores diferentes", not np.allclose(a0.values, a1.values))

# FUNCIONAL: o evento plantado recebe escore mais alto que os dias normais
janela_ev = (S["dia"] >= EV_INI) & (S["dia"] <= EV_FIM + pd.Timedelta(days=JAN - 1))
for modelo in ("nivel1_acumulado", "nivel2_pca", "nivel3_autoencoder", "nivel4_isolation"):
    sub = S[(S["modelo"] == modelo) & (S["conjunto"] == "teste")]
    dentro = sub.loc[janela_ev.reindex(sub.index, fill_value=False), "escore"].median()
    fora = sub.loc[~janela_ev.reindex(sub.index, fill_value=False), "escore"].median()
    checa(f"evento plantado pontua acima do normal em {modelo}", dentro > fora,
          f"dentro {dentro:.4f} vs fora {fora:.4f}")

checa("gargalo principal igual ao numero de componentes do PCA",
      int(log["ae_gargalo_principal"]) == int(log["pca_componentes"]),
      f"gargalo {log['ae_gargalo_principal']} vs PCA {log['pca_componentes']}")
checa("melhor epoca registrada no log", len(log["ae_melhor_epoca"]) == 2 * len(esperadas), len(log.get("ae_melhor_epoca", [])))
checa("modo registrado no log", log["modo_demonstracao"] == DEMO, log["modo_demonstracao"])
if DEMO:
    checa("saidas definitivas nao foram sobrescritas",
          not os.path.exists(f"{RAIZ}/06_dados/escores_04.parquet")
          and not os.path.exists(f"{RAIZ}/05_saidas/04_log_execucao.json")
          and not [f for f in os.listdir(f"{RAIZ}/06_dados/_modelos_04") if f.endswith(".pt")])

# normalizacao so do treino: o log tem que registrar a forma usada
checa("forma da normalizacao registrada", log["normalizacao"] in ("zscore", "log1p_zscore"), log["normalizacao"])
checa("parametros nao pre-registrados listados no log",
      len(log["parametros_nao_preregistrados"]) >= 8, len(log["parametros_nao_preregistrados"]))

checa("diagnostico do Hidroweb por ano gravado (celula 6b)",
      os.path.exists(f"{RAIZ}/05_saidas{SUB}/acumulado_mediano_por_ano_hidroweb.csv"))
checa("versao do notebook registrada como 3", log.get("versao_notebook") == "3", log.get("versao_notebook"))

print()
print("TODOS PASSARAM" if not FALHAS else f"{len(FALHAS)} FALHARAM: {FALHAS}")
sys.exit(1 if FALHAS else 0)
