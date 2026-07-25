from tradingapi_a.mconnect import MConnect
import json

# ==========================
# USER DETAILS
# ==========================
USER_ID = "MA453644"
PASSWORD = "Mahamaya123*"
API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

m = MConnect()

try:
    # Login
    login = m.login(USER_ID, PASSWORD)

    print("==================================================")
    print("LOGIN RESPONSE")
    print("==================================================")
    print(login.text)
    print("Status Code:", login.status_code)
    print("==================================================")

    # Enter OTP / TOTP
    otp = input("Enter OTP: ").strip()

    # Generate Session
    session = m.generate_session(
        API_KEY,
        otp,
        "W"
    )

    print("==================================================")
    print("SESSION RESPONSE")
    print("==================================================")
    print(session.text)

    data = json.loads(session.text)

    if data.get("status") == "success":
        access_token = data["data"]["access_token"]

        with open("access_token.txt", "w") as f:
            f.write(access_token)

        print("\n✅ LOGIN SUCCESS")
        print("Access Token Saved Successfully")
        print("Access Token:")
        print(access_token)

    else:
        print("\n❌ LOGIN FAILED")
        print(data)

except Exception as e:
    print("\nERROR:")
    print(str(e))
  
