from __future__ import annotations

from fastapi.testclient import TestClient

VALID_SUPPLIER = {
    "name": "Acme Computers",
    "country": "Ireland",
    "risk_score": 0.2,
    "sustainability_score": 80.0,
}


def test_create_supplier(client: TestClient) -> None:
    response = client.post("/api/v1/suppliers", json=VALID_SUPPLIER)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["country"] == "Ireland"


def test_create_supplier_rejects_out_of_range_risk(client: TestClient) -> None:
    bad = {**VALID_SUPPLIER, "risk_score": 1.5}  # max is 1.0
    response = client.post("/api/v1/suppliers", json=bad)
    assert response.status_code == 422


def test_supplier_full_lifecycle(client: TestClient) -> None:
    created = client.post("/api/v1/suppliers", json=VALID_SUPPLIER).json()
    supplier_id = created["id"]

    listed = client.get("/api/v1/suppliers").json()
    assert any(s["id"] == supplier_id for s in listed)

    patched = client.patch(
        f"/api/v1/suppliers/{supplier_id}", json={"risk_score": 0.4}
    )
    assert patched.status_code == 200
    assert patched.json()["risk_score"] == 0.4

    deleted = client.delete(f"/api/v1/suppliers/{supplier_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/suppliers/{supplier_id}").status_code == 404
