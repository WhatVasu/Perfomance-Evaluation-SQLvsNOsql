import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_order_checkout_lifecycle(
    client: AsyncClient, admin_auth: dict[str, str], user_auth: dict[str, str]
):
    # 1. Setup category and products
    cat_res = await client.post(
        "/api/v1/products/categories",
        json={"name": "Books", "slug": "books"},
        headers=admin_auth,
    )
    cat_id = cat_res.json()["id"]

    prod1 = (
        await client.post(
            "/api/v1/products",
            json={"name": "Database Systems", "price": 80.0, "stock": 5, "category_id": cat_id},
            headers=admin_auth,
        )
    ).json()

    prod2 = (
        await client.post(
            "/api/v1/products",
            json={"name": "Distributed Systems", "price": 95.0, "stock": 10, "category_id": cat_id},
            headers=admin_auth,
        )
    ).json()

    # 2. Checkout empty cart fails
    empty_checkout = await client.post("/api/v1/orders/checkout", headers=user_auth)
    assert empty_checkout.status_code == 400

    # 3. Add items to cart
    await client.post(
        "/api/v1/cart/items",
        json={"product_id": prod1["id"], "quantity": 2},
        headers=user_auth,
    )
    await client.post(
        "/api/v1/cart/items",
        json={"product_id": prod2["id"], "quantity": 1},
        headers=user_auth,
    )

    # 4. Successful checkout
    checkout_res = await client.post("/api/v1/orders/checkout", headers=user_auth)
    assert checkout_res.status_code == 201
    order = checkout_res.json()
    assert order["status"] == "completed"
    assert order["total_amount"] == 255.0  # (80 * 2) + (95 * 1)
    assert len(order["items"]) == 2

    # 5. Verify cart is cleared
    cart_res = await client.get("/api/v1/cart", headers=user_auth)
    assert len(cart_res.json()["items"]) == 0

    # 6. Verify inventory was accurately decremented
    p1_check = (await client.get(f"/api/v1/products/{prod1['id']}")).json()
    assert p1_check["stock"] == 3  # 5 - 2

    p2_check = (await client.get(f"/api/v1/products/{prod2['id']}")).json()
    assert p2_check["stock"] == 9  # 10 - 1

    # 7. Check order history
    orders_res = await client.get("/api/v1/orders", headers=user_auth)
    assert orders_res.status_code == 200
    assert orders_res.json()["total"] >= 1

    # 8. Get order by id
    detail_res = await client.get(f"/api/v1/orders/{order['id']}", headers=user_auth)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == order["id"]
