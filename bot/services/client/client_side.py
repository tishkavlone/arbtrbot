import asyncio
from bot.services.api.bybit import BybitClient, BybitAPIException
from bot.services.api.bingx import BingXClient, BingXAPIException
from bot.services.api.bitget import BitgetClient, BitgetAPIException

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

      
