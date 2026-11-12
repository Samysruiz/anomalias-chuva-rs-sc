"""
Controle de qualidade para o UNIPLU-BR.

Versao 2.1 (grade por pivot). Os limiares desta versao deixaram de ser palpites: foram
retirados de um processamento independente da base nacional completa,
publicado pelo AIR Centre (PINELO, 2026), em
https://github.com/AIRCentre/UNIPLU-BR

Por que este modulo existe: os autores do UNIPLU-BR declaram que o
tratamento aplicado limitou-se a padronizacao estrutural, sem avaliacao
qualitativa, verificacao de consistencia fisica nem filtragem de valores
extremos (LARHENA, 2026). Os valores sao os originais das agencias.

Principio operacional: nada e apagado aqui. Cada registro recebe
marcadores, separados em duas classes:

  FALHA    — defeito indiscutivel; nao deve entrar no treino.
  SUSPEITO — indicio de defeito; a decisao de usar ou nao e explicita.

Essa separacao preserva a rastreabilidade exigida em trabalho academico.

Ideia central para distinguir defeito de instrumento de chuva real:
a precipitacao e espacialmente coerente. Uma cheia encharca a bacia
inteira; um sensor com defeito grita sozinho. Os criterios espaciais
(qc_isolado_espacial e qc_seco_espacial) sao contribuicao deste
trabalho e nao constam do processamento citado, que trata o pico
isolado apenas no eixo temporal.

Projeto final — Aprendizado Nao Supervisionado
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────

# Limites fisicos absolutos de precipitacao (mm) por resolucao temporal
# (minutos). Fixados em aproximadamente o dobro do recorde mundial da
# Organizacao Meteorologica Mundial para cada duracao.
# Procedencia: PINELO (2026), src/qc.jl, ABSOLUTE_UPPER_BOUNDS.
# Acima disto nao e chuva improvavel: e impossivel.
LIMITES_FISICOS_MM = {
    10: 200.0,
    15: 400.0,
    30: 520.0,
    60: 800.0,
    360: 1680.0,
    1440: 3650.0,
}
# Para estacao de resolucao desconhecida, usa-se o teto diario,
# que e o criterio conservador adotado na mesma fonte.
LIMITE_PADRAO_MM = 3650.0

# Multiplicador da amplitude interquartil para o limiar estatistico por
# estacao, calculado sobre valores nao nulos (Q3 + k x AIQ).
# Procedencia: PINELO (2026), k = 3.0 em todas as redes.
K_IQR = 3.0

# Numero minimo de leituras consecutivas iguais para caracterizar
# sensor travado. Procedencia: PINELO (2026), min_run = 24.
MIN_REPETICOES = 24

# Proporcao de zeros a partir da qual a estacao e considerada plana
# (provavelmente fora de operacao). Procedencia: PINELO (2026),
# zero_fraction = 0.99.
FRACAO_ZEROS_PLANA = 0.99

COLUNAS_FALHA = [
    "qc_negativo",
    "qc_acima_limite_fisico",
    "qc_duplicata",
]

# Indicios de DEFEITO DE INSTRUMENTO. Excluem do treino.
COLUNAS_DEFEITO = [
    "qc_travado",
    "qc_oscilacao_rapida",
    "qc_estacao_plana",
    "qc_isolado_espacial",
    "qc_seco_espacial",
]

# Valor EXTREMO, que pode ser real. NAO exclui do treino.
#
# Razao, descoberta em teste: o criterio de valor atipico por amplitude
# interquartil marcou 89,58% dos registros do evento de chuva intensa
# simulado. Isso era esperado em retrospecto, porque chuva extrema e,
# por definicao, estatisticamente atipica. Usar esse criterio para
# excluir dados removeria justamente o fenomeno que se quer detectar.
#
# O criterio permanece como descritor, nunca como filtro. A distincao
# entre extremo real e defeito de instrumento cabe aos criterios
# espaciais, nao a um limiar estatistico sobre a serie isolada.
#
# O processamento independente adota a mesma postura: marca como
# suspeito e MANTEM o registro na base (PINELO, 2026).
COLUNAS_EXTREMO = [
    "qc_atipico_iqr",
]

COLUNAS_SUSPEITO = COLUNAS_DEFEITO + COLUNAS_EXTREMO

COLUNAS_SINAL = ["qc_ausente"] + COLUNAS_FALHA + COLUNAS_SUSPEITO

RAIO_TERRA_KM = 6371.0


# ─────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────

def passo_minutos(time_step):
    """Converte time_step para minutos, ou NaN se indeterminavel.

    Nos dados reais de RS e SC a coluna time_step e de tipo misto: traz
    inteiros (10, 15, 30, 60, 1440) e tambem a cadeia "Indefinido", em
    5 estacoes da rede ICEA. Converter com int() levanta excecao.

    O processamento independente excluiu 7 estacoes por esse motivo
    (PINELO, 2026). Aqui elas nao sao excluidas: recebem o teto
    conservador e ficam de fora da padronizacao de resolucao, o que e
    sinalizado em vez de silenciado.
    """
    try:
        if pd.isna(time_step):
            return float("nan")
    except (TypeError, ValueError):
        pass
    try:
        return float(int(time_step))
    except (TypeError, ValueError):
        return float("nan")


def _limite_fisico(time_step) -> float:
    """Teto fisico em mm para a resolucao temporal da estacao."""
    passo = passo_minutos(time_step)
    if pd.isna(passo):
        return LIMITE_PADRAO_MM
    return LIMITES_FISICOS_MM.get(int(passo), LIMITE_PADRAO_MM)


def _matriz_vizinhos(info: pd.DataFrame, raio_km: float):
    """Devolve (codigos, dicionario de vizinhos dentro do raio).

    Distancia de haversine entre todos os pares de estacoes.
    """
    coords = info.dropna(subset=["lat", "long"]).drop_duplicates("gauge_code")
    codigos = coords["gauge_code"].to_numpy()
    lat = np.radians(coords["lat"].to_numpy(dtype=float))
    lon = np.radians(coords["long"].to_numpy(dtype=float))

    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = (np.sin(dlat / 2) ** 2
         + np.cos(lat)[:, None] * np.cos(lat)[None, :] * np.sin(dlon / 2) ** 2)
    dist = RAIO_TERRA_KM * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    vizinhos = {
        codigos[i]: codigos[(dist[i] <= raio_km) & (dist[i] > 0)]
        for i in range(len(codigos))
    }
    return codigos, vizinhos


def _grade(df: pd.DataFrame) -> pd.DataFrame:
    """Matriz instante x estacao, para comparar o mesmo horario.

    v2.1: usa pivot (rapido, pouca memoria) quando nao ha pares
    (instante, estacao) repetidos, que e o caso depois da padronizacao
    diaria. Se houver repeticao, cai no pivot_table com maximo, que e o
    comportamento da v2.
    """
    try:
        return df.pivot(index="datetime", columns="gauge_code", values="rain_mm")
    except ValueError:
        return df.pivot_table(
            index="datetime", columns="gauge_code", values="rain_mm", aggfunc="max"
        )


def _marcar_por_pares(df: pd.DataFrame, pares: list, coluna: str) -> pd.DataFrame:
    """Aplica marcacao booleana a partir de uma lista de (codigo, instantes)."""
    df[coluna] = False
    if not pares:
        return df
    suspeitos = pd.concat(pares, ignore_index=True)
    suspeitos["_novo"] = True
    df = df.merge(suspeitos, on=["gauge_code", "datetime"], how="left")
    df[coluna] = df["_novo"].fillna(False).astype(bool)
    return df.drop(columns=["_novo"])


# ─────────────────────────────────────────────────────────────────────
# Classe FALHA — defeito indiscutivel
# ─────────────────────────────────────────────────────────────────────

def marcar_ausente(df: pd.DataFrame) -> pd.DataFrame:
    """Valor nulo. Nao e falha nem suspeita: e ausencia de informacao."""
    df = df.copy()
    df["qc_ausente"] = df["rain_mm"].isna()
    return df


def marcar_negativo(df: pd.DataFrame) -> pd.DataFrame:
    """Chuva negativa nao existe.

    Codigos como -9999 sao convencao de ausencia em varias redes e
    chegam como numero, nao como nulo. O processamento independente nao
    encontrou nenhum negativo na base nacional, o que sugere que a
    padronizacao dos autores ja resolveu isso. A verificacao custa pouco
    e permanece por seguranca.
    """
    df = df.copy()
    df["qc_negativo"] = (df["rain_mm"] < 0).fillna(False)
    return df


def marcar_acima_limite_fisico(df: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    """Acima do dobro do recorde mundial da OMM para a duracao."""
    df = df.copy()
    passos = info.drop_duplicates("gauge_code").set_index("gauge_code")["time_step"].to_dict()
    limites = df["gauge_code"].map(lambda c: _limite_fisico(passos.get(c, np.nan)))
    df["qc_acima_limite_fisico"] = (df["rain_mm"] > limites).fillna(False)
    return df


def marcar_duplicata(df: pd.DataFrame) -> pd.DataFrame:
    """Par (estacao, instante) repetido.

    O processamento independente removeu cerca de 511 mil registros por
    este motivo, concentrados em Telemetria e CEMADEN. Marca todas as
    ocorrencias exceto a primeira.
    """
    df = df.copy()
    df["qc_duplicata"] = df.duplicated(subset=["gauge_code", "datetime"], keep="first")
    return df


# ─────────────────────────────────────────────────────────────────────
# Classe SUSPEITO — indicio de defeito, no eixo temporal
# ─────────────────────────────────────────────────────────────────────

def marcar_travado(df: pd.DataFrame, min_repeticoes: int = MIN_REPETICOES) -> pd.DataFrame:
    """Mesmo valor nao nulo repetido por muitas leituras seguidas.

    Sequencias de zero nao contam: periodo seco e normal e tem
    tratamento proprio em marcar_estacao_plana e marcar_seco_espacial.
    """
    df = df.sort_values(["gauge_code", "datetime"]).reset_index(drop=True).copy()
    travado = np.zeros(len(df), dtype=bool)

    for _, idx in df.groupby("gauge_code", sort=False).indices.items():
        v = df["rain_mm"].to_numpy()[idx]
        muda = np.ones(len(v), dtype=bool)
        if len(v) > 1:
            iguais = (v[1:] == v[:-1]) & ~np.isnan(v[1:]) & ~np.isnan(v[:-1])
            muda[1:] = ~iguais
        bloco = np.cumsum(muda)
        contagem = pd.Series(bloco).map(pd.Series(bloco).value_counts()).to_numpy()
        travado[idx] = (contagem >= min_repeticoes) & (v > 0)

    df["qc_travado"] = travado
    return df


def marcar_oscilacao_rapida(df: pd.DataFrame, min_run: int = MIN_REPETICOES) -> pd.DataFrame:
    """Alternancia entre valor nao nulo e zero a cada intervalo.

    Sugere mal funcionamento intermitente do pluviometro. Procedencia:
    PINELO (2026), verificacao CE5, aplicada a rede CEMADEN.
    """
    df = df.sort_values(["gauge_code", "datetime"]).reset_index(drop=True).copy()
    oscila = np.zeros(len(df), dtype=bool)

    for _, idx in df.groupby("gauge_code", sort=False).indices.items():
        v = df["rain_mm"].to_numpy()[idx]
        if len(v) < min_run:
            continue
        nao_nulo = (v > 0) & ~np.isnan(v)
        zero = (v == 0)
        # alterna se cada posicao difere da seguinte em ser ou nao zero
        alterna = np.zeros(len(v), dtype=bool)
        alterna[:-1] = (nao_nulo[:-1] & zero[1:]) | (zero[:-1] & nao_nulo[1:])
        # sequencias de alternancia com comprimento minimo
        bloco = np.cumsum(~alterna)
        cont = pd.Series(bloco).map(pd.Series(bloco[alterna]).value_counts()).fillna(0).to_numpy()
        oscila[idx] = alterna & (cont >= min_run)

    df["qc_oscilacao_rapida"] = oscila
    return df


def marcar_atipico_iqr(df: pd.DataFrame, k: float = K_IQR) -> pd.DataFrame:
    """Valor acima de Q3 mais k vezes a amplitude interquartil.

    Calculado por estacao, sobre os valores nao nulos, na resolucao
    nativa. Este e o criterio do improvavel; o limite fisico trata do
    impossivel. Procedencia: PINELO (2026), k = 3.0.
    """
    df = df.copy()
    nao_nulos = df.loc[df["rain_mm"] > 0, ["gauge_code", "rain_mm"]]
    if nao_nulos.empty:
        df["qc_atipico_iqr"] = False
        return df

    q = nao_nulos.groupby("gauge_code")["rain_mm"].quantile([0.25, 0.75]).unstack()
    q.columns = ["q1", "q3"]
    q["limiar"] = q["q3"] + k * (q["q3"] - q["q1"])

    limiares = df["gauge_code"].map(q["limiar"])
    df["qc_atipico_iqr"] = (df["rain_mm"] > limiares).fillna(False)
    return df


def marcar_estacao_plana(df: pd.DataFrame,
                         fracao_zeros: float = FRACAO_ZEROS_PLANA) -> pd.DataFrame:
    """Estacao cuja serie e quase inteiramente zero.

    Indica pluviometro fora de operacao ou obstruido durante todo o
    periodo. Marca a serie inteira da estacao, nao registros isolados.
    Procedencia: PINELO (2026), zero_fraction = 0.99.
    """
    df = df.copy()
    validos = df.dropna(subset=["rain_mm"])
    if validos.empty:
        df["qc_estacao_plana"] = False
        return df
    proporcao = validos.assign(_z=validos["rain_mm"] == 0).groupby("gauge_code")["_z"].mean()
    planas = set(proporcao[proporcao >= fracao_zeros].index)
    df["qc_estacao_plana"] = df["gauge_code"].isin(planas)
    return df


# ─────────────────────────────────────────────────────────────────────
# Classe SUSPEITO — coerencia espacial (contribuicao deste trabalho)
# ─────────────────────────────────────────────────────────────────────

def marcar_isolado_espacial(df: pd.DataFrame, info: pd.DataFrame,
                            raio_km: float = 50.0, minimo_vizinhos: int = 2,
                            limiar_mm: float = 20.0,
                            razao_maxima: float = 0.10) -> pd.DataFrame:
    """Chuva intensa numa estacao enquanto a vizinhanca registra quase nada.

    Marca quando a estacao acusa valor acima de `limiar_mm` e a media das
    vizinhas dentro de `raio_km`, no mesmo instante, fica abaixo de
    `razao_maxima` desse valor.

    Estacoes com menos de `minimo_vizinhos` vizinhas nao sao avaliadas:
    sem vizinhanca nao ha como julgar, e marcar seria inventar.

    Diferenca em relacao ao criterio de pico isolado de PINELO (2026):
    aquele e temporal, observa zeros antes e depois na propria serie.
    Este e espacial, compara com outras estacoes no mesmo instante. Sao
    complementares.
    """
    df = df.copy()
    _, vizinhos = _matriz_vizinhos(info, raio_km)
    grade = _grade(df)

    pares = []
    for cod, viz in vizinhos.items():
        viz = [v for v in viz if v in grade.columns]
        if cod not in grade.columns or len(viz) < minimo_vizinhos:
            continue
        serie = grade[cod]
        media_viz = grade[viz].mean(axis=1)
        marca = ((serie > limiar_mm) & (media_viz < serie * razao_maxima)).fillna(False)
        if marca.any():
            pares.append(pd.DataFrame({"gauge_code": cod,
                                       "datetime": serie.index[marca]}))

    return _marcar_por_pares(df, pares, "qc_isolado_espacial")


def marcar_seco_espacial(df: pd.DataFrame, info: pd.DataFrame,
                         raio_km: float = 50.0, minimo_vizinhos: int = 2,
                         limiar_vizinhos_mm: float = 10.0) -> pd.DataFrame:
    """Zero numa estacao enquanto a vizinhanca registra chuva intensa.

    O inverso do criterio anterior, e o mais traicoeiro dos dois. Um
    pluviometro obstruido produz um zero que, isolado, e indistinguivel
    de dado legitimo. Para um modelo treinado a representar a
    normalidade, esse zero falso e mais nocivo que um pico evidente:
    e incorporado silenciosamente ao padrao aprendido.
    """
    df = df.copy()
    _, vizinhos = _matriz_vizinhos(info, raio_km)
    grade = _grade(df)

    pares = []
    for cod, viz in vizinhos.items():
        viz = [v for v in viz if v in grade.columns]
        if cod not in grade.columns or len(viz) < minimo_vizinhos:
            continue
        serie = grade[cod]
        media_viz = grade[viz].mean(axis=1)
        marca = ((serie == 0) & (media_viz > limiar_vizinhos_mm)).fillna(False)
        if marca.any():
            pares.append(pd.DataFrame({"gauge_code": cod,
                                       "datetime": serie.index[marca]}))

    return _marcar_por_pares(df, pares, "qc_seco_espacial")


# ─────────────────────────────────────────────────────────────────────
# Orquestracao
# ─────────────────────────────────────────────────────────────────────

def aplicar_qc(df: pd.DataFrame, info: pd.DataFrame, **kw) -> pd.DataFrame:
    """Roda todas as verificacoes e consolida.

    Acrescenta, alem das colunas de sinalizacao:
      qc_falha    — algum criterio da classe FALHA
      qc_suspeito — algum criterio da classe SUSPEITO
      qc_limpo    — nenhuma falha, nenhuma suspeita, valor presente

    Parametros opcionais repassados: raio_km, minimo_vizinhos,
    limiar_mm, razao_maxima, limiar_vizinhos_mm, min_repeticoes, k.
    """
    df = marcar_ausente(df)
    df = marcar_negativo(df)
    df = marcar_acima_limite_fisico(df, info)
    df = marcar_duplicata(df)

    df = marcar_travado(df, min_repeticoes=kw.get("min_repeticoes", MIN_REPETICOES))
    df = marcar_oscilacao_rapida(df, min_run=kw.get("min_repeticoes", MIN_REPETICOES))
    df = marcar_atipico_iqr(df, k=kw.get("k", K_IQR))
    df = marcar_estacao_plana(df)

    espaciais = {chave: kw[chave] for chave in
                 ("raio_km", "minimo_vizinhos", "limiar_mm", "razao_maxima")
                 if chave in kw}
    df = marcar_isolado_espacial(df, info, **espaciais)

    secos = {chave: kw[chave] for chave in
             ("raio_km", "minimo_vizinhos", "limiar_vizinhos_mm") if chave in kw}
    df = marcar_seco_espacial(df, info, **secos)

    df["qc_falha"] = df[COLUNAS_FALHA].any(axis=1)
    df["qc_defeito"] = df[COLUNAS_DEFEITO].any(axis=1)
    df["qc_extremo"] = df[COLUNAS_EXTREMO].any(axis=1)
    df["qc_suspeito"] = df["qc_defeito"] | df["qc_extremo"]

    # qc_limpo NAO considera qc_extremo: chuva extrema e o objeto de
    # estudo, nao ruido. Excluir extremos aqui esvaziaria o problema.
    df["qc_limpo"] = ~(df["qc_falha"] | df["qc_defeito"] | df["qc_ausente"])
    return df


def relatorio_qc(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela de quantos registros cada criterio pegou.

    Esta tabela vai para o artigo: e a auditoria de consistencia.
    """
    total = len(df)
    classe = {c: "FALHA" for c in COLUNAS_FALHA}
    classe.update({c: "DEFEITO" for c in COLUNAS_DEFEITO})
    classe.update({c: "EXTREMO" for c in COLUNAS_EXTREMO})
    classe["qc_ausente"] = "AUSENTE"

    linhas = []
    for col in COLUNAS_SINAL + ["qc_falha", "qc_defeito", "qc_extremo",
                                "qc_suspeito", "qc_limpo"]:
        if col not in df.columns:
            continue
        n = int(df[col].sum())
        linhas.append({
            "criterio": col,
            "classe": classe.get(col, "RESUMO"),
            "registros": n,
            "percentual": round(100 * n / total, 4) if total else 0.0,
        })
    return pd.DataFrame(linhas)


def padronizar_resolucao(df: pd.DataFrame, info: pd.DataFrame,
                         passo: str = "1D", usar_apenas_limpo: bool = True,
                         cobertura_minima: float = 0.9) -> pd.DataFrame:
    """Coloca todas as estacoes na mesma resolucao temporal.

    O UNIPLU-BR mistura 10 minutos, 1 hora e 1 dia na mesma base. Somar
    series de resolucoes diferentes sem padronizar produz conjunto de
    treino heterogeneo, e o modelo aprende a diferenca entre redes em vez
    da diferenca entre chuva habitual e extrema.

    `cobertura_minima` descarta o periodo agregado quando falta dado
    demais dentro dele: um dia com 3 das 24 horas presentes nao e um
    total diario, e somar daria valor baixo com aparencia de normalidade.
    """
    base = df[df["qc_limpo"]] if usar_apenas_limpo else df
    base = base.dropna(subset=["rain_mm"])

    unicas = info.drop_duplicates("gauge_code").set_index("gauge_code")
    esperado = (unicas["time_step"].map(passo_minutos)
                .reindex(base["gauge_code"].unique()))

    agregado = (base.set_index("datetime")
                .groupby("gauge_code")["rain_mm"]
                .resample(passo)
                .agg(["sum", "count"])
                .reset_index()
                .rename(columns={"sum": "rain_mm", "count": "n_leituras"}))

    minutos_passo = pd.Timedelta(passo).total_seconds() / 60
    agregado["n_esperado"] = (minutos_passo
                              / agregado["gauge_code"].map(esperado)).round()
    agregado["cobertura"] = (agregado["n_leituras"]
                             / agregado["n_esperado"].clip(lower=1))
    agregado["cobertura_ok"] = agregado["cobertura"] >= cobertura_minima
    return agregado


if __name__ == "__main__":
    print(__doc__)
