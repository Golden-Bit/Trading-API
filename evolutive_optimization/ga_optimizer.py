import math
import random
from typing import Any, Dict, List, Union, Optional

import numpy as np
from pydantic import BaseModel, Field, validator

import backtrader as bt
from deap import base, creator, tools

# Assumendo che tu abbia un SDK denominato "bt_sdk" con classe "BTClient"
# che ti permette di inviare backtest a un server remoto o a un motore
# di calcolo. In caso contrario, puoi sostituire con la tua implementazione.
from bt_sdk.sdk import BTClient


class GAConfig(BaseModel):
    """
    Modello Pydantic che definisce tutti i parametri di configurazione
    necessari per l’ottimizzazione evolutiva.

    Attributi:
    ----------
    data_config : Dict[str, Any]
        Configurazione relativa ai dati (per es. sorgente, simbolo, intervallo e date).
        Esempio:
            {
                "source": "yahoo",
                "symbol": "AAPL",
                "interval": "1d",
                "start": "2020-01-01",
                "end":   "2024-12-31"
            }

    strategy_code : str
        Codice Python della strategia Backtrader da ottimizzare, come stringa.
        Questo codice dovrà definire una classe `Strategy(bt.Strategy)`.

    fitness_code : str
        Codice Python che definisce una classe `Fitness` con un metodo `evaluate`
        in grado di ricevere il dizionario `input_strategy` (risultato dell’analisi
        del backtest) e calcolare un valore di fitness (float).

    params_config : Dict[str, Any]
        Definizione dei parametri da ottimizzare e dei loro range/tipi.
        Esempio:
            {
                "fast_period": {
                    "type": "integer",
                    "min": 5,
                    "max": 50
                },
                "slow_period": {
                    "type": "integer",
                    "min": 60,
                    "max": 200
                },
                "use_EMA": {
                    "type": "discrete",
                    "values": [True, False]
                },
                "stop_loss": {
                    "type": "continuous",
                    "min": 0.01,
                    "max": 0.10
                }
            }

    pop_size : int
        Dimensione della popolazione iniziale.

    generations : int
        Numero di generazioni dell’algoritmo genetico.

    cxpb : float
        Probabilità di crossover per ogni coppia di individui.

    mutpb : float
        Probabilità di mutazione per ogni individuo.

    elitism_k : int
        Numero di individui élite da preservare tale e quale ad ogni generazione.

    selection_method : Any
        Funzione di selezione DEAP. Esempio: `tools.selTournament`.

    tournsize : int
        Dimensione del torneo (se si utilizza `tools.selTournament`).

    mate_func : Any
        Funzione di crossover DEAP. Esempio: `tools.cxUniform`.

    mate_indpb : float
        Probabilità di scambio di un singolo gene nel crossover uniforme.

    mut_gene_prob : float
        Probabilità di mutazione del singolo gene (usata nella mutazione personalizzata).

    broker_config : Dict[str, Any]
        Configurazione del broker (es: `{'initial_cash': 100000, 'commission': 0.001}`).

    observers : List[Dict[str, Any]]
        Elenco di osservatori Backtrader (facoltativo).

    analyzers : List[Dict[str, Any]]
        Elenco di analizzatori Backtrader (ad es. `SharpeRatio`, `DrawDown`, ecc.).
    """

    # -------------------------------------------------
    # Definizioni di default per i vari campi:
    # (Nel caso volessi modificarli, potrai farlo istanziando GAConfig)
    # -------------------------------------------------

    data_config: Dict[str, Any] = Field(
        default={
            "source": "yahoo",
            "symbol": "AAPL",
            "interval": "1d",
            "start": "2020-01-01",
            "end": "2024-12-31"
        },
        description="Configurazione dei dati da caricare."
    )

    strategy_code: str = Field(
        default="""
import backtrader as bt

class Strategy(bt.Strategy):
    params = (('fast_period', 10), ('slow_period', 30), ('use_EMA', False), ('stop_loss', 0.05))

    def __init__(self):
        if self.p.use_EMA:
            self.ma_fast = bt.ind.EMA(period=self.p.fast_period)
            self.ma_slow = bt.ind.EMA(period=self.p.slow_period)
        else:
            self.ma_fast = bt.ind.SMA(period=self.p.fast_period)
            self.ma_slow = bt.ind.SMA(period=self.p.slow_period)

        self.crossover = bt.ind.CrossOver(self.ma_fast, self.ma_slow)
        self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.order = self.sell()
            else:
                entry_price = self.position.price
                if self.data.close[0] < entry_price * (1 - self.p.stop_loss):
                    self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None
""",
        description="Codice strategia Backtrader da ottimizzare."
    )

    fitness_code: str = Field(
        default="""
class Fitness:
    def evaluate(self, input_strategy):
        analyzers = input_strategy.get('analyzers', {})
        sr_data = analyzers.get('SharpeRatio', {})
        sharpe = sr_data.get('sharperatio', 0) or 0

        dd_data = analyzers.get('DrawDown', {})
        max_dd = dd_data.get('max_drawdown', 0.0)

        # Esempio: massimizziamo lo Sharpe e penalizziamo parzialmente il drawdown
        return sharpe - (max_dd * 0.1)
""",
        description="Codice Python che definisce la classe `Fitness` con un metodo `evaluate`."
    )

    params_config: Dict[str, Any] = Field(
        default={
            'fast_period': {'type': 'integer', 'min': 5, 'max': 50},
            'slow_period': {'type': 'integer', 'min': 60, 'max': 200},
            'use_EMA': {'type': 'discrete', 'values': [True, False]},
            'stop_loss': {'type': 'continuous', 'min': 0.01, 'max': 0.10}
        },
        description="Definizione dei parametri da ottimizzare, con range e tipo."
    )

    pop_size: int = Field(default=20, description="Dimensione popolazione iniziale.")
    generations: int = Field(default=30, description="Numero generazioni.")
    cxpb: float = Field(default=0.7, description="Probabilità di crossover.")
    mutpb: float = Field(default=0.2, description="Probabilità di mutazione.")
    elitism_k: int = Field(default=1, description="Numero di individui élite da preservare.")

    # Funzioni DEAP (in pratica, si passano come riferimento).
    # Se non usate direttamente come oggetti, si possono passare come stringhe e poi
    # risolverle con un mapping. Qui le usiamo come default su 'tools' di DEAP.
    selection_method: Any = Field(
        default=tools.selTournament,
        description="Metodo di selezione (DEAP). Esempio: tools.selTournament."
    )
    tournsize: int = Field(default=3, description="Dimensione del torneo.")
    mate_func: Any = Field(
        default=tools.cxUniform,
        description="Funzione di crossover (DEAP). Esempio: tools.cxUniform."
    )
    mate_indpb: float = Field(
        default=0.5,
        description="Probabilità di scambio gene nel crossover uniforme."
    )

    # Probabilità di mutazione del singolo gene
    mut_gene_prob: float = Field(
        default=0.2,
        description="Probabilità di mutazione per gene nella mutazione custom."
    )

    # Configurazione broker, analizzatori, observers, etc.
    broker_config: Dict[str, Any] = Field(
        default={
            "initial_cash": 100000,
            "commission": 0.001
        },
        description="Configurazione del broker (capitale iniziale, commissioni, ecc.)."
    )
    observers: List[Dict[str, Any]] = Field(
        default=[],
        description="Lista di observers di Backtrader (opzionale)."
    )
    analyzers: List[Dict[str, Any]] = Field(
        default=[
            {"name": "SharpeRatio"},
            {"name": "DrawDown"}
        ],
        description="Lista di analizzatori di Backtrader (es. SharpeRatio, DrawDown, ecc.)."
    )


class EvolutiveOptimizer:
    """
    Classe che implementa l’algoritmo genetico per l’ottimizzazione di una strategia
    Backtrader, utilizzando la libreria DEAP per la parte evolutiva.

    Parametri:
    ----------
    config : GAConfig
        Istanza del modello Pydantic contenente tutte le configurazioni necessarie
        (codice strategia, codice fitness, configurazione parametri, dimensioni
        dell’algoritmo genetico, ecc.).

    Metodi:
    -------
    run():
        Esegue l’intero processo di ottimizzazione evolutiva:
        1) Prepara la classe Fitness e i parametri
        2) Inizializza la popolazione
        3) Calcola la fitness su ciascun individuo
        4) Effettua selezione, crossover, mutazione
        5) Esegue il backtest su individui nuovi
        6) Applica l’élitismo
        7) Ripete per n generazioni
        8) Stampa e restituisce il logbook con i risultati
    """

    def __init__(self, config: GAConfig):
        """
        Costruttore della classe EvolutiveOptimizer.

        Parametri
        ---------
        config : GAConfig
            Configurazione (Pydantic) dell’algoritmo genetico e del backtest.
        """
        self.config = config

        # Inizializzazione del client Backtrader (ipotizzando sia già configurato per l'autenticazione)
        self.client = BTClient()

        # 1) Eseguo il codice della classe Fitness contenuto in self.config.fitness_code
        self.fitness_namespace = {}
        exec(self.config.fitness_code, self.fitness_namespace)
        # Estraggo la classe Fitness
        self.FitnessClass = self.fitness_namespace['Fitness']
        # Istanza dell’oggetto fitness
        self.fitness_obj = self.FitnessClass()

        # Preparo la lista ordinata dei nomi dei parametri
        self.param_names = list(self.config.params_config.keys())

        # Definizione del tipo di Fitness in DEAP (massimizzazione)
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        # Definizione del tipo Individual (lista di parametri con fitness)
        creator.create("Individual", list, fitness=creator.FitnessMax)

        # Toolbox DEAP
        self.toolbox = base.Toolbox()

        # Registro la funzione per generare individui
        self.toolbox.register("individual", self.generate_individual)
        # Registro la popolazione
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        # Registro la funzione di valutazione
        self.toolbox.register("evaluate", self.evaluate_individual)
        # Registro il crossover
        self.toolbox.register("mate", self.config.mate_func, indpb=self.config.mate_indpb)
        # Registro la mutazione (custom) – definita come metodo sotto
        self.toolbox.register("mutate", self.mutate_individual)
        # Registro la funzione di selezione
        self.toolbox.register("select", self.config.selection_method, tournsize=self.config.tournsize)

        # Strutture di log
        self.stats = tools.Statistics(lambda ind: ind.fitness.values[0])
        self.stats.register("avg", np.mean)
        self.stats.register("std", np.std)
        self.stats.register("min", np.min)
        self.stats.register("max", np.max)

        self.logbook = tools.Logbook()
        self.logbook.header = ["gen", "nevals", "avg", "std", "min", "max"]

    def generate_individual(self):
        """
        Genera un individuo casuale (lista di valori) rispettando la definizione
        dei parametri in self.config.params_config.

        Returns
        -------
        individual : creator.Individual
            Lista dei parametri (float, int o valori discreti) con associata la fitness.
        """
        ind = []
        for name in self.param_names:
            cfg = self.config.params_config[name]
            p_type = cfg['type']

            if p_type == 'continuous':
                # Valore float uniforme nel range [min, max]
                val = random.uniform(cfg['min'], cfg['max'])
            elif p_type == 'integer':
                # Valore intero random nel range [min, max] inclusi
                val = random.randint(cfg['min'], cfg['max'])
            elif p_type == 'discrete':
                # Valore da una lista discreta di possibili valori
                val = random.choice(cfg['values'])
            else:
                raise ValueError(f"Tipo di parametro sconosciuto: {p_type}")

            ind.append(val)

        return creator.Individual(ind)

    def evaluate_individual(self, individual):
        """
        Funzione di valutazione (fitness) di un singolo individuo.
        - Converte i valori dell’individuo in un dizionario di parametri
        - Lancia il backtest tramite self.client
        - Calcola la fitness usando la classe Fitness caricata dinamicamente

        Parametri
        ---------
        individual : creator.Individual
            Individuo (lista di parametri) da valutare.

        Returns
        -------
        tuple
            Tupla con il valore di fitness (un solo valore -> `(fitness,)`).
        """
        # Costruisco il dizionario parametri
        param_values = {name: val for name, val in zip(self.param_names, individual)}

        # Costruisce la configurazione del backtest
        backtest_config = {
            "strategy_script": self.config.strategy_code,
            "data_feed": self.config.data_config,
            "strategy_parameters": param_values,
            "broker": self.config.broker_config,
            "observers": self.config.observers,
            "analyzers": self.config.analyzers
        }

        # Esegue il backtest tramite il client
        result = self.client.run_backtest(backtest_config)

        # Calcolo della fitness attraverso la classe custom
        fitness_value = self.fitness_obj.evaluate(result)

        return (fitness_value,)

    def mutate_individual(self, individual):
        """
        Mutazione personalizzata di un individuo. Ogni gene ha una certa
        probabilità (`self.config.mut_gene_prob`) di venire mutato secondo
        il proprio tipo (continuous, integer o discrete).

        Parametri
        ---------
        individual : creator.Individual
            Individuo da mutare (in-place).

        Returns
        -------
        tuple
            Ritorna la nuova tupla (individual,)
        """
        for i, name in enumerate(self.param_names):
            cfg = self.config.params_config[name]

            # Decidi se mutare questo gene
            if random.random() < self.config.mut_gene_prob:
                if cfg['type'] == 'continuous':
                    # Piccola mutazione gaussiana
                    span = cfg['max'] - cfg['min']
                    individual[i] += random.gauss(0, 0.1 * span)  # Variazione del 10% del range
                    # Clampa entro i limiti
                    individual[i] = max(cfg['min'], min(cfg['max'], individual[i]))

                elif cfg['type'] == 'integer':
                    # Riassegno un nuovo intero a caso
                    individual[i] = random.randint(cfg['min'], cfg['max'])

                elif cfg['type'] == 'discrete':
                    # Scegli un valore diverso dall'attuale
                    choices = [v for v in cfg['values'] if v != individual[i]]
                    if choices:
                        individual[i] = random.choice(choices)

        return (individual,)

    def run(self):
        """
        Metodo principale che esegue l’intero ciclo dell’algoritmo genetico:
        - Inizializzazione popolazione
        - Calcolo fitness iniziale
        - Loop generazionale con selezione, crossover, mutazione, valutazione
        - Elitismo
        - Ritorna il logbook (e stampa i risultati a video).

        Returns
        -------
        logbook : tools.Logbook
            Contiene le statistiche di ogni generazione (avg, min, max, std, ecc.).
        """
        # Inizializza popolazione
        pop = self.toolbox.population(n=self.config.pop_size)

        # Valuta la fitness iniziale di tutta la popolazione
        print("Valutazione iniziale popolazione...")
        for ind in pop:
            ind.fitness.values = self.toolbox.evaluate(ind)

        # Salvo statistiche generazione 0
        record = self.stats.compile(pop)
        self.logbook.record(gen=0, nevals=len(pop), **record)
        print(self.logbook.stream)

        # Loop sulle generazioni
        for gen in range(1, self.config.generations + 1):

            # 1) Selezione dei genitori
            offspring = self.toolbox.select(pop, len(pop) - self.config.elitism_k)
            offspring = list(map(self.toolbox.clone, offspring))

            # 2) Crossover
            for i in range(0, len(offspring) - 1, 2):
                if random.random() < self.config.cxpb:
                    self.toolbox.mate(offspring[i], offspring[i + 1])
                    del offspring[i].fitness.values, offspring[i + 1].fitness.values

            # 3) Mutazione
            nevals = 0
            for i in range(len(offspring)):
                if random.random() < self.config.mutpb:
                    self.toolbox.mutate(offspring[i])
                    del offspring[i].fitness.values

            # 4) Rivaluto la fitness dove invalida
            for ind in offspring:
                if not ind.fitness.valid:
                    ind.fitness.values = self.toolbox.evaluate(ind)
                    nevals += 1

            # 5) Elitismo
            if self.config.elitism_k > 0:
                elites = tools.selBest(pop, self.config.elitism_k)
                elites = [self.toolbox.clone(e) for e in elites]
                offspring.extend(elites)

            # 6) Nuova popolazione
            pop = offspring

            # 7) Statistiche
            record = self.stats.compile(pop)
            self.logbook.record(gen=gen, nevals=nevals, **record)
            print(self.logbook.stream)

        # Al termine, restituisco il logbook (contenente statistiche di ogni generazione)
        return self.logbook


def main():
    """
    Funzione principale di esempio che istanzia la configurazione e avvia
    il processo di ottimizzazione evolutiva.
    """
    # 1) Crea la configurazione di default (o personalizzata) usando GAConfig
    config = GAConfig(
        # Puoi sovrascrivere alcuni campi se vuoi, ad esempio:
        # pop_size=10,
        # generations=5,
        # data_config={"source": "yahoo", "symbol": "AAPL", "interval": "1d", "start": "2020-01-01", "end": "2024-12-31"},
        # etc...
    )

    # 2) Istanzia l’ottimizzatore
    optimizer = EvolutiveOptimizer(config=config)

    # 3) Esegui l’ottimizzazione
    logbook = optimizer.run()

    # 4) Se vuoi, puoi anche analizzare i risultati finali
    # Ad esempio: ottieni i migliori individui dalla popolazione finale
    # pop = ...
    # best_ind = tools.selBest(pop, 1)[0]
    # print("Miglior individuo:", best_ind, best_ind.fitness.values)

    # In questo esempio, lasciamo semplicemente che la funzione finisca.
    # I risultati intermedi sono già stati stampati a video.
    print("Ottimizzazione conclusa.")


# Se vuoi eseguire lo script come programma principale:
if __name__ == "__main__":
    main()
