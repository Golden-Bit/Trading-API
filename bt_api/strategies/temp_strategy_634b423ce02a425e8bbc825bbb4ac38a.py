
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
