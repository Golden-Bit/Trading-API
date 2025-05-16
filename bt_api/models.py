from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# -------------------------
# MODELLI DI CONFIGURAZIONE
# -------------------------

class DataFeedConfig(BaseModel):
    """
    Configurazione per il data feed. Permette diverse modalità:
    - 'csv': usare un file CSV locale (dataname = percorso).
    - 'yahoo': scaricare dati tramite yfinance.
    - 'inline': fornire dati direttamente (tramite 'data_csv' o 'data_dict').
    """
    source: str = Field(
        ...,
        description="Fonte del data feed ('csv' per file locale, 'yahoo' per download da Yahoo Finance, 'inline' per dati diretti)."
    )
    # Se source='csv', si usa dataname come percorso del file CSV
    dataname: Optional[str] = Field(
        None,
        description="Percorso del file CSV (es. 'datas/yhoo-1996-2015.txt')"
    )
    # Se si vogliono scaricare dati da Yahoo Finance (source='yahoo'):
    symbol: Optional[str] = Field(None, description="Ticker/Simbolo per i dati da Yahoo Finance (es. 'AAPL')")
    interval: Optional[str] = Field(
        None,
        description="Intervallo/cadenza, es. '1m','15m','1h','1d','1wk','1mo' ecc. (supportato da Yahoo Finance)."
    )
    start: Optional[datetime] = Field(None, description="Data di inizio download (se non si usa period).")
    end: Optional[datetime] = Field(None, description="Data di fine download (se non si usa period).")
    period: Optional[str] = Field(
        None,
        description="Periodo di dati (es. '1y', '5d', 'max') da Yahoo Finance. Alternativa a start/end."
    )
    # Dati inline (se source='inline'):
    data_csv: Optional[str] = Field(
        None,
        description="Dati storici in formato CSV come stringa (colonne tipiche: Date, Open, High, Low, Close, Volume)."
    )
    data_dict: Optional[Dict[str, List[Any]]] = Field(
        None,
        description="Dati storici come dizionario di liste, ad es. {'Date': [...], 'Open': [...], 'Close': [...], ...}."
    )

    # Parametri comuni a Backtrader (se serve definire timeframe e compressione manualmente)
    timeframe: Optional[str] = Field(
        None,
        description="Timeframe da utilizzare in Backtrader (es. 'Days', 'Minutes', 'Weeks', ...)."
    )
    compression: Optional[int] = Field(
        None,
        description="Fattore di compressione dei dati (es. 1 per daily, 60 per orario, ...)."
    )

    # Opzioni di lettura CSV (se si usa file locale)
    reverse: bool = Field(
        default=False,
        description="Se i dati CSV devono essere letti in ordine inverso (parametro reverse)."
    )
    fromdate: Optional[datetime] = Field(
        None,
        description="Data di inizio (YYYY-MM-DD) per il feed CSV (backtrader)."
    )
    todate: Optional[datetime] = Field(
        None,
        description="Data di fine (YYYY-MM-DD) per il feed CSV (backtrader)."
    )

class BrokerConfig(BaseModel):
    initial_cash: float = Field(..., description="Capitale iniziale per il broker.")
    commission: Optional[float] = Field(
        default=0.0,
        description="Commissione (percentuale o cost) da applicare per trade."
    )

class ObserverConfig(BaseModel):
    name: str = Field(..., description="Nome dell’observer (es. 'Broker', 'DrawDown', 'Trades').")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Parametri opzionali per l’observer."
    )

class AnalyzerConfig(BaseModel):
    name: str = Field(..., description="Nome dell’analyzer (es. 'SharpeRatio', 'TimeReturn', ecc.).")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Parametri opzionali per l’analyzer."
    )

# Modello per il backtest (esecuzione singola)
class BacktestConfig(BaseModel):
    strategy_script: str = Field(
        ...,
        description="Script completo della strategia (deve definire la classe 'Strategy' derivata da bt.Strategy')."
    )
    strategy_parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Parametri della strategia."
    )
    data_feed: DataFeedConfig = Field(
        ...,
        description="Configurazione del data feed (può essere CSV, Yahoo o inline)."
    )
    broker: BrokerConfig = Field(
        ...,
        description="Configurazione del broker (capitale iniziale, commissioni, ecc.)."
    )
    observers: Optional[List[ObserverConfig]] = Field(
        default_factory=list,
        description="Lista di observers da aggiungere a Cerebro."
    )
    analyzers: Optional[List[AnalyzerConfig]] = Field(
        default_factory=list,
        description="Lista di analyzers da aggiungere a Cerebro."
    )
    runonce: bool = Field(
        default=False,
        description="Se utilizzare la modalità runonce di Backtrader."
    )
    preload: bool = Field(
        default=True,
        description="Se pre-caricare i dati in memoria (preload)."
    )

# Modello per l'ottimizzazione (i parametri sono liste di possibili valori)
class OptimizationConfig(BaseModel):
    strategy_script: str = Field(
        ...,
        description="Script completo della strategia (deve definire la classe 'Strategy')."
    )
    strategy_parameters: Dict[str, List[Any]] = Field(
        ...,
        description="Dizionario dei parametri da ottimizzare, es. {'period': [10,20,30]}."
    )
    data_feed: DataFeedConfig = Field(
        ...,
        description="Configurazione del data feed (può essere CSV, Yahoo o inline)."
    )
    broker: BrokerConfig = Field(
        ...,
        description="Configurazione del broker (capitale iniziale, commissioni, ecc.)."
    )
    observers: Optional[List[ObserverConfig]] = Field(
        default_factory=list,
        description="Lista di observers da aggiungere a Cerebro."
    )
    analyzers: Optional[List[AnalyzerConfig]] = Field(
        default_factory=list,
        description="Lista di analyzers da aggiungere a Cerebro."
    )
    runonce: bool = Field(
        default=True,
        description="Se utilizzare la modalità runonce di Backtrader."
    )
    preload: bool = Field(
        default=True,
        description="Se pre-caricare i dati in memoria (preload)."
    )
    optdatas: bool = Field(
        default=True,
        description="Se ottimizzare i data feeds (optdatas)."
    )
    optreturn: bool = Field(
        default=True,
        description="Se ottimizzare il ritorno (optreturn)."
    )
    maxcpus: Optional[int] = Field(
        default=None,
        description="Numero massimo di CPU da utilizzare per l'ottimizzazione."
    )
    top_n: int = Field(
        default=-1,
        description="Quanti run (complessivi) restituire dopo averli ordinati per best_value decrescente. -1 = tutti."
    )
    top_m: int = Field(
        default=-1,
        description="Quante strategie per ogni run restituire, ordinate per final_value decrescente. -1 = tutte."
    )
