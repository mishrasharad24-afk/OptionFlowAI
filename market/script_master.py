import csv
from pathlib import Path


class ScriptMaster:

    def __init__(self):

        self.master_file = Path("/tmp/instrument_master.csv")

    def exists(self):

        return self.master_file.exists()

    def find(self, symbol):

        if not self.exists():
            raise FileNotFoundError(self.master_file)

        with open(self.master_file, "r", encoding="utf-8") as f:

            reader = csv.reader(f)

            for row in reader:

                if len(row) < 3:
                    continue

                if row[2].strip().upper() == symbol.upper():

                    return {
                        "token": row[0],
                        "exchange": row[1],
                        "symbol": row[2],
                        "raw": row
                    }

        return None
