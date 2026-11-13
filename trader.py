"""Trader IA: simulacao de BTC e ETH com dados publicos da Coinbase.
Nao envia ordens reais e nao utiliza credenciais de corretora.
"""

import csv
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

CAPITAL_INICIAL = 900.00
RISCO_POR_OPERACAO = 0.005  # 0,5% do patrimonio estimado
STOP_LOSS = 0.004          # 0,4%
TAKE_PROFIT = 0.008        # 0,8%
ALOCACAO_MAXIMA = 0.50     # no maximo 50% do patrimonio por ativo
ATIVOS = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum"}
PERIODO_CURTO = 9
PERIODO_LONGO = 20
SEGUNDOS_CANDLE = 3600
ARQUIVO_ESTADO = "saldo.json"
ARQUIVO_HISTORICO = "historico.csv"
URL_BASE = "https://api.exchange.coinbase.com"


def requisitar_json(caminho):
    req = urllib.request.Request(
        URL_BASE + caminho,
        headers={
            "User-Agent": "TraderIASimulacao/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resposta:
            return json.load(resposta)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Coinbase respondeu HTTP {exc.code} em {caminho}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha de rede ao consultar Coinbase: {exc.reason}") from exc


def obter_candles(ativo):
    dados = requisitar_json(
        f"/products/{ativo}/candles?granularity={SEGUNDOS_CANDLE}"
    )
    if not isinstance(dados, list):
        raise ValueError(f"Resposta inesperada de candles para {ativo}: {dados}")

    agora = time.time()
    # Coinbase: [timestamp, minimo, maximo, abertura, fechamento, volume].
    # A API retorna os candles em ordem inversa: ordenamos cronologicamente.
    candles = sorted(
        (
            item for item in dados
            if isinstance(item, list)
            and len(item) >= 5
            and float(item[0]) + SEGUNDOS_CANDLE <= agora
        ),
        key=lambda item: int(item[0]),
    )
    if len(candles) < PERIODO_LONGO + 1:
        raise ValueError(f"Dados insuficientes para medias moveis de {ativo}")
    fechamentos = [float(item[4]) for item in candles]
    return fechamentos, int(candles[-1][0])


def obter_preco(ativo):
    dados = requisitar_json(f"/products/{ativo}/ticker")
    preco = float(dados["price"])
    if preco <= 0:
        raise ValueError(f"Preco invalido para {ativo}")
    return preco


def carregar_estado():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {"saldo": CAPITAL_INICIAL, "posicoes": {}, "ultimo_candle": {}}

    with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as arquivo:
        estado = json.load(arquivo)
    campos = ("saldo", "posicoes", "ultimo_candle")
    if not isinstance(estado, dict) or any(campo not in estado for campo in campos):
        raise ValueError(
            "saldo.json possui estrutura incompatÃ­vel. "
            "Guarde uma copia e confira antes de modificar."
        )
    return estado


def salvar_estado(estado):
    temporario = ARQUIVO_ESTADO + ".tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(estado, arquivo, indent=2, ensure_ascii=False)
    os.replace(temporario, ARQUIVO_ESTADO)


def registrar(ativo, acao, preco, quantidade, resultado, saldo, motivo):
    cabecalho = [
        "data_utc", "ativo", "acao", "preco_usd", "quantidade",
        "resultado_usd", "saldo_livre_usd", "motivo",
    ]
    arquivo_novo = (
        not os.path.exists(ARQUIVO_HISTORICO)
        or os.path.getsize(ARQUIVO_HISTORICO) == 0
    )
    with open(ARQUIVO_HISTORICO, "a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        if arquivo_novo:
            escritor.writerow(cabecalho)
        escritor.writerow([
            datetime.now(timezone.utc).isoformat(), ativo, acao,
            round(preco, 4), round(quantidade, 10), round(resultado, 4),
            round(saldo, 4), motivo,
        ])


def media(valores, periodo):
    return sum(valores[-periodo:]) / periodo


def sinal_cruzamento(fechamentos):
    curta_anterior = media(fechamentos[:-1], PERIODO_CURTO)
    longa_anterior = media(fechamentos[:-1], PERIODO_LONGO)
    curta_atual = media(fechamentos, PERIODO_CURTO)
    longa_atual = media(fechamentos, PERIODO_LONGO)

    if curta_anterior <= longa_anterior and curta_atual > longa_atual:
        return "COMPRA", curta_atual, longa_atual
    if curta_anterior >= longa_anterior and curta_atual < longa_atual:
        return "VENDA", curta_atual, longa_atual
    return "AGUARDAR", curta_atual, longa_atual


def vender(estado, ativo, preco, motivo):
    posicao = estado["posicoes"][ativo]
    quantidade = float(posicao["quantidade"])
    entrada = float(posicao["entrada"])
    receita = quantidade * preco
    resultado = (preco - entrada) * quantidade
    estado["saldo"] = float(estado["saldo"]) + receita
    del estado["posicoes"][ativo]
    salvar_estado(estado)
    registrar(ativo, "VENDA", preco, quantidade, resultado, estado["saldo"], motivo)
    print(f"VENDA FICTICIA {ativo}: resultado US$ {resultado:.2f} ({motivo})")


def comprar(estado, ativo, preco, patrimonio_estimado):
    saldo_livre = float(estado["saldo"])
    risco_em_usd = patrimonio_estimado * RISCO_POR_OPERACAO
    valor_pelo_risco = risco_em_usd / STOP_LOSS
    valor_pela_alocacao = patrimonio_estimado * ALOCACAO_MAXIMA
    valor = min(saldo_livre, valor_pelo_risco, valor_pela_alocacao)
    if valor < 1.00:
        print(f"{ativo}: saldo livre insuficiente para uma compra.")
        return

    quantidade = valor / preco
    estado["saldo"] = saldo_livre - valor
    estado["posicoes"][ativo] = {
        "entrada": preco,
        "quantidade": quantidade,
        "stop": preco * (1 - STOP_LOSS),
        "alvo": preco * (1 + TAKE_PROFIT),
    }
    salvar_estado(estado)
    registrar(ativo, "COMPRA", preco, quantidade, 0.0, estado["saldo"], "MM9 cruzou MM20 para cima")
    print(f"COMPRA FICTICIA {ativo}: US$ {valor:.2f} a US$ {preco:.2f}")


def patrimonio_aproximado(estado, precos):
    total = float(estado["saldo"])
    for ativo, posicao in estado["posicoes"].items():
        # Usa cotacao atual se estiver disponivel; senao custo de entrada.
        preco = precos.get(ativo, float(posicao["entrada"]))
        total += float(posicao["quantidade"]) * preco
    return total


def executar():
    print("TRADER IA - SOMENTE SIMULACAO / SEM DINHEIRO REAL")
    print("Capital inicial: US$ 900 | risco-alvo: 0,5% | stop: 0,4% | alvo: 0,8%")
    estado = carregar_estado()
    precos = {}
    erros = []

    for ativo, nome in ATIVOS.items():
        print(f"\nAnalisando {nome} ({ativo})")
        try:
            preco = obter_preco(ativo)
            precos[ativo] = preco
            print(f"Preco de mercado: US$ {preco:.2f}")

            # Verifica saidas em TODA execucao, inclusive no mesmo candle.
            if ativo in estado["posicoes"]:
                posicao = estado["posicoes"][ativo]
                if preco <= float(posicao["stop"]):
                    vender(estado, ativo, preco, "STOP LOSS")
                    continue
                if preco >= float(posicao["alvo"]):
                    vender(estado, ativo, preco, "TAKE PROFIT")
                    continue

            fechamentos, candle_id = obter_candles(ativo)
            if estado["ultimo_candle"].get(ativo) == candle_id:
                print("Candle fechado ja analisado; sem nova entrada.")
                continue

            sinal, mm9, mm20 = sinal_cruzamento(fechamentos)
            print(f"MM9: {mm9:.2f} | MM20: {mm20:.2f} | Sinal: {sinal}")

            if ativo in estado["posicoes"]:
                if sinal == "VENDA":
                    vender(estado, ativo, preco, "CRUZAMENTO DE BAIXA")
                else:
                    print("Posicao ficticia mantida.")
            elif sinal == "COMPRA":
                patrimonio = patrimonio_aproximado(estado, precos)
                comprar(estado, ativo, preco, patrimonio)
            else:
                print("Sem operacao neste candle.")

            estado["ultimo_candle"][ativo] = candle_id
            salvar_estado(estado)
        except Exception as exc:
            erros.append(ativo)
            print(f"ERRO ao analisar {ativo}: {exc}")

    print("\n--- RESUMO ---")
    print(f"Saldo livre: US$ {float(estado['saldo']):.2f}")
    print(f"Posicoes abertas: {len(estado['posicoes'])}")
    print(f"Patrimonio estimado: US$ {patrimonio_aproximado(estado, precos):.2f}")
    print(f"Historico: {ARQUIVO_HISTORICO}")
    salvar_estado(estado)

    if erros:
        raise RuntimeError("Falha ao consultar: " + ", ".join(erros))
    print("SIMULACAO EXECUTADA COM SUCESSO")


if __name__ == "__main__":
    executar()
