"""
Demonstracao didatica do autoencoder do projeto.

NAO usa dados reais. Gera chuva sintetica com estatistica parecida com a do
UNIPLU-BR em RS/SC e treina o autoencoder com a arquitetura EXATA do notebook
04 (15-14-13-14-15, ReLU, Adam, MSE, melhor epoca na validacao). Serve so para
produzir as figuras que explicam o que o modelo faz. Nenhum numero daqui vai
para o relatorio como resultado.

Projeto final - Aprendizado Nao Supervisionado
"""

import json

import numpy as np
import torch
import torch.nn as nn
from numpy.lib.stride_tricks import sliding_window_view
from sklearn.decomposition import PCA

SEMENTE = 0
JANELA = 15
N_ESTACOES = 60
N_DIAS = 4000          # ~11 anos
FRACAO_SECA = 0.62     # proporcao de dias sem chuva
GAMMA_FORMA = 0.62
GAMMA_ESCALA = 12.0

rng = np.random.default_rng(SEMENTE)
torch.manual_seed(SEMENTE)


# ─────────────────────────────────────────────────────────────────────
# 1. Chuva sintetica
# ─────────────────────────────────────────────────────────────────────
def gerar_chuva():
    """Chuva diaria por estacao: dias secos + gama nos dias chuvosos.

    Cada estacao tem um fator climatologico proprio, como no dado real,
    onde o litoral chove mais que a campanha.
    """
    fator = rng.uniform(0.7, 1.4, size=N_ESTACOES)
    molhado = rng.random((N_DIAS, N_ESTACOES)) > FRACAO_SECA
    valores = rng.gamma(GAMMA_FORMA, GAMMA_ESCALA, size=(N_DIAS, N_ESTACOES))
    # persistencia: chuva de hoje puxa a de amanha, como sistema frontal
    A = np.where(molhado, valores, 0.0) * fator
    for _ in range(2):
        A[1:] += 0.25 * A[:-1]
    return A.astype("float32")


def plantar_evento(A, dia, estacoes, dias=5, pico=130.0):
    """Planta uma cheia: varios dias seguidos de chuva muito forte."""
    A = A.copy()
    perfil = np.array([0.35, 0.75, 1.0, 0.8, 0.4])[:dias]
    for k, p in enumerate(perfil):
        A[dia + k, estacoes] += pico * p
    return A


# ─────────────────────────────────────────────────────────────────────
# 2. Mesmo pre-processamento do notebook 04
# ─────────────────────────────────────────────────────────────────────
def preparar(A, corte_treino, corte_valid):
    media = np.nanmean(A[:corte_treino], axis=0)
    desvio = np.nanstd(A[:corte_treino], axis=0)
    desvio = np.where(desvio < 1e-6, 1.0, desvio)
    Z = ((A - media) / desvio).astype("float32")

    W = sliding_window_view(Z, JANELA, axis=0)
    W_mm = sliding_window_view(A, JANELA, axis=0)
    dia_rotulo = np.arange(JANELA - 1, len(A))

    def fatiar(ini, fim):
        dentro = (dia_rotulo - (JANELA - 1) >= ini) & (dia_rotulo <= fim)
        i_dia, i_est = np.where(np.ones_like(W[:, :, 0], dtype=bool) & dentro[:, None])
        return i_dia, i_est

    GAP = JANELA
    fat = {
        "treino": fatiar(0, corte_treino - GAP),
        "validacao": fatiar(corte_treino, corte_valid - GAP),
        "teste": fatiar(corte_valid, len(A) - 1),
    }
    return W, W_mm, media, desvio, fat


def monta(W, fat, nome):
    i_dia, i_est = fat[nome]
    return W[i_dia, i_est, :].astype("float32"), i_dia, i_est


# ─────────────────────────────────────────────────────────────────────
# 3. Autoencoder, igual ao do notebook 04
# ─────────────────────────────────────────────────────────────────────
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
            b = torch.from_numpy(X[i:i + lote])
            saida[i:i + lote] = ((modelo(b) - b) ** 2).mean(dim=1).numpy()
    return saida


def reconstruir(modelo, X):
    modelo.eval()
    with torch.no_grad():
        return modelo(torch.from_numpy(X)).numpy()


def treinar(X_tr, X_va, gargalo, epocas=150, lote=1024, lr=1e-3, paciencia=15):
    camadas = camadas_de(gargalo)
    modelo = monta_ae(camadas)
    otim = torch.optim.Adam(modelo.parameters(), lr=lr)
    perda_fn = nn.MSELoss()
    Xtr_t = torch.from_numpy(X_tr)
    melhor, melhor_epoca, sem_melhora = np.inf, -1, 0
    melhor_estado = None
    for epoca in range(1, epocas + 1):
        modelo.train()
        ordem = torch.randperm(len(Xtr_t))
        for i in range(0, len(ordem), lote):
            b = Xtr_t[ordem[i:i + lote]]
            otim.zero_grad()
            perda = perda_fn(modelo(b), b)
            perda.backward()
            otim.step()
        perda_va = float(np.mean(erro_ae(modelo, X_va)))
        if perda_va < melhor - 1e-6:
            melhor, melhor_epoca, sem_melhora = perda_va, epoca, 0
            melhor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}
        else:
            sem_melhora += 1
            if sem_melhora >= paciencia:
                break
    modelo.load_state_dict(melhor_estado)
    return modelo, camadas, melhor_epoca, melhor


# ─────────────────────────────────────────────────────────────────────
# 4. Execucao
# ─────────────────────────────────────────────────────────────────────
def principal():
    A = gerar_chuva()
    corte_treino, corte_valid = 2600, 3300

    # uma cheia plantada no teste, atingindo 40 das 60 estacoes
    dia_evento = 3600
    est_evento = np.arange(40)
    A = plantar_evento(A, dia_evento, est_evento)

    W, W_mm, media, desvio, fat = preparar(A, corte_treino, corte_valid)
    X_tr, _, _ = monta(W, fat, "treino")
    X_va, _, _ = monta(W, fat, "validacao")
    X_te, i_dia_te, i_est_te = monta(W, fat, "teste")

    print(f"janelas: treino {len(X_tr):,} | validacao {len(X_va):,} | teste {len(X_te):,}")
    print(f"mediana do acumulado de 15 dias no treino: "
          f"{np.median(W_mm[fat['treino'][0], fat['treino'][1], :].sum(axis=1)):.1f} mm")

    pca = PCA(n_components=0.90, svd_solver="full", random_state=0).fit(X_tr)
    gargalo = int(pca.n_components_)
    print(f"PCA: {gargalo} de {JANELA} componentes, "
          f"{pca.explained_variance_ratio_.sum() * 100:.1f}% da variancia")

    modelo, camadas, melhor_epoca, melhor = treinar(X_tr, X_va, gargalo)
    print(f"arquitetura {camadas} | melhor epoca {melhor_epoca} | perda {melhor:.5f}")

    err_va = erro_ae(modelo, X_va)
    err_te = erro_ae(modelo, X_te)
    p99 = float(np.percentile(err_va, 99))
    print(f"erro mediano validacao {np.median(err_va):.4f} | P99 {p99:.4f}")
    print(f"janelas de teste acima do P99: {100 * (err_te > p99).mean():.1f}%")

    # janela normal: erro proximo da mediana. janela extrema: a do evento plantado.
    # qualquer janela que contenha o pico do evento, na estacao mais atingida
    rotulo_te = i_dia_te + JANELA - 1
    alvo = ((rotulo_te >= dia_evento + 2) & (rotulo_te <= dia_evento + JANELA - 1)
            & np.isin(i_est_te, est_evento))
    i_extrema = int(np.where(alvo)[0][np.argmax(err_te[alvo])])
    pct_extrema = float((err_va < err_te[i_extrema]).mean() * 100)
    print(f"erro da janela extrema: {err_te[i_extrema]:.4f} "
          f"(acima de {pct_extrema:.2f}% das janelas de validacao)")
    i_normal = int(np.argsort(np.abs(err_te - np.median(err_va)))[0])

    rec = reconstruir(modelo, X_te[[i_normal, i_extrema]])
    saida = {"arquitetura": camadas, "gargalo": gargalo,
             "variancia_pca": round(float(pca.explained_variance_ratio_.sum()) * 100, 1),
             "melhor_epoca": melhor_epoca,
             "p99_validacao": round(p99, 4),
             "erro_mediano_validacao": round(float(np.median(err_va)), 4),
             "pct_teste_acima_p99": round(float(100 * (err_te > p99).mean()), 1),
             "casos": [], "hist": {}}

    for nome, i, r in (("normal", i_normal, rec[0]), ("extrema", i_extrema, rec[1])):
        est = int(i_est_te[i])
        obs_mm = W_mm[i_dia_te[i], est, :]
        rec_mm = r * desvio[est] + media[est]
        saida["casos"].append({
            "caso": nome,
            "erro": round(float(erro_ae(modelo, X_te[[i]])[0]), 4),
            "acumulado_mm": round(float(obs_mm.sum()), 1),
            "observado_mm": [round(float(v), 1) for v in obs_mm],
            "reconstruido_mm": [round(float(v), 1) for v in rec_mm],
        })

    # histograma do erro na validacao, em escala log
    borda = np.logspace(np.log10(max(err_va.min(), 1e-4)), np.log10(err_va.max()), 31)
    cont, _ = np.histogram(err_va, bins=borda)
    saida["hist"] = {"bordas": [round(float(b), 5) for b in borda],
                     "contagem": [int(c) for c in cont],
                     "erro_extrema": saida["casos"][1]["erro"]}

    with open("/home/claude/demo_ae_saida.json", "w") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print("\n--- casos ---")
    for c in saida["casos"]:
        print(f"{c['caso']:8s} erro {c['erro']:.4f} | acumulado {c['acumulado_mm']:.1f} mm")
    print(f"razao extrema/normal: {saida['casos'][1]['erro'] / saida['casos'][0]['erro']:.1f}x")


if __name__ == "__main__":
    principal()
