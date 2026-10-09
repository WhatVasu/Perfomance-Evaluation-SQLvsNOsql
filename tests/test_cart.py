import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_shopping_cart_workflow(
    client: AsyncClient, admin_auth: dict[str, str], user_auth: dict[str, str]
):
    # 1. Setup category & product
    cat_res = await client.post(
        "/api/v1/products/categories",
        json={"name": "Apparel", "slug": "apparel"},
        headers=admin_auth,
    )
    cat_id = cat_res.json()["id"]

    prod_res = await client.post(
        "/api/v1/products",
        json={
            "name": "Organic Cotton T-Shirt",
            "price": 25.0,
            "stock": 10,
            "category_id": cat_id,
        },
        headers=admin_auth,
    )
    product_id = prod_res.json()["id"]

    # 2. View empty cart
    empty_cart = await client.get("/api/v1/cart", headers=user_auth)
    assert empty_cart.status_code == 200
    assert len(empty_cart.json()["items"]) == 0
    assert empty_cart.json()["total_amount"] == 0.0

    # 3. Add item to cart
    add_res = await client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=user_auth,
    )
    assert add_res.status_code == 200
    cart = add_res.json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 2
    assert cart["items"][0]["subtotal"] == 50.0
    assert cart["total_amount"] == 50.0

    # 4. Add same item again (quantity increments)
    add_more = await client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 1},
        headers=user_auth,
    )
    assert add_more.status_code == 200
    cart = add_more.json()
    assert cart["items"][0]["quantity"] == 3
    assert cart["total_amount"] == 75.0

    # 5. Update quantity
    update_res = await client.put(
        f"/api/v1/cart/items/{product_id}",
        json={"quantity": 1},
        headers=user_auth,
    )
    assert update_res.status_code == 200
    assert update_res.json()["items"][0]["quantity"] == 1
    assert update_res.json()["total_amount"] == 25.0

    # 6. Remove item
    del_res = await client.delete(f"/api/v1/cart/items/{product_id}", headers=user_auth)
    assert del_res.status_code == 200
    assert len(del_res.json()["items"]) == 0
    assert del_res.json()["total_amount"] == 0.0

    # 7. Add again then clear cart
    await client.post(
        "/api/v1/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=user_auth,
    )
    clear_res = await client.delete("/api/v1/cart", headers=user_auth)
    assert clear_res.status_code == 204

    refetched = await client.get("/api/v1/cart", headers=user_auth)
    assert len(refetched.json()["items"]) == 0
