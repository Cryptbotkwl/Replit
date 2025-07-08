import pandas as pd
from utils.logger import logger

def identify_candle_patterns(df):
    try:
        if not all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            logger.error("Missing required columns for candle pattern analysis")
            return df
        if df[['open', 'high', 'low', 'close']].isna().any().any():
            logger.warning("NaN values in candle data, filling with forward/backward fill")
            df = df.fillna(method='ffill').fillna(method='bfill')

        df['candle_pattern'] = 'None'
        for i in range(1, len(df)):
            open_price = df['open'].iloc[i]
            close_price = df['close'].iloc[i]
            high_price = df['high'].iloc[i]
            low_price = df['low'].iloc[i]
            prev_open = df['open'].iloc[i-1]
            prev_close = df['close'].iloc[i-1]

            # Bullish Engulfing
            if prev_close < prev_open and close_price > open_price and close_price > prev_open and open_price < prev_close:
                df.loc[i, 'candle_pattern'] = 'Bullish Engulfing'
            # Bearish Engulfing
            elif prev_close > prev_open and close_price < open_price and close_price < prev_open and open_price > prev_close:
                df.loc[i, 'candle_pattern'] = 'Bearish Engulfing'
            # Hammer
            elif (high_price - low_price) > 3 * abs(open_price - close_price) and (close_price - low_price) > 0.6 * (high_price - low_price):
                df.loc[i, 'candle_pattern'] = 'Hammer'
            # Shooting Star
            elif (high_price - low_price) > 3 * abs(close_price - open_price) and (high_price - close_price) > 0.6 * (high_price - low_price):
                df.loc[i, 'candle_pattern'] = 'Shooting Star'
            # Doji
            elif abs(open_price - close_price) <= (high_price - low_price) * 0.1:
                df.loc[i, 'candle_pattern'] = 'Doji'

            logger.debug(f"Candle pattern at index {i}: {df['candle_pattern'].iloc[i]}")

        logger.info("Candle patterns identified successfully")
        return df
    except Exception as e:
        logger.error(f"Error identifying candle patterns: {str(e)}")
        return df