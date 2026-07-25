import csv
import io


class HistoricalParser:

    def parse_csv(self, csv_text):

        if not csv_text:
            return []

        rows = []

        reader = csv.DictReader(io.StringIO(csv_text))

        for row in reader:

            rows.append({
                "timestamp": row.get("timestamp"),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(float(row.get("volume", 0)))
            })

        return rows

    def count(self, candles):

        return len(candles)

    def first(self, candles):

        if not candles:
            return None

        return candles[0]

    def last(self, candles):

        if not candles:
            return None

        return candles[-1]
