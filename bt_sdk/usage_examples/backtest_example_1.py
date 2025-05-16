# test1_backtest_yahoo.py

"""
Questo script esegue un backtest su dati scaricati da Yahoo Finance (ticker: AAPL)
per l'anno 2020 in timeframe giornaliero (1d). Si utilizza una semplice strategia
SMA Crossover definita come stringa Python, e si aggiungono observers e analyzers.

Per inviare la configurazione all'API, usiamo la classe BTClient dal modulo bt_sdk.
"""

import json
from API.sdk.sdk import BTClient

# 1. Inizializza il client per l'API Backtrader
client = BTClient(base_url="http://localhost:8001")  # Assicurati che l'API sia in ascolto su questa porta

# 2. Definisce la strategia SMA Crossover come codice Python da inviare all'API
strategy_code = """
import backtrader as bt

class Strategy(bt.Strategy):
    params = dict(fast=10, slow=30)  # parametri di default: media veloce=10 giorni, lenta=30 giorni

    def __init__(self):
        # Calcola le medie mobili semplici sui dati di chiusura con i periodi specificati
        self.fast_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.fast)
        self.slow_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.slow)

    def next(self):
        # Se non siamo già in posizione e la media veloce incrocia sopra la lenta, compra (ordine a mercato)
        if not self.position:
            if self.fast_ma[0] > self.slow_ma[0]:
                self.buy()
        # Se siamo in posizione long e la media veloce scende sotto la lenta, chiudi la posizione (vendi)
        elif self.fast_ma[0] < self.slow_ma[0]:
            self.close()
"""

# 3. Configura i dati storici da Yahoo Finance per AAPL (intervallo giornaliero 1d).
# Nel modello DataFeedConfig, quando source='yahoo', occorre usare 'symbol', 'interval', 'start', 'end'.
data_config = {
    "source": "yahoo",      # sorgente dati Yahoo Finance
    "symbol": "AAPL",       # simbolo/ticker
    "interval": "1d",       # intervallo delle candele (1 giorno)
    "start": "2020-01-01",  # data inizio storico (YYYY-MM-DD)
    "end": "2020-12-31"     # data fine storico (YYYY-MM-DD)
}

# 4. Creiamo la configurazione completa del backtest (BacktestConfig).
#    Attenzione: observers e analyzers devono essere array di oggetti, in linea con i modelli pydantic:
#    ObserverConfig e AnalyzerConfig hanno almeno la chiave "name" e opzionalmente "parameters".
backtest_config = {
    "strategy_script": strategy_code,    # il codice della strategia
    "data_feed": data_config,           # configurazione dei dati (Yahoo Finance AAPL)
    "broker": {
        "initial_cash": 100000,         # capitale iniziale
        "commission": 0.001            # commissione 0.1%
    },
    "observers": [
        {"name": "Broker"},     # observer per monitorare capitale, valore portafoglio, etc.
        {"name": "Trades"},     # observer per tracciare le operazioni
        {"name": "DrawDown"},   # observer per calcolare drawdown corrente
        {"name": "BuySell"}     # observer che segna punti di buy/sell sul grafico (interno a backtrader)
    ],
    "analyzers": [
        {"name": "SharpeRatio"},    # calcola rapporto di Sharpe
        {"name": "TradeAnalyzer"},  # statistiche su operazioni (profit/loss, numero di trade, etc.)
        {"name": "SQN"},           # System Quality Number
        {"name": "TimeReturn"}     # ritorni nel tempo
    ]
}

# 5. Esegue il backtest chiamando l'API tramite il client
result = client.run_backtest(backtest_config)

# 6. Salva il risultato JSON su file
with open("result_backtest_yahoo.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=4)

print("Risultati del backtest salvati in result_backtest_yahoo.json")

