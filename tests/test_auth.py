def test_login_requires_pin(client):
    response = client.post("/auth/login", data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Enter your PIN" in response.data


def test_login_success(client, admin_user):
    response = client.post("/auth/login", data={"pin": "1234"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Operations Dashboard" in response.data


def test_logout_flow(auth_client):
    response = auth_client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    # After logout the login page should be shown
    assert b"Enter your PIN" in response.data
