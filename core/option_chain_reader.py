class OptionChainReader:

    def __init__(self):

        self.step = 100

    def get_atm(self, spot):

        return round(spot / self.step) * self.step

    def get_chain(self, spot):

        atm = self.get_atm(spot)

        return {

            "spot": spot,

            "atm": atm,

            "atm_ce": f"{atm} CE",

            "atm_pe": f"{atm} PE",

            "atm_plus_1_ce": f"{atm+100} CE",

            "atm_plus_2_ce": f"{atm+200} CE",

            "atm_minus_1_ce": f"{atm-100} CE",

            "atm_minus_2_ce": f"{atm-200} CE",

            "atm_plus_1_pe": f"{atm+100} PE",

            "atm_plus_2_pe": f"{atm+200} PE",

            "atm_minus_1_pe": f"{atm-100} PE",

            "atm_minus_2_pe": f"{atm-200} PE"

        }


if __name__ == "__main__":

    reader = OptionChainReader()

    chain = reader.get_chain(77593.11)

    print("=" * 60)
    print("OPTION CHAIN READER")
    print("=" * 60)

    for k, v in chain.items():

        print(f"{k:18} : {v}")

    print("=" * 60)
