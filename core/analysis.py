import pandas as pd
from utils.logger import logger
from core.indicators import calculate_indicators
from core.candle_patterns import identify_candle_patterns
from utils.fibonacci import calculate_fibonacci_levels
from utils.support_resistance import identify_support_resistance

def analyze_market(symbol, df, timeframe):
    try:
        logger.info(f"[{symbol}] Starting market analysis for {timeframe}")
        df = calculate_indicators(df)
        df = identify_candle_patterns(df)
        fib_levels = calculate_fibonacci_levels(df['high'], df['low'])
        support, resistance = identify_support_resistance(df['close'], window=20)

        conditions = []
        if df['macd'].iloc[-1] > df['signal_line'].iloc[-1] and df['macd'].iloc[-2] <= df['signal_line'].iloc[-2]:
            conditions.append("MACD")
        if df['rsi'].iloc[-1] < 30:
            conditions.append("Oversold RSI")
        if df['rsi'].iloc[-1] > 70:
            conditions.append("Overbought RSI")
        if df['adx'].iloc[-1] > 25:
            conditions.append("Strong Trend")
        if df['close'].iloc[-1] > df['vwap'].iloc[-1]:
            conditions.append("Above VWAP")
        if df['close'].iloc[-1] > df['bollinger_upper'].iloc[-1]:
            conditions.append("Bollinger Breakout")
        if df['stoch_k'].iloc[-1] > 80:
            conditions.append("Stochastic Overbought")
        elif df['stoch_k'].iloc[-1] < 20:
            conditions.append("Stochastic Oversold")
        last_candle = df['candle_pattern'].iloc[-1]
        if isinstance(last_candle, str):
            if 'Bullish Engulfing' in last_candle or 'Hammer' in last_candle:
                conditions.append(last_candle)
            if 'Bearish Engulfing' in last_candle or 'Shooting Star' in last_candle:
                conditions.append(last_candle)
        if df['close'].iloc[-1] > resistance:
            conditions.append("Breakout Above Resistance")
        if df['close'].iloc[-1] < support:
            conditions.append("Breakdown Below Support")

        if not conditions:
            logger.info(f"[{symbol}] No valid conditions found for {timeframe}")
            return None

        analysis_result = {
            'symbol': symbol,
            'timeframe': timeframe,
            'conditions': conditions,
            'fib_levels': fib_levels,
            'support': support,
            'resistance': resistance,
            'last_price': df['close'].iloc[-1],
            'ma200_status': 'Above' if df['close'].iloc[-1] > df['ma20'].iloc[-1] else 'Below'
        }
        logger.info(f"[{symbol}] Analysis completed: {conditions}")
        return analysis_result
    except Exception as e:
        logger.error(f"[{symbol}] Error in market analysis: {str(e)}", exc_info=True)
        return None