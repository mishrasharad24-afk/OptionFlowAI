import sqlite3


class OptionFlowDB:

    def __init__(self, db_path="optionflow.db"):

        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

    def create_tables(self):

        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS historical_data (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT NOT NULL,

                timeframe TEXT NOT NULL,

                timestamp TEXT NOT NULL,

                open REAL,

                high REAL,

                low REAL,

                close REAL,

                volume INTEGER,

                UNIQUE(symbol, timeframe, timestamp)

            )
            """
        )

        self.conn.commit()

    def insert_candle(self, symbol, timeframe, candle):

        self.cur.execute(
            """
            INSERT OR IGNORE INTO historical_data
            (
                symbol,
                timeframe,
                timestamp,
                open,
                high,
                low,
                close,
                volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                timeframe,
                candle[0],
                candle[1],
                candle[2],
                candle[3],
                candle[4],
                candle[5]
            )
        )

        self.conn.commit()

    def close(self):

        self.conn.close()
