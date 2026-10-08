from sqlalchemy import select

from .helpers import register_customer, register_seller


def setup_offline_customer(client, test_runtime):
    _, storage, _ = test_runtime
    from order_utils.models import InventoryProductRow

    inventory_id, headers = register_seller(client, "offline-seller")

    with storage.get_db_write() as db:
        db.add(
            InventoryProductRow(
                inventory_id=inventory_id,
                product_id="test-product",
                stock=10,
                unit_price=50
            )
        )

    response = client.post(
        "/seller/customers",
        headers=headers,
        json={"name": "Offline customer"}
    )
    assert response.status_code == 201, response.text

    return inventory_id, headers, response.json()["id"]


def get_stock(test_runtime, inventory_id):
    _, storage, _ = test_runtime
    from order_utils.models import InventoryProductRow

    with storage.get_db() as db:
        row = db.get(
            InventoryProductRow,
            (inventory_id, "test-product")
        )
        return row.stock


def create_offline_order(client, headers, customer_id, quantity=2):
    return client.post(
        f"/seller/customers/{customer_id}/orders",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": "test-product",
                    "quantity": quantity
                }
            ]
        }
    )


def test_seller_can_create_view_and_deliver_offline_order(
    client, test_runtime
):
    inventory_id, headers, customer_id = setup_offline_customer(
        client, test_runtime
    )

    response = create_offline_order(client, headers, customer_id)
    assert response.status_code == 201, response.text
    assert response.json()["rejected"] == []

    order_id = response.json()["order_id"]
    assert get_stock(test_runtime, inventory_id) == 8

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=headers
    )
    assert response.status_code == 200, response.text

    order = response.json()
    assert order["customer_id"] is None
    assert order["directory_customer_id"] == customer_id
    assert order["inventory_id"] == inventory_id
    assert order["status"] == "confirmed"
    assert order["total"] == 100
    assert order["items"][0]["quantity"] == 2
    assert order["items"][0]["unit_price"] == 50

    response = client.get("/seller/orders", headers=headers)
    assert response.status_code == 200, response.text
    assert order_id in [row["order_id"] for row in response.json()]

    response = client.post(
        f"/seller/orders/{order_id}/deliver",
        headers=headers
    )
    assert response.status_code == 200, response.text
    assert get_stock(test_runtime, inventory_id) == 8

    response = client.post(
        f"/seller/orders/{order_id}/deliver",
        headers=headers
    )
    assert response.status_code == 409
    assert get_stock(test_runtime, inventory_id) == 8

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=headers
    )
    assert response.json()["status"] == "delivered"


def test_other_seller_cannot_use_customer_or_access_offline_order(
    client, test_runtime
):
    inventory_id, headers, customer_id = setup_offline_customer(
        client, test_runtime
    )
    _, other_headers = register_seller(client, "other-seller")

    response = create_offline_order(
        client, other_headers, customer_id
    )
    assert response.status_code == 404
    assert get_stock(test_runtime, inventory_id) == 10

    response = create_offline_order(client, headers, customer_id)
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=other_headers
    )
    assert response.status_code == 403

    response = client.post(
        f"/seller/orders/{order_id}/deliver",
        headers=other_headers
    )
    assert response.status_code == 403
    assert get_stock(test_runtime, inventory_id) == 8


def test_online_customer_cannot_access_offline_order(
    client, test_runtime
):
    # Register first to exercise overlapping user/customer IDs.
    user_id, customer_headers = register_customer(
        client, "online-customer"
    )
    inventory_id, seller_headers, customer_id = setup_offline_customer(
        client, test_runtime
    )
    assert user_id == customer_id

    response = create_offline_order(
        client, customer_headers, customer_id
    )
    assert response.status_code == 403

    response = create_offline_order(
        client, seller_headers, customer_id
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]

    response = client.get(
        f"/orders/{order_id}",
        headers=customer_headers
    )
    assert response.status_code == 403

    response = client.post(
        f"/orders/{order_id}/items",
        headers=customer_headers,
        json={
            "items": [
                {"product_id": "test-product", "quantity": 1}
            ]
        }
    )
    assert response.status_code == 403

    response = client.post(
        f"/orders/{order_id}/items/test-product/reject",
        headers=customer_headers,
        json={"quantity": 1}
    )
    assert response.status_code == 403

    response = client.post(
        f"/orders/{order_id}/cancel",
        headers=customer_headers
    )
    assert response.status_code == 403
    assert get_stock(test_runtime, inventory_id) == 8

    response = client.get("/orders", headers=customer_headers)
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_rejected_offline_order_does_not_change_stock_or_create_order(
    client, test_runtime
):
    inventory_id, headers, customer_id = setup_offline_customer(
        client, test_runtime
    )

    response = create_offline_order(
        client, headers, customer_id, quantity=11
    )
    assert response.status_code == 409
    assert get_stock(test_runtime, inventory_id) == 10

    _, storage, _ = test_runtime
    from order_utils.models import OrderRow

    with storage.get_db() as db:
        assert db.scalars(select(OrderRow)).all() == []


def test_offline_order_preserves_partial_acceptance(
    client, test_runtime
):
    inventory_id, headers, customer_id = setup_offline_customer(
        client, test_runtime
    )

    response = client.post(
        f"/seller/customers/{customer_id}/orders",
        headers=headers,
        json={
            "items": [
                {"product_id": "test-product", "quantity": 2},
                {"product_id": "test-product", "quantity": 20}
            ]
        }
    )
    assert response.status_code == 201, response.text

    result = response.json()
    assert result["rejected"] == [
        {
            "product_id": "test-product",
            "qty": 20,
            "message": "Insufficient stock"
        }
    ]
    assert get_stock(test_runtime, inventory_id) == 8

    response = client.get(
        f"/seller/orders/{result['order_id']}",
        headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 100
    assert response.json()["items"][0]["quantity"] == 2


def test_offline_order_requires_auth_and_existing_customer(
    client, test_runtime
):
    inventory_id, headers, customer_id = setup_offline_customer(
        client, test_runtime
    )

    response = create_offline_order(client, {}, customer_id)
    assert response.status_code == 401

    response = create_offline_order(client, headers, 999999)
    assert response.status_code == 404
    assert get_stock(test_runtime, inventory_id) == 10