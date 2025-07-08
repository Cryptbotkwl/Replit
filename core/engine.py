from utils.logger import logger
from core.analysis import analyze_market
from core.trade_classifier import classify_trade
from data.collector import fetch_realtime_data
from utils.fibonacci import calculate_fibonacci_levels
import pandas as pd

async def generate_signal(symbol, timeframe, df):
    try:
        logger.info(f"[{symbol}] Starting signal generation for {timeframe}")
        analysis = analyze_market(symbol, df, timeframe)
        if not analysis or not analysis['conditions']:
            logger.info(f"[{symbol}] No valid conditions for signal")
            return None

        fib_levels = analysis['fib_levels']
        last_price = analysis['last_price']
        conditions = analysis['conditions']
        direction = classify_trade(conditions, last_price, analysis['support'], analysis['resistance'])

        if not direction:
            logger.info(f"[{symbol}] No clear trade direction")
            return None

        current_price = last_price
        atr = df['atr'].iloc[-1]
        confidence = min(95.0, 75.0 + len(conditions) * 3.0)  # Higher confidence for scalping

        # Scalping TP/SL
        if direction == "LONG":
            entry = current_price
            tp1 = entry + (0.5 * atr)  # Minimum 1% profit
            tp2 = entry + (1 * atr)
            tp3 = entry + (1.5 * atr)
            sl = entry - (0.5 * atr)
            tp1_percent = ((tp1 - entry) / entry) * 100
            tp2_percent = ((tp2 - entry) / entry) * 100
            tp3_percent = ((tp3 - entry) / entry) * 100
            sl_percent = ((entry - sl) / entry) * 100
        else:  # SHORT
            entry = current_price
            tp1 = entry - (0.5 * atr)
            tp2 = entry - (1 * atr)
            tp3 = entry - (1.5 * atr)
            sl = entry + (0.5 * atr)
            tp1_percent = ((entry - tp1) / entry) * 100
            tp2_percent = ((entry - tp2) / entry) * 100
            tp3_percent = ((entry - tp3) / entry) * 100
            sl_percent = ((sl - entry) / entry) * 100

        # Dynamic possibilities based on ATR and conditions
        base_confidence = confidence / 100
        atr_factor = min(1.0, atr / (entry * 0.01))  # Adjust based on volatility
        tp1_possibility = min(base_confidence * 0.95 * atr_factor, 95.0)
        tp2_possibility = min(base_confidence * 0.85 * atr_factor, tp1_possibility * 0.9)
        tp3_possibility = min(base_confidence * 0.75 * atr_factor, tp2_possibility * 0.9)
        sl_possibility = min(base_confidence * 0.5 * atr_factor, tp3_possibility * 0.8)

        signal = {
            'symbol': symbol,
            'timeframe': timeframe,
            'direction': direction,
            'entry': round(entry, 4),
            'sl': round(sl, 4),
            'tp1': round(tp1, 4),
            'tp2': round(tp2, 4),
            'tp3': round(tp3, 4),
            'tp1_possibility': round(tp1_possibility, 2),
            'tp2_possibility': round(tp2_possibility, 2),
            'tp3_possibility': round(tp3_possibility, 2),
            'sl_possibility': round(sl_possibility, 2),
            'tp1_percent': round(tp1_percent, 2),
            'tp2_percent': round(tp2_percent, 2),
            'tp3_percent': round(tp3_percent, 2),
            'sl_percent': round(sl_percent, 2),
            'confidence': round(confidence, 2),
            'conditions': conditions,
            'trade_type': 'Scalp',
            'trade_duration': '30m',
            'timestamp': pd.Timestamp.now().isoformat(),
            'volume': df['volume'].iloc[-1],
            'ma200_status': analysis['ma200_status'],
            'btc_trend': 0.0
        }
        logger.info(
            f"[{symbol}] Signal generated: {direction}, Confidence: {confidence}%, "
            f"TP1: {tp1_possibility}% ({tp1_percent}%), TP2: {tp2_possibility}% ({tp2_percent}%), "
            f"TP3: {tp3_possibility}% ({tp3_percent}%), SL: {sl_possibility}% ({sl_percent}%)"
        )
        return signal
    except Exception as e:
        logger.error(f"[{symbol}] Error generating signal: {str(e)}", exc_info=True)
        return None