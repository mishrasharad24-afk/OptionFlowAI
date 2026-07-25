import sqlite3

from research.feature_engine import FeatureEngine


class PatternEngine:

    def __init__(self, db_path="optionflow.db"):

        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

        self.feature = FeatureEngine()

    def load(self, symbol, timeframe):

        self.cur.execute(
            """
            SELECT
                timestamp,
                open,
                high,
                low,
                close,
                volume
            FROM historical_data
            WHERE symbol = ?
            AND timeframe = ?
            ORDER BY timestamp
            """,
            (symbol, timeframe)
        )

        return self.cur.fetchall()

    def research(self, symbol, timeframe):

        candles = self.load(symbol, timeframe)

        if len(candles) < 50:
            print("Not enough historical data")
            return False

        features = self.feature.extract(candles)

        print("=" * 50)
        print("AI Research Report")
        print("=" * 50)
        print("Symbol     :", symbol)
        print("Timeframe  :", timeframe)
        print("Candles    :", features["candles"])
        print("Direction  :", features["direction"])
        print("Open       :", features["open"])
        print("Close      :", features["close"])
        print("High       :", features["high"])
        print("Low        :", features["low"])
        print("Range      :", round(features["range"], 2))
        print("Volume     :", features["volume"])

        return features

    def close(self):

        self.conn.close()
