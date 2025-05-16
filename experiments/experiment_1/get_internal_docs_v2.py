import inspect
import json
import os
import backtrader as bt
import backtrader.indicators as btind
import backtrader.feeds as btfeeds
import backtrader.observers as bto
import backtrader.analyzers as btana
import backtrader.strategies as btstrat


class BacktraderDocsDetailed:
    """
    Questa classe raccoglie la documentazione completa degli oggetti di Backtrader,
    organizzata per categorie: core, indicators, datafeeds, observers, analyzers e strategies.

    Per ciascuna classe vengono estratte informazioni quali:
      - Nome della classe, modulo di appartenenza e docstring.
      - Firma del costruttore (__init__).
      - Lista dei metodi (nome, firma e docstring), escludendo i metodi “dunder”.
      - Attributi (non-callable) definiti nella classe, con il loro valore e eventuale documentazione.
      - Schema di input, basato sulla firma del costruttore (parametri, default e annotazioni).
      - Schema dei parametri (se presente l’attributo params tipico di Backtrader).
      - Schema di output: se la classe definisce l’attributo “lines”, si cerca di interpretare in modo
        leggibile i nomi delle linee e altre informazioni.
    """

    def __init__(self):
        # Categorie di moduli da analizzare
        self.modules = {
            "core": bt,
            "indicators": btind,
            "datafeeds": btfeeds,
            "observers": bto,
            "analyzers": btana,
            "strategies": btstrat,
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
            # Se lines_attr è una lista o tupla di elementi (ad esempio stringhe)
            if isinstance(lines_attr, (list, tuple)):
                output_schema["lines"] = [{"name": str(l), "type": "Line", "description": ""} for l in lines_attr]
            elif isinstance(lines_attr, type):
                # Se è una classe, tentiamo di estrarre un attributo _names
                if hasattr(lines_attr, "_names"):
                    names = getattr(lines_attr, "_names")
                    if isinstance(names, (list, tuple)):
                        output_schema["lines"] = [{"name": str(n), "type": "Line", "description": ""} for n in names]
                    else:
                        output_schema["lines"] = {"model": str(lines_attr),
                                                  "detail": "Non è possibile interpretare _names"}
                else:
                    # Proviamo ad usare la docstring del tipo lines_attr per estrarre informazioni
                    doc_lines = inspect.getdoc(lines_attr) or ""
                    output_schema["lines"] = {"model": str(lines_attr), "doc": doc_lines}
            else:
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
                # Considera solo le classi definite nel modulo corrente
                if not cls.__module__.startswith(module.__name__):
                    continue
                cls_info = self.get_class_info(cls)
                docs[category].append(cls_info)
        return docs

    def save_docs_to_files(self, output_dir="backtrader_docs_v2"):
        """
        Salva la documentazione per ogni categoria in file JSON separati in una cartella.
        Ogni categoria avrà una sottocartella e per ogni classe verrà creato un file JSON
        avente come nome il nome della classe.
        """
        docs = self.get_full_docs()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        for category, classes_info in docs.items():
            category_dir = os.path.join(output_dir, category)
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)
            for cls_info in classes_info:
                filename = os.path.join(category_dir, f"{cls_info['name']}.json")
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(cls_info, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    docs_generator = BacktraderDocsDetailed()
    docs_generator.save_docs_to_files()
    print("Documentazione salvata nella cartella 'backtrader_docs'.")
