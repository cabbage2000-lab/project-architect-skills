import csv
import sys

from order_csv import ORDERS


if __name__ == "__main__":
    writer = csv.writer(sys.stdout)
    writer.writerow(["order_id", "customer", "amount"])
    for order in ORDERS:
        writer.writerow([order["id"], order["customer"], order["amount"]])
