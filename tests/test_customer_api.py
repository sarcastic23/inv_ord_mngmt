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