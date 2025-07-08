import ccxt.async_support as ccxt
from utils.logger import logger
from utils.helpers import validate_dataframe
import pandas as pd
import asyncio

async def fetch_realtime_data(symbol, timeframe, limit=1000):
    try:
        exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
        for attempt in range(3):
            try:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                if not ohlcv:
                    logger.warning(f"[{symbol}] No OHLCV data for {timeframe}")
                    await exchange.close()
                    return None
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']).astype(float)
                logger.info(f"[{symbol}] Fetched {len(df)} candles for {timeframe}, columns: {list(df.columns)}")
                if not validate_dataframe(df):
                    logger.warning(f"[{symbol}] Invalid OHLCV data for {timeframe}")
                    await exchange.close()
                    return None
                await exchange.close()
                return df
            except Exception as e:
                logger.error(f"[{symbol}] Retry {attempt+1}/3 for {timeframe}: {str(e)}")
                await asyncio.sleep(2)
        logger.error(f"[{symbol}] Failed to fetch OHLCV for {timeframe} after 3 retries")
        await exchange.close()
        return None
    except Exception as e:
        logger.error(f"[{symbol}] Error fetching OHLCV data: {str(e)}")
        await exchange.close()
        return None