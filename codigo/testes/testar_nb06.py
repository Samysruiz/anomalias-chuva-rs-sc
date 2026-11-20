# -*- coding: utf-8 -*-
"""Teste do notebook 06 (fase 2, versão mínima) com dados sintéticos.

Verifica: travas de hash e de rótulos, média das vizinhas, mesmo conjunto de janelas para E0 e E1,
ajuste sem uso dos rótulos do teste, retomada de treinos, checkpoints, saídas e se a entrada E1
reage a uma anomalia que só aparece nas vizinhas.

Uso:  python testar_nb06.py
"""
import json, os, shutil, subprocess, sys
import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
NB = os.environ.get("NB06", os.path.join(AQUI, "..", "06_fase2_vizinhanca.ipynb"))
PRE = os.path.join(AQUI, "..", "..", "pre-registro")
RAIZ = "/tmp/nb06_teste"
FALHAS = []


def checa(nome, ok, detalhe=""):
    print(("PASSOU " if ok else "FALHOU ") + nome, detalhe)
    if not ok:
        FALHAS.append(nome)


def monta_dados():
    shutil.rmtree(RAIZ, ignore_errors=True)
    for p in ("06_dados", "05_saidas", "02_scripts"):
        os.makedirs(f"{RAIZ}/{p}", exist_ok=True)
    shutil.copy(f"{PRE}/decisoes.json", f"{RAIZ}/02_scripts/decisoes.json")
    shutil.copy(f"{PRE}/decisoes_fase2.json", f"{RAIZ}/02_scripts/decisoes_fase2.json")
    rng = np.random.default_rng(11)
    dias = pd.date_range("1995-01-01", "2025-12-31", freq="D")
    # 4 grupos de 10 estações; dentro do grupo, até ~20 km; grupos a ~200 km
    centros = [(-29.0, -53.0, "RS"), (-30.8, -53.0, "RS"), (-27.0, -50.0, "SC"), (-27.0, -52.0, "SC")]
    linhas, est = [], []
    k = 0
    for gi, (la, lo, uf) in enumerate(centros):
        base = rng.exponential(8.0, len(dias)).astype("float32")      # chuva comum do grupo
        base[rng.random(len(dias)) < 0.65] = 0.0
        for j in range(10):
            g = f"E{k:03d}"; k += 1
            v = (base * rng.uniform(0.6, 1.4, len(dias))).astype("float32")
            m = rng.random(len(dias)) > 0.02
            linhas.append(pd.DataFrame({"gauge_code": g, "dia": dias[m], "rain_mm": v[m]}))
            est.append({"gauge_code": g, "network": "Hidroweb diário" if j < 6 else "Telemetria",
                        "lat": la + rng.uniform(-0.08, 0.08), "long": lo + rng.uniform(-0.08, 0.08),
                        "state": uf, "grupo": gi})
    D = pd.concat(linhas, ignore_index=True)
    EST = pd.DataFrame(est)

    def planta(ini, fim, grupos, mm):
        for gi in grupos:
            alvo = D["gauge_code"].isin(EST.loc[EST["grupo"] == gi, "gauge_code"]) & D["dia"].between(ini, fim)
            D.loc[alvo, "rain_mm"] = rng.uniform(*mm, int(alvo.sum())).astype("float32")

    # eventos de validação (2020–2022) e de teste (2023–2025)
    ev_val = [("2020-06-10", "2020-06-12", [0], "RS"), ("2021-09-05", "2021-09-07", [2], "SC"),
              ("2022-05-20", "2022-05-22", [1], "RS"), ("2022-10-01", "2022-10-03", [3], "SC")]
    ev_te = [("2023-09-04", "2023-09-06", [0, 1], "RS"), ("2024-05-01", "2024-05-05", [0, 1], "RS"),
             ("2024-11-10", "2024-11-12", [2, 3], "SC"), ("2025-07-01", "2025-07-02", [3], "SC")]
    for a, b, gs, _ in ev_val + ev_te:
        planta(pd.Timestamp(a), pd.Timestamp(b), gs, (90, 160))
    # anomalia SÓ nas vizinhas: grupo 2 inteiro chove forte, a estação E020 fica seca
    ALVO = "E020"
    viz = EST.loc[(EST["grupo"] == 2) & (EST["gauge_code"] != ALVO), "gauge_code"]
    m = D["gauge_code"].isin(viz) & D["dia"].between("2024-08-10", "2024-08-12")
    D.loc[m, "rain_mm"] = 150.0
    D.loc[(D["gauge_code"] == ALVO) & D["dia"].between("2024-08-10", "2024-08-12"), "rain_mm"] = 0.0

    D["conjunto"] = np.where(D["dia"] <= "2019-12-31", "treino", np.where(D["dia"] <= "2022-12-31", "validacao", "teste"))
    D["qc_limpo_diario"] = True
    D.to_parquet(f"{RAIZ}/06_dados/chuva_diaria_qc_h12.parquet", index=False)
    EST["elegivel"] = True
    EST["subconjunto_hidroweb"] = EST["network"] == "Hidroweb diário"
    EST.drop(columns="grupo").to_parquet(f"{RAIZ}/06_dados/estacoes_elegiveis.parquet", index=False)

    # rótulos do teste no formato do notebook 03
    ev = []
    for i, (a, b, gs, uf) in enumerate(ev_te):
        ev.append({"UF": uf, "id_evento": f"{uf}_{i:03d}", "data_inicio": pd.Timestamp(a), "data_fim": pd.Timestamp(b),
                   "n_municipios": 6, "severo": True, "extenso": True,
                   "janela_inicio": pd.Timestamp(a) - pd.Timedelta(days=3), "janela_fim": pd.Timestamp(b)})
    pd.DataFrame(ev).to_parquet(f"{RAIZ}/06_dados/eventos_reindesc.parquet", index=False)
    # rótulos da validação no formato da exportação do REInDesC
    oc, n = [], 0
    for a, b, gs, uf in ev_val:
        for d in pd.date_range(a, b):
            n += 1
            oc.append({"ID ocorrência": n, "Data": d.strftime("%Y-%m-%d"), "UF": uf, "Município": f"M{n}",
                       "Magnitude": "GP" if n % 2 else "MP", "Tipologia": "Hidrológico"})
    pd.DataFrame(oc).to_csv(f"{RAIZ}/06_dados/validacao_reindesc_2020_2022.csv", sep=";", index=False, encoding="utf-8")
    return D, EST, ALVO


def roda(extra=None):
    nb = json.load(open(NB, encoding="utf-8"))
    fonte = ["import os", f"os.environ['NB06_RAIZ_TESTE'] = {RAIZ!r}",
             "os.environ['NB06_EPOCAS'] = '4'", "os.environ['NB06_MAX_TREINO'] = '30000'"]
    fonte += ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    script = f"{RAIZ}/nb06_exec.py"
    open(script, "w", encoding="utf-8").write("\n\n".join(fonte))
    return subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=3600)


D, EST, ALVO = monta_dados()

# 1. trava: pré-registro da fase 2 alterado
dec2 = f"{RAIZ}/02_scripts/decisoes_fase2.json"
orig = open(dec2, encoding="utf-8").read()
open(dec2, "w", encoding="utf-8").write(orig.replace('"raio_km": 50.0', '"raio_km": 80.0'))
r = roda()
checa("para se o decisoes_fase2.json for alterado", r.returncode != 0 and "c0e7df1aded21cd7" in (r.stdout + r.stderr))
open(dec2, "w", encoding="utf-8").write(orig)

# 2. trava: falta rótulo da validação
os.rename(f"{RAIZ}/06_dados/validacao_reindesc_2020_2022.csv", f"{RAIZ}/val.bak")
r = roda()
checa("para se faltar o rótulo da validação", r.returncode != 0 and "validacao_reindesc" in (r.stdout + r.stderr))
os.rename(f"{RAIZ}/val.bak", f"{RAIZ}/06_dados/validacao_reindesc_2020_2022.csv")

# 3. execução completa
r = roda()
print(r.stdout[-3500:])
if r.returncode != 0:
    print("STDERR:", r.stderr[-4000:])
    checa("notebook executa sem erro", False)
    sys.exit(1)
checa("notebook executa sem erro", True)

log = json.load(open(f"{RAIZ}/05_saidas/06_log_execucao.json", encoding="utf-8"))
AJ = pd.read_csv(f"{RAIZ}/05_saidas/06_ajuste_validacao.csv")
R = pd.read_csv(f"{RAIZ}/05_saidas/06_metricas_teste.csv")
S = pd.read_parquet(f"{RAIZ}/06_dados/escores_06.parquet")

checa("hashes dos dois pré-registros no log",
      log["decisoes_fase1"]["sha256_16"] == "d4c58a627755c8f9" and log["decisoes_fase2"]["sha256_16"] == "c0e7df1aded21cd7")
checa("grade de 6 configurações por entrada", AJ.groupby("entrada").size().to_dict() == {"E0": 6, "E1": 6},
      AJ.groupby("entrada").size().to_dict())
checa("escolha registrada para E0 e E1", set(log["escolha_ajuste"]) == {"E0", "E1"}, log["escolha_ajuste"])
checa("episódios severos da validação lidos", log["episodios_severos"]["validacao"] == 4, log["episodios_severos"])

# mesmo conjunto de janelas para E0 e E1
k0 = S[(S.entrada == "E0") & (S.modelo == "pca")][["gauge_code", "dia", "conjunto"]]
k1 = S[(S.entrada == "E1") & (S.modelo == "pca")][["gauge_code", "dia", "conjunto"]]
checa("E0 e E1 avaliados nas mesmas janelas", k0.reset_index(drop=True).equals(k1.reset_index(drop=True)))
checa("teste e validação dentro das partições",
      S.loc[S.conjunto == "teste", "dia"].min() >= pd.Timestamp("2023-01-15")
      and S.loc[S.conjunto == "validacao", "dia"].max() <= pd.Timestamp("2022-12-16"))

# média das vizinhas conferida à mão para uma estação e um dia
M = D.pivot_table(index="dia", columns="gauge_code", values="rain_mm")
dia = pd.Timestamp("2024-08-11")
viz = EST.loc[(EST["state"] == "SC") & (EST["gauge_code"] != ALVO) & (abs(EST["long"] + 50.0) < 0.5), "gauge_code"]
esperado = M.loc[dia, viz].dropna().mean()
checa("anomalia só nas vizinhas plantada como esperado", abs(esperado - 150.0) < 1e-3 and M.loc[dia, ALVO] == 0.0)

# E1 reage à anomalia que só aparece nas vizinhas; E0 não tem como ver
jan = (S["gauge_code"] == ALVO) & S["dia"].between("2024-08-10", "2024-08-26") & (S["conjunto"] == "teste")
def razao(entrada, modelo):
    s = S[(S.entrada == entrada) & (S.modelo == modelo) & (S.conjunto == "teste") & (S.gauge_code == ALVO)]
    dentro = s.loc[s["dia"].between("2024-08-12", "2024-08-26"), "escore"].median()
    return dentro / s["escore"].median()
r0, r1 = razao("E0", "pca"), razao("E1", "pca")
checa("PCA com E1 reage à chuva só das vizinhas mais que com E0", r1 > 2 * r0, f"razão E1 {r1:.2f} vs E0 {r0:.2f}")

# checkpoints, melhor modelo e retomada
arqs = os.listdir(f"{RAIZ}/06_dados/_modelos_06")
checa("checkpoint por época, melhor modelo e fim gravados",
      any(a.endswith("_ultima_epoca.pt") for a in arqs) and any(a.endswith("_melhor.pt") for a in arqs)
      and any(a.endswith("_fim.json") for a in arqs), len(arqs))

# 4. os rótulos do teste não influem no ajuste: troca os eventos do teste e roda de novo
ev = pd.read_parquet(f"{RAIZ}/06_dados/eventos_reindesc.parquet")
ev["data_inicio"] = ev["data_inicio"] + pd.Timedelta(days=40)
ev["data_fim"] = ev["data_fim"] + pd.Timedelta(days=40)
ev["janela_inicio"] = ev["data_inicio"] - pd.Timedelta(days=3)
ev["janela_fim"] = ev["data_fim"]
ev.to_parquet(f"{RAIZ}/06_dados/eventos_reindesc.parquet", index=False)
r2 = roda()
checa("segunda execução reaproveita os treinos", r2.returncode == 0 and "reaproveitado" in r2.stdout)
AJ2 = pd.read_csv(f"{RAIZ}/05_saidas/06_ajuste_validacao.csv")
checa("ajuste idêntico com outros rótulos de teste (teste não entra na escolha)",
      np.allclose(AJ["pr_auc_validacao"], AJ2["pr_auc_validacao"]) and
      json.load(open(f"{RAIZ}/05_saidas/06_log_execucao.json"))["escolha_ajuste"] == log["escolha_ajuste"])
R2 = pd.read_csv(f"{RAIZ}/05_saidas/06_metricas_teste.csv")
checa("as métricas do teste mudam com outros rótulos (o teste é mesmo usado no fim)",
      not np.allclose(R["recall_1%"].to_numpy(), R2["recall_1%"].to_numpy()))

cols = {"grupo", "entrada", "modelo", "semente", "recall_1%", "recall_3%", "pr_auc", "falsos_ano_uf_1%", "alarme_teste_1%"}
checa("métricas do teste com as colunas esperadas", cols <= set(R.columns))
checa("grupos todas e hidroweb avaliados", set(R["grupo"]) == {"todas", "hidroweb"})
checa("5 sementes do autoencoder por entrada",
      R[(R.grupo == "todas") & (R.modelo == "autoencoder")].groupby("entrada").size().to_dict() == {"E0": 5, "E1": 5})
checa("vereditos S1 e S2 registrados", all(k in log["vereditos"]["todas"] for k in ("S1", "S2")), log["vereditos"]["todas"])
checa("leitura registrada", isinstance(log["leitura"], str) and len(log["leitura"]) > 20, log["leitura"])
checa("execução reduzida marcada no log", any("reduzida" in k for k in log["nao_preregistrados"]))

print()
print("TODOS PASSARAM" if not FALHAS else f"{len(FALHAS)} FALHARAM: {FALHAS}")
sys.exit(1 if FALHAS else 0)
