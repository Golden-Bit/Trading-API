# routes/memory.py
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any

router = APIRouter(prefix="/memory", tags=["Memory"])

class MemoryConfig(BaseModel):
    level: int = Field(..., description="Livello di memory saving (1, 0, -1, -2)")

@router.get("/")
async def get_memory_report():
    report = {
        "exactbars": 30,
        "details": "I data feed sono limitati al minimo numero di barre necessario per ogni calcolo."
    }
    return report

@router.post("/set")
async def set_memory_config(config: MemoryConfig):
    return {"detail": f"Livello di memory saving impostato a {config.level}"}
