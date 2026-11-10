
import random
from datetime import datetime

# CONFIGURACAO DO TRADER IA
capital = 900.00
risco = 0.005
stop_loss = 0.004
take_profit = 0.008

operacoes = 20

print("TRADER IA - SIMULACAO")
print("Capital inicial: US$ 900")
print("Modo: DINHEIRO FICTICIO")
print("-" * 40)

for numero in range(1, operacoes + 1):
    risco_dolar = capital * risco
    posicao = risco_dolar / stop_loss

    # Resultado aleatorio apenas para teste
    ganhou = random.choice([True, False])

    if ganhou:
        resultado = posicao * take_profit
        status = "LUCRO"
    else:
        resultado = -risco_dolar
        status = "PREJUIZO"

    capital += resultado

    print(
        f"Operacao {numero}: {status} "
        f"US$ {resultado:.2f}"
    )
    print(f"Saldo: US$ {capital:.2f}")
    print("-" * 40)

print("SIMULACAO FINALIZADA")
print(f"Saldo final: US$ {capital:.2f}")
print(f"Data: {datetime.now()}")
