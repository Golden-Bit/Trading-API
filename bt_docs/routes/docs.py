# routes/experiments.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import os
import json

router = APIRouter(prefix="/experiments", tags=["Documentation"])

DOCUMENTATION_DIR = "backtrader_docs"

def read_docs_for_category(category: str) -> List[Dict[str, Any]]:
    category_dir = os.path.join(DOCUMENTATION_DIR, category)
    if not os.path.exists(category_dir):
        raise HTTPException(status_code=404, detail=f"Categoria {category} non trovata.")
    docs = []
    for filename in os.listdir(category_dir):
        if filename.endswith(".json"):
            with open(os.path.join(category_dir, filename), "r", encoding="utf-8") as f:
                docs.append(json.load(f))
    return docs

@router.get("/", response_model=Dict[str, List[Dict[str, Any]]])
async def get_all_docs():
    """
    Restituisce la documentazione completa per tutte le categorie.
    """
    categories = {}
    if not os.path.exists(DOCUMENTATION_DIR):
        raise HTTPException(status_code=404, detail="Nessuna documentazione trovata.")
    for category in os.listdir(DOCUMENTATION_DIR):
        categories[category] = read_docs_for_category(category)
    return categories

@router.get("/{category}", response_model=List[Dict[str, Any]])
async def get_docs_by_category(category: str):
    """
    Restituisce la documentazione per una specifica categoria (es. indicators, strategies, ecc.).
    """
    return read_docs_for_category(category)
