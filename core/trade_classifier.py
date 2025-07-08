from utils.logger import logger

def classify_trade(conditions, last_price, support, resistance):
    try:
        logger.info(f"Classifying trade with conditions: {conditions}")
        score = 0
        for condition in conditions:
            if condition in ["MACD", "Bullish Engulfing", "Hammer", "Breakout Above Resistance", "Oversold RSI", "Stochastic Oversold", "Bollinger Breakout"]:
                score += 2
            elif condition in ["Bearish Engulfing", "Shooting Star", "Breakdown Below Support", "Overbought RSI", "Stochastic Overbought"]:
                score -= 2
            elif condition == "Strong Trend":
                score += 1 if last_price > support else -1
            elif condition == "Above VWAP":
                score += 1

        direction = "LONG" if score > 0 else "SHORT" if score < 0 else None
        if direction is None:
            logger.info(f"No clear direction: Score={score}")
        else:
            logger.info(f"Trade classification: Score={score}, Direction={direction}")
        return direction
    except Exception as e:
        logger.error(f"Error classifying trade: {str(e)}", exc_info=True)
        return None