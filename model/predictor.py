import pandas as pd
import numpy as np
from utils.logger import logger
from data.tracker import track_trade
import asyncio
import os

class SignalPredictor:
    async def predict_signal(self, symbol, df, timeframe):
        try:
            logger.info(f"[{symbol}] Starting signal prediction for {timeframe}")
            conditions = []
            if df['macd'].iloc[-1] > df['signal_line'].iloc[-1]:
                conditions.append('MACD')
                logger.debug(f"[{symbol}] MACD condition met: {df['macd'].iloc[-1]} > {df['signal_line'].iloc[-1]}")
            if df['rsi'].iloc[-1] < 30 or df['rsi'].iloc[-1] > 70:
                conditions.append('RSI')
                logger.debug(f"[{symbol}] RSI condition met: {df['rsi'].iloc[-1]}")
            if df['adx'].iloc[-1] > 25:
                conditions.append('Strong Trend')
                logger.debug(f"[{symbol}] ADX condition met: {df['adx'].iloc[-1]}")
            if df['close'].iloc[-1] > df['vwap'].iloc[-1]:
                conditions.append('VWAP')
                logger.debug(f"[{symbol}] VWAP condition met: {df['close'].iloc[-1]} > {df['vwap'].iloc[-1]}")
            if df['close'].iloc[-1] > df['bollinger_upper'].iloc[-1] or df['close'].iloc[-1] < df['bollinger_lower'].iloc[-1]:
                conditions.append('Bollinger Breakout')
                logger.debug(f"[{symbol}] Bollinger Breakout condition met")
            if 'stoch_k' in df.columns and 'stoch_d' in df.columns:
                if df['stoch_k'].iloc[-1] > df['stoch_d'].iloc[-1]:
                    conditions.append('Stochastic')
                    logger.debug(f"[{symbol}] Stochastic condition met: {df['stoch_k'].iloc[-1]} > {df['stoch_d'].iloc[-1]}")
            else:
                logger.info(f"[{symbol}] Stochastic not available, proceeding without it")

            if len(conditions) < 1:  # Relaxed condition
                logger.info(f"[{symbol}] Insufficient conditions: {conditions}")
                return None

            direction = 'LONG' if df['close'].iloc[-1] > df['ma20'].iloc[-1] else 'SHORT'
            confidence = 50.0 + len(conditions) * 10  # Simplified confidence
            logger.info(f"[{symbol}] Signal conditions: {conditions}, Confidence: {confidence:.2f}")

            signal = {
                'symbol': symbol,
                'direction': direction,
                'entry': df['close'].iloc[-1],
                'confidence': confidence,
                'conditions': ', '.join(conditions),
                'timeframe': timeframe,
                'trade_type': 'Scalping',
                'volume': df['volume'].iloc[-1],
                'quote_volume_24h': 0,
                'leverage': '10x',  # Default, updated in main.py
                'btc_trend': 0.0,
                'timestamp': pd.Timestamp.now().isoformat(),
                'tp1': df['close'].iloc[-1],  # Placeholder, updated in main.py
                'tp2': df['close'].iloc[-1],
                'tp3': df['close'].iloc[-1],
                'sl': df['close'].iloc[-1]
            }

            asyncio.create_task(track_trade(symbol, signal))
            self._log_signal(signal)
            logger.info(f"[{symbol}] Signal predicted: {signal['direction']}, Confidence: {signal['confidence']}%")
            return signal
        except Exception as e:
            logger.error(f"[{symbol}] Error predicting signal: {str(e)}", exc_info=True)
            return None

    def _log_signal(self, signal):
        try:
            df = pd.DataFrame([signal])
            csv_path = 'logs/signals_log_new.csv'
            if not os.path.exists(csv_path):
                df.to_csv(csv_path, index=False)
            else:
                df.to_csv(csv_path, mode='a', header=False, index=False)
            logger.info(f"[{signal['symbol']}] Signal logged to CSV")
        except Exception as e:
            logger.error(f"[{signal['symbol']}] Error logging signal: {str(e)}")