# -*- coding: utf-8 -*-
"""Teste do notebook 05 com dados sinteticos.

Monta a saida dos notebooks 03 e 04 com o mesmo esquema, planta episodios de cheia
no teste e faz um modelo "bom" (escore sobe nos episodios) e um "cego" (escore
aleatorio). Executa as celulas do notebook e verifica: travas, auditoria, que a
calibracao de f usa so a validacao, que o modelo bom detecta e o cego nao, e que
os criterios e arquivos saem.

Uso:  python testar_nb05.py  caminho/para/05_avaliacao.ipynb  caminho/para/decisoes.json
"""
import json, os, shutil, sys, io, contextlib, zlib
import numpy as np
import pandas as pd

NB, DECISOES = sys.argv[1], sys.argv[2]
RAIZ = "/tmp/nb05_teste"
FALHAS = []


def checa(nome, ok, detalhe=""):
    print(("PASSOU " if ok else "FALHOU ") + nome + (f" — {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS.append(nome)


def montar():
    shutil.rmtree(RAIZ, ignore_errors=True)
    for p in ("06_dados", "05_saidas", "02_scripts"):
        os.makedirs(f"{RAIZ}/{p}", exist_ok=True)
    shutil.copy(DECISOES, f"{RAIZ}/02_scripts/decisoes.json")
    rng = np.random.default_rng(11)

    est = [f"E{i:03d}" for i in range(40)]
    uf = ["RS"] * 24 + ["SC"] * 16
    rede = ["Hidroweb diário" if i % 2 == 0 else "Telemetria" for i in range(40)]
    EST = pd.DataFrame({"gauge_code": est, "state": uf, "network": rede, "elegivel": True})
    EST["subconjunto_hidroweb"] = EST["network"] == "Hidroweb diário"
    EST.to_parquet(f"{RAIZ}/06_dados/estacoes_elegiveis.parquet", index=False)

    # ocorrencias sinteticas no teste -> episodios pela mesma regra do notebook 03
    linhas, idn = [], 0
    for u in ("RS", "SC"):
        inicios = pd.to_datetime(rng.choice(pd.date_range("2023-02-01", "2025-12-20", freq="D"), 20, replace=False))
        for d0 in sorted(inicios):
            dur = int(rng.integers(1, 4))
            mag = rng.choice(["GP", "MP", "PP"], p=[0.15, 0.35, 0.5])
            for k in range(dur):
                idn += 1
                linhas.append({"Data": d0 + pd.Timedelta(days=k), "UF": u, "Município": f"M{rng.integers(0, 12)}",
                               "Tipologia": "Hidro", "Magnitude": mag, "ID ocorrência": idn})
    OC = pd.DataFrame(linhas).sort_values(["UF", "Data"]).reset_index(drop=True)
    d = OC.groupby("UF")["Data"].diff()
    OC["id_evento"] = OC["UF"] + "_" + ((d.dt.days > 2) | d.isna()).groupby(OC["UF"]).cumsum().astype(str).str.zfill(3)
    EV = OC.groupby(["UF", "id_evento"]).agg(data_inicio=("Data", "min"), data_fim=("Data", "max"),
                                             n_ocorrencias=("ID ocorrência", "size"),
                                             n_municipios=("Município", "nunique")).reset_index()
    mag = pd.crosstab(OC["id_evento"], OC["Magnitude"]).reindex(columns=["GP", "MP", "PP"], fill_value=0)
    EV = EV.merge(mag.rename(columns={"GP": "n_gp", "MP": "n_mp", "PP": "n_pp"}), on="id_evento", how="left")
    EV["duracao_dias"] = (EV["data_fim"] - EV["data_inicio"]).dt.days + 1
    EV["severo"] = EV[["n_gp", "n_mp"]].sum(axis=1) >= 1
    EV["extenso"] = EV["n_municipios"] >= 5
    EV["janela_inicio"] = EV["data_inicio"] - pd.Timedelta(days=3)
    EV["janela_fim"] = EV["data_fim"]
    EV.to_parquet(f"{RAIZ}/06_dados/eventos_reindesc.parquet", index=False)
    OC.to_parquet(f"{RAIZ}/06_dados/ocorrencias_reindesc.parquet", index=False)

    dias = {"validacao": pd.date_range("2020-01-15", "2022-12-16"), "teste": pd.date_range("2023-01-15", "2025-12-31")}
    em_evento = set()
    for e in EV.itertuples():
        for dd in pd.date_range(e.data_inicio - pd.Timedelta(days=1), e.data_fim):
            em_evento.add((e.UF, dd))
    partes = []
    modelos = [("nivel1_acumulado", -1, 3.0), ("nivel2_pca", -1, 1.5)] + \
              [("nivel3_autoencoder", s, 3.0) for s in range(5)] + \
              [("nivel3_autoencoder_gargalo3", s, 0.8) for s in range(5)] + \
              [("nivel4_isolation", s, 0.0) for s in range(5)]
    for conj, dd in dias.items():
        g = pd.MultiIndex.from_product([est, dd], names=["gauge_code", "dia"]).to_frame(index=False)
        g["uf"] = g["gauge_code"].map(dict(zip(est, uf)))
        flag = np.array([(u, x) in em_evento for u, x in zip(g["uf"], g["dia"])]) if conj == "teste" else np.zeros(len(g), bool)
        for m, s, ganho in modelos:
            r = np.random.default_rng(zlib.crc32(f"{m}|{s}|{conj}".encode()))
            esc = r.lognormal(0, 1, len(g)) + ganho * flag * r.uniform(1.5, 3.0, len(g))
            partes.append(pd.DataFrame({"modelo": m, "semente": np.int16(s), "conjunto": conj,
                                        "gauge_code": g["gauge_code"], "dia": g["dia"], "escore": esc.astype("float32")}))
    S = pd.concat(partes, ignore_index=True)
    S["no_hidroweb"] = S["gauge_code"].isin(set(EST.loc[EST["subconjunto_hidroweb"], "gauge_code"]))
    S.to_parquet(f"{RAIZ}/06_dados/escores_04.parquet", index=False)
    n_va, n_te = 40 * len(dias["validacao"]), 40 * len(dias["teste"])
    json.dump({"modo_demonstracao": False, "decisoes_sha256_16": "d4c58a627755c8f9", "data_execucao": "sintetico",
               "janelas": {"treino": 1, "validacao": n_va, "teste": n_te}},
              open(f"{RAIZ}/05_saidas/04_log_execucao.json", "w"))
    va1 = S[(S["modelo"] == "nivel1_acumulado") & (S["conjunto"] == "validacao")]
    va1.groupby("gauge_code")["escore"].quantile(0.99).rename("p99_acumulado_treino").reset_index()[
        ["p99_acumulado_treino", "gauge_code"]].to_csv(f"{RAIZ}/05_saidas/04_nivel1_p99_treino.csv", index=False)
    return EV


def rodar(decisao):
    os.environ["NB05_RAIZ_TESTE"] = RAIZ
    os.environ["NB05_DECISAO_EMENDA"] = decisao
    os.environ["NB05_DATA_DECISAO"] = "2026-11-18" if decisao else ""
    cel = [c for c in json.load(open(NB, encoding="utf-8"))["cells"] if c["cell_type"] == "code"]
    ns, saida = {"__name__": "__main__"}, io.StringIO()
    parou = None
    with contextlib.redirect_stdout(saida):
        for c in cel:
            try:
                exec(compile("".join(c["source"]), "nb05", "exec"), ns)
            except SystemExit as e:
                parou = str(e)
                break
    return ns, saida.getvalue(), parou


EV = montar()
print(f"episodios sinteticos: {len(EV)}, severos: {int(EV['severo'].sum())}")

# 1. trava: sem decisao, para
_, _, parou = rodar("")
checa("para sem a decisao do grupo sobre a emenda", parou is not None and "DECISAO_EMENDA_LIMIAR" in parou)

# 2. trava: 'aplicada' com v1.2 para
_, _, parou = rodar("aplicada")
checa("para quando 'aplicada' mas o decisoes.json continua v1.2", parou is not None and "1.3" in parou)

# 3. execucao completa
ns, out, parou = rodar("rejeitada")
checa("execucao completa sem parar", parou is None, str(parou))
if parou is None:
    R, VER, RES = ns["R"], ns["VER"], ns["RES"]
    checa("auditoria sem falhas nos dados sinteticos", ns["FALHAS_AUDITORIA"] == [], str(ns["FALHAS_AUDITORIA"]))
    p = R[(R["estacoes"] == "todas") & (R["q"] == 0.99) & R["principal_fonte"] & (R["alvo"] == 0.01)]
    checa("taxa de alarme na validacao <= 1% em todas as configuracoes", (p["taxa_alarme_validacao"] <= 0.01 + 1e-12).all(),
          f"max {p['taxa_alarme_validacao'].max():.4f}")
    p3 = R[(R["estacoes"] == "todas") & (R["q"] == 0.99) & R["principal_fonte"] & (R["alvo"] == 0.03)]
    checa("taxa de alarme na validacao <= 3% no segundo ponto", (p3["taxa_alarme_validacao"] <= 0.03 + 1e-12).all())
    rec = p.groupby("modelo")["recall_principal"].mean()
    print(rec.round(3).to_string())
    checa("modelo bom (autoencoder sintetico) detecta mais que o cego (IF sintetico)",
          rec["nivel3_autoencoder"] > rec["nivel4_isolation"] + 0.2,
          f"{rec['nivel3_autoencoder']:.2f} contra {rec['nivel4_isolation']:.2f}")
    c2 = ns["C2"].groupby("modelo")["auc"].mean()
    checa("criterio 2: AUC do modelo cego perto de 0,5", abs(c2["nivel4_isolation"] - 0.5) < 0.03, f"{c2['nivel4_isolation']:.3f}")
    checa("criterio 2: AUC do modelo bom bem acima de 0,5", c2["nivel3_autoencoder"] > 0.7, f"{c2['nivel3_autoencoder']:.3f}")
    checa("cinco criterios com veredito", len(VER) == 5 and VER["veredito"].isin(["REFUTA", "não refuta", "inconclusivo"]).all())
    checa("criterio 1 refuta quando AE e PCA... (AE sintetico forte > PCA): nao refuta",
          VER.iloc[0]["veredito"] in ("não refuta", "inconclusivo"), VER.iloc[0]["veredito"])
    # o teste nao influencia f: trocar os escores do teste nao muda f
    f_antes = p.set_index(["modelo", "semente"])[["f_RS", "f_SC"]]
    S2 = pd.read_parquet(f"{RAIZ}/06_dados/escores_04.parquet")
    m = S2["conjunto"] == "teste"
    S2.loc[m, "escore"] = S2.loc[m, "escore"] * 10
    S2.to_parquet(f"{RAIZ}/06_dados/escores_04.parquet", index=False)
    ns2, _, parou2 = rodar("rejeitada")
    if parou2 is None:
        p2 = ns2["R"]
        p2 = p2[(p2["estacoes"] == "todas") & (p2["q"] == 0.99) & p2["principal_fonte"] & (p2["alvo"] == 0.01)]
        f_depois = p2.set_index(["modelo", "semente"])[["f_RS", "f_SC"]]
        checa("f e limiares nao dependem do teste (escores de teste x10, f identico)",
              np.allclose(f_antes.sort_index().to_numpy(), f_depois.sort_index().to_numpy()))
    else:
        checa("segunda execucao", False, parou2)
    arqs = ["05_metricas_todas_as_configuracoes.csv", "05_resumo_principal.csv", "05_deteccao_por_episodio.csv",
            "05_criterios_de_refutacao.csv", "05_metricas_extras.csv", "05_sensibilidade_agrupamento.csv",
            "05_sensibilidade_limiar_e_f.csv", "05_log_execucao.json", "05_recall_por_modelo.png",
            "05_serie_alarmes_teste.png"]
    falt = [a for a in arqs if not os.path.exists(f"{RAIZ}/05_saidas/{a}")]
    checa("todos os arquivos de saida gravados", not falt, str(falt))
    print("\n--- trecho da saida da celula 7 ---")
    i = out.find("CRITÉRIOS DE REFUTAÇÃO")
    print(out[i:i + 1400])

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
