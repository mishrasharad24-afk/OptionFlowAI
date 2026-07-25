import csv
import os
from datetime import datetime


class TradeLogger:

    def __init__(self,
                 filename="trade_log.csv"):

        self.filename = filename

        if not os.path.exists(filename):

            with open(filename,
                      "w",
                      newline="") as f:

                writer = csv.writer(f)

                writer.writerow([

                    "timestamp",

                    "signal",

                    "reason",

                    "bull_rate",

                    "bear_rate",

                    "confidence",

                    "matches"

                ])

    def log(self, result):

        with open(self.filename,
                  "a",
                  newline="") as f:

            writer = csv.writer(f)

            writer.writerow([

                datetime.now().isoformat(),

                result["signal"],

                result["reason"],

                result["bull_rate"],

                result["bear_rate"],

                result["confidence"],

                result["matches"]

            ])


if __name__ == "__main__":

    logger = TradeLogger()

    logger.log({

        "signal": "BUY CE",

        "reason": "BULLISH",

        "bull_rate": 82.4,

        "bear_rate": 13.5,

        "confidence": 82.4,

        "matches": 20

    })

    print("=" * 60)

    print("TRADE LOGGER")

    print("=" * 60)

    print("Log Saved")

    print("=" * 60)
