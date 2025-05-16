# test2_optimize_yahoo.py

import json
from API.sdk.sdk import BTClient

client = BTClient(base_url="http://localhost:8001")

strategy_code = """
import backtrader as bt

class Strategy(bt.Strategy):
    params = dict(fast=10, slow=30)

    def __init__(self):
        self.fast_ma = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.p.fast)
        self.slow_ma = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.p.slow)

    def next(self):
        if not self.position:
            if self.fast_ma[0] > self.slow_ma[0]:
                self.buy()
        elif self.fast_ma[0] < self.slow_ma[0]:
            self.close()
"""

data_feed_config = {
    "source": "yahoo",
    "symbol": "AAPL",
    "interval": "1d",
    "start": "2020-01-01",
    "end": "2020-12-31"
}

# strategy_parameters è un dizionario: chiave = nome param, valore = lista di possibili valori
# Il server eseguirà cerebro.optstrategy(StrategyClass, fast=[10,15], slow=[30,50])
optimization_config = {
    "strategy_script": strategy_code,
    "strategy_parameters": {
        "fast": [5, 10, 15, 20],
        "slow": [30, 40, 50, 60]
    },
    "data_feed": data_feed_config,
    "broker": {
        "initial_cash": 100000,
        "commission": 0.001
    },
    "analyzers": [
        {"name": "SharpeRatio"},
        {"name": "TradeAnalyzer"},
        {"name": "SQN"},
        {"name": "TimeReturn"}
    ],
    "runonce": True,
    "preload": True,
    "optdatas": True,
    "optreturn": False,
    "maxcpus": None
}

result = client.run_optimization(optimization_config)

with open("result_optimization_yahoo.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=4)

print("Ottimizzazione completata. Risultati salvati in result_optimization_yahoo.json")
