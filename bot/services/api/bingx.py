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
class BingXCredentials:
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
    

class BingXAPIException(Exception):
    pass

    
class BingXClient:
    def __init__(self,
                credentials: Optional[BingXCredentials] = None,
                rate_limit: float = 0.1,
                max_concurrent_requests: int = 100):
        self.credentials = credentials if credentials else None
        self.base_url = "https://open-api.bingx.com"
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
            raise BingXAPIException("API credentials required for authenticated requests")
        
        query_string = urllib.parse.urlencode(sorted(params.items()))
        
        signature = hmac.new(
            bytes(self.credentials.api_secret, 'utf-8'),
            bytes(query_string, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    
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
            
            if params is None:
                params = {}
                
            params['timestamp'] = str(int(time.time() * 1000))
            
            if self.credentials:
                signature = self._generate_signature(params)
                params['signature'] = signature
                headers['X-BX-APIKEY'] = self.credentials.api_key
                
            try:
                if method == "GET":
                    url += '?' + urllib.parse.urlencode(params)
                    params = None
                    
                async with self._session.request(method, url, headers=headers, json=params) as response:
                    text_response = await response.text()
                    
                    if response.status != 200:
                        raise BingXAPIException(f"API Error: {response.status}")
                    
                    data = json.loads(text_response)
                    return data
                
            except aiohttp.ClientError as e:
                raise BingXAPIException(f"Network error: {str(e)}")
            except Exception as e:
                raise BingXAPIException(f"Unexpected error: {str(e)}")
        
        
    async def get_trading_pairs(self) -> List[TradingPair]:
        response = await self._make_request('GET', '/openApi/spot/v1/common/symbols')
        
        trading_pairs = []
        for pair in response['data']['symbols']:
            if pair.get('status') == 1:
                trading_pairs.append(TradingPair(
                    symbol=pair['symbol']           
                ))
            
        return trading_pairs
    
    
    async def get_orderbook(self, symbol: str, limit: int = 5) -> OrderBook:
        if limit not in [5, 10, 20, 50, 100, 500, 1000]:
            raise BingXAPIException("Limit must be one of: 5, 10, 20, 50, 100, 500, 1000")
        
        params = {
            "symbol": symbol,
            "limit": str(limit)
        }
        
        response = await self._make_request("GET", "/openApi/spot/v1/market/depth", params)
        data = response["data"]
        
        bids = [
            OrderBookLevel(
                price=float(bid[0]),
                quantity=float(bid[1])
            )
            for bid in data["bids"]
        ]
        asks = [
            OrderBookLevel(
                price=float(ask[0]),
                quantity=float(ask[1])
            )
            for ask in data["asks"]
        ]
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=data["ts"]
        )
    
    
    async def get_all_orderbooks(self, trading_pairs: List[TradingPair], limit: int = 5) -> Dict[str, OrderBook]:
        async def fetch_single_orderbook(pair: TradingPair) -> Tuple[str, Optional[OrderBook]]:
            try:
                orderbook = await self.get_orderbook(pair.symbol, limit)
                return pair.symbol, orderbook
            except BingXAPIException as e:
                print(f"Error fetching orderbook for {pair.symbol}: {e}")
                return pair.symbol, None
                
        tasks = [fetch_single_orderbook(pair) for pair in trading_pairs]
        results = await asyncio.gather(*tasks)
        return {symbol: ob for symbol, ob in results if ob is not None}