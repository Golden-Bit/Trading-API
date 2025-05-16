import math
import datetime
from typing import List, Dict, Any, Optional

# Importa la classe GAConfig e EvolutiveOptimizer dal tuo script GA esistente
# (che abbiamo chiamato "ga_optimizer.py" come esempio)
from ga_optimizer import GAConfig, EvolutiveOptimizer

from pydantic import BaseModel, Field


class WalkForwardConfig(BaseModel):
    """
    Configurazione dei parametri per un singolo ciclo di Walk-Forward Optimization.

    Attributi:
    ----------
    total_start : str
        Data di inizio totale su cui eseguire WFO (formato 'YYYY-MM-DD').
    total_end : str
        Data di fine totale su cui eseguire WFO (formato 'YYYY-MM-DD').

    runs : int
        Numero di segmenti totali in cui suddividere i dati storici (se si usa la
        suddivisione automatica). In ciascun segmento, una parte (1 - oos_percent)
        sarà IS e la parte rimanente OOS.

    oos_percent : float
        Percentuale (0.0 < oos_percent < 1.0) di dati in ciascun segmento dedicati all'OOS
        (se si usa la suddivisione automatica). Esempio: 0.3 significa che il 30% di ciascun
        segmento è OOS.

    ga_config : GAConfig
        Configurazione dell'ottimizzazione genetica (popolazione, generazioni,
        range parametri, ecc.). Questa stessa configurazione verrà usata **per
        ciascun segmento IS**. Eventualmente, potresti voler cambiare `data_config`
        ad ogni run, in base alla finestra IS.

    custom_segments : Optional[List[Dict[str, str]]]
        Se non è None (o non è vuota), indica che l’utente fornisce *direttamente* i
        segmenti IS/OOS. In tal caso, ognuno è un dict con chiavi:
            {
              "is_start": "YYYY-MM-DD",
              "is_end":   "YYYY-MM-DD",
              "oos_start":"YYYY-MM-DD",
              "oos_end":  "YYYY-MM-DD"
            }
        Questi segmenti sostituiscono l’uso di `runs` e `oos_percent`.
    """

    total_start: str = Field(..., description="Data inizio del dataset completo")
    total_end: str = Field(..., description="Data fine del dataset completo")
    runs: Optional[int] = Field(None, description="Numero di suddivisioni per WFO (es. 6).")
    oos_percent: Optional[float] = Field(None, description="Percentuale OOS (es. 0.3 = 30%).")
    ga_config: GAConfig
    custom_segments: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Lista di segmenti personalizzati, ognuno con is_start, is_end, oos_start, oos_end."
    )


class WalkForwardRunner:
    """
    Classe che esegue una Walk-Forward Optimization su un singolo set
    (runs, oos_percent) *oppure* su una lista di segmenti personalizzati,
    suddividendo i dati storici in modo sequenziale.

    Esempio di flusso (suddivisione automatica):
    -------------------------------------------
    1. Dividi lo storico [start, end] in 'runs' segmenti consecutivi.
       Per ogni segmento, calcola la lunghezza e splitta in due parti:
         - IS (In-Sample) = (1 - oos_percent) di quel segmento
         - OOS (Out-of-Sample) = (oos_percent) di quel segmento

    2. Per ogni run:
       - Lancia EvolutiveOptimizer su IS --> trova parametri migliori
       - Usa quei parametri su OOS --> backtest su OOS e raccogli i risultati

    3. Al termine, crea un "equity curve" OOS concatenata e statistiche aggregate.

    Esempio di flusso (custom_segments):
    ------------------------------------
    1. L’utente fornisce un elenco di segmenti, ognuno con
         - is_start, is_end
         - oos_start, oos_end
       Non si usa 'runs' né 'oos_percent'.

    2. Per ogni segmento:
       - Lancia EvolutiveOptimizer su [is_start, is_end]
       - Applica i parametri su [oos_start, oos_end]
       - Accumula i risultati e poi produce statistiche finali.
    """

    def __init__(self, wf_config: WalkForwardConfig):
        self.wf_config = wf_config

        # Converti le date in oggetti datetime (se serve per calcolare i segmenti) – se custom_segments
        # non è fornito, useremo i calcoli di runs e oos_percent.
        self.start_date = datetime.datetime.strptime(wf_config.total_start, "%Y-%m-%d")
        self.end_date = datetime.datetime.strptime(wf_config.total_end, "%Y-%m-%d")

        self.total_days = (self.end_date - self.start_date).days
        if self.total_days <= 0:
            raise ValueError("Intervallo date non valido o zero giorni.")

        # Contenitore per i risultati di ogni run
        self.run_results = []  # [{"IS_period":..., "OOS_period":..., "best_params":..., "IS_logbook":..., "OOS_result":...}]
        # (In un caso reale si potrebbero salvare i parametri per ogni generazione, ecc.)

        # Equity cumulativa OOS (opzionale)
        self.oos_equity_curve = []

    def run_walk_forward(self) -> Dict[str, Any]:
        """
        Esegue l'intera procedura WFO. Se `custom_segments` non è vuoto, usa
        quei segmenti. Altrimenti, suddivide automaticamente l'intervallo
        [total_start, total_end] in 'runs' segmenti e li gestisce con oos_percent.

        Returns
        -------
        Dict con chiavi come:
            - 'run_results': lista dei risultati per ciascun run
            - 'wfo_summary': statistiche aggregate (es. media Sharpe OOS, etc.)
        """
        print("\n--- Inizio Walk-Forward Optimization ---")

        # Se l'utente ha fornito segmenti personalizzati, usiamo quelli
        if self._has_custom_segments():
            print("Uso segmenti personalizzati (custom_segments).")
            self._run_custom_segments()
        else:
            print("Uso segmenti calcolati automaticamente da runs/oos_percent.")
            self._run_automatic_segments()

        # Calcolo statistiche finali
        wfo_summary = self._compute_wfo_stats()
        return {
            "run_results": self.run_results,
            "wfo_summary": wfo_summary
        }

    def _has_custom_segments(self) -> bool:
        """
        Ritorna True se config.custom_segments è una lista non vuota.
        """
        segs = self.wf_config.custom_segments
        return (segs is not None) and (len(segs) > 0)

    def _run_custom_segments(self):
        """
        Esegue WFO usando i segmenti definiti manualmente da `custom_segments`.
        Ogni elemento è un dict con:
            {
              "is_start": "YYYY-MM-DD",
              "is_end":   "YYYY-MM-DD",
              "oos_start":"YYYY-MM-DD",
              "oos_end":  "YYYY-MM-DD"
            }
        """
        for run_index, seg in enumerate(self.wf_config.custom_segments):
            is_start_str = seg["is_start"]
            is_end_str = seg["is_end"]
            oos_start_str = seg["oos_start"]
            oos_end_str = seg["oos_end"]

            print(f"\nRun {run_index+1}/{len(self.wf_config.custom_segments)} - "
                  f"IS: {is_start_str} -> {is_end_str}, OOS: {oos_start_str} -> {oos_end_str}")

            # 1) Ottimizzazione su IS
            ga_optimizer, ga_logbook = self._optimize_on_is(is_start_str, is_end_str)

            # 2) Recupero i parametri migliori
            best_params = self._retrieve_best_params(ga_optimizer)

            # 3) Test su OOS
            oos_result = self._run_backtest_with_params(best_params, oos_start_str, oos_end_str)

            # 4) Salvo i risultati
            run_info = {
                "IS_period": (is_start_str, is_end_str),
                "OOS_period": (oos_start_str, oos_end_str),
                "best_params": best_params,
                "IS_logbook": ga_logbook,
                "OOS_result": oos_result
            }
            self.run_results.append(run_info)

    def _run_automatic_segments(self):
        """
        Esegue WFO dividendo [total_start, total_end] in self.wf_config.runs segmenti
        e usando self.wf_config.oos_percent per definire IS e OOS in ciascun segmento.
        """
        total_runs = self.wf_config.runs
        print(f"Periodo totale: {self.wf_config.total_start} -> {self.wf_config.total_end}")
        print(f"Suddivido in {total_runs} segmenti, OOS%={self.wf_config.oos_percent * 100:.1f}%")

        segment_length_days = self.total_days / total_runs

        current_start = self.start_date

        for run_index in range(total_runs):
            segment_end = current_start + datetime.timedelta(days=segment_length_days)
            if run_index == total_runs - 1:
                # Assicuriamoci che l'ultimo segmento arrivi esattamente a fine periodo
                segment_end = self.end_date

            segment_days = (segment_end - current_start).days
            oos_days = int(segment_days * self.wf_config.oos_percent)
            is_days = segment_days - oos_days

            is_start = current_start
            is_end = current_start + datetime.timedelta(days=is_days)
            oos_start = is_end
            oos_end = segment_end

            is_start_str = is_start.strftime("%Y-%m-%d")
            is_end_str = is_end.strftime("%Y-%m-%d")
            oos_start_str = oos_start.strftime("%Y-%m-%d")
            oos_end_str = oos_end.strftime("%Y-%m-%d")

            print(f"\nRun {run_index+1}/{total_runs} "
                  f"- IS: {is_start_str} -> {is_end_str} "
                  f"- OOS: {oos_start_str} -> {oos_end_str}")

            # 1) Ottimizzazione su IS
            ga_optimizer, ga_logbook = self._optimize_on_is(is_start_str, is_end_str)

            # 2) Recupero i parametri migliori
            best_params = self._retrieve_best_params(ga_optimizer)

            # 3) Test su OOS
            oos_result = self._run_backtest_with_params(best_params, oos_start_str, oos_end_str)

            # 4) Salvo i risultati
            run_info = {
                "IS_period": (is_start_str, is_end_str),
                "OOS_period": (oos_start_str, oos_end_str),
                "best_params": best_params,
                "IS_logbook": ga_logbook,
                "OOS_result": oos_result
            }
            self.run_results.append(run_info)

            # Avanzo al prossimo segmento
            current_start = oos_end

    def _optimize_on_is(self, is_start_str: str, is_end_str: str) -> tuple:
        """
        Crea una copia della config GA, modifica le date su [is_start_str, is_end_str],
        istanzia e lancia EvolutiveOptimizer. Ritorna la tupla (optimizer, logbook).
        """
        ga_config_copy = self.wf_config.ga_config.copy(deep=True)
        ga_config_copy.data_config["start"] = is_start_str
        ga_config_copy.data_config["end"] = is_end_str

        ga_optimizer = EvolutiveOptimizer(config=ga_config_copy)
        ga_logbook = ga_optimizer.run()

        return (ga_optimizer, ga_logbook)

    def _retrieve_best_params(self, ga_optimizer: EvolutiveOptimizer) -> Dict[str, Any]:
        """
        Esempio per recuperare i parametri migliori.
        Nel codice mostrato, la popolazione finale è interna a run().
        Occorrerebbe un metodo dell'EvolutiveOptimizer per restituire
        la popolazione o i best individuals. Qui fingiamo di restituire
        parametri di default se non abbiamo un meccanismo implementato.
        """
        # Se c'è un metodo personalizzato, potresti fare:
        # final_pop = ga_optimizer.get_final_population()
        # best_ind = tools.selBest(final_pop, 1)[0]
        # best_params = {name: val for name, val in zip(ga_optimizer.param_names, best_ind)}

        # Altrimenti, fingiamo di non avere l'info e mettiamo parametri 0:
        best_params = {name: 0 for name in ga_optimizer.param_names}
        return best_params

    def _run_backtest_with_params(self, params: Dict[str, Any],
                                  start_str: str, end_str: str) -> Dict[str, Any]:
        """
        Esegue un singolo backtest su [start, end] usando i 'params' fissi,
        e restituisce un dict di statistiche.
        """
        ga_config_copy = self.wf_config.ga_config.copy(deep=True)
        ga_config_copy.data_config["start"] = start_str
        ga_config_copy.data_config["end"] = end_str

        backtest_config = {
            "strategy_script": ga_config_copy.strategy_code,
            "data_feed": ga_config_copy.data_config,
            "strategy_parameters": params,
            "broker": ga_config_copy.broker_config,
            "observers": ga_config_copy.observers,
            "analyzers": ga_config_copy.analyzers
        }

        # In un contesto reale:
        # from bt_sdk.sdk import BTClient
        # client = BTClient()
        # result = client.run_backtest(backtest_config)
        #
        # Per ora, simuliamo un result di test:
        result = {
            "analyzers": {
                "SharpeRatio": {"sharperatio": 1.23},
                "DrawDown": {"max_drawdown": 10.0}
            },
            # Altri dati come trades, equity curve, ecc. se servono
        }
        return result

    def _compute_wfo_stats(self) -> Dict[str, Any]:
        """
        Calcola le statistiche totali su tutti i run WFO:
        - Esempio: WFE medio, profittabilità OOS, etc.

        In questo esempio: media OOS Sharpe, media OOS drawdown...
        """
        oos_sharpes = []
        oos_drawdowns = []

        for r in self.run_results:
            analyzers = r["OOS_result"]["analyzers"]
            sr = analyzers.get("SharpeRatio", {}).get("sharperatio", 0)
            dd = analyzers.get("DrawDown", {}).get("max_drawdown", 0)
            oos_sharpes.append(sr)
            oos_drawdowns.append(dd)

        if len(oos_sharpes) > 0:
            avg_sharpe = sum(oos_sharpes) / len(oos_sharpes)
            avg_dd = sum(oos_drawdowns) / len(oos_drawdowns)
        else:
            avg_sharpe = 0
            avg_dd = 0

        return {
            "avg_OOS_sharpe": avg_sharpe,
            "avg_OOS_drawdown": avg_dd,
            "runs_count": len(self.run_results),
        }


class WalkForwardMatrixRunner:
    """
    Esegue *multipli* WFO testando diverse combinazioni di (runs, oos_percent),
    per simulare la "Walk-Forward Matrix" di StrategyQuant X.

    Se l'utente vuole usare `custom_segments`, in questo esempio, lo
    fornirebbe in `base_config`; tuttavia, la logica di matrix è di solito
    pensata per variare (runs, oos_percent). Quindi, se si desidera
    testare 'N' diverse liste di segmenti custom, dovresti ampliare
    questa classe ad hoc.
    """

    def __init__(self,
                 base_config: GAConfig,
                 total_start: str,
                 total_end: str,
                 runs_list: List[int],
                 oos_list: List[float]):
        """
        Parametri:
        ----------
        base_config : GAConfig
            Configurazione di base per l'ottimizzazione genetica (ad es. pop_size, generations, etc.).
        total_start : str
            Data inizio globale del dataset.
        total_end : str
            Data fine globale del dataset.
        runs_list : List[int]
            Esempio: [5, 6, 7, 8, 10, 12] -> per ogni valore, esegui un WFO con quel 'runs'.
        oos_list : List[float]
            Esempio: [0.2, 0.3, 0.4] -> per ogni valore, esegui un WFO con quella 'oos_percent'.
        """
        self.base_config = base_config
        self.total_start = total_start
        self.total_end = total_end
        self.runs_list = runs_list
        self.oos_list = oos_list

        self.matrix_results = []  # conterrà tutti i risultati (runs, oos%) -> outcome

    def run_matrix(self) -> List[Dict[str, Any]]:
        """
        Esegue la WFO Matrix: per ogni combinazione di (runs, oos_percent),
        lancia WalkForwardRunner e raccoglie i risultati.

        Returns
        -------
        Una lista di dict, uno per combinazione testata.
        """
        for runs in self.runs_list:
            for oos in self.oos_list:
                print(f"\n==== Walk-Forward Matrix test: runs={runs}, oos={oos*100:.1f}% ====")

                # Crea la config WFO con i parametri correnti
                # Attenzione: usiamo 'runs' e 'oos_percent' e NON diamo custom_segments.
                wf_config = WalkForwardConfig(
                    total_start=self.total_start,
                    total_end=self.total_end,
                    runs=runs,
                    oos_percent=oos,
                    ga_config=self.base_config,
                    custom_segments=None
                )

                runner = WalkForwardRunner(wf_config=wf_config)
                result = runner.run_walk_forward()  # dict con run_results, wfo_summary

                # Esempio di "pass/fail": Sharpe OOS > 1 e DD OOS < 20
                summary = result["wfo_summary"]
                pass_crit = (summary["avg_OOS_sharpe"] > 1.0 and summary["avg_OOS_drawdown"] < 20)

                self.matrix_results.append({
                    "runs": runs,
                    "oos_percent": oos,
                    "result": result,
                    "passed": pass_crit
                })

        return self.matrix_results


def main():
    """
    Esempio di utilizzo:
    1) Creazione GAConfig di base
    2) Esecuzione di un WalkForwardRunner con parametri specifici (in automatico)
    3) Esecuzione di un WalkForwardRunner con segmenti custom
    4) Esecuzione (opzionale) di WalkForwardMatrixRunner
    """

    # 1) Creiamo una config GA di base
    ga_config = GAConfig(
        data_config={
            "source": "yahoo",
            "symbol": "AAPL",
            "interval": "1d",
            # Metti range ampio: "start": "2018-01-01", "end": "2024-01-01"
            # ma useremo WFO per segmentarlo
            "start": "2018-01-01",
            "end": "2024-01-01"
        },
        pop_size=50,
        generations=10,
        # Altre impostazioni di default se servono...
    )

    # 2) Esecuzione di un singolo WFO "automatico" con 3 runs e 30% OOS
    wfo_cfg_auto = WalkForwardConfig(
        total_start="2010-01-01",
        total_end="2024-01-01",
        runs=3,
        oos_percent=0.30,
        ga_config=ga_config,
        custom_segments=None  # Non forniamo segmenti manuali
    )
    wfo_runner_auto = WalkForwardRunner(wf_config=wfo_cfg_auto)
    wfo_result_auto = wfo_runner_auto.run_walk_forward()

    print("\n*** RISULTATI FINALI WFO (automatico) ***")
    print("Dettagli di ogni run:", wfo_result_auto["run_results"])
    print("Statistiche aggregate WFO:", wfo_result_auto["wfo_summary"])

    # 3) Esempio: Esecuzione di un WFO con segmenti personalizzati
    custom_segs = [
        {
            "is_start": "2010-01-01",
            "is_end":   "2012-12-31",
            "oos_start":"2013-01-01",
            "oos_end":  "2013-12-31"
        },
        {
            "is_start": "2014-01-01",
            "is_end":   "2015-12-31",
            "oos_start":"2016-01-01",
            "oos_end":  "2016-06-30"
        },
        {
            "is_start": "2017-01-01",
            "is_end":   "2018-12-31",
            "oos_start":"2019-01-01",
            "oos_end":  "2019-12-31"
        },
    ]

    wfo_cfg_custom = WalkForwardConfig(
        total_start="2010-01-01",
        total_end="2024-01-01",
        #runs=3,                 # Ininfluente se usiamo custom_segments
        #oos_percent=0.30,       # Ininfluente se usiamo custom_segments
        ga_config=ga_config,
        custom_segments=custom_segs
    )
    wfo_runner_custom = WalkForwardRunner(wf_config=wfo_cfg_custom)
    wfo_result_custom = wfo_runner_custom.run_walk_forward()

    print("\n*** RISULTATI FINALI WFO (custom segments) ***")
    print("Dettagli di ogni run:", wfo_result_custom["run_results"])
    print("Statistiche aggregate WFO:", wfo_result_custom["wfo_summary"])

    # 4) Esecuzione di un WFO matrix: testare più combinazioni (sempre con auto-segmenti)
    matrix_runner = WalkForwardMatrixRunner(
        base_config=ga_config,
        total_start="2018-01-01",
        total_end="2024-01-01",
        runs_list=[2, 3],
        oos_list=[0.2, 0.3]
    )
    matrix_results = matrix_runner.run_matrix()

    print("\n*** RISULTATI FINALI WFO MATRIX ***")
    for entry in matrix_results:
        print(f"runs={entry['runs']}, oos={entry['oos_percent']} => Passed? {entry['passed']}")

    print("Fine.")


if __name__ == "__main__":
    main()
