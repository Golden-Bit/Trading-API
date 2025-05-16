# routes/indicators.py
from fastapi import APIRouter, HTTPException
from typing import List
from bt_api.models import IndicatorScript
from datetime import datetime

router = APIRouter(prefix="/indicators", tags=["Indicators"])

# Archivio in memoria per gli script indicatori
INDICATORS_DB: List[IndicatorScript] = []
indicator_id_counter = 1

@router.get("/", response_model=List[IndicatorScript])
async def list_indicators():
    """Restituisce l'elenco degli script indicatori salvati."""
    return INDICATORS_DB

@router.post("/", response_model=IndicatorScript)
async def create_indicator(indicator: IndicatorScript):
    """Crea un nuovo indicatore personalizzato a partire dallo script Python integrale."""
    global indicator_id_counter
    indicator.id = indicator_id_counter
    indicator.created_at = datetime.utcnow()
    INDICATORS_DB.append(indicator)
    indicator_id_counter += 1
    return indicator

@router.get("/{indicator_id}", response_model=IndicatorScript)
async def get_indicator(indicator_id: int):
    """Recupera lo script e i dettagli di un indicatore specifico."""
    for ind in INDICATORS_DB:
        if ind.id == indicator_id:
            return ind
    raise HTTPException(status_code=404, detail="Indicatore non trovato")

@router.put("/{indicator_id}", response_model=IndicatorScript)
async def update_indicator(indicator_id: int, indicator_update: IndicatorScript):
    """Aggiorna lo script o i parametri di un indicatore personalizzato."""
    for i, ind in enumerate(INDICATORS_DB):
        if ind.id == indicator_id:
            updated = indicator_update.dict(exclude_unset=True)
            for key, value in updated.items():
                setattr(ind, key, value)
            INDICATORS_DB[i] = ind
            return ind
    raise HTTPException(status_code=404, detail="Indicatore non trovato")

@router.delete("/{indicator_id}")
async def delete_indicator(indicator_id: int):
    """Elimina uno script indicatore salvato."""
    global INDICATORS_DB
    INDICATORS_DB = [ind for ind in INDICATORS_DB if ind.id != indicator_id]
    return {"detail": "Indicatore eliminato"}
