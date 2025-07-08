import pandas as pd
from utils.logger import logger

def identify_support_resistance(prices, window=20):
    try:
        support = prices.rolling(window=window).min().iloc[-1]
        resistance = prices.rolling(window=window).max().iloc[-1]
        logger.info(f"Support: {support}, Resistance: {resistance}")
        return support, resistance
    except Exception as e:
        logger.error(f"Error identifying support/resistance: {str(e)}")
        return None, None