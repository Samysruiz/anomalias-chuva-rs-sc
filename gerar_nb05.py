# -*- coding: utf-8 -*-
"""Gera o notebook 05 — avaliação pré-registrada contra os eventos do REInDesC."""
import json
import sys

CELLS = []


def md(txt):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": txt.strip("\n").splitlines(True)})


def code(txt):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": txt.strip("\n").splitlines(True)})


md("""
# 05 — Avaliação contra os eventos do REInDesC

Projeto final — Aprendizado Não Supervisionado (Wagner). Trabalho do grupo: Felipe Fernandes
Clivati, Juan Carlos Guatierri Alves, Leonardo Secco Silva, Rafael Lazarin Lobo de Almeida,
Samara Ruiz Silva e Victor Hugo Stein Blauth.

**Versão 1, 17/11/2026.** Testado com dados sintéticos; ainda não executado nos dados reais.

Entra com os escores que o notebook 04 gravou e sai com o resultado do trabalho: quantos episódios
de cheia cada modelo detecta, com quantos alarmes falsos, com quantos dias de antecedência, e o
veredito de cada um dos cinco critérios de refutação.

## Antes de rodar: duas travas

1. **A decisão do grupo sobre a emenda do limiar** precisa estar preenchida na célula 2
   (`DECISAO_EMENDA_LIMIAR`). Sem ela o notebook para. Pelo próprio texto da emenda proposta, a
   janela para decidir fecha quando a primeira avaliação roda, e esta é a primeira avaliação.
2. **Nada aqui é ajustado depois de ver o resultado.** Os limiares por estação e a fração regional
   **f** saem só da validação. O teste é pontuado e medido, nunca consultado para decidir.

## O que este notebook faz

1. Audita a entrada: confere linhas, partições, estações e medianas contra o registro do notebook 04.
2. Limiar por estação: percentil 99 do escore na validação (95 e 99,5 como sensibilidade).
3. Alarme regional: dia em alarme na UF quando a fração de estações ativas acima do limiar atinge **f**.
4. Calibra **f** na validação para 1% dos dias (principal) e 3% (segundo ponto); 0,5% e 2% como sensibilidade.
5. No teste: recall por episódio, alarmes falsos por ano, antecedência em dias e PR-AUC diária,
   com média e desvio padrão nas cinco sementes.
6. Replica tudo só com o Hidroweb diário (5º critério de refutação).
7. Confronta os cinco critérios de refutação e calcula as três métricas extras sobre o autoencoder.
8. Grava tabelas, figuras e o registro de execução.

## O que este notebook NÃO faz

- Não retreina nada e não altera nenhum escore.
- Não escolhe o melhor modelo, a melhor semente nem o melhor limiar pelo teste.
- Não calcula a sensibilidade de janela 7 e 30 dias, que exigiria retreinar no notebook 04.
""")

code(r'''
# 1. Configuração, Drive e caminhos
import os, sys, json, time, glob, hashlib, platform, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

RAIZ_TESTE = os.environ.get("NB05_RAIZ_TESTE")
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
os.makedirs(PASTA_SAIDA, exist_ok=True)
print("raiz  :", RAIZ)
print("dados :", PASTA_DADOS)
print("saídas:", PASTA_SAIDA)
''')

md("""
## Trava da emenda do limiar

A emenda proposta em 13/11 (`pre-registro/emenda-proposta-2026-11-13-limiar.md`) acrescenta uma
análise de sensibilidade com o limiar por estação calculado **no treino**. O grupo decide antes
desta primeira avaliação:

- `"rejeitada"`: segue com o `decisoes.json` v1.2. O limiar no treino continua existindo só para o
  nível 1, onde o pré-registro já o define.
- `"aplicada"`: exige o `decisoes.json` v1.3 **e** o arquivo com o percentil 99 de cada modelo no
  treino (`p99_treino_por_modelo.parquet`). **O notebook 04 atual não grava esses escores de
  treino**, então aplicar a emenda exige pontuar as janelas de treino antes. Sem o arquivo, o
  notebook para, em vez de rodar sem a análise que a emenda promete.

Em qualquer dos casos a taxa de alarme observada no teste é relatada ao lado da calibrada.
""")

code(r'''
# 2. Pré-registro, trava da emenda e parâmetros não registrados

# ======================= PREENCHER ANTES DE RODAR ==========================
DECISAO_EMENDA_LIMIAR = ""        # "rejeitada" ou "aplicada"
DATA_DECISAO_GRUPO = ""           # ex.: "2026-11-18"
# ===========================================================================
DECISAO_EMENDA_LIMIAR = DECISAO_EMENDA_LIMIAR or os.environ.get("NB05_DECISAO_EMENDA", "")
DATA_DECISAO_GRUPO = DATA_DECISAO_GRUPO or os.environ.get("NB05_DATA_DECISAO", "")

with open(os.path.join(PASTA_SCRIPTS, "decisoes.json"), "rb") as f:
    _bytes = f.read()
DEC = json.loads(_bytes.decode("utf-8"))
HASH_DECISOES = hashlib.sha256(_bytes).hexdigest()[:16]

VERSOES_ACEITAS = {"1.0": "9e95c5fe56841bf7", "1.1": "ecb0a097f983665c",
                   "1.2": "d4c58a627755c8f9", "1.3": "cbd0f874d7fe9271"}
assert DEC["versao"] in VERSOES_ACEITAS, f"versão {DEC['versao']} não reconhecida; registre a emenda antes de seguir"
if HASH_DECISOES != VERSOES_ACEITAS[DEC["versao"]]:
    raise SystemExit(f"PARADO: hash {HASH_DECISOES} não bate com o registrado para a versão {DEC['versao']} "
                     f"({VERSOES_ACEITAS[DEC['versao']]}). O decisoes.json foi editado sem registrar a emenda.")

if DECISAO_EMENDA_LIMIAR not in ("rejeitada", "aplicada") or not DATA_DECISAO_GRUPO:
    raise SystemExit("PARADO: preencha DECISAO_EMENDA_LIMIAR ('rejeitada' ou 'aplicada') e DATA_DECISAO_GRUPO "
                     "nesta célula. A decisão é do grupo e precisa ser tomada antes da primeira avaliação.")

EMENDA_APLICADA = DECISAO_EMENDA_LIMIAR == "aplicada"
ARQ_P99_TREINO_MODELOS = os.path.join(PASTA_DADOS, "p99_treino_por_modelo.parquet")
if EMENDA_APLICADA:
    if DEC["versao"] != "1.3" or "sensibilidade_periodo_do_limiar" not in DEC.get("pontuacao_e_alarme", {}):
        raise SystemExit("PARADO: a decisão diz 'aplicada', mas o decisoes.json não está na v1.3 com a emenda. "
                         "Rode pre-registro/aplicar_emenda_limiar.py e suba o arquivo novo.")
    if not os.path.exists(ARQ_P99_TREINO_MODELOS):
        raise SystemExit("PARADO: emenda aplicada, mas falta p99_treino_por_modelo.parquet. O notebook 04 não "
                         "grava escores de treino; é preciso pontuar as janelas de treino antes desta avaliação.")
elif DEC["versao"] == "1.3":
    raise SystemExit("PARADO: o decisoes.json está na v1.3 (emenda aplicada), mas a decisão registrada aqui é "
                     "'rejeitada'. Os dois precisam concordar.")
print(f"decisoes.json versão {DEC['versao']} | sha256 {HASH_DECISOES}")
print(f"emenda do limiar: {DECISAO_EMENDA_LIMIAR} (decisão do grupo em {DATA_DECISAO_GRUPO})")

# --- pré-registrado: lido do arquivo ---
PA = DEC["pontuacao_e_alarme"]
Q_PRINCIPAL = 0.99
Q_SENSIBILIDADE = [x / 100 for x in PA["sensibilidade_limiar_estacao"]]          # 0,95 e 0,995
ALVO_PRINCIPAL = 0.01
ALVO_SEGUNDO = 0.03
ALVOS_SENSIBILIDADE = [0.005, 0.02]
ALVOS = [ALVO_PRINCIPAL, ALVO_SEGUNDO] + ALVOS_SENSIBILIDADE
DIAS_ANTES = int(DEC["avaliacao"]["dias_antes_do_inicio"])
SEMENTES = list(DEC["modelos"]["sementes"])
AGRUPAMENTOS = list(DEC["eventos"]["sensibilidade_agrupamento_dias"])
PART = {k: (pd.Timestamp(v[0]), pd.Timestamp(v[1])) for k, v in DEC["particao"].items()
        if isinstance(v, list) and len(v) == 2}

# O pré-registro define o nível 1 como "percentil 99 por estação NO TREINO" (modelos.nivel_1) e a
# regra geral como "percentil 99 do escore na validação" (pontuacao_e_alarme.limiar_estacao).
# A regra específica do nível 1 é a principal para ele; a da validação sai como sensibilidade.
LIMIAR_NIVEL1_PRINCIPAL = "treino"

# --- NÃO pré-registrado: decisões de implementação deste notebook ---
MIN_JANELAS_VALIDACAO = 100   # estação com menos janelas na validação fica sem limiar e não vota
CALIBRAR_F_POR_UF = True      # um f para o RS e outro para SC ("dia em alarme no estado")
NAO_PREREGISTRADOS = {
    "janelas mínimas de validação para a estação ter limiar": MIN_JANELAS_VALIDACAO,
    "f calibrado separadamente por UF": CALIBRAR_F_POR_UF,
    "'acima do limiar' = escore estritamente maior que o limiar": True,
    "'atinge f' = fração maior ou igual a f, com f > 0": True,
    "dias sem estação ativa na UF ficam fora do denominador da taxa de alarme": True,
    "alarme falso = dia de alarme fora da janela de detecção de todos os 121 episódios da UF": True,
    "antecedência = início do episódio menos o primeiro dia de alarme na janela (dias)": True,
    "PR-AUC diária: escore do dia = fração de estações acima do limiar P99; positivo = dia na janela de um episódio severo": True,
    "métrica que decide os critérios 1, 3, 4 e 5 = recall do conjunto principal no ponto de 1%": True,
    "critério 2 = AUC (Mann-Whitney) do escore estação-dia, dias de episódio severo contra os demais, unilateral 5%": True,
    "limiar do nível 1 no conjunto principal": LIMIAR_NIVEL1_PRINCIPAL,
}
print("\nPARÂMETROS NÃO PRÉ-REGISTRADOS (vão para o Quadro de decisões):")
for k, v in NAO_PREREGISTRADOS.items():
    print(" -", k, "=", v)

ARQ_LOG = os.path.join(PASTA_SAIDA, "05_log_execucao.json")
if os.path.exists(ARQ_LOG):
    with open(ARQ_LOG, encoding="utf-8") as f:
        _ant = json.load(f)
    print(f"\nATENÇÃO: já existe uma execução registrada em {_ant.get('data_execucao')}. Rodar de novo serve "
          "para reproduzir; nenhum parâmetro pode mudar por causa do que ela mostrou.")
''')

code(r'''
# 3. Entrada e auditoria de consistência
FALHAS_AUDITORIA = []
def confere(nome, ok, detalhe=""):
    print(("OK    " if ok else "FALHOU") + " " + nome + (f" — {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS_AUDITORIA.append(nome)

arq_esc = os.path.join(PASTA_DADOS, "escores_04.parquet")
for c in (arq_esc, os.path.join(PASTA_DADOS, "estacoes_elegiveis.parquet"),
          os.path.join(PASTA_DADOS, "eventos_reindesc.parquet"), os.path.join(PASTA_DADOS, "ocorrencias_reindesc.parquet"),
          os.path.join(PASTA_SAIDA, "04_log_execucao.json"), os.path.join(PASTA_SAIDA, "04_nivel1_p99_treino.csv")):
    if not os.path.exists(c):
        raise SystemExit(f"não achei {c}. Rode os notebooks 03 e 04 até o fim antes deste.")

S = pd.read_parquet(arq_esc)
S["gauge_code"] = S["gauge_code"].astype(str)
S["dia"] = pd.to_datetime(S["dia"])
S["semente"] = S["semente"].astype(int)
EST = pd.read_parquet(os.path.join(PASTA_DADOS, "estacoes_elegiveis.parquet"))
EST["gauge_code"] = EST["gauge_code"].astype(str)
EV = pd.read_parquet(os.path.join(PASTA_DADOS, "eventos_reindesc.parquet"))
OC = pd.read_parquet(os.path.join(PASTA_DADOS, "ocorrencias_reindesc.parquet"))
for c in ("data_inicio", "data_fim", "janela_inicio", "janela_fim"):
    EV[c] = pd.to_datetime(EV[c])
OC["Data"] = pd.to_datetime(OC["Data"])
with open(os.path.join(PASTA_SAIDA, "04_log_execucao.json"), encoding="utf-8") as f:
    LOG04 = json.load(f)
P99_N1_TREINO = pd.read_csv(os.path.join(PASTA_SAIDA, "04_nivel1_p99_treino.csv"))
P99_N1_TREINO = P99_N1_TREINO.assign(gauge_code=P99_N1_TREINO["gauge_code"].astype(str)).set_index("gauge_code")["p99_acumulado_treino"]

UF_DE = EST.set_index("gauge_code")["state"]
S["uf"] = S["gauge_code"].map(UF_DE)

MODELOS = sorted(S["modelo"].unique())
CHAVES = sorted(S[["modelo", "semente"]].drop_duplicates().itertuples(index=False, name=None))
print("modelos e sementes:", CHAVES)

# a) o registro do 04 é da rodada definitiva e usou este pré-registro
confere("notebook 04 fora do modo demonstração", LOG04.get("modo_demonstracao") is False)
confere("notebook 04 rodou com decisoes v1.2 (hash d4c58a627755c8f9)",
        LOG04.get("decisoes_sha256_16") == "d4c58a627755c8f9", str(LOG04.get("decisoes_sha256_16")))
# b) número de linhas = janelas × (modelos com e sem semente)
jan_va, jan_te = LOG04["janelas"]["validacao"], LOG04["janelas"]["teste"]
n_chaves = len(CHAVES)
confere("linhas do parquet = (janelas de validação + teste) × modelos-semente",
        len(S) == (jan_va + jan_te) * n_chaves, f"{len(S):,} contra {(jan_va + jan_te) * n_chaves:,}")
cont = S.groupby(["modelo", "semente", "conjunto"]).size().unstack()
confere("cada modelo-semente tem as mesmas janelas", (cont["validacao"] == jan_va).all() and (cont["teste"] == jan_te).all())
# c) nada de treino, e cada linha dentro da sua partição
confere("parquet sem linhas de treino", set(S["conjunto"].unique()) == {"validacao", "teste"})
for nome in ("validacao", "teste"):
    sub = S.loc[S["conjunto"] == nome, "dia"]
    ini, fim = PART[nome]
    confere(f"{nome}: dias dentro da partição", (sub.min() >= ini) and (sub.max() <= fim),
            f"{sub.min().date()} a {sub.max().date()}")
# d) sem duplicata e só estações elegíveis
confere("sem linha duplicada (modelo, semente, estação, dia)",
        not S.duplicated(["modelo", "semente", "gauge_code", "dia"]).any())
eleg = set(EST.loc[EST["elegivel"], "gauge_code"])
confere("todas as estações pontuadas são elegíveis", set(S["gauge_code"]).issubset(eleg))
confere("toda estação pontuada tem UF", S["uf"].notna().all())
confere("marcação Hidroweb igual à do notebook 03",
        set(S.loc[S["no_hidroweb"], "gauge_code"]) == set(EST.loc[EST["subconjunto_hidroweb"], "gauge_code"]) & set(S["gauge_code"]))
# e) medianas iguais às impressas pela rodada de 17/11/2026 (garante que o parquet é dessa rodada)
MEDIANAS_17_11 = {("nivel1_acumulado", "teste"): 58.400005, ("nivel1_acumulado", "validacao"): 42.299999,
                  ("nivel2_pca", "teste"): 0.031863, ("nivel2_pca", "validacao"): 0.021208,
                  ("nivel3_autoencoder", "teste"): 0.015136, ("nivel3_autoencoder", "validacao"): 0.009385,
                  ("nivel3_autoencoder_gargalo3", "teste"): 0.223008, ("nivel3_autoencoder_gargalo3", "validacao"): 0.139969,
                  ("nivel4_isolation", "teste"): 0.368308, ("nivel4_isolation", "validacao"): 0.351763}
if not RAIZ_TESTE:
    med = S.groupby(["modelo", "conjunto"])["escore"].median()
    dif = {k: abs(med.get(k, np.nan) - v) / v for k, v in MEDIANAS_17_11.items()}
    confere("medianas iguais às da rodada de 17/11/2026", all(d < 1e-4 for d in dif.values()),
            "; ".join(f"{k[0]}/{k[1]}: {med.get(k, np.nan):.6f}" for k, d in dif.items() if not d < 1e-4))
# f) eventos
if not RAIZ_TESTE:
    confere("121 episódios e 37 severos", (len(EV), int(EV["severo"].sum())) == (121, 37), f"{len(EV)} e {int(EV['severo'].sum())}")
confere("janela de detecção = início − 3 dias até o fim",
        ((EV["data_inicio"] - EV["janela_inicio"]).dt.days == DIAS_ANTES).all() and (EV["janela_fim"] == EV["data_fim"]).all())
confere("todos os episódios dentro do período de teste",
        (EV["data_inicio"] >= PART["teste"][0]).all() and (EV["data_fim"] <= PART["teste"][1]).all())

if FALHAS_AUDITORIA and not RAIZ_TESTE:
    raise SystemExit(f"PARADO: {len(FALHAS_AUDITORIA)} conferência(s) falharam: {FALHAS_AUDITORIA}. "
                     "Mande esta saída ao Claude antes de seguir.")
print(f"\nauditoria: {len(FALHAS_AUDITORIA)} falha(s)")
''')

md("""
## As funções da avaliação

Tudo o que transforma escore em alarme fica nesta célula, para ser lido e auditado num lugar só.
O teste nunca entra numa função que escolhe parâmetro: `limiares` e `calibrar_f` recebem só a
validação.
""")

code(r'''
# 4. Funções
from sklearn.metrics import average_precision_score, roc_auc_score
from scipy.stats import mannwhitneyu, spearmanr

def limiares(val, q):
    """Percentil q do escore de cada estação na validação; estação com poucas janelas fica sem limiar."""
    g = val.groupby("gauge_code")["escore"]
    n = g.size()
    return g.quantile(q)[n >= MIN_JANELAS_VALIDACAO]

def fracao_diaria(df, thr):
    """Por UF e dia: estações ativas (com escore e limiar) e fração delas acima do limiar."""
    t = df["gauge_code"].map(thr)
    m = t.notna().to_numpy()
    d = pd.DataFrame({"uf": df["uf"].to_numpy()[m], "dia": df["dia"].to_numpy()[m],
                      "acima": (df["escore"].to_numpy()[m] > t.to_numpy()[m])})
    r = d.groupby(["uf", "dia"])["acima"].agg(ativas="size", acima="sum").reset_index()
    r["frac"] = r["acima"] / r["ativas"]
    return r

def calibrar_f(frac_val, alvo):
    """Menor f > 0 tal que a fração de dias da validação com frac >= f fique <= alvo."""
    v = np.sort(frac_val.to_numpy())
    n = len(v)
    cand = np.unique(v[v > 0])
    for c in cand:                               # crescente: o primeiro que cumpre é o menor
        taxa = (n - np.searchsorted(v, c, side="left")) / n
        if taxa <= alvo:
            return float(c), float(taxa)
    return float(v.max() + 1e-9), 0.0            # nenhum f cumpre: sem alarme (registrado)

def calibrar(Fv, alvo):
    out = {}
    for uf, g in Fv.groupby("uf"):
        out[uf] = calibrar_f(g["frac"], alvo)
    return out

def alarmes(Ft, fs):
    a = Ft.copy()
    a["f"] = a["uf"].map({k: v[0] for k, v in fs.items()})
    a["alarme"] = a["frac"] >= a["f"]
    return a

def avaliar_episodios(A, ev):
    """Detecção, primeiro alarme e antecedência de cada episódio."""
    dias_alarme = {uf: set(g.loc[g["alarme"], "dia"]) for uf, g in A.groupby("uf")}
    linhas = []
    for e in ev.itertuples(index=False):
        janela = pd.date_range(e.janela_inicio, e.janela_fim, freq="D")
        hits = [d for d in janela if d in dias_alarme.get(e.UF, set())]
        primeiro = min(hits) if hits else pd.NaT
        linhas.append({"id_evento": e.id_evento, "UF": e.UF, "severo": bool(e.severo), "extenso": bool(e.extenso),
                       "detectado": bool(hits), "primeiro_alarme": primeiro,
                       "antecedencia_dias": (e.data_inicio - primeiro).days if hits else np.nan})
    return pd.DataFrame(linhas)

def dias_em_janela(ev):
    s = set()
    for e in ev.itertuples(index=False):
        for d in pd.date_range(e.janela_inicio, e.janela_fim, freq="D"):
            s.add((e.UF, d))
    return s

JANELAS_TODOS = dias_em_janela(EV)
JANELAS_SEVEROS = dias_em_janela(EV[EV["severo"]])
DIAS_EVENTO_SEVERO = set()
for e in EV[EV["severo"]].itertuples(index=False):
    for d in pd.date_range(e.data_inicio, e.data_fim, freq="D"):
        DIAS_EVENTO_SEVERO.add((e.UF, d))

def metricas(A, det, taxa_val):
    """Resumo de uma configuração no teste."""
    anos = {uf: g["dia"].nunique() / 365.25 for uf, g in A.groupby("uf")}
    chave = list(zip(A["uf"], A["dia"]))
    falso = A["alarme"].to_numpy() & np.array([k not in JANELAS_TODOS for k in chave])
    fa_ano = np.mean([falso[(A["uf"] == uf).to_numpy()].sum() / anos[uf] for uf in anos])
    sev = det[det["severo"]]
    r = {
        "recall_principal": sev["detectado"].mean(),
        "detectados_principal": int(sev["detectado"].sum()),
        "recall_secundario": det["detectado"].mean(),
        "recall_extenso": sev.loc[sev["extenso"], "detectado"].mean(),
        "recall_local": sev.loc[~sev["extenso"], "detectado"].mean(),
        "recall_RS": sev.loc[sev["UF"] == "RS", "detectado"].mean(),
        "recall_SC": sev.loc[sev["UF"] == "SC", "detectado"].mean(),
        "alarmes_falsos_por_ano_por_uf": fa_ano,
        "antecedencia_mediana_dias": sev["antecedencia_dias"].median(),
        "taxa_alarme_teste": A["alarme"].mean(),
        "taxa_alarme_validacao": float(np.mean([v[1] for v in taxa_val.values()])),
    }
    return r

def pr_auc(Ft):
    y = np.array([k in JANELAS_SEVEROS for k in zip(Ft["uf"], Ft["dia"])])
    return average_precision_score(y, Ft["frac"]), y.mean()

def criterio2(te):
    """Escore estação-dia nos dias de episódio severo contra os demais dias da mesma UF."""
    y = np.array([k in DIAS_EVENTO_SEVERO for k in zip(te["uf"], te["dia"])])
    auc = roc_auc_score(y, te["escore"])
    p = mannwhitneyu(te["escore"].to_numpy()[y], te["escore"].to_numpy()[~y], alternative="greater").pvalue
    razao = np.median(te["escore"].to_numpy()[y]) / np.median(te["escore"].to_numpy()[~y])
    return auc, p, razao
print("funções prontas")
''')

md("""
## O cálculo

Para cada modelo, semente, conjunto de estações (todas e só Hidroweb) e percentil do limiar, a
célula faz sempre a mesma coisa: limiar por estação na validação, fração diária, **f** calibrado na
validação, alarmes no teste, métricas. Nada depende do resultado de outra configuração.
""")

code(r'''
# 5. Grade de avaliação
t0 = time.time()
LINHAS, DETECCOES, ALARMES_PRINCIPAIS, FRAC_TESTE = [], [], {}, {}
GRUPOS = {"todas": S, "hidroweb": S[S["no_hidroweb"]]}

for nome_est, SS in GRUPOS.items():
    por_chave = {k: g for k, g in SS.groupby(["modelo", "semente"])}
    for (modelo, semente), g in por_chave.items():
        va = g[g["conjunto"] == "validacao"]
        te = g[g["conjunto"] == "teste"]
        configs = [("validacao", q) for q in [Q_PRINCIPAL] + Q_SENSIBILIDADE]
        if modelo == "nivel1_acumulado":
            configs.append(("treino", Q_PRINCIPAL))
        for fonte, q in configs:
            thr = limiares(va, q) if fonte == "validacao" else P99_N1_TREINO
            Fv, Ft = fracao_diaria(va, thr), fracao_diaria(te, thr)
            principal_fonte = (fonte == LIMIAR_NIVEL1_PRINCIPAL) if modelo == "nivel1_acumulado" else (fonte == "validacao")
            if q == Q_PRINCIPAL and principal_fonte:
                FRAC_TESTE[(nome_est, modelo, semente)] = Ft
            ap, prev = pr_auc(Ft)
            for alvo in ALVOS:
                fs = calibrar(Fv, alvo)
                A = alarmes(Ft, fs)
                det = avaliar_episodios(A, EV)
                r = metricas(A, det, fs)
                r.update({"estacoes": nome_est, "modelo": modelo, "semente": semente, "fonte_limiar": fonte,
                          "q": q, "alvo": alvo, "principal_fonte": principal_fonte, "pr_auc": ap,
                          "prevalencia": prev, "estacoes_com_limiar": int(len(thr)),
                          "f_RS": fs.get("RS", (np.nan,))[0], "f_SC": fs.get("SC", (np.nan,))[0]})
                LINHAS.append(r)
                if q == Q_PRINCIPAL and principal_fonte and alvo in (ALVO_PRINCIPAL, ALVO_SEGUNDO):
                    DETECCOES.append(det.assign(estacoes=nome_est, modelo=modelo, semente=semente, alvo=alvo))
                    ALARMES_PRINCIPAIS[(nome_est, modelo, semente, alvo)] = A
    print(f"{nome_est}: pronto em {time.time() - t0:.0f} s")

R = pd.DataFrame(LINHAS)
DET = pd.concat(DETECCOES, ignore_index=True)
print(f"\n{len(R)} configurações avaliadas")
''')

code(r'''
# 6. Resultado principal: todas as estações, P99, 1% e 3% dos dias
COLS = ["recall_principal", "recall_secundario", "recall_extenso", "recall_local", "recall_RS", "recall_SC",
        "alarmes_falsos_por_ano_por_uf", "antecedencia_mediana_dias", "pr_auc", "taxa_alarme_teste", "taxa_alarme_validacao"]
P = R[(R["estacoes"] == "todas") & (R["q"] == Q_PRINCIPAL) & R["principal_fonte"]]

def resumo(df):
    m = df.groupby(["alvo", "modelo"])[COLS].agg(["mean", "std"])
    m.columns = [f"{a}_{b}" for a, b in m.columns]
    m["sementes"] = df.groupby(["alvo", "modelo"]).size()
    return m.reset_index()

RES = resumo(P)
for alvo in (ALVO_PRINCIPAL, ALVO_SEGUNDO):
    print(f"\n=== ponto de operação: {alvo:.0%} dos dias de validação em alarme ===")
    t = RES[RES["alvo"] == alvo].copy()
    t["recall principal"] = t.apply(lambda x: f"{x.recall_principal_mean:.1%} ± {0 if np.isnan(x.recall_principal_std) else x.recall_principal_std:.1%}", axis=1)
    t["recall secundário"] = t["recall_secundario_mean"].map("{:.1%}".format)
    t["falsos/ano/UF"] = t["alarmes_falsos_por_ano_por_uf_mean"].map("{:.1f}".format)
    t["antecedência (d)"] = t["antecedencia_mediana_dias_mean"].map("{:.1f}".format)
    t["PR-AUC"] = t.apply(lambda x: f"{x.pr_auc_mean:.3f} ± {0 if np.isnan(x.pr_auc_std) else x.pr_auc_std:.3f}", axis=1)
    t["alarme teste"] = t["taxa_alarme_teste_mean"].map("{:.2%}".format)
    t["alarme valid."] = t["taxa_alarme_validacao_mean"].map("{:.2%}".format)
    print(t[["modelo", "sementes", "recall principal", "recall secundário", "falsos/ano/UF",
             "antecedência (d)", "PR-AUC", "alarme valid.", "alarme teste"]].to_string(index=False))

prev = P["prevalencia"].iloc[0]
print(f"\nPR-AUC de um detector ao acaso = prevalência de dias positivos = {prev:.3f}")
print("A taxa de alarme do teste ao lado da validação é obrigatória no relatório (achado 05).")
''')

md("""
## Os cinco critérios de refutação

A métrica que decide é a fixada na célula 2: **recall do conjunto principal no ponto de 1%**. Como
37 episódios dão granularidade de 2,7 pontos percentuais, cada critério também é recalculado no
ponto de 3% e na PR-AUC. Quando as três leituras discordam, o veredito é **inconclusivo**, e não o
que for mais favorável.
""")

code(r'''
# 7. Critérios de refutação
AE, PCA_, N1, IF_, AE3 = ("nivel3_autoencoder", "nivel2_pca", "nivel1_acumulado",
                          "nivel4_isolation", "nivel3_autoencoder_gargalo3")

def tabela(estacoes, alvo):
    t = R[(R["estacoes"] == estacoes) & (R["q"] == Q_PRINCIPAL) & R["principal_fonte"] & (R["alvo"] == alvo)]
    return t

def criterios(estacoes, leitura):
    if leitura == "pr_auc":
        t, met = tabela(estacoes, ALVO_PRINCIPAL), "pr_auc"
    else:
        t, met = tabela(estacoes, ALVO_PRINCIPAL if leitura == "1%" else ALVO_SEGUNDO), "recall_principal"
    v = lambda m: t.loc[t["modelo"] == m].sort_values("semente")[met].to_numpy()
    ae, pca, n1 = v(AE), v(PCA_)[0], v(N1)[0]
    outros = {m: v(m).mean() for m in (PCA_, AE, IF_, AE3)}
    c1 = not np.all(ae > pca)
    c3 = not any(x > n1 for x in outros.values())
    c4 = ae.std(ddof=1) > abs(ae.mean() - pca)
    return {"c1": c1, "c3": c3, "c4": c4, "ae": ae, "pca": pca, "n1": n1, "outros": outros}

# critério 2: escore estação-dia nos dias de episódio severo
C2 = []
for (modelo, semente), g in S[S["conjunto"] == "teste"].groupby(["modelo", "semente"]):
    auc, p, razao = criterio2(g)
    C2.append({"modelo": modelo, "semente": semente, "auc": auc, "p_unilateral": p, "razao_medianas": razao})
C2 = pd.DataFrame(C2)
print("Critério 2 — o escore se eleva nos dias de episódio severo?")
print(C2.groupby("modelo")[["auc", "p_unilateral", "razao_medianas"]].agg(["mean", "std"]).round(4).to_string())
c2_ae = C2[C2["modelo"] == AE]
c2_refuta = not ((c2_ae["auc"] > 0.5) & (c2_ae["p_unilateral"] < 0.05)).all()

VEREDITOS = []
leituras = ["1%", "3%", "pr_auc"]
CR = {(e, l): criterios(e, l) for e in ("todas", "hidroweb") for l in leituras}
def veredito(lista):
    return "REFUTA" if all(lista) else ("não refuta" if not any(lista) else "inconclusivo")

for cod, texto in [("c1", "o autoencoder não supera o PCA de forma consistente nas 5 sementes"),
                   ("c3", "nenhum modelo supera o limiar de chuva acumulada"),
                   ("c4", "a variabilidade entre sementes excede a diferença AE − PCA")]:
    vals = [CR[("todas", l)][cod] for l in leituras]
    VEREDITOS.append({"criterio": texto, "1%": vals[0], "3%": vals[1], "PR-AUC": vals[2], "veredito": veredito(vals)})
VEREDITOS.insert(1, {"criterio": "o escore do autoencoder não se eleva nos dias dos eventos do teste",
                     "1%": c2_refuta, "3%": c2_refuta, "PR-AUC": c2_refuta,
                     "veredito": "REFUTA" if c2_refuta else "não refuta"})

# critério 5: as conclusões dos critérios 1, 3 e 4 se repetem só com o Hidroweb?
c2_hw = S[(S["conjunto"] == "teste") & S["no_hidroweb"] & (S["modelo"] == AE)]
c2_hw_ok = all((lambda a: a[0] > 0.5 and a[1] < 0.05)(criterio2(g)) for _, g in c2_hw.groupby("semente"))
c2_igual = c2_hw_ok != c2_refuta
nao_reproduz = {l: not (all(CR[("todas", l)][c] == CR[("hidroweb", l)][c] for c in ("c1", "c3", "c4")) and c2_igual)
                for l in leituras}
VEREDITOS.append({"criterio": "o resultado não se reproduz só com o Hidroweb diário",
                  "1%": nao_reproduz["1%"], "3%": nao_reproduz["3%"], "PR-AUC": nao_reproduz["pr_auc"],
                  "veredito": veredito(list(nao_reproduz.values()))})
print("\nSó Hidroweb diário:")
for l in leituras:
    c = CR[("hidroweb", l)]
    print(f"  [{l}] autoencoder: {np.round(c['ae'], 3)} | PCA: {c['pca']:.3f} | nível 1: {c['n1']:.3f}")
VER = pd.DataFrame(VEREDITOS)
print("\nCRITÉRIOS DE REFUTAÇÃO (True = a condição de refutação ocorreu nessa leitura)")
print(VER.to_string(index=False))
for l in leituras:
    c = CR[("todas", l)]
    print(f"\n[{l}] autoencoder por semente: {np.round(c['ae'], 3)} | PCA: {c['pca']:.3f} | nível 1: {c['n1']:.3f}")
''')

md("""
## As três métricas extras

Respondem à suspeita levantada pela demonstração didática: o autoencoder mede a forma da chuva ou
só o volume? São descritivas e não decidem nada. Usam a semente 0 dos modelos com semente.
""")

code(r'''
# 8. Métricas extras
te = S[S["conjunto"] == "teste"]
base = te[te["modelo"] == N1][["gauge_code", "dia", "escore"]].rename(columns={"escore": "acumulado"})
def pega(m, s):
    return te[(te["modelo"] == m) & (te["semente"] == s)][["gauge_code", "dia", "escore"]]
EXTRA = []
for m in (PCA_, AE, AE3, IF_):
    s = -1 if m == PCA_ else 0
    j = pega(m, s).merge(base, on=["gauge_code", "dia"])
    EXTRA.append({"metrica": f"Spearman(escore {m}, chuva acumulada)", "valor": spearmanr(j["escore"], j["acumulado"]).statistic})
def topo(m, s, frac=0.01):
    d = pega(m, s)
    k = max(1, int(len(d) * frac))
    return set(map(tuple, d.nlargest(k, "escore")[["gauge_code", "dia"]].astype(str).to_numpy()))
T = {m: topo(m, -1 if m in (PCA_, N1) else 0) for m in (N1, PCA_, AE, IF_)}
for a, b in [(AE, PCA_), (AE, N1), (PCA_, N1), (IF_, N1), (AE, IF_)]:
    EXTRA.append({"metrica": f"sobreposição do 1% mais anômalo, {a} × {b} (Jaccard)",
                  "valor": len(T[a] & T[b]) / len(T[a] | T[b])})
j = pega(AE, 0).merge(pega(PCA_, -1), on=["gauge_code", "dia"], suffixes=("_ae", "_pca"))
EXTRA.append({"metrica": "Spearman(autoencoder, PCA)", "valor": spearmanr(j["escore_ae"], j["escore_pca"]).statistic})
EXTRA = pd.DataFrame(EXTRA)
print(EXTRA.round(3).to_string(index=False))
print("\nLeitura: Spearman do autoencoder com a chuva acumulada perto de 1 e sobreposição alta com o nível 1 "
      "indicam que o autoencoder mede sobretudo volume; Spearman AE × PCA perto de 1 indica que a não linearidade "
      "não muda a ordenação.")
''')

code(r'''
# 9. Sensibilidade ao agrupamento dos episódios (1, 2, 3 e 5 dias)
def episodios(oc, gap):
    oc = oc.sort_values(["UF", "Data"]).copy()
    d = oc.groupby("UF")["Data"].diff()
    oc["_novo"] = (d.dt.days > gap) | d.isna()
    oc["id_evento"] = oc["UF"] + "_" + oc.groupby("UF")["_novo"].cumsum().astype(str).str.zfill(3)
    ev = oc.groupby(["UF", "id_evento"]).agg(data_inicio=("Data", "min"), data_fim=("Data", "max"),
                                             n_municipios=("Município", "nunique")).reset_index()
    sev = oc[oc["Magnitude"].isin(["GP", "MP"])].groupby("id_evento").size()
    ev["severo"] = ev["id_evento"].map(sev).fillna(0) > 0
    ev["extenso"] = ev["n_municipios"] >= 5
    ev["janela_inicio"] = ev["data_inicio"] - pd.Timedelta(days=DIAS_ANTES)
    ev["janela_fim"] = ev["data_fim"]
    return ev

SENS_AGR = []
for gap in AGRUPAMENTOS:
    evg = episodios(OC, gap)
    for (est, m, s, alvo), A in ALARMES_PRINCIPAIS.items():
        if est != "todas":
            continue
        det = avaliar_episodios(A, evg[evg["severo"]])
        SENS_AGR.append({"agrupamento_dias": gap, "modelo": m, "semente": s, "alvo": alvo,
                         "episodios_severos": int(evg["severo"].sum()), "recall_principal": det["detectado"].mean()})
SENS_AGR = pd.DataFrame(SENS_AGR)
print(SENS_AGR.groupby(["alvo", "agrupamento_dias", "episodios_severos", "modelo"])["recall_principal"]
      .mean().unstack("modelo").round(3).to_string())
''')

code(r'''
# 10. Sensibilidade do limiar (P95, P99,5) e de f (0,5% e 2%), todas as estações
SENS = (R[(R["estacoes"] == "todas")]
        .groupby(["fonte_limiar", "q", "alvo", "modelo"])[["recall_principal", "pr_auc", "taxa_alarme_teste"]]
        .mean().round(3).reset_index())
print(SENS.pivot_table(index=["fonte_limiar", "q", "alvo"], columns="modelo", values="recall_principal").to_string())
print("\nnível 1 com limiar do TREINO (regra específica do pré-registro) contra limiar da validação, a 1%:")
print(R[(R["modelo"] == N1) & (R["estacoes"] == "todas") & (R["q"] == Q_PRINCIPAL) & (R["alvo"] == ALVO_PRINCIPAL)]
      [["fonte_limiar", "recall_principal", "pr_auc", "taxa_alarme_validacao", "taxa_alarme_teste"]].to_string(index=False))
''')

code(r'''
# 11. Figuras
import matplotlib
if RAIZ_TESTE:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

ORDEM = [N1, PCA_, AE, AE3, IF_]
ROT = {N1: "Chuva acumulada", PCA_: "PCA", AE: "Autoencoder (13)", AE3: "Autoencoder (3)", IF_: "Isolation Forest"}
fig, ax = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
for i, alvo in enumerate((ALVO_PRINCIPAL, ALVO_SEGUNDO)):
    t = RES[RES["alvo"] == alvo].set_index("modelo").reindex(ORDEM)
    ax[i].bar(range(len(ORDEM)), t["recall_principal_mean"], yerr=t["recall_principal_std"].fillna(0),
              color="#2D70AD", capsize=4)
    ax[i].set_xticks(range(len(ORDEM)), [ROT[m] for m in ORDEM], rotation=20, ha="right")
    ax[i].set_title(f"Recall dos 37 episódios severos — alarme em {alvo:.0%} dos dias")
    ax[i].set_ylim(0, 1)
ax[0].set_ylabel("recall (média ± desvio nas sementes)")
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, "05_recall_por_modelo.png"), dpi=150)
plt.show()

fig, axs = plt.subplots(2, 1, figsize=(13, 6), sharex=True)
for ax, uf in zip(axs, ["RS", "SC"]):
    for m, cor in [(N1, "#687A8B"), (AE, "#1F9187")]:
        s = -1 if m == N1 else 0
        A = ALARMES_PRINCIPAIS[("todas", m, s, ALVO_PRINCIPAL)]
        a = A[A["uf"] == uf]
        ax.plot(a["dia"], a["frac"], lw=0.6, color=cor, label=f"{ROT[m]} (fração acima do limiar)")
        ax.scatter(a.loc[a["alarme"], "dia"], a.loc[a["alarme"], "frac"], s=12, color=cor)
    for e in EV[(EV["UF"] == uf) & EV["severo"]].itertuples():
        ax.axvspan(e.janela_inicio, e.janela_fim + pd.Timedelta(days=1), color="#DC8B37", alpha=0.25)
    ax.set_title(f"{uf}: fração diária de estações acima do limiar; laranja = janela de detecção dos episódios severos")
    ax.set_ylabel("fração")
axs[0].legend(loc="upper left", fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, "05_serie_alarmes_teste.png"), dpi=150)
plt.show()
''')

code(r'''
# 12. Gravar e registrar
R.to_csv(os.path.join(PASTA_SAIDA, "05_metricas_todas_as_configuracoes.csv"), index=False)
RES.to_csv(os.path.join(PASTA_SAIDA, "05_resumo_principal.csv"), index=False)
DET.to_csv(os.path.join(PASTA_SAIDA, "05_deteccao_por_episodio.csv"), index=False)
VER.to_csv(os.path.join(PASTA_SAIDA, "05_criterios_de_refutacao.csv"), index=False)
C2.to_csv(os.path.join(PASTA_SAIDA, "05_criterio2_por_semente.csv"), index=False)
EXTRA.to_csv(os.path.join(PASTA_SAIDA, "05_metricas_extras.csv"), index=False)
SENS_AGR.to_csv(os.path.join(PASTA_SAIDA, "05_sensibilidade_agrupamento.csv"), index=False)
SENS.to_csv(os.path.join(PASTA_SAIDA, "05_sensibilidade_limiar_e_f.csv"), index=False)

log = {
    "notebook": "05_avaliacao", "versao_notebook": "1",
    "data_execucao": pd.Timestamp.now().isoformat(),
    "decisoes_versao": DEC["versao"], "decisoes_sha256_16": HASH_DECISOES,
    "emenda_limiar": DECISAO_EMENDA_LIMIAR, "data_decisao_grupo": DATA_DECISAO_GRUPO,
    "escores_04_execucao": LOG04.get("data_execucao"),
    "auditoria_falhas": FALHAS_AUDITORIA,
    "criterios": VER.to_dict("records"),
    "parametros_nao_preregistrados": NAO_PREREGISTRADOS,
    "pandas": pd.__version__, "python": platform.python_version(),
}
with open(ARQ_LOG, "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2, default=str)
print("gravado em", PASTA_SAIDA)
print("\nMANDE AO CLAUDE: as saídas das células 3, 6, 7, 8, 9 e 10, e as duas figuras.")
''')


def nb():
    return {"cells": CELLS, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "colab": {"provenance": []}}, "nbformat": 4, "nbformat_minor": 5}


SUGESTAO_MD = """
## Versão de sugestão: o que já vem preenchido

Esta cópia vem com a **sugestão** registrada em `pre-registro/decisao-emenda-limiar-proposta.md`:
`DECISAO_EMENDA_LIMIAR = "rejeitada"` e o nível 1 com o limiar do treino como principal.
**A data da decisão vem vazia de propósito:** o notebook continua parando até alguém do grupo
preencher `DATA_DECISAO_GRUPO`, o que só deve acontecer depois que o grupo concordar. Se o grupo
preferir aplicar a emenda, troque para `"aplicada"` e siga as instruções da célula 2.
"""


if __name__ == "__main__":
    sugestao = "--sugestao" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--sugestao"]
    if sugestao:
        i = next(k for k, c in enumerate(CELLS) if c["cell_type"] == "code" and "PREENCHER ANTES DE RODAR" in "".join(c["source"]))
        src = "".join(CELLS[i]["source"])
        alvo = 'DECISAO_EMENDA_LIMIAR = ""        # "rejeitada" ou "aplicada"'
        assert alvo in src
        src = src.replace(alvo, 'DECISAO_EMENDA_LIMIAR = "rejeitada"   # SUGESTÃO; o grupo confirma ou troca por "aplicada"')
        src = src.replace('DATA_DECISAO_GRUPO = ""           # ex.: "2026-11-18"',
                          'DATA_DECISAO_GRUPO = ""           # VAZIO DE PROPÓSITO: preencha só depois que o grupo concordar')
        CELLS[i]["source"] = src.splitlines(True)
        CELLS.insert(1, {"cell_type": "markdown", "metadata": {}, "source": SUGESTAO_MD.strip("\n").splitlines(True)})
    destino = args[0] if args else "05_avaliacao.ipynb"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(nb(), f, ensure_ascii=False, indent=1)
    print("ok", len(CELLS), "celulas ->", destino)
