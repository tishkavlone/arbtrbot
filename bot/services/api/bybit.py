import aiohttp
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import hmac
import hashlib
import time
import urllib.parse


@dataclass
class BybitCredentials:
    api_key: str
    api_secret: str
    testnet: bool = False
    

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
    

class BybitAPIException(Exception):
    pass

    
class BybitClient:
    def __init__(self,
                credentials: Optional[BybitCredentials] = None,
                rate_limit: float = 0.0083,
                max_concurrent_requests: int = 600):
        self.credentials = credentials if credentials else None
        self.base_url = "https://api-testnet.bybit.com/v5" if credentials and credentials.testnet else "https://api.bybit.com/v5"
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
            raise BybitAPIException("API credentials required for authenticated requests")
        
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
                    "X-BAPI-API-KEY": self.credentials.api_key,
                    "X-BAPI-SIGN": signature,
                    "X-BAPI-TIMESTAMP": timestamp
                })
                
            try:
                if method == "GET" and params:
                    url += '?' + urllib.parse.urlencode(params)
                    params = None
                    
                async with self._session.request(method, url, headers=headers, json=params) as response:
                    data = await response.json()
                    
                    if response.status != 200 or data.get('retCode') != 0:
                        raise BybitAPIException(f"API Error: {data.get('retMsg', 'Unknown error')}")
                    
                    return data
            except aiohttp.ClientError as e:
                raise BybitAPIException(f"Network error: {str(e)}")
            except Exception as e:
                raise BybitAPIException(f"Unexpected error: {str(e)}")
        
        
    async def get_trading_pairs(self) -> List[TradingPair]:
        response = await self._make_request('GET', '/market/instruments-info', {'category': 'spot'})
        
        trading_pairs = []
        for pair in response['result']['list']:
            if pair['status'].lower() == "trading":
                trading_pairs.append(TradingPair(
                    symbol=pair['symbol']           
                ))
            
        return trading_pairs
    
    
    async def get_orderbook(self, symbol: str, limit: int = 1) -> OrderBook:
        if limit not in [1, 25, 50, 100, 200]:
            raise BybitAPIException("Limit must be one of: 1, 25, 50, 100, 200")
        
        params = {
            "category": "spot",
            "symbol": symbol,
            "limit": str(limit)
        }
        
        response = await self._make_request("GET", "/market/orderbook", params)
        data = response["result"]
        
        bids = [
            OrderBookLevel(
                price=float(bid[0]),
                quantity=float(bid[1])
            )
            for bid in data["b"]
        ]
        asks = [
            OrderBookLevel(
                price=float(ask[0]),
                quantity=float(ask[1])
            )
            for ask in data["a"]
        ]
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=data["ts"]
        )
    
    
    async def get_all_orderbooks(self, trading_pairs: List[TradingPair], limit: int = 1) -> Dict[str, OrderBook]:
        async def fetch_single_orderbook(pair: TradingPair) -> Tuple[str, Optional[OrderBook]]:
            try:
                orderbook = await self.get_orderbook(pair.symbol, limit)
                return pair.symbol, orderbook
            except BybitAPIException as e:
                print(f"Error fetching orderbook for {pair.symbol}: {e}")
                return pair.symbol, None
        tasks = [fetch_single_orderbook(pair) for pair in trading_pairs]
        results = await asyncio.gather(*tasks)
        return {symbol: ob for symbol, ob in results if ob is not None}