# routes/optimization.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import backtrader as bt
from datetime import datetime

router = APIRouter(prefix="/optimization", tags=["Optimization"])


class OptimizationRequest(BaseModel):
    strategy: str = Field(..., description="Nome della strategia (es. 'ExampleStrategy')")
    parameters: Dict[str, List[Any]] = Field(..., description="Dizionario dei parametri da ottimizzare")
    preload: bool = True
    runonce: bool = True
    optdatas: bool = True
    optreturn: bool = True
    maxcpus: Optional[int] = None


@router.post("/", response_model=Dict[str, Any])
async def run_optimization(opt_req: OptimizationRequest):
    cerebro = bt.Cerebro(runonce=opt_req.runonce)
    cerebro.broker.setcash(50000)
    data = bt.feeds.YahooFinanceCSVData(
        dataname="datas/yhoo-1996-2015.txt",
        fromdate=datetime(1996, 1, 1),
        todate=datetime(2015, 12, 31),
        reverse=True
    )
    cerebro.adddata(data)

    # Strategia di esempio che utilizza i parametri passati
    class ExampleStrategy(bt.Strategy):
        params = opt_req.parameters

        def __init__(self):
            period = self.p.get("smaperiod", [20])[0]
            self.sma = bt.indicators.SMA(self.data.close, period=period)

        def next(self):
            if self.data.close[0] > self.sma[0]:
                self.buy()
            elif self.data.close[0] < self.sma[0]:
                self.sell()

    cerebro.optstrategy(ExampleStrategy, **opt_req.parameters)
    try:
        cerebro.run(preload=opt_req.preload, optdatas=opt_req.optdatas, optreturn=opt_req.optreturn)
        final_value = cerebro.broker.getvalue()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'ottimizzazione: {str(e)}")

    return {
        "optimization_id": "opt_1",
        "results": [{"parameters": opt_req.parameters, "final_value": final_value}],
        "message": "Ottimizzazione completata."
    }


@router.get("/{optimization_id}", response_model=Dict[str, Any])
async def get_optimization_result(optimization_id: str):
    if optimization_id == "opt_1":
        return {"optimization_id": "opt_1", "results": [{"smaperiod": 20, "final_value": 55000}]}
    raise HTTPException(status_code=404, detail="Sessione di ottimizzazione non trovata")
