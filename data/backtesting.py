import pandas as pd
import ccxt.async_support as ccxt
from utils.logger import logger
from core.engine import generate_signal
from data.collector import fetch_realtime_data
import asyncio

async def backtest_signals(symbol, timeframe="15m", limit=1000):
    try:
        exchange = ccxt.binance({"enableRateLimit": True})
        ohlcv = await fetch_realtime_data(symbol, timeframe, limit)
        if ohlcv is None or len(ohlcv) < 100:
            logger.warning(f"[{symbol}] Insufficient data for backtesting")
            await exchange.close()
            return None

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']).astype(float)
        results = []
        for i in range(100, len(df)):
            window = df.iloc[:i]
            signal = await generate_signal(symbol, timeframe, window)
            if signal:
                actual_price = df['close'].iloc[i:i+50].to_list()
                result = simulate_trade(signal, actual_price)
                results.append(result)

        await exchange.close()
        if not results:
            logger.info(f"[{symbol}] No signals generated in backtest")
            return None

        win_rate = sum(1 for r in results if r['profit'] > 0) / len(results)
        avg_profit = sum(r['profit'] for r in results) / len(results)
        logger.info(f"[{symbol}] Backtest completed: Win rate={win_rate:.2f}, Avg profit={avg_profit:.2f}%")
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'total_trades': len(results),
            'win_rate': win_rate,
            'avg_profit': avg_profit
        }
    except Exception as e:
        logger.error(f"[{symbol}] Backtest error: {str(e)}")
        await exchange.close()
        return None

def simulate_trade(signal, prices):
    try:
        entry = signal['entry']
        sl = signal['sl']
        tp1 = signal['tp1']
        direction = signal['direction']
        result = {'profit': 0, 'status': 'pending'}

        for price in prices:
            if direction == "LONG":
                if price >= tp1:
                    result['profit'] = ((tp1 - entry) / entry) * 100
                    result['status'] = 'tp1'
                    break
                elif price <= sl:
                    result['profit'] = ((sl - entry) / entry) * 100
                    result['status'] = 'sl'
                    break
            else:
                if price <= tp1:
                    result['profit'] = ((entry - tp1) / entry) * 100
                    result['status'] = 'tp1'
                    break
                elif price >= sl:
                    result['profit'] = ((entry - sl) / entry) * 100
                    result['status'] = 'sl'
                    break
        logger.info(f"[{signal['symbol']}] Trade simulation: {result['status']}, Profit={result['profit']:.2f}%")
        return result
    except Exception as e:
        logger.error(f"Error simulating trade: {str(e)}")
        return {'profit': 0, 'status': 'error'}