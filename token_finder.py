import csv

MASTER_FILE = "/tmp/instrument_master.csv"


def find_symbol(exchange, symbol):
    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)

        for row in reader:
            if len(row) < 4:
                continue

            # row[1] = exchange id
            # row[2] = trading symbol

            if row[2].strip().upper() == symbol.upper():
                print("-" * 70)
                print("Found Symbol")
                print("-" * 70)

                print("Exchange ID :", row[1])
                print("Token       :", row[0])
                print("Symbol      :", row[2])

                print("\nComplete Row:\n")
                print(row)
                return

    print("Symbol not found")


print("Searching NIFTY...")
find_symbol("NSE", "NIFTY")

print()

print("Searching SENSEX...")
find_symbol("BSE", "SENSEX")
