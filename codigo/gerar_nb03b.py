# -*- coding: utf-8 -*-
"""Gera o notebook 03b — verificação independente da base de tempo com a GHCNh (NOAA)."""
import json
import sys

CELLS = []


def md(txt):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": txt.strip("\n").splitlines(True)})


def code(txt):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": txt.strip("\n").splitlines(True)})


md("""
# 03b — O carimbo do UNIPLU-BR está mesmo em UTC? Verificação com a GHCNh da NOAA

Projeto final — Aprendizado Não Supervisionado (Wagner). Trabalho do grupo.

**Versão 1, 17/11/2026.** Testado com dados sintéticos; ainda não executado nos dados reais.

## Por que este notebook existe

Em 12/11 o grupo adotou UTC como base de tempo dos carimbos do UNIPLU-BR, **com ressalva**: a
verificação de terceiro era parcial (achado 01). Este notebook compara as estações sub-diárias do
UNIPLU-BR com estações horárias da GHCNh, da NOAA, que são uma fonte independente. Os resumos
diários da própria NOAA são calculados num dia que vai de 00 a 23 UTC, ou seja, o relógio da GHCNh
é UTC.

## Critério fixado ANTES de olhar os dados

Para cada registro de chuva da NOAA (quantidade acumulada em P horas, terminando no instante T, em
UTC), soma-se a chuva das estações do UNIPLU-BR próximas no intervalo (T − P + L, T + L], com o
deslocamento L variando de −6 a +6 horas, e mede-se a correlação.

| Pico da curva | Leitura |
|---|---|
| L = 0 | carimbo do UNIPLU-BR em UTC: **decisão de 12/11 confirmada** |
| L = −3 | carimbo em hora de Brasília: **decisão de 12/11 errada** |
| outro valor, ou curva sem pico claro | **inconclusivo** |

"Pico claro" = correlação no pico pelo menos 0,05 acima da correlação a 3 horas de distância dele.
Este valor foi fixado aqui, antes da execução.

Sinal: se o carimbo estivesse em hora de Brasília, uma chuva às 15 h UTC teria sido gravada como
12 h; a soma do UNIPLU-BR só coincidiria com a NOAA deslocando a janela 3 horas para trás (L = −3).

## Regras

- Só o período de **treino** (2014–2019, quando há redes sub-diárias). O teste não é tocado.
- Só as redes sub-diárias que estão no estudo (Telemetria e INMET subdiário). As estações diárias
  são carimbadas à 0 h e não respondem à pergunta.
- Pares a no máximo `RAIO_KM` do aeroporto ou da estação da NOAA.
""")

code(r'''
# 1. Configuração e caminhos
import os, io, json, time, math, urllib.request
import numpy as np
import pandas as pd

RAIZ_TESTE = os.environ.get("NB03B_RAIZ_TESTE")
if RAIZ_TESTE:
    RAIZ = RAIZ_TESTE
else:
    from google.colab import drive
    drive.mount("/content/drive", force_remount=False)
    BASE = "/content/drive/MyDrive"
    candidatos = [os.path.join(BASE, "NÃO SUPERVISIONADO", "PROJETO FINAL WAG"),
                  os.path.join(BASE, "NÃOSUPERVISIONADO", "PROJETO FINAL WAG"),
                  os.path.join(BASE, "PROJETO FINAL WAG")]
    achados = [c for c in candidatos if os.path.isdir(c)]
    if not achados:
        raise SystemExit("não achei a pasta PROJETO FINAL WAG")
    RAIZ = achados[0]

PASTA_DADOS = os.path.join(RAIZ, "06_dados")
PASTA_SAIDA = os.path.join(RAIZ, "05_saidas")
PASTA_NOAA = os.path.join(PASTA_DADOS, "noaa_ghcnh")
os.makedirs(PASTA_NOAA, exist_ok=True)

# parâmetros (fixados antes da execução)
CAIXA = {"lat": (-34.0, -25.5), "lon": (-58.0, -48.0)}      # RS e SC
PERIODO = (pd.Timestamp("2014-01-01"), pd.Timestamp("2019-12-31 23:59"))
RAIO_KM = 15.0
DESLOCAMENTOS = list(range(-6, 7))
MARGEM_PICO = 0.05
REDES_SUBDIARIAS = ["Telemetria", "INMET subdiário"]
print("raiz:", RAIZ, "| NOAA em:", PASTA_NOAA)
''')

md("""
## Baixar da NOAA

A célula baixa a lista de estações da GHCNh, separa as do Brasil dentro da caixa do RS e de SC, e
baixa o arquivo de cada uma. A documentação da NOAA descreve o caminho dos arquivos por estação;
como o endereço publicado passa por uma página interativa, a célula tenta as duas formas do
caminho e informa qual funcionou. Se nenhuma funcionar, a saída diz o que baixar à mão.
""")

code(r'''
# 2. Download (só no Colab; o teste usa arquivos locais)
URL_LISTA = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh-station-list.txt"
BASES = ["https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-station/",
         "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/index.html#hourly/access/by-station/"]

def baixar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "projeto-academico-faculdade-donaduzzi"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dado = r.read()
    if dado[:15].lower().startswith(b"<!doctype html") or dado[:6].lower() == b"<html>":
        raise ValueError("a resposta é uma página HTML, não o arquivo")
    with open(destino, "wb") as f:
        f.write(dado)
    return len(dado)

arq_lista = os.path.join(PASTA_NOAA, "ghcnh-station-list.txt")
if not os.path.exists(arq_lista):
    print("baixando a lista de estações...")
    baixar(URL_LISTA, arq_lista)

linhas = []
with open(arq_lista, encoding="latin-1") as f:
    for ln in f:
        p = ln.split()
        if len(p) >= 3:
            try:
                linhas.append((p[0], float(p[1]), float(p[2]), " ".join(p[3:])))
            except ValueError:
                pass
LISTA = pd.DataFrame(linhas, columns=["id", "lat", "lon", "resto"])
NOAA_EST = LISTA[LISTA["id"].str.startswith("BR") & LISTA["lat"].between(*CAIXA["lat"]) & LISTA["lon"].between(*CAIXA["lon"])].copy()
print(f"estações GHCNh no Brasil dentro da caixa RS/SC: {len(NOAA_EST)}")
print(NOAA_EST.to_string(index=False))

baixadas, falhas = [], []
for sid in NOAA_EST["id"]:
    destino = os.path.join(PASTA_NOAA, f"GHCNh_{sid}_por.psv")
    if os.path.exists(destino):
        baixadas.append(sid)
        continue
    ok = False
    for base in BASES:
        try:
            n = baixar(base + f"GHCNh_{sid}_por.psv", destino)
            print(f"{sid}: {n / 1e6:.1f} MB de {base}")
            baixadas.append(sid); ok = True
            break
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
    if not ok:
        falhas.append((sid, ultimo))
print(f"\nbaixadas: {len(baixadas)} | falharam: {len(falhas)}")
if falhas:
    print("Falharam:", falhas[:5])
    print("Para baixar à mão: abra https://www.ncei.noaa.gov/access/search/data-search/global-historical-climatology-network-hourly ,\n"
          f"procure cada código acima e salve o arquivo .psv em {PASTA_NOAA} com o nome GHCNh_<código>_por.psv")
if not baixadas:
    raise SystemExit("nenhuma estação da NOAA disponível; veja as instruções acima")
''')

code(r'''
# 3. Ler a NOAA: registros de chuva com o período de acumulação
def ler_noaa(arq):
    d = pd.read_csv(arq, sep="|", low_memory=False)
    cols = {c.lower(): c for c in d.columns}
    falta = [c for c in ("year", "month", "day", "hour") if c not in cols]
    if falta:
        raise ValueError(f"colunas de data ausentes {falta}; colunas: {list(d.columns)[:20]}")
    minuto = d[cols["minute"]] if "minute" in cols else 0
    t = pd.to_datetime(dict(year=d[cols["year"]], month=d[cols["month"]], day=d[cols["day"]],
                            hour=d[cols["hour"]], minute=minuto), errors="coerce")
    partes = []
    for c in d.columns:
        cl = c.lower()
        if cl == "precipitation":
            p = 1
        elif cl.startswith("precipitation_") and cl.endswith("_hour") and cl.count("_") == 2:
            p = int(cl.split("_")[1])
        else:
            continue
        v = pd.to_numeric(d[c], errors="coerce")
        m = v.notna() & t.notna()
        partes.append(pd.DataFrame({"T": t[m].dt.floor("h"), "P": p, "noaa_mm": v[m]}))
    if not partes:
        raise ValueError(f"nenhuma coluna de precipitação reconhecida; colunas: {list(d.columns)}")
    r = pd.concat(partes, ignore_index=True)
    return r[(r["T"] >= PERIODO[0]) & (r["T"] <= PERIODO[1]) & (r["noaa_mm"] >= 0) & (r["noaa_mm"] < 500)]

NOAA = {}
for sid in baixadas:
    try:
        r = ler_noaa(os.path.join(PASTA_NOAA, f"GHCNh_{sid}_por.psv"))
        if len(r):
            NOAA[sid] = r
            print(f"{sid}: {len(r):,} registros de chuva em 2014–2019 | períodos (h): {sorted(r['P'].unique())}")
    except Exception as e:
        print(f"{sid}: não li — {e}")
print("\nATENÇÃO, duas leituras a conferir na documentação da GHCNh (ghcnh_DOCUMENTATION.pdf) antes de usar o "
      "resultado:\n  1) a coluna 'precipitation' foi lida como acumulado de 1 hora;\n  2) o valor do instante T foi lido "
      "como a chuva do período que TERMINA em T (convenção dos boletins METAR e SYNOP).\nSe alguma não valer, "
      "o pico se desloca de 1 hora ou mais; corrija aqui e rode de novo.")
''')

code(r'''
# 4. UNIPLU-BR sub-diário perto de cada estação da NOAA, em série horária pelo carimbo original
EST_U = pd.read_parquet(os.path.join(PASTA_DADOS, "estacoes_rs_sc.parquet"))
EST_U.columns = [c.lower() for c in EST_U.columns]
EST_U["gauge_code"] = EST_U["gauge_code"].astype(str)
EST_U = EST_U[EST_U["network"].isin(REDES_SUBDIARIAS)].drop_duplicates("gauge_code")

def dist_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))

PARES = []
for e in NOAA_EST[NOAA_EST["id"].isin(NOAA)].itertuples():
    dk = dist_km(e.lat, e.lon, EST_U["lat"].to_numpy(), EST_U["long"].to_numpy())
    for g, k, rede in zip(EST_U["gauge_code"][dk <= RAIO_KM], dk[dk <= RAIO_KM], EST_U["network"][dk <= RAIO_KM]):
        PARES.append({"noaa": e.id, "gauge_code": g, "km": round(float(k), 1), "rede": rede})
PARES = pd.DataFrame(PARES)
print(f"pares a até {RAIO_KM:.0f} km: {len(PARES)}")
if PARES.empty:
    raise SystemExit("nenhuma estação sub-diária do UNIPLU-BR perto das estações da NOAA; aumente RAIO_KM e registre")
print(PARES.to_string(index=False))

cod = list(PARES["gauge_code"].unique())
U = pd.read_parquet(os.path.join(PASTA_DADOS, "chuva_rs_sc_bruto.parquet"), columns=["gauge_code", "datetime", "rain_mm"],
                    filters=[("gauge_code", "in", cod)])
U["gauge_code"] = U["gauge_code"].astype(str)
U["datetime"] = pd.to_datetime(U["datetime"])
U = U[(U["datetime"] >= PERIODO[0] - pd.Timedelta(days=2)) & (U["datetime"] <= PERIODO[1] + pd.Timedelta(days=2))
      & U["rain_mm"].between(0, 200)].drop_duplicates(["gauge_code", "datetime"])
# a leitura de um instante t cobre o intervalo que termina em t; vai para a hora que termina em ceil(t)
U["H"] = U["datetime"].dt.ceil("h")
HOR = U.groupby(["gauge_code", "H"])["rain_mm"].sum()
print(f"\nleituras do UNIPLU-BR usadas: {len(U):,}")
''')

code(r'''
# 5. Correlação em função do deslocamento
def curva(sid, gauge):
    r = NOAA[sid]
    s = HOR.loc[gauge] if gauge in HOR.index.get_level_values(0) else None
    if s is None or s.empty:
        return None
    idx = pd.date_range(s.index.min(), s.index.max(), freq="h")
    s = s.reindex(idx, fill_value=0.0)
    cs = np.concatenate([[0.0], np.cumsum(s.to_numpy())])
    t0 = idx[0]
    out = {}
    for L in DESLOCAMENTOS:
        fim = ((r["T"] + pd.Timedelta(hours=L) - t0) / pd.Timedelta(hours=1)).to_numpy().astype(int)
        ini = fim - r["P"].to_numpy()
        ok = (ini >= 0) & (fim + 1 < len(cs))
        if ok.sum() < 200:
            return None
        u = cs[fim[ok] + 1] - cs[ini[ok] + 1]
        n = r["noaa_mm"].to_numpy()[ok]
        out[L] = np.corrcoef(u, n)[0, 1] if u.std() > 0 and n.std() > 0 else np.nan
    return out

CURVAS = []
for p in PARES.itertuples():
    c = curva(p.noaa, p.gauge_code)
    if c:
        CURVAS.append({"noaa": p.noaa, "gauge_code": p.gauge_code, "rede": p.rede, "km": p.km, **{f"L{L:+d}": v for L, v in c.items()}})
CURVAS = pd.DataFrame(CURVAS)
if CURVAS.empty:
    raise SystemExit("nenhum par com dados suficientes no período")
cols = [f"L{L:+d}" for L in DESLOCAMENTOS]
media = CURVAS[cols].mean()
print(f"pares com curva: {len(CURVAS)}\n")
print("correlação média por deslocamento (horas):")
print(media.round(3).to_string())
pico = int(media.idxmax()[1:])
viz = [media.get(f"L{pico - 3:+d}", np.nan), media.get(f"L{pico + 3:+d}", np.nan)]
claro = media.max() - np.nanmax(viz) >= MARGEM_PICO
if pico == 0 and claro:
    VEREDITO = "CONFIRMADO: carimbo do UNIPLU-BR em UTC (pico em 0 h)"
elif pico == -3 and claro:
    VEREDITO = "REFUTADO: carimbo em hora de Brasília (pico em −3 h); a decisão de 12/11 precisa de emenda"
else:
    VEREDITO = f"INCONCLUSIVO: pico em {pico:+d} h, margem {media.max() - np.nanmax(viz):.3f}"
print("\n" + VEREDITO)
print("\npor rede (pico de cada curva):")
CURVAS["pico_h"] = CURVAS[cols].astype(float).idxmax(axis=1).str[1:].astype(int)
print(CURVAS.groupby("rede")["pico_h"].value_counts().to_string())
''')

code(r'''
# 6. Figura e registro
import matplotlib
if RAIZ_TESTE:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8, 4))
for _, row in CURVAS.iterrows():
    ax.plot(DESLOCAMENTOS, row[cols].astype(float).to_numpy(), color="#B9C7D3", lw=0.8)
ax.plot(DESLOCAMENTOS, media.to_numpy(), color="#142B47", lw=2.5, marker="o", label="média dos pares")
ax.axvline(0, color="#1F9187", ls="--", label="UTC (0 h)")
ax.axvline(-3, color="#DC8B37", ls="--", label="hora de Brasília (−3 h)")
ax.set_xlabel("deslocamento aplicado ao UNIPLU-BR (horas)")
ax.set_ylabel("correlação com a GHCNh (NOAA)")
ax.set_title("Em que deslocamento o UNIPLU-BR coincide com a NOAA?")
ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, "03b_verificacao_utc_noaa.png"), dpi=150)
plt.show()
CURVAS.to_csv(os.path.join(PASTA_SAIDA, "03b_curvas_por_par.csv"), index=False)
with open(os.path.join(PASTA_SAIDA, "03b_log_execucao.json"), "w", encoding="utf-8") as f:
    json.dump({"notebook": "03b_verificacao_utc_noaa", "data_execucao": pd.Timestamp.now().isoformat(),
               "veredito": VEREDITO, "pares": int(len(CURVAS)), "raio_km": RAIO_KM,
               "periodo": [str(x) for x in PERIODO], "estacoes_noaa": sorted(NOAA),
               "correlacao_media": media.round(4).to_dict()}, f, ensure_ascii=False, indent=2)
print("MANDE AO CLAUDE: as saídas das células 2 a 5 e a figura.")
''')


def nb():
    return {"cells": CELLS, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"}, "colab": {"provenance": []}},
        "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else "03b_verificacao_utc_noaa.ipynb"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(nb(), f, ensure_ascii=False, indent=1)
    print("ok", len(CELLS), "celulas ->", destino)
