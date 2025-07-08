import pandas as pd
from datetime import datetime, timedelta
from utils.logger import logger
import asyncio

def validate_dataframe(df: pd.DataFrame) -> bool:
    try:
        if df.empty:
            logger.warning("DataFrame is empty")
            return False
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            logger.warning(f"Missing required columns: {set(required_columns) - set(df.columns)}")
            return False
        if len(df) < 10:
            logger.warning(f"Insufficient data: {len(df)} rows, need at least 10")
            return False
        nan_count = df[required_columns].isna().sum().sum()
        if nan_count > len(df) * 0.05:
            logger.warning(f"Too many NaN values: {nan_count}")
            return False
        logger.info(f"DataFrame validated: {len(df)} rows, NaN count: {nan_count}")
        return True
    except Exception as e:
        logger.error(f"Error validating DataFrame: {str(e)}")
        return False

def get_timestamp():
    return int(datetime.now().timestamp())

def format_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"Error formatting timestamp: {str(e)}")
        return str(timestamp)

def is_cooldown_active(symbol: str, last_signal_time: dict, cooldown: int) -> bool:
    try:
        if symbol in last_signal_time:
            last_time = last_signal_time[symbol]
            return (datetime.now() - last_time).total_seconds() < cooldown
        return False
    except Exception as e:
        logger.error(f"Error checking cooldown for {symbol}: {str(e)}")
        return False

def scan_pause(seconds: int):
    try:
        return asyncio.sleep(seconds)
    except Exception as e:
        logger.error(f"Error in scan_pause: {str(e)}")
        return asyncio.sleep(0)