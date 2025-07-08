import pandas as pd
import asyncio
from utils.logger import logger
from data.collector import fetch_realtime_data
from core.indicators import calculate_indicators

async def multi_timeframe_boost(symbol, exchange, direction, timeframes=['5m', '15m', '1h', '4h']):
    try:
        logger.info(f"[{symbol}] Starting multi-timeframe boost for {direction}")
        agreements = 0
        total_timeframes = len(timeframes)
        for tf in timeframes[1:]:  # Skip primary timeframe
            for attempt in range(3):
                try:
                    ohlcv = await fetch_realtime_data(symbol, tf, limit=50)
                    if ohlcv is None or len(ohlcv) < 30:
                        logger.warning(f"[{symbol}] Insufficient data for {tf} on attempt {attempt + 1}")
                        if attempt < 2:
                            await asyncio.sleep(2)
                            continue
                        break
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']).astype(float)
                    df = calculate_indicators(df)
                    if df['ma20'].isna().any():
                        logger.warning(f"[{symbol}] NaN in MA20 for {tf}")
                        break
                    trend = 'LONG' if df['close'].iloc[-1] > df['ma20'].iloc[-1] else 'SHORT'
                    if trend == direction:
                        agreements += 1
                    logger.debug(f"[{symbol}] Timeframe {tf}: Trend={trend}, Matches direction={direction}")
                    break
                except Exception as e:
                    logger.error(f"[{symbol}] Retry {attempt + 1}/3 for {tf}: {str(e)}")
                    if attempt < 2:
                        await asyncio.sleep(2)
                        continue
                    logger.error(f"[{symbol}] Failed to fetch data for {tf} after 3 attempts")
                    break

        boost = agreements / (total_timeframes - 1) if total_timeframes > 1 else 0.0
        logger.info(f"[{symbol}] Multi-timeframe boost: {boost:.2f} ({agreements}/{total_timeframes - 1})")
        return boost
    except Exception as e:
        logger.error(f"[{symbol}] Error in multi-timeframe analysis: {str(e)}", exc_info=True)
        return 0.0