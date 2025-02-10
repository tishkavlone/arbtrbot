import asyncio
from bot.services.api.bybit import BybitClient, BybitAPIException
from bot.services.api.bingx import BingXClient, BingXAPIException
from bot.services.api.bitget import BitgetClient, BitgetAPIException
from bot.services.api.bitmart import BitMartClient, BitMartAPIException
from bot.services.api.coinbase import CoinBaseClient, CoinBaseAPIException
from bot.services.api.gate import GateClient, GateAPIException

async def get_bybit():
    async with BybitClient() as client:
        try:
            trading_pairs = await client.get_trading_pairs()
            order_books = await client.get_all_orderbooks(trading_pairs)
            return order_books
        except BybitAPIException as e:
            print(f"Error: {e}")
       
       
async def get_bingx():
    async with BingXClient() as client:
        try:
            trading_pairs = await client.get_trading_pairs()
            order_books = await client.get_all_orderbooks(trading_pairs)
            return order_books
    # TODO: Время выполнения (+-100сек, ограничено api)
        except BingXAPIException as e:
            print(f"Erorr: {e}")
            
            
async def get_bitget():
    async with BitgetClient() as client:
        try:
            trading_pairs = await client.get_trading_pairs()
            order_books = await client.get_all_orderbooks(trading_pairs)
            return order_books
        except BitgetAPIException as e:
            print(f"Erorr: {e}")
            
            
async def get_bitmart():
    async with BitMartClient() as client:
        try:
            trading_pairs = await client.get_trading_pairs()
            order_books = await client.get_all_orderbooks(trading_pairs)
            print(order_books)
        except BitMartAPIException as e:
            print(f"Erorr: {e}")
            
            
async def get_coinbase():
    async with CoinBaseClient() as client:
        try:
            trading_pairs = await client.get_trading_pairs()
            order_books = await client.get_all_orderbooks(trading_pairs)
            print(order_books)
        except BitMartAPIException as e:
            print(f"Erorr: {e}")
            
    
async def get_gate():
    async with GateClient() as client:
        try:
            trading_pairs = await client.get_trading_pairs()
            order_books = await client.get_all_orderbooks(trading_pairs)
            print(order_books)
        except GateAPIException as e:
            print(f"Erorr: {e.with_traceback()}")
            
            
asyncio.run(get_gate())

      
