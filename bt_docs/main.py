# ga_optimizer.py
from fastapi import FastAPI
from routes import indicators, strategies, available, datafeeds, optimization, memory, live, docs

app = FastAPI(
    title="Backtrader API",
    description="API per gestire Backtrader tramite FastAPI, con gestione di indicatori, strategie, data feeds, observers, ottimizzazione, memoria e live trading.",
    version="1.0.0"
)

app.include_router(indicators.router)
app.include_router(strategies.router)
app.include_router(available.router)   # Qui sono inclusi gli endpoint per available_indicators, observers e analyzers
app.include_router(datafeeds.router)
app.include_router(optimization.router)
app.include_router(memory.router)
app.include_router(live.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
