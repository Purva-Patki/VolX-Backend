from ast import parse
import datetime
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import numpy as np
from pydantic import BaseModel
import yfinance as yf
from datetime import datetime, timedelta
import json
import asyncio

app = FastAPI()
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TradingData(BaseModel):
    Close: float
    High: float
    Low: float 
    Open: float
    Volume: float
    Date: str

@app.get("/commodity/{com_id}")
async def get_commodity_details(com_id: str, days: int = 7):
    try:
        # Get historical data
        historical_data = yf.download(com_id, period=f"{days}d", interval="1d")
        
        # Get live data
        ticker = yf.Ticker(com_id)
        live_price = ticker.info.get('regularMarketPrice', 0)
        live_high = ticker.info.get('regularMarketDayHigh', 0)
        live_low = ticker.info.get('regularMarketDayLow', 0)
        live_open = ticker.info.get('regularMarketOpen', 0)
        live_volume = ticker.info.get('regularMarketVolume', 0)
        
        if historical_data.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for symbol {com_id}. Please verify the symbol."
            )

        json_data = []

        # Add historical data
        for date, row in historical_data.iterrows():
            entry = {
                "Date": date.strftime("%Y-%m-%d"),
                "Close": round(float(row["Close"]), 2),
                "High": round(float(row["High"]), 2),
                "Low": round(float(row["Low"]), 2),
                "Open": round(float(row["Open"]), 2),
                "Volume": int(row["Volume"]),
            }
            json_data.append(entry)
        
        if not json_data:
            return JSONResponse(
                content={"message": "No Data Found!!!"},
                status_code=404
            )
            
        return JSONResponse(
            content=json_data,
            status_code=200
        )
        
    except Exception as e:
        if "No data found" in str(e):
            raise HTTPException(
                status_code=404,
                detail=f"Symbol not found: {com_id}. Try using format like 'BTC-USD' for crypto or '^VIX' for indices"
            )
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )

@app.get("/commodity/{com_id}/stats")
async def get_commodity_stats(com_id: str, days: int = 7):
    try:
        historical_data = yf.download(com_id, period=f"{days}d", interval="1d")
        
        if historical_data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {com_id}")
        
        closing_prices = historical_data["Close"].values
        std_dev = float(np.std(closing_prices))
        mean = float(np.mean(closing_prices))
        
        return JSONResponse({
            "symbol": com_id,
            "days": days,
            "closing_prices": [round(float(p), 2) for p in closing_prices],
            "standard_deviation": round(std_dev, 2),
            "mean": round(mean, 2),
            "min": round(float(np.min(closing_prices)), 2),
            "max": round(float(np.max(closing_prices)), 2),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add WebSocket endpoint for live updates
@app.websocket("/ws/{com_id}")
async def websocket_endpoint(websocket: WebSocket, com_id: str, days: int = 7):
    await websocket.accept()
    try:
        while True:
            # Get n days of closing data for std dev
            historical_data = yf.download(com_id, period=f"{days}d", interval="1d")
            
            # Get latest 1-minute candle for live price
            live_data_df = yf.download(com_id, period="1d", interval="1m")
            
            if not live_data_df.empty and not historical_data.empty:
                latest = live_data_df.iloc[-1]
                closing_prices = historical_data["Close"].values
                
                live_data = {
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Close": round(float(latest["Close"]), 2),
                    "High": round(float(latest["High"]), 2),
                    "Low": round(float(latest["Low"]), 2),
                    "Open": round(float(latest["Open"]), 2),
                    "Volume": int(latest["Volume"]),
                    "StandardDeviation": round(float(np.std(closing_prices)), 2),
                    "Mean": round(float(np.mean(closing_prices)), 2),
                    "isLive": True
                }
                
                await websocket.send_json(live_data)
            
            await asyncio.sleep(10)
    except Exception as e:
        print(f"WebSocket Error: {str(e)}")
        await websocket.close()