from Business import Inventory,Product


inventory = Inventory(1)

test_id = "rollback-test"

if test_id in inventory:
    raise ValueError("Use a different test ID; this one already exists")

try:
    inventory.add_products([
        Product(test_id, "Temporary product", 10, 50),
        Product("invalid-test", "Invalid product", -1, 20),
    ])
except ValueError as error:
    print("Expected error:", error)

print("First product was saved:", test_id in inventory)