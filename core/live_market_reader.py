import sqlite3


class LiveMarketReader:

    def __init__(self,
                 db_path="optionflow.db"):

        self.conn = sqlite3.connect(db_path)

        self.conn.row_factory = sqlite3.Row

    def latest_candles(self,
                       symbol="SENSEX",
                       timeframe="5minute",
                       limit=100):

        cur = self.conn.cursor()

        cur.execute("""

        SELECT *

        FROM historical_data

        WHERE symbol=?

        AND timeframe=?

        ORDER BY timestamp DESC

        LIMIT ?

        """,

        (

            symbol,

            timeframe,

            limit

        ))

        rows = cur.fetchall()

        rows = [

            dict(x)

            for x in rows

        ]

        rows.reverse()

        return rows

    def latest_candle(self,
                      symbol="SENSEX",
                      timeframe="5minute"):

        data = self.latest_candles(

            symbol,

            timeframe,

            1

        )

        if data:

            return data[0]

        return None

    def close(self):

        self.conn.close()


if __name__ == "__main__":

    reader = LiveMarketReader()

    candles = reader.latest_candles(

        limit=5

    )

    print("=" * 60)

    print("LIVE MARKET READER")

    print("=" * 60)

    print("Candles :", len(candles))

    print()

    for row in candles:

        print(

            row["timestamp"],

            row["close"]

        )

    print("=" * 60)

    reader.close()
