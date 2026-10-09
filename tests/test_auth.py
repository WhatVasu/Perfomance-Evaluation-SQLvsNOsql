import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_registration_and_login(client: AsyncClient):
    # 1. Register new user
    reg_payload = {
        "email": "testuser@example.com",
        "full_name": "Test User",
        "password": "Password123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    user = reg_res.json()
    assert user["email"] == reg_payload["email"]
    assert user["full_name"] == reg_payload["full_name"]
    assert "id" in user
    assert "hashed_password" not in user

    # 2. Duplicate registration should fail
    dup_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409

    # 3. Login with correct credentials
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": "Password123!"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # 4. Login with invalid password
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    # 5. Access profile with token
    auth_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    me_res = await client.get("/api/v1/users/me", headers=auth_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == reg_payload["email"]

    # 6. Access profile without token
    unauth_res = await client.get("/api/v1/users/me")
    assert unauth_res.status_code == 401
