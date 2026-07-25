from mstock_quote_api import MStockQuoteAPI


class OptionPriceReader:

    def __init__(self):

        self.api = MStockQuoteAPI()

    def get_price(self, symbol):

        data = self.api.get_ltp([symbol])

        return self._parse(symbol, data)

    def get_prices(self, symbols):

        data = self.api.get_ltp(symbols)

        result = {}

        for symbol in symbols:

            result[symbol] = self._parse(symbol, data)

        return result

    def _parse(self, symbol, data):

        try:

            if isinstance(data, list):

                for row in data:

                    if row.get("symbol") == symbol:

                        return {

                            "symbol": symbol,

                            "ltp": row.get("ltp"),

                            "raw": row

                        }

            elif isinstance(data, dict):

                if symbol in data:

                    return {

                        "symbol": symbol,

                        "ltp": data[symbol].get("ltp"),

                        "raw": data[symbol]

                    }

            return {

                "symbol": symbol,

                "ltp": None,

                "raw": data

            }

        except Exception:

            return {

                "symbol": symbol,

                "ltp": None,

                "raw": data

            }


if __name__ == "__main__":

    reader = OptionPriceReader()

    print("=" * 60)

    print("OPTION PRICE READER")

    print("=" * 60)

    print()

    print("Ready")

    print()

    print("Use:")

    print('reader.get_price("NSE:ACC")')

    print()

    print("=" * 60)
