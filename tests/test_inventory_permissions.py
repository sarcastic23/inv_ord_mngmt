from .helpers import register_customer, register_seller


def test_owner_can_create_and_update_inventory_product(client):
    inventory_id, headers = register_seller(client, "owner")

    url = f"/inventories/{inventory_id}/products"
    products = [
        {
            "id": "owner-product",
            "name": "Owner product",
            "stock": 20,
            "unit_price": 75
        }
    ]

    response = client.put(url, json=products, headers=headers)
    assert response.status_code == 200, response.text

    product_url = f"{url}/owner-product"
    response = client.get(product_url)
    assert response.status_code == 200, response.text
    assert response.json() == products[0]

    products[0]["stock"] = 12
    products[0]["unit_price"] = 80

    response = client.put(url, json=products, headers=headers)
    assert response.status_code == 200, response.text

    response = client.get(product_url)
    assert response.status_code == 200, response.text
    assert response.json() == products[0]


def test_customer_cannot_modify_inventory(client):
    _, headers = register_customer(client, "customer")

    response = client.put(
        "/inventories/1/products",
        headers=headers,
        json=[
            {
                "id": "test-product",
                "name": "Changed product",
                "stock": 999,
                "unit_price": 1
            }
        ]
    )
    assert response.status_code == 403, response.text

    response = client.get("/inventories/1/products/test-product")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": "test-product",
        "name": "Test product",
        "stock": 10,
        "unit_price": 50
    }


def test_seller_cannot_modify_another_inventory(client):
    owner_inventory_id, owner_headers = register_seller(client, "owner")
    _, other_headers = register_seller(client, "other")

    url = f"/inventories/{owner_inventory_id}/products"
    original = {
        "id": "owner-product",
        "name": "Owner product",
        "stock": 20,
        "unit_price": 75
    }

    response = client.put(url, json=[original], headers=owner_headers)
    assert response.status_code == 200, response.text

    response = client.put(
        url,
        headers=other_headers,
        json=[
            {
                "id": "owner-product",
                "name": "Changed product",
                "stock": 999,
                "unit_price": 1
            }
        ]
    )
    assert response.status_code == 403, response.text

    response = client.get(f"{url}/owner-product")
    assert response.status_code == 200, response.text
    assert response.json() == original


def test_seller_cannot_rename_shared_product(client):
    inventory_id, headers = register_seller(client, "seller")

    url = f"/inventories/{inventory_id}/products"

    response = client.put(
        url,
        headers=headers,
        json=[
            {
                "id": "test-product",
                "name": "Changed name",
                "stock": 5,
                "unit_price": 70
            }
        ]
    )
    assert response.status_code == 200, response.text

    response = client.get(f"{url}/test-product")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": "test-product",
        "name": "Test product",
        "stock": 5,
        "unit_price": 70
    }

    response = client.get("/inventories/1/products/test-product")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": "test-product",
        "name": "Test product",
        "stock": 10,
        "unit_price": 50
    }

    response = client.put(
        url,
        headers=headers,
        json=[
            {
                "id": "test-product",
                "name": "Another name",
                "stock": 8,
                "unit_price": 90
            }
        ]
    )
    assert response.status_code == 200, response.text

    response = client.get(f"{url}/test-product")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": "test-product",
        "name": "Test product",
        "stock": 8,
        "unit_price": 90
    }