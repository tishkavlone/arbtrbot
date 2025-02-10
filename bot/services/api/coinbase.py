import aiohttp
import asyncio
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import hmac
import hashlib
import time
import urllib.parse


@dataclass
class CoinBaseCredentials:
    api_key: str
    api_secret: str
    api_passphrase: str
    

@dataclass
class TradingPair:
    symbol: str
    

@dataclass
class OrderBookLevel:
    price: float
    quantity: float
    
    
@dataclass
class OrderBook:
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: int
    

class CoinBaseAPIException(Exception):
    pass

    
class CoinBaseClient:
    def __init__(self,
                credentials: Optional[CoinBaseCredentials] = None,
                rate_limit: float = 0.1,
                max_concurrent_requests: int = 10):
        self.credentials = credentials if credentials else None
        self.base_url = "https://api.exchange.coinbase.com"
        self._session: Optional[aiohttp.ClientSession] = None
        self.rate_limit = rate_limit
        self._request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._request_lock = asyncio.Lock()
        self._last_request_time = 0.0
        
    
    async def __aenter__(self):
        await self.create_session()
        return self
    
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
        
        
    async def create_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
            
            
    async def close_session(self):
        if self._session:
            await self._session.close()
            self._session = None
            
            
    def _generate_signature(self, params: Dict[str, str]) -> str:
        if not self.credentials:
            raise CoinBaseAPIException("API credentials required for authenticated requests")
        
        timestamp = str(int(time.time() * 1000))
        param_str = timestamp
        
        if params:
            sorted_params = sorted(params.items(), key=lambda x: x[0])
            param_str += "".join([f"{key}{value}" for key, value in sorted_params])
            
        signature = hmac.new(
            bytes(self.credentials.api_secret, 'utf-8'),
            bytes(param_str, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp 
    
    
    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        async with self._request_semaphore:
            async with self._request_lock:
                current_time = time.time()
                time_since_last_request = current_time - self._last_request_time
                if time_since_last_request < self.rate_limit:
                    await asyncio.sleep(self.rate_limit - time_since_last_request)
                self._last_request_time = time.time()
                
            if not self._session:
                await self.create_session()
                
            url = f"{self.base_url}{endpoint}"
            headers = {}
            
            if self.credentials:
                signature, timestamp = self._generate_signature(params or {})
                headers.update({
                    "CB-ACCESS-KEY": self.credentials.api_key,
                    "CB-ACCESS-SIGN": signature,
                    "X-BM-TIMESTAMP": timestamp,
                    "CB-ACCESS-PASSPHRASE": self.credentials.api_passphrase
                })
                
            try:
                if method == "GET" and params:
                    url += '?' + urllib.parse.urlencode(params)
                    params = None
                    
                async with self._session.request(method, url, headers=headers, json=params) as response:
                    text_response = await response.text()
                    
                    if response.status != 200 :
                        raise CoinBaseAPIException(f"API Error: {response.status}")
                    
                    data = json.loads(text_response)
                    return data
            except aiohttp.ClientError as e:
                raise CoinBaseAPIException(f"Network error: {str(e)}")
            except Exception as e:
                raise CoinBaseAPIException(f"Unexpected error: {str(e)}")
        
        
    async def get_trading_pairs(self) -> List[TradingPair]:
        response = await self._make_request('GET', '/products')
        
        trading_pairs = []
        for pair in response:
            if pair["status"].lower() == 'online':
                trading_pairs.append(TradingPair(
                    symbol=pair["id"]
                ))
            
        return trading_pairs
    
    
    async def get_orderbook(self, symbol: str, limit: int = 5) -> OrderBook:
        if limit <= 0 or limit > 50 :
            raise CoinBaseAPIException("Limit must be > 0 and <= 50")
        level = 2
        params = {
            "level": level
        }
        
        response = await self._make_request("GET", f"/products/{symbol}/book", params)
        
        bids = [
            OrderBookLevel(
                price=float(bid[0]),
                quantity=float(bid[1])
            )
            for bid in response["bids"][:limit]
        ]
        asks = [
            OrderBookLevel(
                price=float(ask[0]),
                quantity=float(ask[1])
            )
            for ask in response["asks"][:limit]
        ]
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=int(time.time() * 1000)
        )
    
    
    async def get_all_orderbooks(self, trading_pairs: List[TradingPair], limit: int = 5) -> Dict[str, OrderBook]:
        async def fetch_single_orderbook(pair: TradingPair) -> Tuple[str, Optional[OrderBook]]:
            try:
                orderbook = await self.get_orderbook(pair.symbol, limit)
                return pair.symbol, orderbook
            except CoinBaseAPIException as e:
                print(f"Error fetching orderbook for {pair.symbol}: {e}")
                return pair.symbol, None
        tasks = [fetch_single_orderbook(pair) for pair in trading_pairs]
        results = await asyncio.gather(*tasks)
        return {symbol: ob for symbol, ob in results if ob is not None}