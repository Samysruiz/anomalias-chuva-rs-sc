"""
Aplica a emenda proposta em 13/11/2026 ao pre-registro.

NAO rode isto sem a decisao do grupo. Leia primeiro
`pre-registro/emenda-proposta-2026-11-13-limiar.md`.

O que faz:
  1. confere que o arquivo esta na versao 1.2 e com o hash esperado;
  2. acrescenta a sensibilidade de periodo do limiar;
  3. acrescenta a emenda datada;
  4. passa a versao para 1.3;
  5. imprime o novo sha256 de 16 digitos, que precisa entrar em
     VERSOES_ACEITAS na celula 2 dos notebooks 03 e 04.

Nao sobrescreve nada sem confirmacao e nao mexe no decisoes_v1.0_original.json.
"""

import hashlib
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(AQUI, "decisoes.json")

VERSAO_ESPERADA = "1.2"
HASH_ESPERADO = "d4c58a627755c8f9"
VERSAO_NOVA = "1.3"

SENSIBILIDADE = (
    "P99 do escore calculado sobre o treino 1995-2019, alem do P99 na validacao"
)
MOTIVO = (
    "achado 5: a validacao 2020-2022 esta 20% abaixo da mediana do treino na chuva "
    "acumulada de 15 dias, com 2020 sendo o ano mais seco dos 31; calibrar a taxa de "
    "alarme nesse periodo e aplica-la ao teste produz taxa observada diferente da calibrada"
)
EMENDA = {
    "data": "2026-11-13",
    "item": "sensibilidade do periodo de calibracao do limiar",
    "detalhe": (
        "acrescentada analise de sensibilidade com o P99 calculado no treino, alem do "
        "P99 na validacao pre-registrado, que continua sendo o ponto principal. Motivo "
        "no achado 5. Emenda feita antes de qualquer calculo de recall ou de taxa de "
        "alarme; o notebook 05 nao existia nesta data."
    ),
}


def hash16(caminho):
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def principal():
    if not os.path.exists(ARQUIVO):
        sys.exit(f"nao encontrei {ARQUIVO}")

    atual = hash16(ARQUIVO)
    with open(ARQUIVO, "rb") as f:
        dec = json.loads(f.read())

    print(f"versao atual: {dec['versao']} | sha256_16: {atual}")

    if dec["versao"] != VERSAO_ESPERADA or atual != HASH_ESPERADO:
        sys.exit(
            "ABORTADO: o arquivo nao esta na versao 1.2 esperada.\n"
            f"  esperado: versao {VERSAO_ESPERADA}, hash {HASH_ESPERADO}\n"
            f"  achado  : versao {dec['versao']}, hash {atual}\n"
            "Alguem ja mexeu no pre-registro. Resolva isso antes de aplicar a emenda."
        )

    if "sensibilidade_periodo_do_limiar" in dec["pontuacao_e_alarme"]:
        sys.exit("ABORTADO: a emenda ja foi aplicada.")

    resposta = input("\nAplicar a emenda e passar para a versao 1.3? [digite SIM] ").strip()
    if resposta != "SIM":
        sys.exit("nada foi alterado.")

    dec["pontuacao_e_alarme"]["sensibilidade_periodo_do_limiar"] = SENSIBILIDADE
    dec["pontuacao_e_alarme"]["motivo_sensibilidade_periodo"] = MOTIVO
    dec["emendas"].append(EMENDA)
    dec["versao"] = VERSAO_NOVA

    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(dec, f, ensure_ascii=False, indent=1)
        f.write("\n")

    novo = hash16(ARQUIVO)
    print(f"\naplicada. versao {VERSAO_NOVA} | novo sha256_16: {novo}")
    print("\nACRESCENTE esta linha a VERSOES_ACEITAS na celula 2 dos notebooks 03 e 04:")
    print(f'    "{VERSAO_NOVA}": "{novo}",')
    print("\nSem isso, a guarda de hash vai avisar que o pre-registro mudou.")


if __name__ == "__main__":
    principal()
