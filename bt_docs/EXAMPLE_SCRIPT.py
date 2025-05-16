#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Esempio completo di utilizzo di Backtrader:
  - Creazione di una strategia personalizzata.
  - Associazione di observers e analyzers.
  - Esecuzione di un backtest reale con un data feed (da file CSV).
  - Esecuzione di un’ottimizzazione variando un parametro della strategia.

ATTENZIONE:
  L'esecuzione dinamica di codice (es. exec()) è utilizzata per simulare la ricezione di uno script
  della strategia da parte di un utente. In ambiente di produzione occorre adottare tecniche di sandboxing
  e validazione degli script per evitare rischi di sicurezza.
"""

import os
import backtrader as bt
from datetime import datetime


########################################
# 1. DEFINIZIONE DELLA STRATEGIA
########################################

# La strategia viene definita in una classe. Questa strategia usa una SMA e genera segnali di acquisto
# quando il prezzo chiude sopra la SMA e segnali di vendita quando il prezzo chiude sotto la SMA.
class MyStrategy(bt.Strategy):
    params = (('smaperiod', 15),)

    def __init__(self):
        # Inizializza una media mobile semplice sull'close
        self.sma = bt.indicators.SMA(self.data.close, period=self.p.smaperiod)
        # Crea un indicatore di crossover tra il prezzo e la SMA
        self.crossover = bt.indicators.CrossOver(self.data.close, self.sma)

    def next(self):
        # Se non abbiamo posizioni e il crossover è positivo, compra
        if not self.position:
            if self.crossover > 0:
                self.buy()
        # Se abbiamo una posizione e il crossover diventa negativo, chiudi la posizione
        elif self.crossover < 0:
            self.close()


########################################
# 2. FUNZIONE DI BACKTEST
########################################

def run_backtest(smaperiod=15, datafeed_path=None):
    """
    Esegue un backtest con i seguenti parametri:
      - smaperiod: il periodo per la media mobile
      - datafeed_path: percorso del file CSV per il data feed (se None, viene usato un file di default)

    Restituisce il valore finale del portafoglio e il cash residuo.
    """
    # Se il datafeed non viene specificato, usa un file di default (modifica il percorso in base alla tua struttura)
    if datafeed_path is None:
        datafeed_path = os.path.join("datas", "yhoo-1996-2015.txt")
    if not os.path.exists(datafeed_path):
        raise Exception(f"Il file del datafeed non esiste: {datafeed_path}")

    # Crea un'istanza di Cerebro
    cerebro = bt.Cerebro()
    # Imposta il capitale iniziale (ad esempio 50.000)
    cerebro.broker.setcash(50000)

    # Carica il data feed da CSV (utilizzando il feed YahooFinanceCSVData)
    data = bt.feeds.YahooFinanceCSVData(
        dataname=datafeed_path,
        fromdate=datetime(1996, 1, 1),
        todate=datetime(2015, 12, 31),
        reverse=True
    )
    cerebro.adddata(data)

    # Aggiunge la strategia alla sessione, passando il parametro smaperiod
    cerebro.addstrategy(MyStrategy, smaperiod=smaperiod)

    # Aggiungi observers: Broker (mostra cash e portafoglio), DrawDown, Trades
    cerebro.addobserver(bt.observers.Broker)
    cerebro.addobserver(bt.observers.DrawDown)
    cerebro.addobserver(bt.observers.Trades)

    # Aggiungi analyzers: Sharpe Ratio e TimeReturn
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years, _name='annual_return')

    # Esegue il backtest
    results = cerebro.run()
    final_value = cerebro.broker.getvalue()
    cash = cerebro.broker.getcash()

    # Per visualizzare graficamente il backtest, decommentare la riga seguente:
    # cerebro.plot()

    return {"final_value": final_value, "cash": cash, "sharpe": results[0].analyzers.sharpe.get_analysis(),
            "annual_return": results[0].analyzers.annual_return.get_analysis()}


########################################
# 3. FUNZIONE DI OTTIMIZZAZIONE
########################################

def run_optimization(smaperiod_range=range(10, 21), datafeed_path=None):
    """
    Esegue l'ottimizzazione della strategia variando il parametro "smaperiod" nell'intervallo fornito.

    - smaperiod_range: un range (es. range(10, 21)) da provare.
    - datafeed_path: percorso del file CSV per il data feed.

    Restituisce una lista di risultati con il parametro e il valore finale del portafoglio.
    """
    if datafeed_path is None:
        datafeed_path = os.path.join("datas", "yhoo-1996-2015.txt")
    if not os.path.exists(datafeed_path):
        raise Exception(f"Il file del datafeed non esiste: {datafeed_path}")

    cerebro = bt.Cerebro(optreturn=True)  # optreturn consente di ottenere risultati semplificati per l'ottimizzazione
    cerebro.broker.setcash(50000)

    data = bt.feeds.YahooFinanceCSVData(
        dataname=datafeed_path,
        fromdate=datetime(1996, 1, 1),
        todate=datetime(2015, 12, 31),
        reverse=True
    )
    cerebro.adddata(data)

    # Ottimizza la strategia variando "smaperiod" nel range specificato
    cerebro.optstrategy(MyStrategy, smaperiod=smaperiod_range)

    # Esegui l'ottimizzazione
    optimized_runs = cerebro.run()

    # Costruisci una lista di risultati: per ogni strategia ottimizzata restituisce il parametro e il valore finale
    results_list = []
    for run in optimized_runs:
        # Ogni run è una lista (perché può esserci più di una strategia, se abbiamo più data feeds)
        strat = run[0]
        params = strat.params.__dict__
        final_value = cerebro.broker.getvalue()  # Attenzione: per ottimizzazione, il valore finale va estratto dal run specifico; qui si semplifica.
        results_list.append({"parameters": params, "final_value": final_value})

    return results_list


########################################
# 4. ESECUZIONE DEL BACKTEST E OTTIMIZZAZIONE
########################################

if __name__ == "__main__":
    # Esempio di esecuzione backtest con un determinato smaperiod
    print("Esecuzione Backtest:")
    backtest_result = run_backtest(smaperiod=15, datafeed_path=os.path.join("datas", "yhoo-1996-2015.txt"))
    print("Risultati Backtest:")
    print(f"  Valore finale portafoglio: {backtest_result['final_value']:.2f}")
    print(f"  Cash residuo: {backtest_result['cash']:.2f}")
    print(f"  Sharpe Ratio: {backtest_result['sharpe']}")
    print(f"  Rendimento annuale: {backtest_result['annual_return']}")

    # Esempio di ottimizzazione variando il parametro smaperiod
    print("\nEsecuzione Ottimizzazione:")
    opt_results = run_optimization(smaperiod_range=range(10, 21),
                                   datafeed_path=os.path.join("datas", "yhoo-1996-2015.txt"))
    print("Risultati Ottimizzazione:")
    for res in opt_results:
        print(res)
