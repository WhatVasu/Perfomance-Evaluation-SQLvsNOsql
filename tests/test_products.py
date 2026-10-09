import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_product_catalog_lifecycle(
    client: AsyncClient, admin_auth: dict[str, str], user_auth: dict[str, str]
):
    # 1. Create category as admin
    cat_payload = {"name": "Electronics", "slug": "electronics"}
    cat_res = await client.post("/api/v1/products/categories", json=cat_payload, headers=admin_auth)
    assert cat_res.status_code == 201
    category = cat_res.json()
    assert category["name"] == "Electronics"
    cat_id = category["id"]

    # 2. Non-admin cannot create category
    forbidden_cat = await client.post(
        "/api/v1/products/categories", json=cat_payload, headers=user_auth
    )
    assert forbidden_cat.status_code == 403

    # 3. Create products as admin
    p1_payload = {
        "name": "Wireless Noise Cancelling Headphones",
        "description": "High fidelity sound with ANC",
        "price": 299.99,
        "stock": 50,
        "category_id": cat_id,
    }
    p1_res = await client.post("/api/v1/products", json=p1_payload, headers=admin_auth)
    assert p1_res.status_code == 201
    p1 = p1_res.json()
    assert p1["name"] == p1_payload["name"]
    assert p1["stock"] == 50

    p2_payload = {
        "name": "USB-C Fast Charging Cable",
        "description": "Braided 2 meter cable",
        "price": 19.99,
        "stock": 100,
        "category_id": cat_id,
    }
    p2_res = await client.post("/api/v1/products", json=p2_payload, headers=admin_auth)
    assert p2_res.status_code == 201

    # 4. List products (pagination)
    list_res = await client.get("/api/v1/products?page=1&page_size=10")
    assert list_res.status_code == 200
    catalog = list_res.json()
    assert catalog["total"] >= 2
    assert len(catalog["items"]) >= 2

    # 5. Filter by price
    price_filter = await client.get("/api/v1/products?min_price=100.0")
    assert price_filter.status_code == 200
    expensive_items = price_filter.json()["items"]
    assert all(item["price"] >= 100.0 for item in expensive_items)

    # 6. Text search by name
    search_res = await client.get("/api/v1/products?search=Headphones")
    assert search_res.status_code == 200
    matched = search_res.json()["items"]
    assert len(matched) >= 1
    assert any("Headphones" in item["name"] for item in matched)

    # 7. Get single product by ID
    get_res = await client.get(f"/api/v1/products/{p1['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == p1["id"]

    # 8. Update product
    update_res = await client.put(
        f"/api/v1/products/{p1['id']}",
        json={"price": 249.99, "stock": 45},
        headers=admin_auth,
    )
    assert update_res.status_code == 200
    updated_p1 = update_res.json()
    assert updated_p1["price"] == 249.99
    assert updated_p1["stock"] == 45
