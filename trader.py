        mm20 = sum(fechamentos[-20:]) / 20 
        mm50 = sum(fechamentos[-50:]) / 50
        indicador = rsi(fechamentos)
        pos = estado['posicoes'].get(moeda)
        if pos:
            saida = None
            motivo = None
            # Se ambos forem tocados na mesma vela, assumir o pior caso.
            if v['l'] <= pos['stop']:
                saida, motivo = min(v['o'], pos['stop']), 'STOP'
            elif v['h'] >= pos['alvo']:
                saida, motivo = pos['alvo'], 'ALVO'
            elif mm20 < mm50:
                saida, motivo = v['c'], 'SAIDA_TENDENCIA'
            if saida is not None:
                recebido = pos['quantidade'] * saida * (1 - TAXA)
                pnl = recebido - pos['custo_total']
                estado['caixa'] += recebido
                del estado['posicoes'][moeda]
                registrar(estado, v['t'], moeda, motivo, saida, pnl)
        elif mm20 > mm50 and 50 <= indicador <= 70:
            # Sem alavancagem; taxa de entrada e saida incluidas no limite de risco estimado.
            patrimonio = estado['caixa'] + sum(
                p['quantidade'] * p['entrada'] for p in estado['posicoes'].values())
            limite_risco = patrimonio * RISCO / (STOP + 2 * TAXA)
            valor = min(estado['caixa'] * 0.45, limite_risco)
            if valor >= 10:
                quantidade = (valor / (1 + TAXA)) / v['c']
                estado['caixa'] -= valor
                estado['posicoes'][moeda] = {
                    'quantidade': quantidade, 'entrada': v['c'], 'custo_total': valor,
                    'stop': v['c'] * (1 - STOP), 'alvo': v['c'] * (1 + ALVO)}
                registrar(estado, v['t'], moeda, 'COMPRA_FICTICIA', v['c'])
        estado['ultima_vela'][moeda] = v['t']
    print(f'{moeda}: ultima vela analisada: {estado["ultima_vela"].get(moeda)}')


def main():
    estado = carregar()
    # Primeiro buscar tudo: se a API falhar, nao alterar o estado.
    mercado = {moeda: buscar_velas(par) for moeda, par in PARES.items()}
    for moeda, velas in mercado.items():
        if len(velas) < 51:
            raise RuntimeError(f'Historico insuficiente para {moeda}')
        simular(estado, moeda, velas)
    ultimo_preco = {m: vs[-1]['c'] for m, vs in mercado.items()}
    patrimonio = estado['caixa'] + sum(
        p['quantidade'] * ultimo_preco[m] for m, p in estado['posicoes'].items())
    print(f"Caixa: US$ {estado['caixa']:.2f} | Patrimonio estimado: US$ {patrimonio:.2f}")
    print('Posicoes ficticias abertas:', ', '.join(estado['posicoes']) or 'nenhuma')
    with open(ARQUIVO, 'w', encoding='utf-8') as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
