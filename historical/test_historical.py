from broker.login import BrokerLogin
from broker.session import session
from historical.collector import HistoricalCollector


def main():

    print("=" * 60)
    print("Historical API Test")
    print("=" * 60)

    otp = input("Enter m.Stock OTP: ").strip()

    broker = BrokerLogin()
    token = broker.login(otp)

    if not token:
        print("Login Failed")
        return

    session.set_token(token)

    collector = HistoricalCollector()

    collector.collect(
        exchange="BSE",
        token="51",
        symbol="SENSEX",
        timeframe="5minute",
        from_date="2024-08-02 09:15:00",
        to_date="2024-08-02 15:30:00"
    )


if __name__ == "__main__":
    main()
