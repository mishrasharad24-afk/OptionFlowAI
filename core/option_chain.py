from rest_client import RestClient

client = RestClient()

try:
    # Option Chain Master Test
    response = client.get("getoptionchainmaster/2")

    print("Status Code:", response.status_code)
    print(response.text)

except Exception as e:
    print("ERROR:", e)
