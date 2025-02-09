import asyncio
from bot.services.api.bybit import BybitClient, BybitAPIException

async def get_bybit():
    async with BybitClient() as client:
        try:
            trading_pairs = await client.get_trading_pairs()
            order_books = await client.get_all_orderbooks(trading_pairs)
            return order_books
        except BybitAPIException as e:
            print(f"Error: {e}")
       
      
