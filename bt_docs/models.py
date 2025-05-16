# models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class IndicatorScript(BaseModel):
    id: Optional[int] = Field(None, description="ID univoco dell'indicatore")
    name: str = Field(..., description="Nome (alias) dell'indicatore")
    code: str = Field(..., description="Script Python completo (inclusa la definizione della classe, es. 'class Indicator(bt.Indicator): ...')")
    description: Optional[str] = Field(None, description="Descrizione tecnica dell'indicatore")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parametri (es. period, movav, ecc.)")
    plot_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Opzioni di plotting")
    created_at: Optional[datetime] = None

class StrategyScript(BaseModel):
    id: Optional[int] = Field(None, description="ID univoco della strategia")
    name: str = Field(..., description="Nome della strategia")
    code: str = Field(..., description="Script Python completo della strategia (inclusa la definizione della classe 'Strategy' derivata da bt.Strategy)")
    description: Optional[str] = Field(None, description="Descrizione della logica di trading")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parametri della strategia")
    created_at: Optional[datetime] = None

class RunStrategyRequest(BaseModel):
    datafeed_id: Optional[int] = Field(None, description="ID del datafeed da utilizzare (se non fornito, viene usato un CSV di default)")
    runonce: bool = Field(default=False, description="Se utilizzare la modalità runonce")
    preload: bool = Field(default=True, description="Se pre-caricare i dati")
