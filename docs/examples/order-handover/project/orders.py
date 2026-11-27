import sys

from order_csv import ORDERS, write_orders


if __name__ == "__main__":
    write_orders(sys.stdout, ORDERS)
