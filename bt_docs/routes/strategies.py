# routes/strategies.py
import backtrader as bt
from fastapi import APIRouter, HTTPException
from typing import List
from bt_api.models import StrategyScript, RunStrategyRequest
from datetime import datetime
import os
from bt_api.routes.datafeeds import DATAFEEDS_DB  # Per recuperare il datafeed se specificato

router = APIRouter(prefix="/strategies", tags=["Strategies"])

STRATEGIES_DB: List[StrategyScript] = []
strategy_id_counter = 1


@router.get("/", response_model=List[StrategyScript])
async def list_strategies():
    """Restituisce l'elenco delle strategie salvate."""
    return STRATEGIES_DB


@router.post("/", response_model=StrategyScript)
async def create_strategy(strategy: StrategyScript):
    """Crea e salva una nuova strategia (script Python completo)."""
    global strategy_id_counter
    strategy.id = strategy_id_counter
    strategy.created_at = datetime.utcnow()
    STRATEGIES_DB.append(strategy)
    strategy_id_counter += 1
    return strategy


@router.get("/{strategy_id}", response_model=StrategyScript)
async def get_strategy(strategy_id: int):
    """Recupera i dettagli di una strategia specifica."""
    for strat in STRATEGIES_DB:
        if strat.id == strategy_id:
            return strat
    raise HTTPException(status_code=404, detail="Strategia non trovata")


@router.put("/{strategy_id}", response_model=StrategyScript)
async def update_strategy(strategy_id: int, strat_update: StrategyScript):
    """Aggiorna lo script o i parametri di una strategia esistente."""
    for i, strat in enumerate(STRATEGIES_DB):
        if strat.id == strategy_id:
            updated = strat_update.dict(exclude_unset=True)
            for key, value in updated.items():
                setattr(strat, key, value)
            STRATEGIES_DB[i] = strat
            return strat
    raise HTTPException(status_code=404, detail="Strategia non trovata")


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: int):
    """Elimina una strategia salvata."""
    global STRATEGIES_DB
    STRATEGIES_DB = [s for s in STRATEGIES_DB if s.id != strategy_id]
    return {"detail": "Strategia eliminata"}


@router.post("/run/{strategy_id}")
async def run_strategy(strategy_id: int, run_req: RunStrategyRequest):
    """
    Esegue il backtest della strategia specificata.

    - Se `datafeed_id` è fornito, si cerca il datafeed registrato; altrimenti si usa un CSV di default.
    - Il codice della strategia viene eseguito dinamicamente per ottenere la classe "Strategy".
    - Viene creata una sessione di backtest con Backtrader (Cerebro), il datafeed viene aggiunto e la strategia viene eseguita.
    - Vengono restituiti il valore finale del portafoglio e altre statistiche.
    """
    strat = next((s for s in STRATEGIES_DB if s.id == strategy_id), None)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategia non trovata")

    datafeed_path = "datas/yhoo-1996-2015.txt"
    if run_req.datafeed_id:
        for df in DATAFEEDS_DB:
            if df.id == run_req.datafeed_id:
                datafeed_path = df.dataname
                break

    if not os.path.exists(datafeed_path):
        raise HTTPException(status_code=500, detail="Datafeed di default non trovato.")

    try:
        data = bt.feeds.YahooFinanceCSVData(
            dataname=datafeed_path,
            fromdate=datetime(1996, 1, 1),
            todate=datetime(2015, 12, 31),
            reverse=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento del datafeed: {str(e)}")

    cerebro = bt.Cerebro(runonce=run_req.runonce)
    cerebro.broker.setcash(50000)
    cerebro.adddata(data)

    local_context = {}
    try:
        exec(strat.code, {}, local_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'esecuzione dello script: {str(e)}")

    StrategyClass = local_context.get("Strategy")
    if not StrategyClass:
        raise HTTPException(status_code=400, detail="Lo script non definisce una classe 'Strategy'")

    cerebro.addstrategy(StrategyClass, **(strat.parameters or {}))

    try:
        cerebro.run(preload=run_req.preload)
        final_value = cerebro.broker.getvalue()
        cash = cerebro.broker.getcash()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante il backtest: {str(e)}")

    return {
        "detail": f"Strategia {strat.name} eseguita con successo.",
        "final_value": final_value,
        "cash": cash
    }
