"""Teste do notebook 03 com dados sinteticos no formato real. Uso: python testar_nb03.py UTC|local"""
import os, sys, json, shutil, subprocess
import numpy as np, pandas as pd

FUSO = sys.argv[1] if len(sys.argv) > 1 else "UTC"
RAIZ = "/tmp/nb03_teste"
shutil.rmtree(RAIZ, ignore_errors=True)
for p in ("06_dados", "02_scripts", "05_saidas"):
    os.makedirs(f"{RAIZ}/{p}")
shutil.copy("/home/claude/qc_uniplu.py", f"{RAIZ}/02_scripts/")
shutil.copy("/home/claude/decisoes.json", f"{RAIZ}/02_scripts/")

rng = np.random.default_rng(7)
est, blocos = [], []

def serie_horaria(ini, fim):
    idx = pd.date_range(ini, fim, freq="h")
    hora = idx.hour.to_numpy()
    p_chuva = 0.04 + 0.08 * np.exp(-((hora - 17) ** 2) / 18.0)   # pico no fim da tarde
    v = np.where(rng.random(len(idx)) < p_chuva, rng.gamma(0.8, 3.0, len(idx)), 0.0)
    return idx, v

def evento(idx, v, a, b, mult):
    m = (idx >= a) & (idx <= b)
    v[m] += rng.gamma(3.0, mult, m.sum())
    return v

# 12 estacoes horarias (rede CEMADEN), 2014-2025, proximas entre si
for i in range(12):
    cod = f"C{i:02d}"
    est.append(dict(gauge_code=cod, city="X", state="RS", lat=-29.2 + 0.03 * (i % 4), long=-51.9 + 0.03 * (i // 4),
                    elevation=50.0, time_step="60", network="CEMADEN", responsible="ANA", utc="-3"))
    idx, v = serie_horaria("2014-01-01", "2025-12-31 23:00")
    v = evento(idx, v, "2024-05-02", "2024-05-05 23:00", 3.0)
    blocos.append(pd.DataFrame({"gauge_code": cod, "datetime": idx, "rain_mm": v}))

# 6 estacoes diarias (Hidroweb), 1995-2025
for i in range(6):
    cod = f"H{i:02d}"
    est.append(dict(gauge_code=cod, city="Y", state="SC", lat=-29.2 + 0.04 * i, long=-51.85,
                    elevation=40.0, time_step="1440", network="Hidroweb diário", responsible="SGB", utc="-3"))
    idx = pd.date_range("1995-01-01 12:00", "2025-12-31 12:00", freq="D")
    v = np.where(rng.random(len(idx)) < 0.3, rng.gamma(0.9, 8.0, len(idx)), 0.0)
    blocos.append(pd.DataFrame({"gauge_code": cod, "datetime": idx, "rain_mm": v}))
# travado: H00 com 9 dias iguais e positivos
d = blocos[-6]; m = (d["datetime"] >= "2010-03-01") & (d["datetime"] < "2010-03-10"); d.loc[m, "rain_mm"] = 1.2
# pico isolado espacial: H01, 150 mm num dia em que as vizinhas estao secas
d = blocos[-5]; dia = pd.Timestamp("2012-06-15 12:00")
for b in blocos[-6:]:
    b.loc[b["datetime"] == dia, "rain_mm"] = 0.0
d.loc[d["datetime"] == dia, "rain_mm"] = 150.0

# estacao plana (tudo zero, horaria)
est.append(dict(gauge_code="P00", city="Z", state="RS", lat=-29.25, long=-51.9, elevation=10.0,
                time_step="60", network="CEMADEN", responsible="ANA", utc="-3"))
idx = pd.date_range("2014-01-01", "2025-12-31 23:00", freq="h")
blocos.append(pd.DataFrame({"gauge_code": "P00", "datetime": idx, "rain_mm": 0.0}))
# Indefinido
est.append(dict(gauge_code="I00", city="W", state="RS", lat=-29.3, long=-51.9, elevation=10.0,
                time_step="Indefinido", network="ICEA", responsible="ICEA", utc="-3"))
idx = pd.date_range("2018-01-01", "2020-12-31 23:00", freq="h")
blocos.append(pd.DataFrame({"gauge_code": "I00", "datetime": idx, "rain_mm": rng.gamma(0.3, 1.0, len(idx))}))

bruto = pd.concat(blocos, ignore_index=True)
# duplicatas: 20 copias identicas, 5 conflitantes (em C03)
c3 = bruto[bruto["gauge_code"] == "C03"].sample(25, random_state=1)
ident = c3.iloc[:20]
conf = c3.iloc[20:].copy(); conf["rain_mm"] = conf["rain_mm"] + 7.0
bruto = pd.concat([bruto, ident, conf], ignore_index=True).sample(frac=1.0, random_state=3).reset_index(drop=True)
# negativo e acima do limite fisico em C05
i5 = bruto.index[bruto["gauge_code"] == "C05"][:4]
bruto.loc[i5[:2], "rain_mm"] = -9999.0
bruto.loc[i5[2:], "rain_mm"] = 950.0

bruto.to_parquet(f"{RAIZ}/06_dados/chuva_rs_sc_bruto.parquet", index=False, row_group_size=200_000)
pd.DataFrame(est).to_parquet(f"{RAIZ}/06_dados/estacoes_rs_sc.parquet", index=False)
print("sintetico:", len(bruto), "linhas,", len(est), "estacoes")

# zips por ano, para os diagnosticos B e C (celulas 5 e 6).
# A coluna do fuso vai como "UTC" maiuscula, como no arquivo real.
import zipfile, io as _io
os.makedirs(f"{RAIZ}/06_dados/uniplu_rs_sc", exist_ok=True)
_info = pd.DataFrame(est).rename(columns={"utc": "UTC"})
for uf, ano in (("RS", "2015"), ("SC", "2020")):
    sub = bruto[bruto["datetime"].dt.year == int(ano)]
    bi, bd = _io.BytesIO(), _io.BytesIO()
    _info.to_parquet(bi, index=False); sub.to_parquet(bd, index=False)
    with zipfile.ZipFile(f"{RAIZ}/06_dados/uniplu_rs_sc/{uf}_{ano}.zip", "w") as z:
        z.writestr("table_info.parquet", bi.getvalue())
        z.writestr("table_data.parquet", bd.getvalue())
print("zips de diagnostico:", sorted(os.listdir(f"{RAIZ}/06_dados/uniplu_rs_sc")))

# ocorrencias sinteticas do REInDesC (celula 19): um episodio severo e um PP isolado por UF
_oc = []
_n = 0
for uf, base in (("RS", "2024-05-02"), ("SC", "2023-10-04")):
    for k, mag in enumerate(["GP", "MP", "PP", "PP", "PP"]):
        _n += 1
        _oc.append({"ID ocorrência": _n, "Data": (pd.Timestamp(base) + pd.Timedelta(days=k % 3)).date(),
                    "UF": uf, "Município": f"Mun{k}", "Tipologia": "Hidro", "Magnitude": mag})
    _n += 1
    _oc.append({"ID ocorrência": _n, "Data": pd.Timestamp("2025-02-01").date(), "UF": uf,
                "Município": "MunX", "Tipologia": "Hidro", "Magnitude": "PP"})
pd.DataFrame(_oc).to_csv(f"{RAIZ}/06_dados/reindesc_teste.csv", sep=";", index=False, encoding="utf-8")
print("ocorrencias REInDesC sinteticas:", len(_oc))

# extrai celulas de codigo do notebook
nb = json.load(open("/home/claude/03_qualidade_e_preparo.ipynb", encoding="utf-8"))
codigo = ["import matplotlib; matplotlib.use('Agg')"]
for c in nb["cells"]:
    if c["cell_type"] == "code":
        src = "".join(c["source"]).replace('FUSO_CONFIRMADO = "UTC"', f'FUSO_CONFIRMADO = "{FUSO}"')
        codigo.append(src)
open("/tmp/nb03_exec.py", "w", encoding="utf-8").write("\n\n".join(codigo))
env = dict(os.environ, NB03_RAIZ_TESTE=RAIZ, NB03_MAX_LINHAS="300000", MPLBACKEND="Agg")
r = subprocess.run([sys.executable, "-I", "/tmp/nb03_exec.py"], env=env, capture_output=True, text=True, cwd="/tmp")
print(r.stdout[-9000:]); print("STDERR:", r.stderr[-3500:]); print("retorno", r.returncode)

# ---------- verificacoes dirigidas ----------
if r.returncode != 0:
    sys.exit(1)
ok = True
def checa(nome, cond, detalhe=""):
    global ok
    ok &= bool(cond)
    print(("PASSOU " if cond else "FALHOU ") + nome, detalhe)

S = pd.read_parquet(f"{RAIZ}/06_dados/chuva_diaria_qc_h12.parquet")
S["dia"] = pd.to_datetime(S["dia"])
a = pd.read_csv(f"{RAIZ}/05_saidas/03_auditoria_por_criterio.csv").set_index("criterio")["registros"]
checa("negativos = 2", a["qc_negativo"] == 2, a["qc_negativo"])
checa("acima do limite fisico = 2", a["qc_acima_limite_fisico"] == 2, a["qc_acima_limite_fisico"])
checa("copias identicas descartadas = 20", a["n_copias_identicas_descartadas"] == 20, a["n_copias_identicas_descartadas"])
checa("pares conflitantes = 5", a["n_pares_duplicata_conflitante"] == 5, a["n_pares_duplicata_conflitante"])
checa("estacao plana P00 fora dos dias validos", "P00" not in set(S["gauge_code"]))
checa("estacao Indefinido I00 fora", "I00" not in set(S["gauge_code"]))
h0 = S[(S["gauge_code"] == "H00") & (S["dia"] >= "2010-03-01") & (S["dia"] < "2010-03-10")]
checa("travado diario H00 marcado (9 dias)", h0["qc_travado"].sum() == 9, int(h0["qc_travado"].sum()))
sp = S[(S["gauge_code"] == "H01") & (S["dia"] == "2012-06-15")]
checa("pico isolado H01 marcado", len(sp) == 1 and bool(sp["qc_isolado_espacial"].iloc[0]), sp[["rain_mm","qc_isolado_espacial"]].to_dict("records"))
ev = S[(S["gauge_code"].str.startswith("C")) & (S["dia"] >= "2024-05-03") & (S["dia"] <= "2024-05-05")]
checa("evento de maio de 2024 nao removido", len(ev) >= 30, f"{len(ev)} linhas, {ev['qc_limpo_diario'].mean():.2%} limpas, media {ev['rain_mm'].mean():.1f} mm")
checa("evento muito acima do normal", ev["rain_mm"].mean() > 3 * S[(S['gauge_code'].str.startswith('C')) & (S['dia'] >= '2023-01-01') & (S['dia'] < '2024-04-01')]["rain_mm"].mean())
# fronteira do dia: janela (D-1 12:00, D 12:00] rotulada em D
import pandas as pd
x = pd.Series([1.0, 2.0, 4.0], index=pd.to_datetime(["2024-03-10 11:00", "2024-03-10 13:00", "2024-03-11 12:00"]))
y = x.resample("24h", offset="12h", closed="right", label="right").sum()
y.index = y.index.normalize()
checa("fronteira do dia", y.loc["2024-03-10"] == 1.0 and y.loc["2024-03-11"] == 6.0, y.to_dict())
# deslocamento alternativo gravado
checa("deslocamento alternativo h20 gravado", os.path.exists(f"{RAIZ}/06_dados/chuva_diaria_agregada_h20.parquet"))
A20 = pd.read_parquet(f"{RAIZ}/06_dados/chuva_diaria_agregada_h20.parquet")
checa("h20 tem dias e difere de h12", len(A20) > 0 and abs(A20["rain_mm"].sum() - S["rain_mm"].sum()) > 0,
      f"{len(A20):,} dias")
# diagnostico C rodou e gravou
checa("diagnostico C gravou a varredura", os.path.exists(f"{RAIZ}/05_saidas/03_diagnostico_fechamento_dia.csv"))
DC = pd.read_csv(f"{RAIZ}/05_saidas/03_diagnostico_fechamento_dia.csv")
checa("varredura com 3 defasagens e 24 horas", set(DC["defasagem"]) == {-1, 0, 1} and DC["h"].nunique() == 24,
      f"{len(DC)} linhas")
# rotulos do REInDesC
EVT = pd.read_parquet(f"{RAIZ}/06_dados/eventos_reindesc.parquet")
checa("eventos REInDesC montados", len(EVT) == 4, f"{len(EVT)} episodios")
checa("dois episodios severos", int(EVT["severo"].sum()) == 2, EVT[["UF", "severo", "n_gp", "n_mp"]].to_dict("records"))
checa("janela comeca 3 dias antes", bool(((EVT["data_inicio"] - EVT["janela_inicio"]).dt.days == 3).all()))
print("\nTODOS PASSARAM" if ok else "\nHA FALHAS")
sys.exit(0 if ok else 2)
