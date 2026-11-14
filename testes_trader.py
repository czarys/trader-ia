"""Testa o trader.py real com precos artificiais, sem rede ou saldo real."""
import contextlib
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import trader


class TesteTrader(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory(prefix="teste_trader_")
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        for nome, valor in {
            "ARQUIVO_ESTADO": str(self.pasta / "saldo_teste.json"),
            "ARQUIVO_HISTORICO": str(self.pasta / "historico_teste.csv"),
        }.items():
            remendo = patch.object(trader, nome, valor)
            remendo.start()
            self.addCleanup(remendo.stop)
        # Uma chamada de rede acidental faz o teste falhar.
        rede = patch.object(trader.urllib.request, "urlopen", side_effect=AssertionError("Rede proibida no teste"))
        rede.start()
        self.addCleanup(rede.stop)

    def executar(self, preco, candle=1000, fechamentos=None):
        if fechamentos is None:
            fechamentos = [100.0] * 20 + [101.0]
        with patch.object(trader, "obter_preco", return_value=preco), patch.object(
            trader, "obter_candles", return_value=(fechamentos, candle)
        ), contextlib.redirect_stdout(io.StringIO()):
            trader.executar()
        return trader.carregar_estado()

    def historico(self):
        with open(trader.ARQUIVO_HISTORICO, encoding="utf-8", newline="") as arquivo:
            return list(csv.DictReader(arquivo))

    def test_01_compra_dos_dois_ativos(self):
        estado = self.executar(100.0)
        self.assertAlmostEqual(estado["saldo"], 0.0)
        self.assertEqual(set(estado["posicoes"]), set(trader.ATIVOS))
        for posicao in estado["posicoes"].values():
            self.assertAlmostEqual(posicao["quantidade"], 4.5)
            self.assertAlmostEqual(posicao["stop"], 99.6)
            self.assertAlmostEqual(posicao["alvo"], 100.8)
        self.assertEqual([r["acao"] for r in self.historico()], ["COMPRA", "COMPRA"])

    def test_02_saida_pelo_alvo(self):
        self.executar(100.0)
        estado = self.executar(100.8)  # mesmo candle: a saida deve ocorrer
        self.assertEqual(estado["posicoes"], {})
        self.assertAlmostEqual(estado["saldo"], 907.2)
        vendas = self.historico()[2:]
        self.assertEqual([r["motivo"] for r in vendas], ["TAKE PROFIT"] * 2)
        self.assertAlmostEqual(sum(float(r["resultado_usd"]) for r in vendas), 7.2)

    def test_03_saida_pelo_stop(self):
        self.executar(100.0)
        estado = self.executar(99.6)
        self.assertEqual(estado["posicoes"], {})
        self.assertAlmostEqual(estado["saldo"], 896.4)
        self.assertEqual([r["motivo"] for r in self.historico()[2:]], ["STOP LOSS"] * 2)

    def test_04_mesmo_candle_nao_duplica_compra(self):
        primeiro = self.executar(100.0)
        segundo = self.executar(100.0)
        self.assertEqual(primeiro, segundo)
        self.assertEqual(len(self.historico()), 2)

    def test_05_saida_por_cruzamento_de_baixa(self):
        self.executar(100.0)
        estado = self.executar(100.0, candle=1300, fechamentos=[100.0] * 20 + [99.0])
        self.assertEqual(estado["posicoes"], {})
        self.assertAlmostEqual(estado["saldo"], 900.0)
        self.assertEqual([r["motivo"] for r in self.historico()[2:]], ["CRUZAMENTO DE BAIXA"] * 2)

    def test_06_sem_sinal_preserva_capital(self):
        estado = self.executar(100.0, fechamentos=[100.0] * 21)
        self.assertAlmostEqual(estado["saldo"], 900.0)
        self.assertEqual(estado["posicoes"], {})
        self.assertFalse(Path(trader.ARQUIVO_HISTORICO).exists())
        self.assertEqual(estado["ultimo_candle"], {a: 1000 for a in trader.ATIVOS})


if __name__ == "__main__":
    unittest.main(verbosity=2)
