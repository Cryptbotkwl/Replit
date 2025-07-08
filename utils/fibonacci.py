from utils.logger import logger

def calculate_fibonacci_levels(high, low):
    try:
        diff = high.max() - low.min()
        levels = {
            'r1': low.min() + diff * 0.236,
            'r2': low.min() + diff * 0.382,
            'r3': low.min() + diff * 0.618,
            's1': high.max() - diff * 0.236,
            's2': high.max() - diff * 0.382,
            's3': high.max() - diff * 0.618
        }
        logger.info(f"Fibonacci levels calculated: {levels}")
        return levels
    except Exception as e:
        logger.error(f"Error calculating Fibonacci levels: {str(e)}")
        return {}