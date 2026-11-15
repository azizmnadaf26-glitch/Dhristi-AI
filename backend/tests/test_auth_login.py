from app.security.tokens import decode_access_token

GOOD = {"email": "user@example.com", "password": "Correct-Pass-123"}
BAD = {"email": "user@example.com", "password": "wrong-password"}


def test_login_success(client, make_user):
    user = make_user()
    response = client.post("/api/auth/login", json=GOOD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["must_change_password"] is True
    claims = decode_access_token(body["access_token"])
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "clinician"


def test_wrong_password_and_unknown_email_look_identical(client, make_user):
    make_user()
    wrong = client.post("/api/auth/login", json=BAD)
    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_account_locks_after_five_failures(client, make_user):
    make_user()
    for _ in range(5):
        assert client.post("/api/auth/login", json=BAD).status_code == 401
    # Even the correct password is refused while locked.
    response = client.post("/api/auth/login", json=GOOD)
    assert response.status_code == 423
    assert response.json()["error"]["code"] == "account_locked"


def test_deactivated_user_cannot_log_in(client, make_user):
    make_user(is_active=False)
    assert client.post("/api/auth/login", json=GOOD).status_code == 401


def test_unknown_fields_are_rejected(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "a@b.com", "password": "x", "role": "admin"},
    )
    assert response.status_code == 422