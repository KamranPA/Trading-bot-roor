# FILE: src/coinex_client.py
# PURPOSE: CoinEx API Client for fetching market data and live prices

import requests
import logging

logger = logging.getLogger(__name__)

class CoinExClient:
    def __init__(self):
        self.base_url = "https://api.coinex.com/v2"
        self.session = requests.Session()

    def get_last_candles(self, market: str, limit: int = 100, period: str = "4h") -> list:
        """
        Fetches the recent OHLCV candles for a given market from CoinEx V2 API.
        """
        interval_map = {
            "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
            "1h": "1hour", "2h": "2hour", "4h": "4hour", "6h": "6hour",
            "12h": "12hour", "1d": "1day", "3d": "3day", "1w": "1week"
        }
        
        coinex_period = interval_map.get(period, "4hour")
        url = f"{self.base_url}/market/kline"
        params = {
            "market": market,
            "period": coinex_period,
            "limit": limit
        }
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0 or "data" not in data:
                logger.error(f"CoinEx API error for {market}: {data.get('message')}")
                return []
                
            candles = data["data"]
            formatted_candles = []
            
            for c in candles:
                formatted_candles.append({
                    "timestamp": int(c[0]),
                    "open": float(c[1]),
                    "close": float(c[2]),
                    "high": float(c[3]),
                    "low": float(c[4]),
                    "volume": float(c[5])
                })
            return formatted_candles
            
        except Exception as e:
            logger.error(f"Failed to fetch candles for {market} from CoinEx: {e}")
            return []

    def get_current_price(self, market: str) -> float:
        """
        Fetches the current live price (ticker) for a given market.
        Returns 0.0 if failed.
        """
        url = f"{self.base_url}/market/ticker"
        params = {"market": market}
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == 0 and "data" in data:
                ticker_info = data["data"]
                if isinstance(ticker_info, list) and len(ticker_info) > 0:
                    return float(ticker_info[0]["last"])
                elif isinstance(ticker_info, dict):
                    return float(ticker_info.get("last", 0.0))
            
            # Fallback if ticker structure varies
            url_all = f"{self.base_url}/market/ticker/all"
            res_all = self.session.get(url_all, timeout=10)
            data_all = res_all.json()
            if data_all.get("code") == 0 and "data" in data_all:
                tickers = data_all["data"].get("ticker", {})
                if market in tickers:
                    return float(tickers[market].get("last", 0.0))

            logger.error(f"Could not parse ticker for {market}")
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching live price for {market}: {e}")
            return 0.0
