# bt_client.py
import requests
import logging


class BTClient:
    def __init__(self, base_url: str = "http://localhost:8001"):
        """Inizializza il client con l'URL base dell'API Backtrader."""
        self.base_url = base_url
        # Opzionalmente, si potrebbe configurare una requests.Session() per riutilizzare la connessione

    def run_backtest(self, config):
        """Esegue una richiesta POST di backtest con la configurazione fornita."""
        url = f"{self.base_url}/backtest"
        # Se config è un modello Pydantic, convertiamolo in dict
        if hasattr(config, "dict"):
            payload = config.dict()
        else:
            payload = config  # assume sia già dict
        try:
            response = requests.post(url, json=payload)
            # Verifica se la risposta HTTP indica un errore (status code non 200)
            response.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Backtest request failed: {e}")
            # Se disponibile, logga il contenuto della risposta (es. messaggio di errore dal server)
            try:
                logging.error(f"Response content: {response.text}")
            except Exception:
                pass
            # Propaga l'eccezione dopo il logging
            raise
        # Restituisce il JSON della risposta come dizionario Python
        return response.json()

    def run_optimization(self, config):
        """Esegue una richiesta POST di optimization con la configurazione fornita."""
        url = f"{self.base_url}/optimization"
        if hasattr(config, "dict"):
            payload = config.dict()
        else:
            payload = config
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Optimization request failed: {e}")
            try:
                logging.error(f"Response content: {response.text}")
            except Exception:
                pass
            raise
        return response.json()
