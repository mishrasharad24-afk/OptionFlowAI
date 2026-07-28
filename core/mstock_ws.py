from pathlib import Path

from tradingapi_a import __config__
from tradingapi_a.mticker import MTicker

API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "access_token.txt"

TOKEN = 65682


class MStockWebSocket:

    def __init__(self):
        self.ws = None

    def connect(self):

        if not TOKEN_FILE.exists():
            raise FileNotFoundError(f"Access token not found: {TOKEN_FILE}")

        access_token = TOKEN_FILE.read_text().strip()

        self.ws = MTicker(
            API_KEY,
            access_token,
            __config__.mticker_url
        )

        self.ws.on_connect = self.on_connect
        self.ws.on_ticks = self.on_ticks
        self.ws.on_close = self.on_close
        self.ws.on_error = self.on_error

        print("Connecting to m.Stock WebSocket...")

        self.ws.connect()

    def on_connect(self, ws, response):

        print("✅ WebSocket Connected")

        ws.send_login_after_connect()

        print(f"Subscribing Token : {TOKEN}")

        ws.subscribe([TOKEN])

        ws.set_mode(MTicker.MODE_FULL, [TOKEN])

    def on_ticks(self, ws, ticks):

        print("=" * 80)

        for tick in ticks:

            print(tick)

        print("=" * 80)

    def on_close(self, ws, code, reason):

        print(f"WebSocket Closed : {code} {reason}")

    def on_error(self, ws, code, reason):

        print(f"WebSocket Error : {code} {reason}")


if __name__ == "__main__":
    MStockWebSocket().connect()

