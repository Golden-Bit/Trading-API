# routes/datafeeds.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/datafeeds", tags=["Data Feeds"])

class DataFeed(BaseModel):
    id: Optional[int] = None
    source: str
    dataname: str
    timeframe: str
    compression: int
    fromdate: Optional[date]
    todate: Optional[date]
    reversed: bool = False

DATAFEEDS_DB: List[DataFeed] = []
datafeed_id_counter = 1

@router.get("/", response_model=List[DataFeed])
async def list_datafeeds():
    return DATAFEEDS_DB

@router.post("/", response_model=DataFeed)
async def create_datafeed(datafeed: DataFeed):
    global datafeed_id_counter
    datafeed.id = datafeed_id_counter
    DATAFEEDS_DB.append(datafeed)
    datafeed_id_counter += 1
    return datafeed

@router.get("/{datafeed_id}", response_model=DataFeed)
async def get_datafeed(datafeed_id: int):
    for df in DATAFEEDS_DB:
        if df.id == datafeed_id:
            return df
    raise HTTPException(status_code=404, detail="Datafeed non trovato")

@router.post("/{datafeed_id}/resample", response_model=DataFeed)
async def resample_datafeed(datafeed_id: int, timeframe: str, compression: int):
    for df in DATAFEEDS_DB:
        if df.id == datafeed_id:
            df.timeframe = timeframe
            df.compression = compression
            return df
    raise HTTPException(status_code=404, detail="Datafeed non trovato")
