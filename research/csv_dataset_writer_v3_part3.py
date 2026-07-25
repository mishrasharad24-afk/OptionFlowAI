import csv

from csv_dataset_writer_v3_part2 import DatasetGenerator


class DatasetWriterV3:

    def build(self,
              filename="training_dataset_v3.csv"):

        app = DatasetGenerator()

        rows = app.build()

        if not rows:

            print("No Rows")
            return

        headers = list(rows[0].keys())

        with open(filename,
                  "w",
                  newline="") as f:

            writer = csv.DictWriter(
                f,
                fieldnames=headers
            )

            writer.writeheader()

            writer.writerows(rows)

        app.close()

        print("=" * 60)
        print("AI DATASET V3 CREATED")
        print("=" * 60)
        print("Rows :", len(rows))
        print("Columns :", len(headers))
        print("File :", filename)
        print("=" * 60)


if __name__ == "__main__":

    DatasetWriterV3().build()
