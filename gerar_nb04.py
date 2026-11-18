# -*- coding: utf-8 -*-
"""Gera o notebook 04 — janelas, normalização e modelos."""
import json
import sys

CELLS = []


def md(txt):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": txt.strip("\n").splitlines(True)})


def code(txt):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": txt.strip("\n").splitlines(True)})


md("""
# 04 — Janelas, normalização e modelos

Projeto final — Aprendizado Não Supervisionado (Wagner). Trabalho do grupo: Felipe Fernandes
Clivati, Juan Carlos Guatierri Alves, Leonardo Secco Silva, Rafael Lazarin Lobo de Almeida,
Samara Ruiz Silva e Victor Hugo Stein Blauth.

**Versão 3, 18/11/2026.** Inclui as alterações do Felipe: o diagnóstico da chuva acumulada por ano
no Hidroweb (célula 6b) e as saídas do modo de demonstração em subpastas `_demo`. A rodada real é
idêntica à versão 2, que rodou em 17/11/2026 e reproduziu exatamente a de 13/11/2026.

Entra com o que o notebook 03 gravou e sai com os **escores de anomalia** por estação e por dia,
para validação e teste. A transformação de escore em alarme, e o confronto com os eventos, são do
notebook 05. A separação é proposital: assim os escores ficam gravados e a avaliação pode ser
refeita sem retreinar nada.

## O que este notebook faz

1. Lê `decisoes.json` (v1.1). Nenhum parâmetro registrado é digitado aqui.
2. Monta janelas de 15 dias por estação, **só completas**, com intervalo entre partições.
3. Normaliza por estação, com média e desvio **calculados apenas no treino**.
4. Treina os quatro níveis da escada: chuva acumulada, PCA, autoencoder e Isolation Forest.
5. Grava os escores de validação e teste, mais o registro de execução.

## O que este notebook NÃO faz

- Não calcula alarme, recall, antecedência nem PR-AUC. Isso é do notebook 05.
- **Não consulta o conjunto de teste para nenhuma decisão.** O teste é pontuado e gravado, nada mais.
- Não calibra os limiares espaciais do QC, que continuam com os valores de partida do notebook 03.

## Regra de vazamento, aplicada em quatro pontos

| Onde | Como |
|---|---|
| Janelas | Uma janela só entra numa partição se **todos** os seus 15 dias estiverem nela |
| Intervalo entre partições | Os últimos 15 dias do treino e os últimos 15 da validação são descartados |
| Normalização | Média e desvio por estação vêm **só** dos dias de treino |
| Ajuste dos modelos | PCA, autoencoder e Isolation Forest são ajustados **só** com janelas de treino |

Consequência que precisa estar no relatório: como a janela é causal e termina no dia rotulado, os
14 primeiros dias de cada partição não recebem escore. No teste, o primeiro dia pontuável é
**2023-01-15**. Um evento que comece antes disso é indetectável por construção, e a célula 6 conta
quantos são.

## Parâmetros que o pré-registro fixa

Janela de 15 dias com passo de 1 dia, unidade univariada por estação; normalização por estação com
estatísticas só do treino; intervalo entre conjuntos igual ao comprimento da janela; PCA com
componentes que explicam 90% da variância no treino; autoencoder com checkpoint a cada época e
preservação do melhor modelo na validação; Isolation Forest; sementes 0 a 4.

## Parâmetros que o pré-registro NÃO fixa

A célula 2 imprime a lista completa. Os que mais pesam no resultado: a forma da normalização, a
arquitetura e o treino do autoencoder, os hiperparâmetros do Isolation Forest, o teto de janelas
de treino e a exigência de janela completa. Todos entram no Quadro de decisões do relatório.
""")

code(r'''
# 1. Configuração, Drive e caminhos
import os, sys, json, time, gc, glob, hashlib, platform, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 200)

RAIZ_TESTE = os.environ.get("NB04_RAIZ_TESTE")
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
PASTA_MODELOS = os.path.join(PASTA_DADOS, "_modelos_04")
os.makedirs(PASTA_SAIDA, exist_ok=True)
os.makedirs(PASTA_MODELOS, exist_ok=True)

print("raiz    :", RAIZ)
print("dados   :", PASTA_DADOS)
print("saídas  :", PASTA_SAIDA)
print("modelos :", PASTA_MODELOS)
''')

code(r'''
# 2. Pré-registro e parâmetros não registrados
with open(os.path.join(PASTA_SCRIPTS, "decisoes.json"), "rb") as f:
    _bytes = f.read()
DEC = json.loads(_bytes.decode("utf-8"))
HASH_DECISOES = hashlib.sha256(_bytes).hexdigest()[:16]

VERSOES_ACEITAS = {"1.0": "9e95c5fe56841bf7", "1.1": "ecb0a097f983665c", "1.2": "d4c58a627755c8f9"}
assert DEC["versao"] in VERSOES_ACEITAS, f"versão {DEC['versao']} não reconhecida; registre a emenda antes de seguir"
if HASH_DECISOES != VERSOES_ACEITAS[DEC["versao"]]:
    print(f"ATENÇÃO: hash {HASH_DECISOES} não bate com o registrado para a versão {DEC['versao']} "
          f"({VERSOES_ACEITAS[DEC['versao']]}). O arquivo foi editado sem registrar a emenda.")

# --- pré-registrado: nada abaixo é digitado, tudo vem do arquivo ---
JANELA = int(DEC["entrada_modelo"]["janela_dias"])
PASSO_JANELA = int(DEC["entrada_modelo"]["passo_janela_dias"])
ABLACAO_JANELA = list(DEC["entrada_modelo"]["ablacao_janela_dias"])
SEMENTES = list(DEC["modelos"]["sementes"])
VAR_PCA = 0.90
PART = {k: (pd.Timestamp(v[0]), pd.Timestamp(v[1])) for k, v in DEC["particao"].items()
        if isinstance(v, list) and len(v) == 2}
DESLOC_PRINCIPAL = 12

# --- NÃO pré-registrado: decisões de implementação deste notebook ---
NORMALIZACAO = "zscore"          # "zscore" | "log1p_zscore" (sensibilidade)
EXIGIR_JANELA_COMPLETA = True    # janela com qualquer dia ausente é descartada
MAX_JANELAS_TREINO = int(os.environ.get("NB04_MAX_TREINO", 500_000))   # teto para caber no Colab
SEMENTE_AMOSTRA = 0
# O gargalo do autoencoder NÃO é parâmetro livre: ele é igualado ao número de componentes que o
# PCA reteve pela regra pré-registrada de 90% da variância (célula 8). Sem isso, a comparação entre
# os níveis 2 e 3 mede diferença de capacidade, não o efeito da não linearidade, que é a pergunta
# do pré-registro. O gargalo de sensibilidade roda em paralelo, como ablação declarada.
# MODO DEMONSTRAÇÃO: rodada rápida e barata, só para o grupo ver a comparação funcionando.
# NÃO produz resultado para o relatório. Os arquivos saem com sufixo _demo e nada definitivo
# é sobrescrito. Para a rodada de verdade, deixe em False.
MODO_DEMONSTRACAO = True

AE_GARGALO_SENSIBILIDADE = 3
AE_EPOCAS = int(os.environ.get("NB04_EPOCAS", 150))
AE_LOTE = 1024
AE_LR = 1e-3
AE_PACIENCIA = 15                # épocas sem melhora na validação antes de parar
IF_ARVORES = 200
IF_AMOSTRA = 256
DESVIO_MINIMO = 1e-6             # piso do desvio na normalização, evita divisão por zero

NAO_PREREGISTRADOS = {
    "forma da normalização por estação": NORMALIZACAO,
    "exigir janela completa (sem dia ausente)": EXIGIR_JANELA_COMPLETA,
    "teto de janelas de treino": MAX_JANELAS_TREINO,
    "semente da amostragem de treino": SEMENTE_AMOSTRA,
    "gargalo do autoencoder": "igual ao nº de componentes do PCA (regra pré-registrada de 90%)",
    "gargalo da ablação do autoencoder": AE_GARGALO_SENSIBILIDADE,
    "épocas, lote e taxa de aprendizado do autoencoder": [AE_EPOCAS, AE_LOTE, AE_LR],
    "paciência (parada antecipada) do autoencoder": AE_PACIENCIA,
    "árvores e amostra do Isolation Forest": [IF_ARVORES, IF_AMOSTRA],
    "piso do desvio padrão na normalização": DESVIO_MINIMO,
    "dia que rotula a janela": "último dia (janela causal, não usa futuro)",
    "deslocamento do dia usado": f"{DESLOC_PRINCIPAL} h (principal, pré-registrado)",
}

assert 1 <= AE_GARGALO_SENSIBILIDADE < JANELA, "o gargalo da ablação precisa ser menor que a janela"

SUFIXO = ""
PASTA_ESCORES = PASTA_DADOS      # onde escores_04.parquet é gravado
if MODO_DEMONSTRACAO:
    SUFIXO = "_demo"
    # Saídas da demonstração ficam em subpastas _demo, separadas dos resultados reais.
    PASTA_SAIDA = os.path.join(PASTA_SAIDA, "_demo")
    PASTA_MODELOS = os.path.join(PASTA_MODELOS, "_demo")
    PASTA_ESCORES = os.path.join(PASTA_DADOS, "_demo")
    for _p in (PASTA_SAIDA, PASTA_MODELOS, PASTA_ESCORES):
        os.makedirs(_p, exist_ok=True)
    MAX_JANELAS_TREINO = min(MAX_JANELAS_TREINO, 100_000)
    AE_EPOCAS = min(AE_EPOCAS, 10)
    SEMENTES = SEMENTES[:2]
    NAO_PREREGISTRADOS["MODO DEMONSTRAÇÃO"] = (
        f"ligado: {MAX_JANELAS_TREINO} janelas, {AE_EPOCAS} épocas, sementes {SEMENTES}")
    print("\n" + "=" * 78)
    print("  MODO DEMONSTRAÇÃO LIGADO")
    print("  Rodada rápida, apenas para o grupo ver a comparação entre os modelos funcionando.")
    print("  NÃO use estes números no relatório: o treino é curto, a amostra é menor e são")
    print("  apenas 2 das 5 sementes pré-registradas.")
    print(f"  Tudo sai com sufixo '{SUFIXO}', nas subpastas _demo, e nada definitivo é sobrescrito.")
    print("  Para a rodada de verdade, mude MODO_DEMONSTRACAO para False e rode de novo.")
    print("=" * 78 + "\n")
print("decisoes.json versão", DEC["versao"], "| sha256", HASH_DECISOES)
for _e in DEC.get("emendas", []):
    print(f"  emenda {_e['data']}: {_e['item']}")
print(f"\njanela {JANELA} dias, passo {PASSO_JANELA}, sementes {SEMENTES}")
print("partições:", {k: (a.date().isoformat(), b.date().isoformat()) for k, (a, b) in PART.items()})
print("\nPARÂMETROS NÃO PRÉ-REGISTRADOS (vão para o Quadro de decisões):")
for k, v in NAO_PREREGISTRADOS.items():
    print(" -", k, "=", v)
''')

code(r'''
# 3. Entrada: o que o notebook 03 gravou
arq_chuva = os.path.join(PASTA_DADOS, f"chuva_diaria_qc_h{DESLOC_PRINCIPAL}.parquet")
for caminho in (arq_chuva, os.path.join(PASTA_DADOS, "estacoes_elegiveis.parquet")):
    if not os.path.exists(caminho):
        raise SystemExit(f"não achei {caminho}. Rode o notebook 03 até o fim antes deste.")

D = pd.read_parquet(arq_chuva)
EST = pd.read_parquet(os.path.join(PASTA_DADOS, "estacoes_elegiveis.parquet"))
D["dia"] = pd.to_datetime(D["dia"])

elegiveis = EST.loc[EST["elegivel"], "gauge_code"]
hidroweb = set(EST.loc[EST["subconjunto_hidroweb"], "gauge_code"])
D = D[D["gauge_code"].isin(set(elegiveis)) & D["qc_limpo_diario"]].copy()

print(f"estações elegíveis: {len(elegiveis)} | subconjunto Hidroweb (5º critério): {len(hidroweb)}")
print(f"dias limpos de estações elegíveis: {len(D):,}")
print(f"período: {D['dia'].min().date()} a {D['dia'].max().date()}")
print("\npor conjunto:")
print(D["conjunto"].value_counts().to_string())

arq_ev = os.path.join(PASTA_DADOS, "eventos_reindesc.parquet")
EV = pd.read_parquet(arq_ev) if os.path.exists(arq_ev) else None
if EV is None:
    print("\nATENÇÃO: eventos_reindesc.parquet não encontrado. O notebook roda, mas a célula 6 "
          "não consegue contar os eventos perdidos pelo aquecimento da janela.")
else:
    print(f"\neventos do REInDesC: {len(EV)} episódios, {int(EV['severo'].sum())} severos")
''')

md("""
## Parte 1 — Janelas

A unidade de entrada é **uma janela de 15 dias de uma estação**, univariada, como o pré-registro fixa.
A janela é **causal**: ela termina no dia que rotula, de modo que o escore do dia D usa apenas os dias
D−14 a D. Isso importa para a antecedência, que o notebook 05 vai medir: com janela centrada, o escore
do dia D usaria chuva posterior a D e a antecedência ficaria inflada.

Janelas com qualquer dia ausente são **descartadas**, não preenchidas. Preencher lacuna com média ou
zero inventaria dado e, num detector de anomalias, dado inventado vira padrão aprendido.
""")

code(r'''
# 4. Construção das janelas
from numpy.lib.stride_tricks import sliding_window_view

# matriz dias × estações; ausência vira NaN e a janela que a contiver é descartada
M = D.pivot_table(index="dia", columns="gauge_code", values="rain_mm", aggfunc="first")
M = M.sort_index()
dias = M.index.to_numpy()
estacoes = M.columns.to_numpy()
A = M.to_numpy(dtype="float32")
print(f"matriz: {A.shape[0]:,} dias × {A.shape[1]:,} estações | "
      f"células ausentes: {np.isnan(A).mean() * 100:.1f}%")

# normalização por estação, com média e desvio SÓ do treino
ini_tr, fim_tr = PART["treino"]
mask_tr_dias = (dias >= np.datetime64(ini_tr)) & (dias <= np.datetime64(fim_tr))
A_tr = A[mask_tr_dias]
if NORMALIZACAO == "log1p_zscore":
    A_use, A_tr_use = np.log1p(A), np.log1p(A_tr)
else:
    A_use, A_tr_use = A, A_tr
MEDIA = np.nanmean(A_tr_use, axis=0)
DESVIO = np.nanstd(A_tr_use, axis=0)
sem_treino = ~np.isfinite(MEDIA) | ~np.isfinite(DESVIO) | (DESVIO < DESVIO_MINIMO)
if sem_treino.any():
    print(f"estações sem estatística de treino utilizável (desvio < {DESVIO_MINIMO}): {int(sem_treino.sum())} — excluídas")
MEDIA = np.where(sem_treino, 0.0, MEDIA)
DESVIO = np.where(sem_treino, 1.0, DESVIO)
Z = ((A_use - MEDIA) / DESVIO).astype("float32")
Z[:, sem_treino] = np.nan   # descarta a estação inteira

# janelas causais: a janela termina no dia que ela rotula
W = sliding_window_view(Z, JANELA, axis=0)          # (dias-J+1, estações, J)
W_bruto = sliding_window_view(A, JANELA, axis=0)    # mesma forma, em mm, para o nível 1
dias_rotulo = dias[JANELA - 1:]
valida = ~np.isnan(W).any(axis=2)                   # (dias-J+1, estações)
print(f"janelas possíveis: {valida.size:,} | completas: {int(valida.sum()):,} "
      f"({100 * valida.mean():.1f}%)")
''')

code(r'''
# 5. Partição das janelas, com o intervalo entre conjuntos
GAP = JANELA   # pré-registrado: intervalo entre conjuntos igual ao comprimento da janela

def faixa_particao(nome):
    ini, fim = PART[nome]
    ini, fim = np.datetime64(ini), np.datetime64(fim)
    # a janela inteira precisa estar dentro da partição: o rótulo é o último dia,
    # logo o primeiro dia da janela é rotulo - (J-1)
    primeiro_dia = dias_rotulo - np.timedelta64(JANELA - 1, "D")
    dentro = (primeiro_dia >= ini) & (dias_rotulo <= fim)
    # intervalo: os últimos GAP dias do treino e da validação não entram
    if nome in ("treino", "validacao"):
        dentro &= dias_rotulo <= (fim - np.timedelta64(GAP, "D"))
    return dentro

IDX = {}
for nome in ("treino", "validacao", "teste"):
    linhas = faixa_particao(nome)
    i_dia, i_est = np.where(valida & linhas[:, None])
    IDX[nome] = (i_dia, i_est)
    if len(i_dia):
        print(f"{nome:10s}: {len(i_dia):>9,} janelas | "
              f"{pd.Timestamp(dias_rotulo[i_dia.min()]).date()} a {pd.Timestamp(dias_rotulo[i_dia.max()]).date()} | "
              f"{len(np.unique(i_est)):>4} estações")
    else:
        print(f"{nome:10s}: nenhuma janela")

def monta(nome, bruto=False):
    i_dia, i_est = IDX[nome]
    fonte = W_bruto if bruto else W
    return fonte[i_dia, i_est, :].astype("float32")

# amostragem do treino, com semente fixa, só para caber na memória e no tempo
i_dia_tr, i_est_tr = IDX["treino"]
if len(i_dia_tr) > MAX_JANELAS_TREINO:
    rng = np.random.default_rng(SEMENTE_AMOSTRA)
    sel = rng.choice(len(i_dia_tr), size=MAX_JANELAS_TREINO, replace=False)
    sel.sort()
    IDX["treino"] = (i_dia_tr[sel], i_est_tr[sel])
    print(f"\ntreino amostrado: {MAX_JANELAS_TREINO:,} de {len(i_dia_tr):,} janelas "
          f"(semente {SEMENTE_AMOSTRA}); aumente MAX_JANELAS_TREINO se houver folga")

X_tr = monta("treino")
X_va = monta("validacao")
X_te = monta("teste")
print(f"\nX_treino {X_tr.shape} | X_validacao {X_va.shape} | X_teste {X_te.shape}")
print(f"memória aproximada: {(X_tr.nbytes + X_va.nbytes + X_te.nbytes) / 1e6:.0f} MB")
''')

code(r'''
# 6. Auditoria das janelas e o custo do aquecimento
linhas = []
for nome in ("treino", "validacao", "teste"):
    i_dia, i_est = IDX[nome]
    if not len(i_dia):
        continue
    linhas.append({"conjunto": nome, "janelas": len(i_dia), "estacoes": len(np.unique(i_est)),
                   "primeiro_dia": pd.Timestamp(dias_rotulo[i_dia.min()]).date(),
                   "ultimo_dia": pd.Timestamp(dias_rotulo[i_dia.max()]).date()})
AUD_JAN = pd.DataFrame(linhas)
print(AUD_JAN.to_string(index=False))

# quantos eventos severos caem antes do primeiro dia pontuável do teste
if EV is not None and len(IDX["teste"][0]):
    primeiro_te = pd.Timestamp(dias_rotulo[IDX["teste"][0].min()])
    sev = EV[EV["severo"]]
    perdidos = sev[sev["data_fim"] < primeiro_te]
    print(f"\nprimeiro dia pontuável do teste: {primeiro_te.date()}")
    print(f"episódios severos indetectáveis por construção (terminam antes disso): {len(perdidos)} de {len(sev)}")
    if len(perdidos):
        print(perdidos[["UF", "data_inicio", "data_fim", "n_municipios"]].to_string(index=False))
    print("Este número vai para as limitações do relatório.")

# por rede, para a replicação do 5º critério
est_idx = {g: i for i, g in enumerate(estacoes)}
idx_hidroweb = np.array([est_idx[g] for g in hidroweb if g in est_idx])
print(f"\nestações do subconjunto Hidroweb presentes na matriz: {len(idx_hidroweb)}")
''')

code(r'''
# 6b. Diagnóstico: mediana da chuva acumulada por ano, só no Hidroweb diário
mask_hw = np.zeros(len(estacoes), dtype=bool)
mask_hw[idx_hidroweb] = True

Af = np.nan_to_num(A, nan=0.0)
C = np.cumsum(Af, axis=0, dtype="float64")
zero = np.zeros((1, A.shape[1]), dtype="float64")
acum = (C[JANELA - 1:] - np.vstack([zero, C[:-JANELA]])).astype("float32")

ok = valida & mask_hw[None, :]
anos_rot = pd.DatetimeIndex(dias_rotulo).year

linhas = []
for ano in np.unique(anos_rot):
    sel = (anos_rot == ano)[:, None] & ok
    v = acum[sel]
    if v.size:
        linhas.append({"ano": int(ano), "janelas": int(v.size),
                       "mediana_mm": round(float(np.median(v)), 1),
                       "p90_mm": round(float(np.percentile(v, 90)), 1)})
DIAG = pd.DataFrame(linhas)
print(DIAG.to_string(index=False))
DIAG.to_csv(os.path.join(PASTA_SAIDA, "acumulado_mediano_por_ano_hidroweb.csv"), index=False)
''')

md("""
## Parte 2 — A escada de modelos

Quatro níveis, do mais simples ao mais elaborado, todos pontuando a **mesma** janela e gravando o
escore no **mesmo** formato. A comparação só é honesta se a única coisa que muda for o modelo.

| Nível | Modelo | Escore de anomalia |
|---|---|---|
| 1 | Chuva acumulada na janela | a própria soma em mm |
| 2 | PCA com 90% da variância | erro quadrático de reconstrução |
| 3 | Autoencoder, com gargalo igual ao nº de componentes do PCA | erro quadrático de reconstrução |
| 4 | Isolation Forest | inverso da facilidade de isolamento |

Níveis 1 e 2 são determinísticos e rodam uma vez. Níveis 3 e 4 rodam com as cinco sementes
pré-registradas, e o relatório reporta média e desvio padrão entre elas.

**O gargalo do autoencoder é igualado ao número de componentes que o PCA reteve.** Isso não é
detalhe de implementação: é o que torna a comparação entre os níveis 2 e 3 uma pergunta sobre
não linearidade, e não sobre capacidade. Um autoencoder com gargalo de 3 contra um PCA de 13
componentes reconstrói pior por ter menos dimensões, e nada disso diria respeito à não linearidade.
Um gargalo menor roda em paralelo como ablação declarada.
""")

code(r'''
# 7. Nível 1 — chuva acumulada na janela (referência sem aprendizado)
ESCORES = {}   # (modelo, semente) -> dict com "validacao" e "teste"

acum_va = monta("validacao", bruto=True).sum(axis=1)
acum_te = monta("teste", bruto=True).sum(axis=1)
ESCORES[("nivel1_acumulado", -1)] = {"validacao": acum_va, "teste": acum_te}

# o pré-registro também define, para este nível, o percentil 99 por estação NO TREINO.
# Guardado à parte para o notebook 05 comparar com a regra comum (P99 na validação).
acum_tr = monta("treino", bruto=True).sum(axis=1)
i_est_tr = IDX["treino"][1]
P99_TREINO = (pd.DataFrame({"estacao": i_est_tr, "acum": acum_tr})
              .groupby("estacao")["acum"].quantile(0.99))
print(f"nível 1 pronto | acumulado mediano na validação: {np.median(acum_va):.1f} mm, "
      f"no teste: {np.median(acum_te):.1f} mm")
print(f"P99 por estação no treino: mediana {P99_TREINO.median():.1f} mm, "
      f"de {P99_TREINO.min():.1f} a {P99_TREINO.max():.1f} mm")
''')

code(r'''
# 8. Nível 2 — PCA com os componentes que explicam 90% da variância no treino
from sklearn.decomposition import PCA

pca = PCA(n_components=VAR_PCA, svd_solver="full", random_state=0).fit(X_tr)
print(f"componentes retidos: {pca.n_components_} de {JANELA} "
      f"| variância explicada: {pca.explained_variance_ratio_.sum() * 100:.1f}%")

def erro_pca(X):
    return ((X - pca.inverse_transform(pca.transform(X))) ** 2).mean(axis=1)

ESCORES[("nivel2_pca", -1)] = {"validacao": erro_pca(X_va), "teste": erro_pca(X_te)}
print(f"erro mediano de reconstrução | validação {np.median(ESCORES[('nivel2_pca', -1)]['validacao']):.4f} "
      f"| teste {np.median(ESCORES[('nivel2_pca', -1)]['teste']):.4f}")
''')

code(r'''
# 9. Nível 3 — autoencoder, com checkpoint a cada época e melhor modelo na validação
import torch
import torch.nn as nn

DISPOSITIVO = "cuda" if torch.cuda.is_available() else "cpu"
print("dispositivo:", DISPOSITIVO)

# O gargalo principal é o número de componentes que o PCA reteve pela regra pré-registrada.
# Assim a comparação entre os níveis 2 e 3 isola a não linearidade, em vez de medir capacidade.
AE_GARGALO_PRINCIPAL = int(pca.n_components_)
GARGALOS = [(AE_GARGALO_PRINCIPAL, "nivel3_autoencoder"),
            (AE_GARGALO_SENSIBILIDADE, f"nivel3_autoencoder_gargalo{AE_GARGALO_SENSIBILIDADE}")]
print(f"gargalo principal: {AE_GARGALO_PRINCIPAL} (igual ao PCA) | ablação: {AE_GARGALO_SENSIBILIDADE}")

def camadas_de(gargalo):
    meio = (JANELA + gargalo) // 2
    seq = [JANELA, meio, gargalo, meio, JANELA]
    return [c for i, c in enumerate(seq) if i in (0, 2, 4) or (c != gargalo and c != JANELA)]

def monta_ae(camadas):
    blocos, n = [], len(camadas)
    for i in range(n - 1):
        blocos.append(nn.Linear(camadas[i], camadas[i + 1]))
        if i < n - 2:
            blocos.append(nn.ReLU())
    return nn.Sequential(*blocos)

def erro_ae(modelo, X, lote=8192):
    modelo.eval()
    saida = np.empty(len(X), dtype="float32")
    with torch.no_grad():
        for i in range(0, len(X), lote):
            b = torch.from_numpy(X[i:i + lote]).to(DISPOSITIVO)
            saida[i:i + lote] = ((modelo(b) - b) ** 2).mean(dim=1).cpu().numpy()
    return saida

HIST_AE = []
t0 = time.time()
for gargalo, nome_modelo in GARGALOS:
    camadas = camadas_de(gargalo)
    print(f"\n--- {nome_modelo} | arquitetura {camadas} ---")
    for semente in SEMENTES:
        torch.manual_seed(semente)
        np.random.seed(semente)
        modelo = monta_ae(camadas).to(DISPOSITIVO)
        otim = torch.optim.Adam(modelo.parameters(), lr=AE_LR)
        perda_fn = nn.MSELoss()
        Xtr_t = torch.from_numpy(X_tr)
        melhor, melhor_epoca, sem_melhora = np.inf, -1, 0
        marca = f"g{gargalo}_semente{semente}"
        caminho_melhor = os.path.join(PASTA_MODELOS, f"ae_{marca}{SUFIXO}_melhor.pt")

        for epoca in range(1, AE_EPOCAS + 1):
            modelo.train()
            ordem = torch.randperm(len(Xtr_t))
            soma, n = 0.0, 0
            for i in range(0, len(ordem), AE_LOTE):
                b = Xtr_t[ordem[i:i + AE_LOTE]].to(DISPOSITIVO)
                otim.zero_grad()
                perda = perda_fn(modelo(b), b)
                perda.backward()
                otim.step()
                soma += float(perda.detach()) * len(b); n += len(b)
            perda_tr = soma / max(n, 1)
            perda_va = float(np.mean(erro_ae(modelo, X_va)))
            HIST_AE.append({"gargalo": gargalo, "semente": semente, "epoca": epoca,
                            "perda_treino": perda_tr, "perda_validacao": perda_va})
            # checkpoint a cada época, como o pré-registro exige
            torch.save({"epoca": epoca, "estado": modelo.state_dict(), "perda_validacao": perda_va},
                       os.path.join(PASTA_MODELOS, f"ae_{marca}{SUFIXO}_epoca{epoca:03d}.pt"))
            if perda_va < melhor - 1e-6:
                melhor, melhor_epoca, sem_melhora = perda_va, epoca, 0
                torch.save({"epoca": epoca, "estado": modelo.state_dict(), "perda_validacao": perda_va},
                           caminho_melhor)
            else:
                sem_melhora += 1
                if sem_melhora >= AE_PACIENCIA:
                    break

        modelo.load_state_dict(torch.load(caminho_melhor, map_location=DISPOSITIVO)["estado"])
        ESCORES[(nome_modelo, semente)] = {"validacao": erro_ae(modelo, X_va), "teste": erro_ae(modelo, X_te)}
        aviso = "  <-- ATENCAO: parou no teto de epocas, pode estar subtreinado" if melhor_epoca == AE_EPOCAS else ""
        print(f"  semente {semente}: melhor época {melhor_epoca} de {AE_EPOCAS}, "
              f"perda na validação {melhor:.5f}{aviso}")

HIST_AE = pd.DataFrame(HIST_AE)
print(f"\nautoencoder pronto em {time.time() - t0:.0f} s")
resumo = HIST_AE.loc[HIST_AE.groupby(["gargalo", "semente"])["perda_validacao"].idxmin(),
                     ["gargalo", "semente", "epoca", "perda_validacao"]]
print(resumo.to_string(index=False))
if (resumo["epoca"] == AE_EPOCAS).any():
    print("\nATENCAO: alguma semente teve a melhor epoca no teto. Aumente AE_EPOCAS e rode de novo.")
''')

code(r'''
# 10. Nível 4 — Isolation Forest
from sklearn.ensemble import IsolationForest

t0 = time.time()
for semente in SEMENTES:
    iso = IsolationForest(n_estimators=IF_ARVORES, max_samples=IF_AMOSTRA,
                          random_state=semente, n_jobs=-1).fit(X_tr)
    # score_samples é maior para o normal; invertido, fica maior para o anômalo
    ESCORES[("nivel4_isolation", semente)] = {"validacao": -iso.score_samples(X_va),
                                              "teste": -iso.score_samples(X_te)}
    print(f"semente {semente}: escore mediano na validação "
          f"{np.median(ESCORES[('nivel4_isolation', semente)]['validacao']):.4f}")
print(f"\nIsolation Forest pronto em {time.time() - t0:.0f} s")
''')

code(r'''
# 11. Consolidar e gravar os escores
partes = []
for (modelo, semente), d in ESCORES.items():
    for conjunto in ("validacao", "teste"):
        i_dia, i_est = IDX[conjunto]
        partes.append(pd.DataFrame({
            "modelo": modelo, "semente": np.int16(semente), "conjunto": conjunto,
            "gauge_code": estacoes[i_est],
            "dia": pd.to_datetime(dias_rotulo[i_dia]),
            "escore": d[conjunto].astype("float32"),
        }))
S = pd.concat(partes, ignore_index=True)
S["no_hidroweb"] = S["gauge_code"].isin(hidroweb)

arq = os.path.join(PASTA_ESCORES, f"escores_04{SUFIXO}.parquet")
S.to_parquet(arq, index=False)
HIST_AE.to_csv(os.path.join(PASTA_SAIDA, f"04_historico_autoencoder{SUFIXO}.csv"), index=False)
AUD_JAN.to_csv(os.path.join(PASTA_SAIDA, f"04_auditoria_janelas{SUFIXO}.csv"), index=False)
P99_TREINO.rename("p99_acumulado_treino").to_frame().assign(
    gauge_code=lambda t: estacoes[t.index.to_numpy()]).to_csv(
    os.path.join(PASTA_SAIDA, f"04_nivel1_p99_treino{SUFIXO}.csv"), index=False)

print(f"{len(S):,} linhas de escore gravadas em {arq}")
print(S.groupby(["modelo", "conjunto"])["escore"].agg(["size", "median"]).to_string())

log = {
    "notebook": "04_janelas_e_modelos", "versao_notebook": "3",
    "modo_demonstracao": MODO_DEMONSTRACAO,
    "data_execucao": pd.Timestamp.now().isoformat(),
    "decisoes_versao": DEC["versao"], "decisoes_sha256_16": HASH_DECISOES,
    "janela_dias": JANELA, "gap_entre_particoes_dias": int(GAP),
    "deslocamento_h": DESLOC_PRINCIPAL, "normalizacao": NORMALIZACAO,
    "janelas": {k: int(len(v[0])) for k, v in IDX.items()},
    "pca_componentes": int(pca.n_components_),
    "ae_gargalo_principal": int(AE_GARGALO_PRINCIPAL),
    "ae_gargalo_ablacao": int(AE_GARGALO_SENSIBILIDADE),
    "ae_melhor_epoca": resumo.to_dict("records"),
    "pca_variancia_explicada": float(pca.explained_variance_ratio_.sum()),
    "dispositivo": DISPOSITIVO, "torch": torch.__version__,
    "pandas": pd.__version__, "python": platform.python_version(),
    "parametros_nao_preregistrados": NAO_PREREGISTRADOS,
}
with open(os.path.join(PASTA_SAIDA, f"04_log_execucao{SUFIXO}.json"), "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2, default=str)

print("\nPARÂMETROS NÃO PRÉ-REGISTRADOS (Quadro de decisões do relatório):")
for k, v in NAO_PREREGISTRADOS.items():
    print(" -", k, "=", v)
if MODO_DEMONSTRACAO:
    print("\n" + "=" * 78)
    print("  ESTES NÚMEROS SÃO DE DEMONSTRAÇÃO E NÃO VÃO PARA O RELATÓRIO.")
    print("  Para a rodada definitiva: MODO_DEMONSTRACAO = False na célula 2.")
    print("=" * 78)
print("\nMANDE AO CLAUDE: as saídas das células 5, 6, 8, 9 e 11.")
''')

md("""
## O que o notebook 05 vai fazer

Com `escores_04.parquet` em mãos, sem retreinar nada:

1. Limiar por estação: percentil 99 do escore **na validação**, com sensibilidade em 95 e 99,5.
2. Alarme regional: dia em alarme quando a fração de estações ativas acima do limiar atinge **f**.
3. Calibração de **f** na validação, nos dois pontos de operação: 1% e 3% dos dias.
4. Detecção: evento detectado se houver ao menos um dia de alarme de 3 dias antes do início até o fim.
5. Métricas: recall por evento, alarmes falsos por ano, antecedência em dias, PR-AUC diária, com
   média e desvio padrão nas cinco sementes.
6. Replicação restrita ao Hidroweb diário — o quinto critério de refutação.
7. Confronto com os quatro critérios de refutação restantes.

**Nada disso toca no teste para decidir coisa alguma.** Os limiares e a calibração saem da validação;
o teste só é pontuado e medido.
""")


def nb():
    return {"cells": CELLS, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "colab": {"provenance": []}}, "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    import os
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "04_janelas_e_modelos.ipynb")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(nb(), f, ensure_ascii=False, indent=1)
    print("ok", len(CELLS), "celulas ->", destino)
