# routes/available.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import inspect
import backtrader.indicators as btind
import backtrader.observers as bto
import backtrader.analyzers as btana

router = APIRouter(prefix="/available", tags=["Available Objects"])


def get_objects_info(module) -> List[Dict[str, Any]]:
    """
    Estrae informazioni dettagliate per tutte le classi definite in un modulo.
    Le informazioni includono:
      - Nome, modulo e docstring.
      - Firma del costruttore (__init__).
      - Lista dei metodi (nome, firma e docstring).
      - Schema di input (parametri del costruttore).
      - Schema dei parametri (dall’attributo 'params', se presente).
      - Schema di output (se la classe definisce 'lines', si cerca di interpretare i nomi delle linee).
    """
    objects_info = []
    for name, cls in inspect.getmembers(module, inspect.isclass):
        # Filtra solo le classi definite nel modulo (evita quelle importate)
        if not cls.__module__.startswith(module.__name__):
            continue

        info = {}
        info["name"] = cls.__name__
        info["module"] = cls.__module__
        info["doc"] = inspect.getdoc(cls) or ""

        # Firma del costruttore
        try:
            info["constructor_signature"] = str(inspect.signature(cls.__init__))
        except Exception:
            info["constructor_signature"] = "N/A"

        # Estrazione dei metodi (escludendo quelli "dunder")
        methods = []
        for mname, m in inspect.getmembers(cls, predicate=inspect.isfunction):
            if mname.startswith("__") and mname.endswith("__"):
                continue
            try:
                sig = str(inspect.signature(m))
            except Exception:
                sig = "N/A"
            methods.append({
                "name": mname,
                "signature": sig,
                "doc": inspect.getdoc(m) or ""
            })
        info["methods"] = methods

        # Schema di input: basato sulla firma del costruttore, escludendo 'self'
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

        # Schema dei parametri: analizza l'attributo "params" se presente
        params_schema = {}
        if hasattr(cls, "params"):
            params_attr = getattr(cls, "params")
            try:
                # In Backtrader, params è spesso una tupla di tuple
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

        # Schema di output: se la classe definisce l'attributo "lines"
        output_schema = {}
        if hasattr(cls, "lines"):
            lines_attr = getattr(cls, "lines")
            if isinstance(lines_attr, (list, tuple)):
                # Se le linee sono definite come una lista/tupla, le usiamo direttamente
                output_schema["lines"] = [{"name": str(l), "type": "Line", "description": ""} for l in lines_attr]
            elif isinstance(lines_attr, type):
                # Se è una classe, tentiamo di estrarne le _names se presenti
                if hasattr(lines_attr, "_names"):
                    names = getattr(lines_attr, "_names")
                    if isinstance(names, (list, tuple)):
                        output_schema["lines"] = [{"name": str(n), "type": "Line", "description": ""} for n in names]
                    else:
                        output_schema["lines"] = {"model": str(lines_attr),
                                                  "detail": "Impossibile interpretare _names"}
                else:
                    # Fallback: usa la docstring della classe lines
                    doc_lines = inspect.getdoc(lines_attr) or ""
                    output_schema["lines"] = {"model": str(lines_attr), "doc": doc_lines}
            else:
                try:
                    lines_list = list(lines_attr)
                    output_schema["lines"] = [{"name": str(l), "type": "Line", "description": ""} for l in lines_list]
                except Exception as e:
                    output_schema["lines"] = {"type": str(type(lines_attr)), "doc": inspect.getdoc(lines_attr) or ""}
        info["output_schema"] = output_schema

        objects_info.append(info)
    return objects_info


@router.get("/indicators", response_model=List[Dict[str, Any]])
async def available_indicators():
    """
    Restituisce la documentazione completa per tutti gli indicatori disponibili in Backtrader.
    """
    return get_objects_info(btind)


@router.get("/observers", response_model=List[Dict[str, Any]])
async def available_observers():
    """
    Restituisce la documentazione completa per tutti gli observers disponibili in Backtrader.
    """
    return get_objects_info(bto)


@router.get("/analyzers", response_model=List[Dict[str, Any]])
async def available_analyzers():
    """
    Restituisce la documentazione completa per tutti gli analyzers disponibili in Backtrader.
    """
    return get_objects_info(btana)
