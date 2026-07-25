from broker.login import BrokerLogin
from historical.collector import HistoricalCollector


def main():
    print("=" * 50)
    print("OptionFlowAI Starting...")
    print("=" * 50)

    otp = input("Enter m.Stock OTP: ").strip()

    broker = BrokerLogin()

    token = broker.login(otp)

    if not token:
        print("❌ Login Failed")
        return

    print("✅ Login Success")
    print("Access Token Received")

    collector = HistoricalCollector()

if __name__ == "__main__":
    main()
