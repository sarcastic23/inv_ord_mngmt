
from .Business import Inventory,Product,orders

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

inventory = Inventory(1)
product_id = "__reject_delivery_test__"

inventory.add_products([
    Product(product_id, "Reject delivery test", 10, 10)
])

order = orders(inventory, customer_id=903)
order.confirmed_order([(product_id, 4)])

barrier = Barrier(2)


def reject():
    barrier.wait(timeout=10)
    return order.reject_order(product_id, 4)


def deliver():
    barrier.wait(timeout=10)
    return order.deliver_order()


with ThreadPoolExecutor(max_workers=2) as executor:
    rejection = executor.submit(reject)
    delivery = executor.submit(deliver)

    rejected_qty = rejection.result()
    delivered = delivery.result()

summary = order.view_order()
stock = inventory[product_id].stock

print("Rejected quantity:", rejected_qty)
print("Delivery result:", delivered)
print("Final status:", summary["status"])
print("Final stock:", stock)

if summary["status"] == "cancelled":
    assert rejected_qty == 4
    assert delivered is False
    assert stock == 10
    assert summary["items"] == []
else:
    assert summary["status"] == "delivered"
    assert rejected_qty is False
    assert delivered is True
    assert stock == 6
    assert len(summary["items"]) == 1
    assert summary["items"][0]["quantity"] == 4

print("Rejection vs delivery test passed")