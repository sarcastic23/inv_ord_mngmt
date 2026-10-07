def register_and_login(client, username):
    credentials = {
        "username": username,
        "password": "test-password-123"
    }

    response = client.post("/auth/register", json=credentials)
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]

    response = client.post("/auth/login", json=credentials)
    assert response.status_code == 200, response.text

    headers = {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }

    return user_id, headers


def create_order(client, headers):
    response = client.post(
        "/orders",
        headers=headers,
        json={
            "inventory_id": 1,
            "items": [
                {"product_id": "test-product", "quantity": 4}
            ]
        }
    )

    assert response.status_code == 201, response.text
    assert response.json()["rejected"] == []

    return response.json()["order_id"]


def current_stock(client):
    response = client.get("/inventories/1/products")
    assert response.status_code == 200, response.text

    return next(
        product["stock"]
        for product in response.json()
        if product["id"] == "test-product"
    )




def test_order_requires_valid_token(client):
    body = {
        "inventory_id": 1,
        "items": [
            {"product_id": "test-product", "quantity": 1}
        ]
    }

    response = client.post("/orders", json=body)
    assert response.status_code == 401

    response = client.post(
        "/orders",
        json=body,
        headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401

    assert current_stock(client) == 10


def test_other_user_cannot_access_order(client):
    alice_id, alice_headers = register_and_login(client, "alice")
    _, bob_headers = register_and_login(client, "bob")
    order_id = create_order(client, alice_headers)

    responses = [
        client.get(
            f"/orders/{order_id}",
            headers=bob_headers
        ),
        client.post(
            f"/orders/{order_id}/items",
            headers=bob_headers,
            json={
                "items": [
                    {"product_id": "test-product", "quantity": 1}
                ]
            }
        ),
        client.post(
            f"/orders/{order_id}/items/test-product/reject",
            headers=bob_headers,
            json={"quantity": 1}
        ),
        client.post(
            f"/orders/{order_id}/cancel",
            headers=bob_headers
        )
    ]

    for response in responses:
        assert response.status_code == 403, response.text

    response = client.get(
        f"/orders/{order_id}",
        headers=alice_headers
    )
    assert response.status_code == 200, response.text

    order = response.json()
    assert order["customer_id"] == alice_id
    assert order["status"] == "confirmed"
    assert order["items"][0]["quantity"] == 4
    assert current_stock(client) == 6


def test_cancellation_restores_stock_only_once(client):
    _, headers = register_and_login(client, "alice")
    order_id = create_order(client, headers)

    assert current_stock(client) == 6

    response = client.post(
        f"/orders/{order_id}/cancel",
        headers=headers
    )
    assert response.status_code == 200, response.text
    assert current_stock(client) == 10

    response = client.post(
        f"/orders/{order_id}/cancel",
        headers=headers
    )
    assert response.status_code == 409
    assert current_stock(client) == 10

    response = client.get(
        f"/orders/{order_id}",
        headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert response.json()["items"][0]["quantity"] == 4


def test_inventory_list_is_public(client):
    response = client.get("/inventories")

    assert response.status_code == 200, response.text
    assert response.json() == [
        {"id": 1, "name": "Test inventory"}
    ]


def test_login_rejects_wrong_password(client):
    register_and_login(client, "alice")

    response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "wrong-password"}
    )

    assert response.status_code == 401, response.text

def test_inventory_product_is_public(client):
    response = client.get("/inventories/1/products/test-product")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": "test-product",
        "name": "Test product",
        "stock": 10,
        "unit_price": 50
    }


def test_missing_inventory_product_returns_404(client):
    response = client.get("/inventories/1/products/missing")

    assert response.status_code == 404




def test_add_items_and_partially_reject(client):
    _, headers = register_and_login(client, "alice")
    order_id = create_order(client, headers)

    # Initial order: 4 units at 50 each.
    assert current_stock(client) == 6

    response = client.post(
        f"/orders/{order_id}/items",
        headers=headers,
        json={
            "items": [
                {"product_id": "test-product", "quantity": 2}
            ]
        }
    )

    assert response.status_code == 200, response.text
    assert response.json()["order_id"] == order_id
    assert response.json()["rejected"] == []
    assert current_stock(client) == 4

    response = client.get(f"/orders/{order_id}", headers=headers)
    assert response.status_code == 200, response.text

    order = response.json()
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity"] == 6
    assert order["total"] == 300
    assert order["status"] == "confirmed"

    response = client.post(
        f"/orders/{order_id}/items/test-product/reject",
        headers=headers,
        json={"quantity": 1}
    )

    assert response.status_code == 200, response.text
    assert response.json()["removed_quantity"] == 1
    assert current_stock(client) == 5

    response = client.get(f"/orders/{order_id}", headers=headers)
    assert response.status_code == 200, response.text

    order = response.json()
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity"] == 5
    assert order["total"] == 250
    assert order["status"] == "confirmed"

def test_seller_registration_and_login(client):
    credentials = {
        "username": "seller1",
        "password": "test-password-123"
    }

    response = client.post(
        "/seller/register",
        json={
            **credentials,
            "inventory_name": "Seller inventory"
        }
    )

    assert response.status_code == 201, response.text
    seller = response.json()

    response = client.get("/inventories")
    assert response.status_code == 200, response.text
    assert {
        "id": seller["inventory_id"],
        "name": "Seller inventory"
    } in response.json()

    response = client.post("/seller/login", json=credentials)
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]

    register_and_login(client, "customer1")

    response = client.post(
        "/seller/login",
        json={
            "username": "customer1",
            "password": "test-password-123"
        }
    )
    assert response.status_code == 401



def test_seller_orders_are_isolated(client):
    from order_utils.models import OrderRow
    from order_utils.storage import get_db_write

    sellers = []

    for username in ("seller1", "seller2"):
        credentials = {
            "username": username,
            "password": "test-password-123"
        }

        response = client.post(
            "/seller/register",
            json={
                **credentials,
                "inventory_name": f"{username} inventory"
            }
        )
        assert response.status_code == 201, response.text
        inventory_id = response.json()["inventory_id"]

        response = client.post("/seller/login", json=credentials)
        assert response.status_code == 200, response.text

        headers = {
            "Authorization": f"Bearer {response.json()['access_token']}"
        }
        sellers.append((inventory_id, headers))

    customer_id, customer_headers = register_and_login(client, "customer1")

    # Seed orders to test listing and access independently of checkout.
    with get_db_write() as db:
        for inventory_id, _ in sellers:
            db.add(
                OrderRow(
                    customer_id=customer_id,
                    inventory_id=inventory_id,
                    status="confirmed"
                )
            )

    for inventory_id, headers in sellers:
        response = client.get("/seller/orders", headers=headers)

        assert response.status_code == 200, response.text
        orders = response.json()
        assert len(orders) == 1
        assert orders[0]["inventory_id"] == inventory_id

    response = client.get("/seller/orders", headers=customer_headers)
    assert response.status_code == 403

    response = client.get("/seller/orders")
    assert response.status_code == 401



def test_seller_order_details_are_isolated(client):
    from order_utils.models import OrderRow
    from order_utils.storage import get_db_write

    sellers = []

    for username in ("seller1", "seller2"):
        credentials = {
            "username": username,
            "password": "test-password-123"
        }

        response = client.post(
            "/seller/register",
            json={
                **credentials,
                "inventory_name": f"{username} inventory"
            }
        )
        assert response.status_code == 201, response.text
        inventory_id = response.json()["inventory_id"]

        response = client.post("/seller/login", json=credentials)
        assert response.status_code == 200, response.text

        headers = {
            "Authorization": f"Bearer {response.json()['access_token']}"
        }
        sellers.append((inventory_id, headers))

    customer_id, customer_headers = register_and_login(client, "customer1")
    inventory_id, owner_headers = sellers[0]
    _, other_headers = sellers[1]

    with get_db_write() as db:
        order = OrderRow(
            customer_id=customer_id,
            inventory_id=inventory_id,
            status="confirmed"
        )
        db.add(order)
        db.flush()
        order_id = order.id

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=owner_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["order_id"] == order_id
    assert response.json()["customer_id"] == customer_id

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=other_headers
    )
    assert response.status_code == 403

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=customer_headers
    )
    assert response.status_code == 403

    response = client.get(f"/seller/orders/{order_id}")
    assert response.status_code == 401

    response = client.get(
        "/seller/orders/999999",
        headers=owner_headers
    )
    assert response.status_code == 404