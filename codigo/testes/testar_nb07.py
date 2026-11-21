# -*- coding: utf-8 -*-
"""Teste do notebook 07 (falhas dos sensores) com dados sintéticos.

Cenário A: duas estações do RS travam ou somem durante os episódios severos -> o placebo tem de acusar.
Cenário B: as mesmas falhas caem em dias sorteados fora dos episódios -> o placebo não pode acusar.
Também confere a fronteira do dia contra o resample do notebook 03, a contagem de leituras travadas,
a retomada dos lotes e a trava de hash do pré-registro.

Uso:  python testar_nb07.py
"""
import json, os, shutil, subprocess, sys, time
import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
NB = os.path.join(AQUI, "..", "07_falhas_dos_sensores.ipynb")
PRE = os.path.join(AQUI, "..", "..", "pre-registro")
QC = os.path.join(AQUI, "..", "qc_uniplu.py")
FALHAS = []


def checa(nome, ok, detalhe=""):
    print(("PASSOU " if ok else "FALHOU ") + nome, detalhe)
    if not ok:
        FALHAS.append(nome)


def monta(raiz, cenario):
    shutil.rmtree(raiz, ignore_errors=True)
    for p in ("06_dados", "05_saidas", "02_scripts"):
        os.makedirs(f"{raiz}/{p}", exist_ok=True)
    for f in ("decisoes.json", "decisoes_07_falhas.json"):
        shutil.copy(f"{PRE}/{f}", f"{raiz}/02_scripts/{f}")
    shutil.copy(QC, f"{raiz}/02_scripts/qc_uniplu.py")
    rng = np.random.default_rng(5)
    horas = pd.date_range("2022-10-01", "2025-12-31 23:00", freq="h")
    est = []
    for i in range(8):
        uf = "RS" if i < 4 else "SC"
        est.append({"gauge_code": f"{uf}{i}", "state": uf, "lat": -29.5 + 0.1 * i if uf == "RS" else -27.0 + 0.1 * i,
                    "long": -53.0 + 0.1 * i, "time_step": 60, "network": "CEMADEN" if i == 0 else ("ANA" if i % 2 else "INMET"),
                    "city": "x", "elevation": 1.0, "responsible": "x", "utc": True})
    info = pd.DataFrame(est)
    # episódios: 4 severos no RS, 2 no SC, alguns não severos
    sev_rs = [("2023-06-10", "2023-06-14"), ("2023-11-15", "2023-11-20"), ("2024-04-29", "2024-05-08"), ("2025-06-01", "2025-06-04")]
    sev_sc = [("2023-10-04", "2023-10-08"), ("2024-12-01", "2024-12-03")]
    nao_sev = [("RS", "2023-08-01", "2023-08-01"), ("SC", "2025-02-02", "2025-02-03")]
    ev = []
    for uf, lst in (("RS", sev_rs), ("SC", sev_sc)):
        for k, (a, b) in enumerate(lst):
            ev.append({"UF": uf, "id_evento": f"{uf}_{k:03d}", "data_inicio": pd.Timestamp(a), "data_fim": pd.Timestamp(b),
                       "severo": True})
    for k, (uf, a, b) in enumerate(nao_sev):
        ev.append({"UF": uf, "id_evento": f"{uf}_n{k}", "data_inicio": pd.Timestamp(a), "data_fim": pd.Timestamp(b), "severo": False})
    EV = pd.DataFrame(ev)
    EV["janela_inicio"] = EV["data_inicio"] - pd.Timedelta(days=3)
    EV["janela_fim"] = EV["data_fim"]
    for c in ("n_ocorrencias", "n_municipios", "n_gp", "n_mp", "n_pp", "duracao_dias"):
        EV[c] = 1
    EV["extenso"] = False
    EV.to_parquet(f"{raiz}/06_dados/eventos_reindesc.parquet", index=False)

    # período das falhas: dentro dos episódios do RS (A) ou deslocado 70 dias (B)
    desl = pd.Timedelta(days=0 if cenario == "A" else 70)
    partes = []
    injetado = {}
    for r in est:
        v = (rng.random(len(horas)) < 0.08) * rng.exponential(2.0, len(horas))
        v = np.round(v, 1).astype("float64")
        s = pd.Series(v, index=horas)
        if r["gauge_code"] == "RS0":          # trava em 0,4 mm durante cada episódio (A) ou fora (B)
            n = 0
            for a, b in sev_rs:
                ia, ib = pd.Timestamp(a) - pd.Timedelta(days=2) + desl, pd.Timestamp(b) + desl
                m = (s.index >= ia) & (s.index <= ib)
                s[m] = 0.4; n += int(m.sum())
            injetado["RS0"] = n
        if r["gauge_code"] == "RS1":          # some (sem leitura) durante cada episódio (A) ou fora (B)
            for a, b in sev_rs:
                ia, ib = pd.Timestamp(a) - pd.Timedelta(days=3) + desl, pd.Timestamp(b) + desl
                s = s[~((s.index >= ia) & (s.index <= ib + pd.Timedelta(hours=23)))]
        partes.append(pd.DataFrame({"gauge_code": r["gauge_code"], "datetime": s.index, "rain_mm": s.values}))
    bruto = pd.concat(partes, ignore_index=True)
    # uma cópia idêntica e uma duplicata conflitante
    bruto = pd.concat([bruto, bruto.iloc[[10]], bruto.iloc[[20]].assign(rain_mm=99.0)], ignore_index=True)
    bruto.to_parquet(f"{raiz}/06_dados/chuva_rs_sc_bruto.parquet", index=False)
    info.to_parquet(f"{raiz}/06_dados/estacoes_rs_sc.parquet", index=False)
    pd.DataFrame({"gauge_code": info["gauge_code"], "elegivel": True}).to_parquet(
        f"{raiz}/06_dados/estacoes_elegiveis.parquet", index=False)

    # diário como o notebook 03: só leituras limpas, resample de 24 h deslocado 12 h, fechado à direita
    sys.path.insert(0, os.path.dirname(QC))
    import qc_uniplu as ql
    d = bruto.drop_duplicates(["gauge_code", "datetime", "rain_mm"])
    d = d[~d.duplicated(["gauge_code", "datetime"], keep=False)]
    d = ql.marcar_travado(ql.marcar_oscilacao_rapida(d))
    d = d[~d["qc_travado"] & ~d["qc_oscilacao_rapida"]].set_index("datetime")
    a = (d.groupby("gauge_code")["rain_mm"].resample("24h", offset="12h", closed="right", label="right")
          .agg(["sum", "count"]).reset_index())
    a.columns = ["gauge_code", "rotulo", "rain_mm", "n"]
    a["dia"] = a["rotulo"].dt.normalize()
    a = a[a["n"] >= 0.9 * 24]
    a["qc_travado"] = False
    a["qc_limpo_diario"] = True
    a["conjunto"] = "teste"
    for c in ("qc_isolado_espacial", "qc_seco_espacial", "qc_atipico_iqr"):
        a[c] = False
    a[["gauge_code", "dia", "rain_mm", "conjunto", "qc_travado", "qc_isolado_espacial", "qc_seco_espacial",
       "qc_atipico_iqr", "qc_limpo_diario"]].to_parquet(f"{raiz}/06_dados/chuva_diaria_qc_h12.parquet", index=False)
    return injetado


def roda(raiz, extra=None):
    with open(NB, encoding="utf-8") as f:
        nb = json.load(f)
    src = "\n\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    arq = os.path.join(raiz, "_nb07.py")
    with open(arq, "w", encoding="utf-8") as f:
        f.write(src)
    env = dict(os.environ, NB07_RAIZ_TESTE=raiz, NB07_MAX_LINHAS="60000", MPLBACKEND="Agg")
    if extra:
        env.update(extra)
    t = time.time()
    p = subprocess.run([sys.executable, arq], capture_output=True, text=True, env=env, cwd=raiz)
    return p, time.time() - t


def main():
    # 1. fronteira do dia igual ao resample do notebook 03
    t = pd.Series(pd.to_datetime(["2024-01-01 12:00", "2024-01-01 12:10", "2024-01-02 11:59", "2024-01-02 12:00",
                                  "2024-01-01 00:00", "2024-01-01 23:50"]))
    s = pd.DataFrame({"g": "x", "datetime": t, "v": 1.0}).set_index("datetime")
    r = s.groupby("g")["v"].resample("24h", offset="12h", closed="right", label="right").count().reset_index()
    # rótulo do resample por carimbo
    rot = []
    for x in t:
        b = r[r["datetime"] >= x].iloc[0]["datetime"]
        rot.append(b.normalize())
    calc = (t - pd.Timedelta(hours=12)).dt.ceil("D")
    checa("fronteira do dia igual ao resample do notebook 03", list(calc) == rot, str(list(calc.dt.date)))

    for cen in ("A", "B"):
        raiz = f"/tmp/nb07_teste_{cen}"
        inj = monta(raiz, cen)
        p, dt = roda(raiz)
        ok = p.returncode == 0
        checa(f"cenário {cen}: roda sem erro", ok, f"({dt:.0f} s)" if ok else p.stderr[-3000:])
        if not ok:
            continue
        res = pd.read_csv(f"{raiz}/05_saidas/07_teste_placebo.csv").set_index("estatistica")
        pe = pd.read_csv(f"{raiz}/05_saidas/07_falhas_por_estacao.csv").set_index("gauge_code")
        if cen == "A":
            checa("A: leituras travadas de RS0 = injetadas", int(pe.loc["RS0", "n_trav"]) == inj["RS0"],
                  f"{int(pe.loc['RS0', 'n_trav'])} x {inj['RS0']}")
            checa("A: placebo acusa a indisponibilidade (p < 0,05)", res.loc["T_indisp", "p_valor"] < 0.05,
                  f"p = {res.loc['T_indisp', 'p_valor']:.3f}")
            checa("A: placebo acusa o travamento (p < 0,05)", res.loc["T_travado", "p_valor"] < 0.05,
                  f"p = {res.loc['T_travado', 'p_valor']:.3f}")
            sen = pd.read_csv(f"{raiz}/05_saidas/07_sensibilidades.csv")
            s2 = sen[sen["sensibilidade"] == "S2_cemaden_teste_todo"]
            checa("A: S2 acusa o travamento do Cemaden nos episódios", len(s2) == 1 and float(s2["p_valor"].iloc[0]) < 0.05,
                  str(s2[["observado_pct", "p_valor"]].to_dict("records")))
            s1 = sen[sen["sensibilidade"].str.startswith("S1") & (sen["estatistica"] == "T_indisp")]
            checa("A: S1 roda e acusa", len(s1) == 1 and float(s1["p_valor"].iloc[0]) < 0.05, str(s1["p_valor"].tolist()))
            checa("A: estações sem falha não travam", int(pe.drop(index=["RS0"])["n_trav"].sum()) == 0)
            # retomada: lotes prontos não são refeitos
            p2, dt2 = roda(raiz)
            res2 = pd.read_csv(f"{raiz}/05_saidas/07_teste_placebo.csv").set_index("estatistica")
            checa("A: retomada não refaz lotes", p2.returncode == 0 and "lote 1/" not in p2.stdout)
            checa("A: mesma semente, mesmo resultado", res2.equals(res))
            for f in ("07_mapa_travamento.png", "07_calor_ano_mes.png", "07_serie_teste.png",
                      "07_mapa_excesso_episodios.png", "07_placebo.png", "07_log_execucao.json",
                      "07_falhas_rede_ano.csv", "07_episodios_sem_janela.csv"):
                checa(f"A: gera {f}", os.path.exists(f"{raiz}/05_saidas/{f}"))
            # trava de hash
            arq = f"{raiz}/02_scripts/decisoes_07_falhas.json"
            with open(arq, "a", encoding="utf-8") as f:
                f.write(" ")
            p3, _ = roda(raiz)
            checa("A: pré-registro editado faz o notebook parar", p3.returncode != 0 and "editado" in (p3.stdout + p3.stderr))
        else:
            checa("B: falhas fora dos episódios não são acusadas (p >= 0,05)", res.loc["T_indisp", "p_valor"] >= 0.05,
                  f"p = {res.loc['T_indisp', 'p_valor']:.3f}")
    print("\n" + ("TODOS OS TESTES PASSARAM" if not FALHAS else f"{len(FALHAS)} FALHA(S): {FALHAS}"))
    sys.exit(1 if FALHAS else 0)


if __name__ == "__main__":
    main()
