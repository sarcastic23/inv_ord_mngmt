from .helpers import register_customer, register_seller


def test_seller_delivery_permissions_and_stock(client):
    from order_utils.Business import Inventory, Product

    inventory_id, seller_headers = register_seller(client, "seller1")
    _, other_seller_headers = register_seller(client, "seller2")
    _, customer_headers = register_customer(client, "customer1")

    inventory = Inventory(inventory_id)
    inventory.add_products([
        Product("delivery-test", "Delivery product", 10, 50)
    ])

    response = client.post(
        "/orders",
        headers=customer_headers,
        json={
            "inventory_id": inventory_id,
            "items": [
                {"product_id": "delivery-test", "quantity": 4}
            ]
        }
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]

    endpoint = f"/seller/orders/{order_id}/deliver"

    response = client.post(endpoint)
    assert response.status_code == 401

    response = client.post(endpoint, headers=customer_headers)
    assert response.status_code == 403

    response = client.post(endpoint, headers=other_seller_headers)
    assert response.status_code == 403

    # The old customer delivery endpoint must be removed.
    response = client.post(
        f"/orders/{order_id}/deliver",
        headers=customer_headers
    )
    assert response.status_code == 404

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=seller_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "confirmed"
    assert inventory["delivery-test"].stock == 6

    response = client.post(endpoint, headers=seller_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "order_id": order_id,
        "status": "delivered"
    }

    response = client.get(
        f"/seller/orders/{order_id}",
        headers=seller_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "delivered"
    assert inventory["delivery-test"].stock == 6

    response = client.post(endpoint, headers=seller_headers)
    assert response.status_code == 409
    assert inventory["delivery-test"].stock == 6





from .helpers import register_customer, register_seller


def test_seller_can_create_and_list_customers(client):
    inventory_id, headers = register_seller(client, "seller")

    response = client.post(
        "/seller/customers",
        headers=headers,
        json={
            "name": "  Ram  ",
            "phone": "9800000000",
            "address": "Kathmandu"
        }
    )
    assert response.status_code == 201, response.text

    customer = response.json()
    assert customer == {
        "id": customer["id"],
        "inventory_id": inventory_id,
        "name": "Ram",
        "phone": "9800000000",
        "address": "Kathmandu"
    }

    response = client.get("/seller/customers", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == [customer]


def test_customer_contact_fields_are_optional(client):
    inventory_id, headers = register_seller(client, "seller")

    response = client.post(
        "/seller/customers",
        headers=headers,
        json={"name": "Sita"}
    )
    assert response.status_code == 201, response.text

    customer = response.json()
    assert customer["inventory_id"] == inventory_id
    assert customer["name"] == "Sita"
    assert customer["phone"] is None
    assert customer["address"] is None


def test_seller_customer_lists_are_isolated(client):
    _, owner_headers = register_seller(client, "owner")
    _, other_headers = register_seller(client, "other")

    response = client.post(
        "/seller/customers",
        headers=owner_headers,
        json={
            "name": "Private customer",
            "phone": "9800000000",
            "address": "Private address"
        }
    )
    assert response.status_code == 201, response.text
    customer = response.json()

    response = client.get("/seller/customers", headers=other_headers)
    assert response.status_code == 200, response.text
    assert response.json() == []

    response = client.get("/seller/customers", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json() == [customer]


def test_customer_account_cannot_manage_seller_customers(client):
    _, headers = register_customer(client, "customer")

    response = client.post(
        "/seller/customers",
        headers=headers,
        json={"name": "Ram"}
    )
    assert response.status_code == 403, response.text

    response = client.get("/seller/customers", headers=headers)
    assert response.status_code == 403, response.text


def test_seller_customers_require_authentication(client):
    response = client.post(
        "/seller/customers",
        json={"name": "Ram"}
    )
    assert response.status_code == 401, response.text

    response = client.get("/seller/customers")
    assert response.status_code == 401, response.text


def test_customer_name_cannot_be_blank(client):
    _, headers = register_seller(client, "seller")

    response = client.post(
        "/seller/customers",
        headers=headers,
        json={"name": "   "}
    )
    assert response.status_code == 422, response.text

    response = client.get("/seller/customers", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == []




def test_owner_can_view_and_update_customer(client):
    inventory_id, headers = register_seller(client, "owner")

    response = client.post(
        "/seller/customers",
        headers=headers,
        json={
            "name": "Ram",
            "phone": "9800000000",
            "address": "Kathmandu"
        }
    )
    assert response.status_code == 201, response.text
    original = response.json()
    url = f"/seller/customers/{original['id']}"

    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == original

    response = client.patch(
        url,
        headers=headers,
        json={"address": "  Pokhara  ", "phone": None}
    )
    assert response.status_code == 200, response.text

    expected = {
        **original,
        "address": "Pokhara",
        "phone": None
    }
    assert response.json() == expected
    assert response.json()["inventory_id"] == inventory_id

    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == expected


def test_other_seller_cannot_view_or_update_customer(client):
    _, owner_headers = register_seller(client, "owner")
    _, other_headers = register_seller(client, "other")

    response = client.post(
        "/seller/customers",
        headers=owner_headers,
        json={"name": "Private customer", "phone": "9800000000"}
    )
    assert response.status_code == 201, response.text
    original = response.json()
    url = f"/seller/customers/{original['id']}"

    response = client.get(url, headers=other_headers)
    assert response.status_code == 404, response.text

    response = client.patch(
        url,
        headers=other_headers,
        json={"name": "Changed"}
    )
    assert response.status_code == 404, response.text

    response = client.get(url, headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json() == original


def test_customer_detail_endpoints_require_seller_access(client):
    _, owner_headers = register_seller(client, "owner")
    _, customer_headers = register_customer(client, "customer")

    response = client.post(
        "/seller/customers",
        headers=owner_headers,
        json={"name": "Ram"}
    )
    assert response.status_code == 201, response.text
    url = f"/seller/customers/{response.json()['id']}"

    for headers, expected_status in [
        ({}, 401),
        (customer_headers, 403)
    ]:
        response = client.get(url, headers=headers)
        assert response.status_code == expected_status, response.text

        response = client.patch(
            url,
            headers=headers,
            json={"name": "Changed"}
        )
        assert response.status_code == expected_status, response.text


def test_invalid_customer_updates_leave_record_unchanged(client):
    _, headers = register_seller(client, "owner")

    response = client.post(
        "/seller/customers",
        headers=headers,
        json={"name": "Ram"}
    )
    assert response.status_code == 201, response.text
    original = response.json()
    url = f"/seller/customers/{original['id']}"

    for changes in [
        {},
        {"name": None},
        {"name": "   "},
        {"inventory_id": 1}
    ]:
        response = client.patch(url, headers=headers, json=changes)
        assert response.status_code == 422, response.text

    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == original


def test_missing_customer_returns_404(client):
    _, headers = register_seller(client, "owner")

    response = client.get("/seller/customers/999999", headers=headers)
    assert response.status_code == 404, response.text

    response = client.patch(
        "/seller/customers/999999",
        headers=headers,
        json={"name": "Ram"}
    )
    assert response.status_code == 404, response.text