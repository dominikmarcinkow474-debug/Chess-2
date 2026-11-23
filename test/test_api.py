def register_and_login(client, email="test@example.com"):
    response = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    assert response.status_code == 201, response.text
    response = client.post("/auth/login", data={"username": email, "password": "correct-horse-battery"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_health(client):
    assert client.get("/health").json()["status"] == "ok"

def test_register_login_and_me(client):
    headers = register_and_login(client)
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

def test_duplicate_registration(client):
    register_and_login(client)
    response = client.post("/auth/register", json={"email": "test@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 409

def test_auth_required(client):
    assert client.post("/games", json={}).status_code == 401

def test_create_game_and_reject_illegal_move(client):
    headers = register_and_login(client)
    game = client.post("/games", json={}, headers=headers)
    assert game.status_code == 201
    game_id = game.json()["id"]
    bad = client.post(f"/games/{game_id}/moves", json={"uci": "e2e5"}, headers=headers)
    assert bad.status_code == 422

def test_user_cannot_access_another_users_game(client):
    h1 = register_and_login(client, "one@example.com")
    game = client.post("/games", json={}, headers=h1).json()
    h2 = register_and_login(client, "two@example.com")
    response = client.get(f"/games/{game['id']}", headers=h2)
    assert response.status_code == 404
