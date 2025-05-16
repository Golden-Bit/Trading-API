import os
import inspect
import json
import backtrader.indicators as btind
import backtrader.feeds as btfeeds
import backtrader.observers as bto
import backtrader.analyzers as btana
import backtrader.strategies as btstrat
import backtrader.cerebro as btcerebro

import backtrader as bt

class BacktraderDocsDetailed:
    """
    Questa classe raccoglie la documentazione completa degli oggetti di Backtrader,
    organizzata per categorie: indicators, datafeeds, observers, analyzers e strategies.

    Per ciascuna classe vengono estratte informazioni quali:
      - Nome della classe, modulo di appartenenza e docstring.
      - Firma del costruttore (__init__).
      - Lista dei metodi (nome, firma e docstring), escludendo i metodi “dunder”.
      - Attributi (non-callable) definiti nella classe, con il loro valore e eventuale documentazione.
      - Schema di input, basato sulla firma del costruttore (parametri, default e annotazioni).
      - Schema dei parametri (se presente l’attributo params tipico di Backtrader).
      - Schema di output: se la classe definisce l’attributo “lines” (tipico negli indicatori),
        si cerca di estrarre in modo umano leggibile i nomi delle linee e altre informazioni.
    """
    def __init__(self):
        # Definiamo i moduli da analizzare
        self.modules = {
            "indicators": btind,
            "datafeeds": btfeeds,
            "observers": bto,
            "analyzers": btana,
            "strategies": btstrat,
            "cerebro": btcerebro,
        }

    def get_class_info(self, cls):
        info = {}
        info["name"] = cls.__name__
        info["module"] = cls.__module__
        info["doc"] = inspect.getdoc(cls) or ""

        # Firma del costruttore (__init__)
        try:
            info["constructor_signature"] = str(inspect.signature(cls.__init__))
        except Exception:
            info["constructor_signature"] = "N/A"

        # Metodi: lista di metodi non "dunder"
        methods = []
        for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith("__") and name.endswith("__"):
                continue
            try:
                sig = str(inspect.signature(member))
            except Exception:
                sig = "N/A"
            methods.append({
                "name": name,
                "signature": sig,
                "doc": inspect.getdoc(member) or ""
            })
        info["methods"] = methods

        # Attributi: estrae i membri non callable e non "dunder"
        attributes = {}
        for name, value in cls.__dict__.items():
            if name.startswith("__") and name.endswith("__"):
                continue
            if not callable(value):
                attributes[name] = {
                    "value": repr(value),
                    "doc": (inspect.getdoc(value) or "").strip()
                }
        info["attributes"] = attributes

        # Input schema: basato sulla firma del costruttore (escludendo "self")
        input_schema = {}
        try:
            sig = inspect.signature(cls.__init__)
            for param in sig.parameters.values():
                if param.name == "self":
                    continue
                input_schema[param.name] = {
                    "default": param.default if param.default is not param.empty else None,
                    "annotation": str(param.annotation) if param.annotation is not param.empty else "Any"
                }
        except Exception:
            input_schema = {}
        info["input_schema"] = input_schema

        # Parameters schema: analizza l'attributo "params" se presente
        params_schema = {}
        if hasattr(cls, "params"):
            params_attr = getattr(cls, "params")
            try:
                # In Backtrader spesso params è una tupla di tuple
                for param in params_attr:
                    if isinstance(param, tuple) and len(param) >= 2:
                        param_name = param[0]
                        default = param[1]
                        extra = param[2] if len(param) > 2 else None
                        params_schema[param_name] = {
                            "default": default,
                            "extra": extra
                        }
            except Exception:
                params_schema = {}
        info["params_schema"] = params_schema

        # Output schema: se la classe definisce l'attributo "lines"
        output_schema = {}
        if hasattr(cls, "lines"):
            lines_attr = getattr(cls, "lines")
            # Se lines_attr è una tupla o lista di elementi (ad es. di stringhe) usale direttamente
            if isinstance(lines_attr, (list, tuple)):
                # Se gli elementi sono stringhe, assumiamo che siano i nomi
                if all(isinstance(l, str) for l in lines_attr):
                    output_schema["lines"] = [{"name": l, "type": "Line", "description": ""} for l in lines_attr]
                else:
                    output_schema["lines"] = [{"name": str(l), "type": "Line", "description": ""} for l in lines_attr]
            elif isinstance(lines_attr, type):
                # Se è un tipo (classe) allora si prova a verificare se esiste un attributo _names
                if hasattr(lines_attr, "_names"):
                    names = getattr(lines_attr, "_names")
                    if isinstance(names, (list, tuple)):
                        output_schema["lines"] = [{"name": str(n), "type": "Line", "description": ""} for n in names]
                    else:
                        output_schema["lines"] = {"model": str(lines_attr),
                                                  "detail": "Non è possibile interpretare _names"}
                else:
                    # Fallback: analizza la docstring e prova a estrarre informazioni
                    doc_lines = inspect.getdoc(lines_attr) or ""
                    output_schema["lines"] = {"model": str(lines_attr), "doc": doc_lines}
            else:
                # Se non rientra in nessuno dei casi, prova ad iterare
                try:
                    lines_list = list(lines_attr)
                    output_schema["lines"] = [{"name": str(l), "type": "Line", "description": ""} for l in lines_list]
                except Exception as e:
                    output_schema["lines"] = {"type": str(type(lines_attr)), "doc": inspect.getdoc(lines_attr) or ""}
        info["output_schema"] = output_schema

        return info

    def get_full_docs(self):
        """
        Restituisce un dizionario in cui le chiavi sono le categorie (es. "indicators")
        e il valore è una lista di documentazione dettagliata per ogni classe del modulo.
        """
        docs = {}
        for category, module in self.modules.items():
            docs[category] = []
            for name, cls in inspect.getmembers(module, inspect.isclass):
                # Considera solo le classi definite in questo modulo (filtra per __module__)
                if cls.__module__.startswith(module.__name__):
                    cls_info = self.get_class_info(cls)
                    docs[category].append(cls_info)
        return docs

    def write_docs_to_files(self, output_dir="backtrader_docs"):
        """
        Scrive i documenti JSON in file, organizzando le informazioni in cartelle per categoria.
        Per ogni categoria viene creata una cartella e per ogni classe un file JSON avente nome
        <nome_classe>.json.
        """
        full_docs = self.get_full_docs()

        # Crea la cartella principale se non esiste
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for category, docs in full_docs.items():
            category_dir = os.path.join(output_dir, category)
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)
            for cls_doc in docs:
                filename = f"{cls_doc['name']}.json"
                file_path = os.path.join(category_dir, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cls_doc, f, indent=4)
        print(f"Documentazione salvata in {output_dir}")


if __name__ == "__main__":
    docs_obj = BacktraderDocsDetailed()
    # Scrive tutta la documentazione in file JSON organizzati in cartelle per categoria
    docs_obj.write_docs_to_files()
