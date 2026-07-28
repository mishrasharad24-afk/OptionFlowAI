from core.mstock_session import api


def get_atm_option_chain(exchange="2", token="26000", depth=2):
    print("Loading option chain...")

    try:
        result = api.get_option_chain_data(
            exchange,
            "31JUL2026",
            token,
        )

        if hasattr(result, "json"):
            result = result.json()

        print(result)
        return result

    except Exception as e:
        print("ERROR:", e)
        return None

