import csv


ORDERS = [
    {"id": "A1", "customer": "Lin, Mei", "amount": "12.50", "state": "settled"},
    {"id": "A2", "customer": "Bo", "amount": "7.00", "state": "cancelled"},
]


def write_orders(stream, orders):
    writer = csv.writer(stream)
    writer.writerow(["order_id", "customer", "amount"])
    for order in orders:
        writer.writerow([order["id"], order["customer"], order["amount"]])
