import pandas as pd
import numpy as np
from utils.logger import logger
try:
    import pandas_ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False

def calculate_indicators(df):
    try:
        if len(df) < 10:
            logger.warning(f"Insufficient data for indicators: {len(df)} candles")
            return df
        if df[['open', 'high', 'low', 'close', 'volume']].isna().any().any():
            logger.warning("NaN values in input data, filling with forward/backward fill")
            df = df.fillna(method='ffill').fillna(method='bfill')

        # Moving Averages
        df['ma20'] = df['close'].rolling(window=20, min_periods=10).mean()
        # EMA and MACD
        df['ema8'] = df['close'].ewm(span=8, adjust=False, min_periods=5).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False, min_periods=10).mean()
        df['macd'] = df['ema8'] - df['ema21']
        df['signal_line'] = df['macd'].ewm(span=5, adjust=False, min_periods=3).mean()
        # RSI
        if PANDAS_TA_AVAILABLE:
            df['rsi'] = pandas_ta.rsi(df['close'], length=9)
        else:
            df['rsi'] = calculate_rsi(df['close'], 9)
        # ADX
        if PANDAS_TA_AVAILABLE:
            adx = pandas_ta.adx(df['high'], df['low'], df['close'], length=14)
            df['adx'] = adx['ADX_14']
        else:
            df['adx'] = calculate_adx(df['high'], df['low'], df['close'], 14)
        # VWAP
        df['vwap'] = calculate_vwap(df)
        # ATR
        df['atr'] = calculate_atr(df['high'], df['low'], df['close'], 14)
        # Stochastic Oscillator
        df['stoch_k'], df['stoch_d'] = calculate_stochastic(df['high'], df['low'], df['close'], 14, 3, 3)
        # Bollinger Bands
        df['bollinger_mid'] = df['close'].rolling(window=20, min_periods=10).mean()
        df['bollinger_std'] = df['close'].rolling(window=20, min_periods=10).std()
        df['bollinger_upper'] = df['bollinger_mid'] + (df['bollinger_std'] * 2)
        df['bollinger_lower'] = df['bollinger_mid'] - (df['bollinger_std'] * 2)

        logger.info(f"Indicators calculated: {list(df.columns)}")
        return df
    except Exception as e:
        logger.error(f"Error calculating indicators: {str(e)}")
        return df

def calculate_rsi(series, period=9):
    try:
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=5).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period, min_periods=5).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except Exception as e:
        logger.error(f"Error calculating RSI: {str(e)}")
        return pd.Series(np.nan, index=series.index)

def calculate_adx(high, low, close, period=14):
    try:
        tr = pd.DataFrame(index=high.index)
        tr['h_l'] = high - low
        tr['h_pc'] = abs(high - close.shift())
        tr['l_pc'] = abs(low - close.shift())
        tr['tr'] = tr[['h_l', 'h_pc', 'l_pc']].max(axis=1)
        dm_plus = high - high.shift()
        dm_minus = low.shift() - low
        dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0)
        dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0)
        atr = tr['tr'].rolling(window=period, min_periods=7).mean()
        di_plus = (dm_plus.rolling(window=period, min_periods=7).mean() / atr) * 100
        di_minus = (dm_minus.rolling(window=period, min_periods=7).mean() / atr) * 100
        dx = (abs(di_plus - di_minus) / (di_plus + di_minus)) * 100
        return dx.rolling(window=period, min_periods=7).mean()
    except Exception as e:
        logger.error(f"Error calculating ADX: {str(e)}")
        return pd.Series(np.nan, index=high.index)

def calculate_vwap(df):
    try:
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        volume_sum = df['volume'].cumsum()
        price_volume = (typical_price * df['volume']).cumsum()
        return price_volume / volume_sum
    except Exception as e:
        logger.error(f"Error calculating VWAP: {str(e)}")
        return pd.Series(np.nan, index=df.index)

def calculate_atr(high, low, close, period=14):
    try:
        tr = pd.DataFrame(index=high.index)
        tr['h_l'] = high - low
        tr['h_pc'] = abs(high - close.shift())
        tr['l_pc'] = abs(low - close.shift())
        tr['tr'] = tr[['h_l', 'h_pc', 'l_pc']].max(axis=1)
        return tr['tr'].rolling(window=period, min_periods=7).mean()
    except Exception as e:
        logger.error(f"Error calculating ATR: {str(e)}")
        return pd.Series(np.nan, index=high.index)

def calculate_stochastic(high, low, close, k_period=14, d_period=3, slowing=3):
    try:
        lowest_low = low.rolling(window=k_period, min_periods=7).min()
        highest_high = high.rolling(window=k_period, min_periods=7).max()
        stoch_k = ((close - lowest_low) / (highest_high - lowest_low)) * 100
        stoch_k = stoch_k.rolling(window=slowing, min_periods=2).mean()
        stoch_d = stoch_k.rolling(window=d_period, min_periods=2).mean()
        return stoch_k, stoch_d
    except Exception as e:
        logger.error(f"Error calculating stochastic: {str(e)}")
        return pd.Series(np.nan, index=high.index), pd.Series(np.nan, index=high.index)