import logging

from historical.curve_option_backtest import (
    MConnect,
    API_KEY,
    TOKEN_FILE,
    parse,
)

log = logging.getLogger(__name__)


class OptionQuote:

    def __init__(self):

        self.api = MConnect(API_KEY)

        if not self.api.load_access_token(TOKEN_FILE):
            raise RuntimeError("Unable to load access token")

    def _empty(self, token):

        return {
            "token": token,
            "ltp": 0.0,
            "volume": 0,
            "oi": 0,
            "oi_change": 0,
            "bid": 0.0,
            "ask": 0.0,
            "iv": 0.0,
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
        }
    def get_quote(self, token):

        quote = self._empty(token)

        try:

            data = self.api.get_quotes([str(token)])

            if not data:
                return quote

            item = data[0] if isinstance(data, list) else data

            quote["ltp"] = parse(item.get("ltp", 0))
            quote["volume"] = parse(item.get("volume", 0))
            quote["oi"] = parse(item.get("oi", 0))
            quote["oi_change"] = parse(item.get("oi_change", 0))

            quote["bid"] = parse(item.get("best_bid_price", 0))
            quote["ask"] = parse(item.get("best_ask_price", 0))

            quote["iv"] = parse(item.get("iv", 0))
            quote["delta"] = parse(item.get("delta", 0))
            quote["gamma"] = parse(item.get("gamma", 0))
            quote["theta"] = parse(item.get("theta", 0))
            quote["vega"] = parse(item.get("vega", 0))

            return quote

        except Exception as e:

            log.exception(
                "Option quote failed for token %s",
                token,
            )

            return quote
def get_option_quote(token):

    return OptionQuote().get_quote(token)


if __name__ == "__main__":

    import json

    TEST_TOKEN = "65682"   # ATM option token, change if needed

    quote = get_option_quote(TEST_TOKEN)

    print("=" * 60)
    print("OPTION QUOTE")
    print("=" * 60)

    print(
        json.dumps(
            quote,
            indent=4
        )
    )

