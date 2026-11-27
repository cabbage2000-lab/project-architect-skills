import sys

from order_csv import ORDERS, write_orders


if __name__ == "__main__":
    settled = [order for order in ORDERS if order["state"] == "settled"]
    write_orders(sys.stdout, settled)
