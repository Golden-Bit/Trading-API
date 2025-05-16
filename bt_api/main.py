import io
import glob
from datetime import datetime
import backtrader as bt
import uvicorn
import yfinance as yf
import pandas as pd
import os, sys, uuid, importlib.util
from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any

from bt_api.models import (
    DataFeedConfig, ObserverConfig, AnalyzerConfig,
    BacktestConfig, OptimizationConfig
)

# -------------------------
# COSTANTI E CONFIGURAZIONE
# -------------------------

STRATEGIES_DIR = "strategies"
CACHE_DIR = "cache"
CACHE_LIMIT_BYTES = 5 * 1024**3  # 5 GB

os.makedirs(CACHE_DIR, exist_ok=True)  # Assicura l'esistenza della cartella cache
os.makedirs(STRATEGIES_DIR, exist_ok=True)  # Assicura l'esistenza della cartella cache

# -------------------------
# INIZIALIZZAZIONE DELL'API
# -------------------------
app = FastAPI(
    title="Backtrader Backtest & Optimization API",
    description="API per configurare ed eseguire backtest e ottimizzazioni di strategie con Backtrader, importando script o scaricando dati da Yahoo Finance, e configurando broker, observers e analyzers.",
    version="2.0.0"
)

# -------------------------
# FUNZIONI DI SUPPORTO: CACHE
# -------------------------
def _enforce_cache_limit():
    """
    Controlla la dimensione complessiva della cartella cache e,
    se supera i 5 GB, elimina i file meno recentemente usati (LRU) finché non rientra nel limite.
    """
    files = glob.glob(os.path.join(CACHE_DIR, "*.csv"))
    total_size = 0
    file_sizes = []
    for f in files:
        s = os.path.getsize(f)
        file_sizes.append((f, s))
        total_size += s

    if total_size <= CACHE_LIMIT_BYTES:
        return  # Siamo sotto il limite, non serve fare nulla

    # Ordina i file per ultimo accesso (atime), dal più vecchio al più recente
    file_sizes.sort(key=lambda x: os.path.getatime(x[0]))

    for (fname, size) in file_sizes:
        try:
            os.remove(fname)
            total_size -= size
            if total_size <= CACHE_LIMIT_BYTES:
                break
        except OSError:
            # In caso di errore di rimozione, procedi col successivo
            pass

def _cache_file_name(symbol: str, interval: str, start: datetime = None, end: datetime = None, period: str = None) -> str:
    """
    Crea il nome file per la cache in base ai parametri usati (symbol, interval, start/end o period).
    """
    # Normalizza i parametri in stringhe
    # Se si usa 'period', non considerare start/end
    if period:
        return os.path.join(CACHE_DIR, f"{symbol}_{interval}_{period}.csv")
    else:
        s = start.strftime("%Y%m%d") if start else "NONE"
        e = end.strftime("%Y%m%d") if end else "NONE"
        return os.path.join(CACHE_DIR, f"{symbol}_{interval}_{s}_{e}.csv")

def fetch_yahoo_data(symbol: str, interval: str,
                     start: datetime = None, end: datetime = None,
                     period: str = None) -> pd.DataFrame:
    """
    Scarica i dati storici da Yahoo Finance tramite yfinance, con caching in locale.
    Se il file esiste in cache, lo carica da lì (aggiornando l'atime per la LRU).
    Altrimenti lo scarica, lo salva in cache e poi lo restituisce.
    """
    cache_file = _cache_file_name(symbol, interval, start, end, period)
    if os.path.exists(cache_file):
        # Carica i dati dal file di cache
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        # Aggiorna l'atime (ultimo accesso)
        os.utime(cache_file, None)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"Dati in cache vuoti per {symbol} con intervallo {interval}")
        return df
    else:
        # Scarica i dati da yfinance
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(interval=interval, start=start, end=end, period=period)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Errore nel download da Yahoo Finance: {e}")

        if df.empty:
            raise HTTPException(status_code=404, detail=f"Nessun dato disponibile da Yahoo Finance per {symbol}")

        # Salva in cache
        df.to_csv(cache_file)
        _enforce_cache_limit()
        return df


def load_inline_data(data_csv: str = None, data_dict: Dict[str, List[Any]] = None) -> pd.DataFrame:
    """
    Carica i dati forniti inline (stringa CSV o dizionario di liste) in un DataFrame Pandas.
    """
    if data_csv:
        try:
            df = pd.read_csv(io.StringIO(data_csv))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Errore nel parsing del CSV inline: {e}")
    elif data_dict:
        try:
            df = pd.DataFrame(data_dict)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Errore nella creazione DataFrame dal dizionario: {e}")
    else:
        raise HTTPException(status_code=400, detail="Nessun dato inline fornito (data_csv o data_dict)")

    if df.empty:
        raise HTTPException(status_code=400, detail="I dati inline forniti sono vuoti.")

    return df


def map_interval_to_bt_timeframe(interval: str):
    """
    Mappa la stringa di intervallo tipica di Yahoo (es. '1m', '15m', '1h', '1d', ecc.)
    in timeframe e compression per Backtrader.
    Esempi:
      - '1m' -> (Minutes, 1)
      - '15m' -> (Minutes, 15)
      - '1h' -> (Minutes, 60)
      - '1d' -> (Days, 1)
      - '5d' -> (Days, 5)
      - '1wk' -> (Weeks, 1)
      - '2mo' -> (Months, 2)
    """
    if not interval:
        # default: daily
        return (bt.TimeFrame.Days, 1)

    interval = interval.lower().strip()
    if interval.endswith("m"):  # es. '15m'
        try:
            minutes = int(interval[:-1])
            return (bt.TimeFrame.Minutes, minutes)
        except ValueError:
            return (bt.TimeFrame.Minutes, 1)
    elif interval.endswith("h"):  # es. '1h'
        try:
            hours = int(interval[:-1])
            return (bt.TimeFrame.Minutes, hours * 60)
        except ValueError:
            return (bt.TimeFrame.Minutes, 60)
    elif interval.endswith("d"):  # es. '1d', '5d'
        try:
            days = int(interval[:-1])
            return (bt.TimeFrame.Days, days)
        except ValueError:
            return (bt.TimeFrame.Days, 1)
    elif interval.endswith("wk"):  # es. '1wk'
        try:
            wks = int(interval[:-2])
            return (bt.TimeFrame.Weeks, wks)
        except ValueError:
            return (bt.TimeFrame.Weeks, 1)
    elif interval.endswith("mo"):  # es. '1mo', '3mo'
        try:
            mos = int(interval[:-2])
            return (bt.TimeFrame.Months, mos)
        except ValueError:
            return (bt.TimeFrame.Months, 1)
    else:
        # se non riconosciuto, di default daily
        return (bt.TimeFrame.Days, 1)


def create_datafeed(config: DataFeedConfig) -> bt.feeds.PandasData:
    """
    Crea un data feed di Backtrader a partire dalla configurazione.
    Supporta 3 modalità:
      1) source='csv': usa un file CSV locale (YahooFinanceCSVData).
      2) source='yahoo': scarica i dati via yfinance (in cache).
      3) source='inline': usa data_csv o data_dict forniti.
    Ritorna un oggetto PandasData pronto per l'inserimento in Cerebro.
    """
    # Caso 1: CSV locale
    if config.source.lower() == "csv":
        if not config.dataname:
            raise HTTPException(
                status_code=400,
                detail="Per 'csv' devi specificare il percorso (dataname)."
            )
        from_date = config.fromdate or datetime(2000, 1, 1)
        to_date = config.todate or datetime.now()

        try:
            data = bt.feeds.YahooFinanceCSVData(
                dataname=config.dataname,
                fromdate=from_date,
                todate=to_date,
                reverse=config.reverse
            )
            return data

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore nel caricamento del data feed CSV: {str(e)}")

    # Caso 2: Download da Yahoo Finance
    elif config.source.lower() == "yahoo":
        if not config.symbol:
            raise HTTPException(
                status_code=400,
                detail="Per 'yahoo' devi specificare almeno un 'symbol'."
            )
        # Scarica i dati con yfinance (con cache)
        df = fetch_yahoo_data(
            symbol=config.symbol,
            interval=config.interval or '1d',  # default giornaliero
            start=config.start,
            end=config.end,
            period=config.period
        )
        # Ordiniamo i dati per data e costruiamo un feed PandasData
        df.sort_index(inplace=True)

        # Mappiamo l'intervallo Yahoo in timeframe e compression, se non specificati
        if not config.timeframe or not config.compression:
            timeframe, compression = map_interval_to_bt_timeframe(config.interval or '1d')
        else:
            # Se l'utente li ha già specificati, li usiamo
            # Mappiamo comunque la stringa timeframe in oggetto TimeFrame se possibile
            timeframe_str = (config.timeframe or 'Days').lower()
            if timeframe_str == 'days':
                timeframe = bt.TimeFrame.Days
            elif timeframe_str == 'minutes':
                timeframe = bt.TimeFrame.Minutes
            elif timeframe_str == 'weeks':
                timeframe = bt.TimeFrame.Weeks
            elif timeframe_str == 'months':
                timeframe = bt.TimeFrame.Months
            else:
                timeframe = bt.TimeFrame.Days
            compression = config.compression or 1

        data = bt.feeds.PandasData(dataname=df, timeframe=timeframe, compression=compression)
        return data

    # Caso 3: dati inline
    elif config.source.lower() == "inline":
        # Carica i dati come DataFrame
        df = load_inline_data(data_csv=config.data_csv, data_dict=config.data_dict)
        # Verifica che ci sia almeno la colonna "Close"
        if 'Close' not in df.columns:
            raise HTTPException(status_code=400, detail="Nei dati inline manca la colonna 'Close'.")

        # Se c'è la colonna Date, impostiamola come indice
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)

        # Se timeframe/compression non sono specificati, di default daily
        if not config.timeframe or not config.compression:
            timeframe, compression = bt.TimeFrame.Days, 1
        else:
            # Mappiamo la stringa timeframe
            timeframe_str = (config.timeframe or 'Days').lower()
            if timeframe_str == 'days':
                timeframe = bt.TimeFrame.Days
            elif timeframe_str == 'minutes':
                timeframe = bt.TimeFrame.Minutes
            elif timeframe_str == 'weeks':
                timeframe = bt.TimeFrame.Weeks
            elif timeframe_str == 'months':
                timeframe = bt.TimeFrame.Months
            else:
                timeframe = bt.TimeFrame.Days
            compression = config.compression or 1

        data = bt.feeds.PandasData(dataname=df, timeframe=timeframe, compression=compression)
        return data

    else:
        raise HTTPException(
            status_code=400,
            detail="Fonte data feed non supportata. Usa 'csv', 'yahoo' o 'inline'."
        )

# -------------------------
# FUNZIONI PER OBSERVER E ANALYZER
# -------------------------
def add_observers(cerebro, observers: List[ObserverConfig]):
    """
    Aggiunge gli observers al Cerebro utilizzando le configurazioni fornite.
    """
    for obs in observers:
        try:
            obs_class = getattr(bt.observers, obs.name)
            cerebro.addobserver(obs_class, **obs.parameters)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Errore nell'aggiunta dell'observer {obs.name}: {str(e)}"
            )

def add_analyzers(cerebro, analyzers: List[AnalyzerConfig]):
    """
    Aggiunge gli analyzers al Cerebro utilizzando le configurazioni fornite.
    """
    for ana in analyzers:
        try:
            ana_class = getattr(bt.analyzers, ana.name)
            cerebro.addanalyzer(ana_class, _name=ana.name, **ana.parameters)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Errore nell'aggiunta dell'analyzer {ana.name}: {str(e)}"
            )

# -------------------------
# ENDPOINT PER BACKTEST
# -------------------------
@app.post("/backtest")
async def run_backtest(config: BacktestConfig):
    """
    Esegue il backtest configurabile:
      - Importa lo script della strategia (che deve definire la classe 'Strategy' derivata da bt.Strategy).
      - Carica i dati (CSV locale, Yahoo Finance o inline).
      - Configura Cerebro (broker, observers, analyzers).
      - Esegue il backtest e restituisce i risultati (valore portafoglio finale, cash, analisi).
    """
    # 1. Creazione del data feed
    data = create_datafeed(config.data_feed)

    # 2. Crea l'istanza di Cerebro e configura il broker
    cerebro = bt.Cerebro(runonce=config.runonce)
    cerebro.broker.setcash(config.broker.initial_cash)
    if config.broker.commission and config.broker.commission > 0:
        cerebro.broker.setcommission(commission=config.broker.commission)

    cerebro.adddata(data)

    # 3. Importa dinamicamente lo script della strategia
    local_context = {}
    global_context = {
        'bt': bt
        # Se vuoi aggiungere altri simboli (ad es. date, logging, ecc.), basta inserirli qui
    }
    try:
        exec(config.strategy_script, global_context, local_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nello script della strategia: {str(e)}")

    StrategyClass = local_context.get("Strategy")
    if not StrategyClass:
        raise HTTPException(
            status_code=400,
            detail="Lo script non definisce una classe 'Strategy'."
        )

    # 4. Aggiunge la strategia a Cerebro
    try:
        cerebro.addstrategy(StrategyClass, **(config.strategy_parameters or {}))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Errore nell'aggiunta della strategia: {str(e)}"
        )

    # 5. Aggiunge observers e analyzers, se presenti
    if config.observers:
        add_observers(cerebro, config.observers)
    if config.analyzers:
        add_analyzers(cerebro, config.analyzers)

    # 6. Esegui il backtest
    try:
        result = cerebro.run(preload=config.preload)
        final_value = cerebro.broker.getvalue()
        cash = cerebro.broker.getcash()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante il backtest: {str(e)}")

    # 7. Recupera i risultati degli analyzers
    analyzers_results = {}
    if config.analyzers:
        strat_instance = result[0]
        for ana in config.analyzers:
            try:
                analyzers_results[ana.name] = strat_instance.analyzers.getbyname(ana.name).get_analysis()
            except Exception as e:
                analyzers_results[ana.name] = f"Errore nel recupero: {str(e)}"

    return {
        "detail": "Backtest eseguito con successo.",
        "final_value": final_value,
        "cash": cash,
        "analyzers": analyzers_results
    }

# -------------------------
# ENDPOINT PER OTTIMIZZAZIONE
# -------------------------
@app.post("/optimization")
async def run_optimization(config: OptimizationConfig):
    """
    Esegue l'ottimizzazione della strategia con parametri multipli (liste):
      - strategy_script: codice Python che definisce la classe 'Strategy' in un modulo
      - data_feed: configurazione del feed (CSV/Yahoo/inline)
      - broker: configurazione broker (initial_cash, commission, ecc.)
      - strategy_parameters: dict con liste di valori da ottimizzare
      - observers/analyzers: da aggiungere a Cerebro
      - runonce, preload, optdatas, optreturn, maxcpus: impostazioni di Cerebro
      - top_n: se > 0, restituisce solo i primi top_n run (ordinati per best_value)
      - top_m: se > 0, per ogni run restituisce solo le prime top_m strategie (ordinate per final_value)
    """

    # 1. Salvataggio su file .py del codice strategy_script
    strategy_script = config.strategy_script
    unique_id = uuid.uuid4().hex
    module_name = f"strategies.temp_strategy_{unique_id}"
    file_path = os.path.join("strategies", f"temp_strategy_{unique_id}.py")

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(strategy_script)

        # Import dinamico del modulo
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "Strategy"):
            raise HTTPException(status_code=400, detail="Classe Strategy non trovata nello script fornito.")
        StrategyClass = getattr(module, "Strategy")

    except Exception as e:
        # Rimuove il file in caso di errore iniziale
        if os.path.isfile(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Errore nell'import del modulo strategia: {str(e)}")

    # 2. Creazione del data feed
    data = create_datafeed(config.data_feed)

    # 3. Creazione di Cerebro
    cerebro = bt.Cerebro(runonce=config.runonce)
    cerebro.optreturn = bool(config.optreturn)

    if config.broker.initial_cash:
        cerebro.broker.setcash(config.broker.initial_cash)
    if config.broker.commission and config.broker.commission > 0:
        cerebro.broker.setcommission(commission=config.broker.commission)

    cerebro.adddata(data)

    # 4. Aggiunta strategia in modalità ottimizzazione
    try:
        cerebro.optstrategy(StrategyClass, **config.strategy_parameters)
    except Exception as e:
        # Rimuove file e poi solleva
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Errore nell'aggiunta della strategia in ottimizzazione: {str(e)}")

    # 5. Aggiunta observers e analyzers (se presenti)
    if config.observers:
        add_observers(cerebro, config.observers)
    if config.analyzers:
        add_analyzers(cerebro, config.analyzers)

    # 6. Esegui l'ottimizzazione
    try:
        if config.maxcpus:
            results = cerebro.run(
                preload=config.preload,
                optdatas=config.optdatas,
                maxcpus=config.maxcpus,
                optreturn=cerebro.optreturn
            )
        else:
            results = cerebro.run(
                preload=config.preload,
                optdatas=config.optdatas,
                optreturn=cerebro.optreturn
            )
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Errore durante l'ottimizzazione: {str(e)}")

    # 7. Rimozione del file temporaneo di strategia
    if os.path.isfile(file_path):
        os.remove(file_path)

    # 8. Costruisci la lista dei risultati, con supporto top_n / top_m
    all_runs = []
    # results è una lista di runs (ogni run è una lista di strategie)

    for run_index, run_strats in enumerate(results):
        # run_strats => elenco di strategie
        run_data = {
            "run_index": run_index,
            "best_value": None,
            "strategies": []
        }

        # Estraggo i dati di ciascuna strategia in questo run
        strat_info_list = []

        for strat_instance in run_strats:
            # Otteniamo parametri
            param_dict = dict(strat_instance.params.__dict__)

            # Otteniamo final_value
            final_value = strat_instance.broker.getvalue()

            # Recupero analyzers (se optreturn=False e la strategia è reale)
            analyzers_output = {}
            if config.analyzers and not cerebro.optreturn:
                for ana_cfg in config.analyzers:
                    ana_name = ana_cfg.name
                    try:
                        ana_obj = strat_instance.analyzers.getbyname(ana_name)
                        analyzers_output[ana_name] = ana_obj.get_analysis()
                    except:
                        analyzers_output[ana_name] = "Errore nel recupero o optreturn=True"

            # Recupero observers: non hanno get_analysis() standard,
            # ma possiamo almeno elencare quelli presenti
            #observers_output = []
            #if config.observers and not cerebro.optreturn:
                # strategy_instance._observersbyname => dict di observers
                # ma è API interna di Backtrader; potremmo enumerarli, es.:
                #obs_names = [o.__class__.__name__ for o in strat_instance._observers]
                #observers_output = obs_names

            # Salvo la strategia
            strat_info_list.append({
                "parameters": param_dict,
                "final_value": final_value,
                "analyzers": analyzers_output,
                #"observers": observers_output
            })

        # Ordino le strategie del run per final_value decrescente
        strat_info_list.sort(key=lambda x: x["final_value"], reverse=True)

        # Se top_m > 0, prendo solo le prime top_m strategie
        if config.top_m and config.top_m > 0:
            strat_info_list = strat_info_list[: config.top_m]

        run_data["strategies"] = strat_info_list

        # Se abbiamo almeno una strategia, best_value = final_value della prima (che è la migliore)
        if strat_info_list:
            run_data["best_value"] = strat_info_list[0]["final_value"]

        all_runs.append(run_data)

    # Ora ordino i run per best_value decrescente
    all_runs.sort(key=lambda x: (x["best_value"] is not None, x["best_value"]), reverse=True)

    # Se top_n > 0, prendo solo i primi top_n run
    if config.top_n and config.top_n > 0:
        all_runs = all_runs[: config.top_n]

    return {
        "detail": "Ottimizzazione completata.",
        "results": all_runs
    }

# -------------------------
# AVVIO DELL'API
# -------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
