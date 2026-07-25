import sqlite3


class HistoricalReader:

    def __init__(self, db_path="optionflow.db"):

        self.conn = sqlite3.connect(db_path)

        self.conn.row_factory = sqlite3.Row

    def load(self, symbol=None, timeframe=None):

        cur = self.conn.cursor()

        sql = """
        SELECT
            timestamp,
            symbol,
            timeframe,
            open,
            high,
            low,
            close,
            volume
        FROM historical_data
        """

        where = []
        values = []

        if symbol:

            where.append("symbol=?")
            values.append(symbol)

        if timeframe:

            where.append("timeframe=?")
            values.append(timeframe)

        if where:

            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY timestamp"

        cur.execute(sql, values)

        rows = []

        for r in cur.fetchall():

            rows.append(dict(r))

        return rows

    def close(self):

        self.conn.close()


if __name__ == "__main__":

    reader = HistoricalReader()

    data = reader.load()

    print("=" * 60)
    print("HISTORICAL READER")
    print("=" * 60)
    print("Rows :", len(data))

    if data:

        print()
        print("First Row")
        print(data[0])

        print()
        print("Last Row")
        print(data[-1])

    reader.close()
