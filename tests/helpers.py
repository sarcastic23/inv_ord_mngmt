def register_customer(client, username):
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


def register_seller(client, username):
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

    return inventory_id, headers