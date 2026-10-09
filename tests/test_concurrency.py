import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_concurrent_checkout_stock_atomicity(client: AsyncClient, admin_auth: dict[str, str]):
    """
    Simulates high concurrent checkout race condition:
    - Product has stock = 5
    - 10 distinct users attempt to checkout simultaneously
    - Asserts:
        1. Exactly 5 checkouts succeed (201)
        2. Exactly 5 checkouts fail with stock exhaustion (409)
        3. Stock NEVER goes negative (stock == 0)
        4. Total created orders == 5
    """
    # 1. Admin creates category and limited-stock product (stock = 5)
    cat_res = await client.post(
        "/api/v1/products/categories",
        json={"name": "Flash Sale", "slug": "flash-sale"},
        headers=admin_auth,
    )
    cat_id = cat_res.json()["id"]

    prod_res = await client.post(
        "/api/v1/products",
        json={
            "name": "Limited Edition Sneaker",
            "price": 150.0,
            "stock": 5,
            "category_id": cat_id,
        },
        headers=admin_auth,
    )
    product_id = prod_res.json()["id"]

    # 2. Register and login 10 distinct users, adding 1 item to each cart
    user_tokens: list[str] = []
    num_users = 10

    for i in range(num_users):
        email = f"racer_{i}@benchmark.test"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "full_name": f"Racer {i}", "password": "Password123!"},
        )
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        token = login_res.json()["access_token"]
        user_tokens.append(token)

        # Add item to user cart
        await client.post(
            "/api/v1/cart/items",
            json={"product_id": product_id, "quantity": 1},
            headers={"Authorization": f"Bearer {token}"},
        )

    # 3. Fire all 10 checkouts concurrently
    async def attempt_checkout(token: str):
        return await client.post(
            "/api/v1/orders/checkout",
            headers={"Authorization": f"Bearer {token}"},
        )

    checkout_responses = await asyncio.gather(*[attempt_checkout(t) for t in user_tokens])

    success_count = sum(1 for r in checkout_responses if r.status_code == 201)
    conflict_count = sum(1 for r in checkout_responses if r.status_code == 409)

    # 4. Verify exact atomicity
    assert success_count == 5, f"Expected 5 successes, got {success_count}"
    assert conflict_count == 5, f"Expected 5 conflicts, got {conflict_count}"

    # 5. Verify final inventory is exactly 0 and never negative
    final_prod = (await client.get(f"/api/v1/products/{product_id}")).json()
    assert final_prod["stock"] == 0, f"Expected 0 stock, got {final_prod['stock']}"
