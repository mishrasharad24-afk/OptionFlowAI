import csv


class DatasetLoader:

    def __init__(self, filename):

        self.filename = filename

    def load(self):

        rows = []

        with open(self.filename, "r") as file:

            reader = csv.DictReader(file)

            for row in reader:

                rows.append(row)

        return rows


if __name__ == "__main__":

    loader = DatasetLoader(
        "training_dataset_v2.csv"
    )

    data = loader.load()

    print("=" * 60)
    print("DATASET LOADER")
    print("=" * 60)

    print("Rows Loaded :", len(data))

    print()

    print("First Row")

    print(data[0])

    print()

    print("Last Row")

    print(data[-1])

    print("=" * 60)
