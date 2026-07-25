import requests


class TelegramSignalSender:

    def __init__(self,
                 bot_token,
                 chat_id):

        self.bot_token = 7705146253:AAGpL1cyzqL6_afWFGdrXGAU5M0Ku1VCFVM
        self.chat_id = -1002519123618

    def send(self, result):

        message = f"""
🤖 OPTIONFLOW AI

📈 Signal : {result['signal']}

📌 Reason : {result['reason']}

🟢 Bull : {result['bull_rate']} %

🔴 Bear : {result['bear_rate']} %

🎯 Confidence : {result['confidence']} %

📊 Matches : {result['matches']}
"""

        url = (
            f"https://api.telegram.org/bot"
            f"{self.bot_token}/sendMessage"
        )

        payload = {

            "chat_id": self.chat_id,

            "text": message

        }

        r = requests.post(

            url,

            data=payload,

            timeout=10

        )

        return r.status_code == 200


if __name__ == "__main__":

    BOT_TOKEN = "YOUR_BOT_TOKEN"

    CHAT_ID = "YOUR_CHAT_ID"

    sender = TelegramSignalSender(

        BOT_TOKEN,

        CHAT_ID

    )

    ok = sender.send({

        "signal": "BUY CE",

        "reason": "BULLISH",

        "bull_rate": 82.4,

        "bear_rate": 13.6,

        "confidence": 82.4,

        "matches": 20

    })

    print("=" * 60)

    print("TELEGRAM SIGNAL SENDER")

    print("=" * 60)

    print("Message Sent :", ok)

    print("=" * 60)
