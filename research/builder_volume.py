from volume_features import VolumeFeatures


class VolumeBuilder:

    @staticmethod
    def build(volume, average_volume):

        ratio = VolumeFeatures.ratio(
            volume,
            average_volume
        )

        strength = VolumeFeatures.strength(
            ratio
        )

        return {

            "volume": volume,

            "avg_volume": average_volume,

            "volume_ratio": ratio,

            "volume_strength": strength

        }


if __name__ == "__main__":

    row = VolumeBuilder.build(

        volume=245000,

        average_volume=180000

    )

    print("=" * 50)
    print("VOLUME BUILDER")
    print("=" * 50)

    for k, v in row.items():

        print(f"{k:20} : {v}")

    print("=" * 50)
