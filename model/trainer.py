import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from utils.logger import logger
from core.indicators import calculate_indicators

class SignalTrainer:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)

    def prepare_data(self, df):
        try:
            df = calculate_indicators(df)
            df['target'] = np.where(df['close'].shift(-1) > df['close'], 1, 0)
            features = ['ma20', 'ma50', 'ma200', 'rsi', 'macd', 'signal_line', 'adx', 'vwap', 'stochastic', 'atr']
            X = df[features].dropna()
            y = df['target'].loc[X.index]
            return X, y
        except Exception as e:
            logger.error(f"Error preparing data: {str(e)}")
            return None, None

    def train(self, df):
        try:
            X, y = self.prepare_data(df)
            if X is None or y is None:
                return False
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            self.model.fit(X_train, y_train)
            score = self.model.score(X_test, y_test)
            logger.info(f"Model trained with accuracy: {score:.2f}")
            return True
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return False

    def predict(self, df):
        try:
            X, _ = self.prepare_data(df)
            if X is None:
                return None
            predictions = self.model.predict(X)
            logger.info(f"Predictions made for {len(predictions)} samples")
            return predictions
        except Exception as e:
            logger.error(f"Error predicting: {str(e)}")
            return None