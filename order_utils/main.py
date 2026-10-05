
from pprint import pprint

from Business import Inventory, orders


inventory = Inventory(1)

while True:
    print("\n1. View inventory")
    print("2. View order")
    print("0. Exit")

    choice = input("Choose: ").strip()

    if choice == "1":
        for product in inventory:
            print(
                f"{product.id}: {product.name} | "
                f"Stock: {product.stock} | "
                f"Price: {product.unit_price}"
            )

    elif choice == "2":
        try:
            customer_id = int(input("Customer ID: "))
            order_id = int(input("Order ID: "))

            order = orders(
                inventory,
                customer_id,
                order_id=order_id
            )

            pprint(order.view_order())

        except ValueError as error:
            print("Could not open order:", error)

    elif choice == "0":
        break

    else:
        print("Invalid choice")