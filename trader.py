
import json
import os
import urllib.request
from datetime import datetime, timezone

# ====================================
# CONFIGURACOES DO TRADER IA
# ====================================

CAPITAL_INICIAL = 900.0
RISCO = 0.005
STOP_LOSS = 0.004
TAKE_PROFIT = 0.008

ATIVOS = ["BTCUSDT", "ETHUSDT"]
INTERVALO = "1h"

ARQUIVO_ESTADO = "estado_trader.json"


def carregar_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        with open(ARQUIVO_ESTADO, "r") as arquivo:
            return json.load(arquivo)

    return {
        "saldo": CAPITAL_INICIAL,
        "posicoes": {},
        "historico": [],
        "ultimo_candle": {}
    }


def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w") as arquivo:
        json.dump(estado, arquivo, indent=4)


def obter_candles(ativo):
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={ativo}&interval={INTERVALO}&limit=50"
    )

    requisicao = urllib.request.Request(
        url,
        headers={"User-Agent": "TraderIASimulacao/1.0"}
    )

    with urllib.request.urlopen(
        requisicao, timeout=15
    ) as resposta:
        dados = json.load(resposta)

    # Descarta o candle ainda em formacao.
    candles = dados[:-1]

    fechamentos = [
        float(candle[4]) for candle in candles
    ]

    return fechamentos, candles[-1][0]


def media_movel(valores, periodo):
    return sum(valores[-periodo:]) / periodo


def registrar(estado, ativo, tipo, preco, quantidade, resultado=0):
    operacao = {
        "data": datetime.now(
            timezone.utc
        ).isoformat(),
        "ativo": ativo,
        "tipo": tipo,
        "preco": round(preco, 8),
        "quantidade": round(quantidade, 10),
        "resultado": round(resultado, 2),
        "saldo": round(estado["saldo"], 2)
    }

    estado["historico"].append(operacao)
    print(operacao)


def executar():
    estado = carregar_estado()

    print("================================")
    print("TRADER IA - PAPER TRADING")
    print("Capital inicial: US$ 900")
    print("BTC e ETH - SIMULACAO")
    print("================================")

    for ativo in ATIVOS:
        try:
            fechamentos, candle_id = obter_candles(ativo)
            preco = fechamentos[-1]

            mm9 = media_movel(fechamentos, 9)
            mm20 = media_movel(fechamentos, 20)

            mm9_anterior = media_movel(
                fechamentos[:-1], 9
            )
            mm20_anterior = media_movel(
                fechamentos[:-1], 20
            )

            print(f"\nAtivo: {ativo}")
            print(f"Preco: US$ {preco:.2f}")
            print(f"MM9: {mm9:.2f}")
            print(f"MM20: {mm20:.2f}")

            posicao = estado["posicoes"].get(ativo)

            # Verifica uma posicao existente.
            if posicao:
                entrada = posicao["entrada"]
                quantidade = posicao["quantidade"]

                stop = entrada * (1 - STOP_LOSS)
                alvo = entrada * (1 + TAKE_PROFIT)

                motivo = None

                if preco <= stop:
                    motivo = "STOP LOSS"
                elif preco >= alvo:
                    motivo = "TAKE PROFIT"

                if motivo:
                    valor_venda = quantidade * preco
                    resultado = (
                        preco - entrada
                    ) * quantidade

                    estado["saldo"] += valor_venda
                    del estado["posicoes"][ativo]

                    registrar(
                        estado,
                        ativo,
                        motivo,
                        preco,
                        quantidade,
                        resultado
                    )

                    salvar_estado(estado)
                else:
                    print("Posicao aberta mantida.")

                continue

            # Evita repetir sinal do mesmo candle.
            if estado["ultimo_candle"].get(ativo) == candle_id:
                print("Candle ja analisado.")
                continue

            estado["ultimo_candle"][ativo] = candle_id

            cruzamento_compra = (
                mm9_anterior <= mm20_anterior
                and mm9 > mm20
            )

            if not cruzamento_compra:
                print("Sem sinal de compra.")
                salvar_estado(estado)
                continue

            # Dimensionamento da posicao.
            saldo = estado["saldo"]
            risco_em_dolar = saldo * RISCO

            valor_por_risco = (
                risco_em_dolar / STOP_LOSS
            )

            valor_compra = min(
                saldo,
                valor_por_risco
            )

            if valor_compra <= 0:
                print("Saldo insuficiente.")
                continue

            quantidade = valor_compra / preco

            estado["saldo"] -= valor_compra

            estado["posicoes"][ativo] = {
                "entrada": preco,
                "quantidade": quantidade
            }

            registrar(
                estado,
                ativo,
                "COMPRA SIMULADA",
                preco,
                quantidade
            )

            salvar_estado(estado)

        except Exception as erro:
            print(f"Erro em {ativo}: {erro}")
            raise

    print("\n================================")
    print(f"Saldo livre: US$ {estado['saldo']:.2f}")

    patrimonio = estado["saldo"]

    for ativo, posicao in estado["posicoes"].items():
        patrimonio += (
            posicao["quantidade"]
            * posicao["entrada"]
        )

    print(
        f"Patrimonio pelo custo: "
        f"US$ {patrimonio:.2f}"
    )

    print(
        f"Operacoes registradas: "
        f"{len(estado['historico'])}"
    )

    salvar_estado(estado)


if __name__ == "__main__":
    executar()
