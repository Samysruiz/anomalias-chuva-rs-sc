# -*- coding: utf-8 -*-
"""Teste do notebook 03b com dados sinteticos: carimbo em UTC deve dar CONFIRMADO,
carimbo em hora de Brasilia deve dar REFUTADO. Uso: python testar_nb03b.py nb.ipynb"""
import json, os, shutil, sys, io, contextlib
import numpy as np, pandas as pd
NB = sys.argv[1]; RAIZ = "/tmp/nb03b_teste"; FALHAS = []

def montar(desloc_h):
    shutil.rmtree(RAIZ, ignore_errors=True)
    for p in ("06_dados/noaa_ghcnh", "05_saidas"):
        os.makedirs(f"{RAIZ}/{p}", exist_ok=True)
    rng = np.random.default_rng(3)
    horas = pd.date_range("2014-01-01", "2019-12-31 23:00", freq="h")
    # chuva "verdadeira" em UTC, em pancadas
    verdade = np.where(rng.random(len(horas)) < 0.04, rng.exponential(4, len(horas)), 0.0)
    noaa = [("BR000083971", -30.0, -51.2), ("BR000083899", -27.6, -48.5)]
    with open(f"{RAIZ}/06_dados/noaa_ghcnh/ghcnh-station-list.txt", "w") as f:
        f.write("USW00003812  35.43 -82.54 ASHEVILLE\n")
        for sid, la, lo in noaa:
            f.write(f"{sid} {la:.4f} {lo:.4f} 10.0 TESTE\n")
    for sid, la, lo in noaa:
        # convencao da NOAA: o valor no instante T e a chuva acumulada no periodo que TERMINA em T
        v = np.r_[0.0, verdade[:-1]] * rng.uniform(0.7, 1.3, len(horas))
        df = pd.DataFrame({"Station_ID": sid, "Year": horas.year, "Month": horas.month, "Day": horas.day,
                           "Hour": horas.hour, "Minute": 0, "precipitation": np.round(v, 1)})
        s6 = pd.Series(v, index=horas).rolling(6).sum()
        df["precipitation_6_hour"] = np.where(horas.hour % 6 == 0, np.round(s6.to_numpy(), 1), np.nan)
        df.loc[rng.random(len(df)) < 0.5, "precipitation"] = np.nan   # metade dos horarios sem dado de 1 h
        df.to_csv(f"{RAIZ}/06_dados/noaa_ghcnh/GHCNh_{sid}_por.psv", sep="|", index=False)
    est, linhas = [], []
    for k, (sid, la, lo) in enumerate(noaa):
        for j, rede in enumerate(["Telemetria", "INMET subdiário", "Hidroweb diário"]):
            g = f"G{k}{j}"
            est.append({"gauge_code": g, "network": rede, "lat": la + 0.03 * (j + 1), "long": lo + 0.02, "state": "RS"})
            if rede == "Hidroweb diário":
                continue
            t10 = pd.date_range("2014-01-01", "2019-12-31 23:50", freq="10min")
            # leitura de 10 min: chuva da hora UTC dividida; carimbo deslocado se for hora local
            base = np.repeat(verdade, 6)[:len(t10)] / 6 * rng.uniform(0.6, 1.4, len(t10))
            carimbo = t10 + pd.Timedelta(minutes=10) + pd.Timedelta(hours=desloc_h)
            m = base > 0
            linhas.append(pd.DataFrame({"gauge_code": g, "datetime": carimbo[m], "rain_mm": base[m].astype("float32")}))
    pd.DataFrame(est).to_parquet(f"{RAIZ}/06_dados/estacoes_rs_sc.parquet", index=False)
    pd.concat(linhas, ignore_index=True).to_parquet(f"{RAIZ}/06_dados/chuva_rs_sc_bruto.parquet", index=False)

def rodar():
    os.environ["NB03B_RAIZ_TESTE"] = RAIZ
    ns, out = {"__name__": "__main__"}, io.StringIO()
    with contextlib.redirect_stdout(out):
        for c in [c for c in json.load(open(NB, encoding="utf-8"))["cells"] if c["cell_type"] == "code"]:
            exec(compile("".join(c["source"]), "nb03b", "exec"), ns)
    return ns, out.getvalue()

for desloc, esperado in [(0, "CONFIRMADO"), (-3, "REFUTADO")]:
    montar(desloc)
    ns, out = rodar()
    v = ns["VEREDITO"]
    ok = v.startswith(esperado)
    print(("PASSOU" if ok else "FALHOU"), f"carimbo deslocado {desloc:+d} h ->", v)
    print("   curva media:", ns["media"].round(3).to_dict())
    if not ok: FALHAS.append(desloc)
    if desloc == 0:
        ok2 = len(ns["NOAA_EST"]) == 2 and set(ns["PARES"]["rede"]) == {"Telemetria", "INMET subdiário"}
        print(("PASSOU" if ok2 else "FALHOU"), "filtra Brasil na caixa RS/SC e so redes sub-diarias")
        if not ok2: FALHAS.append("filtro")
print(f"{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
