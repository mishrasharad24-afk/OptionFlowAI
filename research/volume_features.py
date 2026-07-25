class VolumeFeatures:

    @staticmethod
    def ratio(volume, average):

        if average <= 0:
            return 0.0

        return round(volume / average, 2)

    @staticmethod
    def strength(ratio):

        if ratio >= 2:
            return "HIGH"

        if ratio >= 1.2:
            return "NORMAL"

        return "LOW"
