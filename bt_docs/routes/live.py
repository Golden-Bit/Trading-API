# routes/live.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import backtrader as bt

router = APIRouter(prefix="/live", tags=["Live Trading"])

class BrokerConfig(BaseModel):
    broker: str = Field(..., description="Nome del broker (es. 'InteractiveBrokers', 'Oanda')")
    config: Dict[str, Any] = Field(..., description="Configurazione del broker (host, port, clientId, ecc.)")

class OrderRequest(BaseModel):
    action: str = Field(..., description="Azione: 'buy' o 'sell'")
    symbol: str = Field(..., description="Simbolo dell'asset")
    size: int = Field(..., description="Dimensione dell'ordine")
    order_type: str = Field(..., description="Tipo di ordine, ad es. 'limit' o 'market'")
    price: Optional[float] = Field(None, description="Prezzo per l'ordine limit (se applicabile)")
    valid_until: Optional[str] = Field(None, description="Data di scadenza in formato ISO8601")

@router.get("/status")
async def live_status():
    status = {
        "cash": 50000,
        "positions": [],
        "P&L": 0.0,
        "live_data": {"symbol": "AAPL", "price": 150.0}
    }
    return status

@router.post("/start")
async def start_live(broker_config: BrokerConfig):
    try:
        # Esempio: istanza di uno store live (ad es. IBStore) per il broker reale.
        # Qui va implementata la logica reale di connessione live.
        return {"detail": f"Live trading avviato con broker {broker_config.broker}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'avvio del live trading: {str(e)}")

@router.post("/stop")
async def stop_live():
    return {"detail": "Live trading interrotto"}

@router.post("/order")
async def send_live_order(order: OrderRequest):
    try:
        return {"detail": f"Ordine {order.action} per {order.symbol} inviato", "order": order.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'invio dell'ordine: {str(e)}")

@router.get("/orders")
async def list_live_orders():
    orders = [
        {"order_id": 1, "symbol": "AAPL", "action": "buy", "status": "submitted"},
        {"order_id": 2, "symbol": "AAPL", "action": "sell", "status": "filled"}
    ]
    return orders
