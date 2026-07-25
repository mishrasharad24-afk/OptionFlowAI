class VWAPFeatures:

    @staticmethod
    def side(price, vwap):

        if price > vwap:
            return "ABOVE"

        if price < vwap:
            return "BELOW"

        return "ON"
