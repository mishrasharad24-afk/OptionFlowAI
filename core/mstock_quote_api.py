from tradingapi_a.mconnect import MConnect


class MStockQuoteAPI:

    def __init__(self):

        API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

        with open(
            "/home/ec2-user/OptionFlowAI/access_token.txt",
            "r"
        ) as f:
            ACCESS_TOKEN = f.read().strip()

        self.client = MConnect(
            api_key=API_KEY,
            access_Token=ACCESS_TOKEN
        )

    def get_ltp(self, symbols):

        try:

            response = self.client.get_ltp(symbols)

            if hasattr(response, "json"):

                return response.json()

            return response

        except Exception as e:

            return {
                "status": "error",
                "message": str(e)
            }

    def get_option_chain_master(self, exchange_id):

        try:

            response = self.client.get_option_chain_master(
                exchange_id
            )

            if hasattr(response, "json"):

                return response.json()

            return response

        except Exception as e:

            return {
                "status": "error",
                "message": str(e)
            }

    def get_option_chain_data(
        self,
        exchange_id,
        expiry,
        token
    ):

        try:

            response = self.client.get_option_chain_data(
                exchange_id,
                expiry,
                token
            )

            if hasattr(response, "json"):

                return response.json()

            return response

        except Exception as e:

            return {
                "status": "error",
                "message": str(e)
            }


if __name__ == "__main__":

    print("=" * 60)
    print("MSTOCK QUOTE API")
    print("=" * 60)

    api = MStockQuoteAPI()

    print()
    print("Module Loaded Successfully")
    print()
    print("Methods Available")
    print("-----------------")
    print("1. get_ltp()")
    print("2. get_option_chain_master()")
    print("3. get_option_chain_data()")
    print()

    print("=" * 60)
