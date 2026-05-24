from __future__ import annotations

from fastapi.testclient import TestClient

EVENT_PAYLOAD = {
    "name": "Q3 Laptops",
    "category": "IT Hardware",
    "total_demand": 1000,
    "max_suppliers": 3,
    "min_quality_score": 70.0,
    "max_average_risk": 0.4,
}
SUPPLIER_PAYLOAD = {
    "name": "Acme Computers",
    "country": "Ireland",
    "risk_score": 0.2,
    "sustainability_score": 80.0,
}


def _seed_event_and_supplier(client: TestClient) -> tuple[int, int]:
    event_id = client.post("/api/v1/events", json=EVENT_PAYLOAD).json()["id"]
    supplier_id = client.post("/api/v1/suppliers", json=SUPPLIER_PAYLOAD).json()["id"]
    return event_id, supplier_id


def _bid_payload(event_id: int, supplier_id: int) -> dict:
    return {
        "event_id": event_id,
        "supplier_id": supplier_id,
        "unit_price": 800.0,
        "capacity": 400,
        "lead_time_days": 21,
        "quality_score": 85.0,
    }


def test_create_bid_happy_path(client: TestClient) -> None:
    event_id, supplier_id = _seed_event_and_supplier(client)
    response = client.post(
        "/api/v1/bids", json=_bid_payload(event_id, supplier_id)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["event_id"] == event_id
    assert body["supplier_id"] == supplier_id


def test_create_bid_missing_event(client: TestClient) -> None:
    supplier_id = client.post("/api/v1/suppliers", json=SUPPLIER_PAYLOAD).json()["id"]
    response = client.post("/api/v1/bids", json=_bid_payload(999, supplier_id))
    assert response.status_code == 404
    assert "Event" in response.json()["detail"]


def test_create_bid_missing_supplier(client: TestClient) -> None:
    event_id = client.post("/api/v1/events", json=EVENT_PAYLOAD).json()["id"]
    response = client.post("/api/v1/bids", json=_bid_payload(event_id, 999))
    assert response.status_code == 404
    assert "Supplier" in response.json()["detail"]


def test_create_bid_duplicate_returns_409(client: TestClient) -> None:
    event_id, supplier_id = _seed_event_and_supplier(client)
    payload = _bid_payload(event_id, supplier_id)
    assert client.post("/api/v1/bids", json=payload).status_code == 201
    duplicate = client.post("/api/v1/bids", json=payload)
    assert duplicate.status_code == 409


def test_list_bids_filtered_by_event(client: TestClient) -> None:
    event_id_a, supplier_id = _seed_event_and_supplier(client)
    event_id_b = client.post(
        "/api/v1/events", json={**EVENT_PAYLOAD, "name": "Other event"}
    ).json()["id"]

    client.post("/api/v1/bids", json=_bid_payload(event_id_a, supplier_id))
    client.post("/api/v1/bids", json=_bid_payload(event_id_b, supplier_id))

    bids_for_a = client.get("/api/v1/bids", params={"event_id": event_id_a}).json()
    assert len(bids_for_a) == 1
    assert bids_for_a[0]["event_id"] == event_id_a


def test_bid_update_and_delete(client: TestClient) -> None:
    event_id, supplier_id = _seed_event_and_supplier(client)
    bid_id = client.post(
        "/api/v1/bids", json=_bid_payload(event_id, supplier_id)
    ).json()["id"]

    patched = client.patch(f"/api/v1/bids/{bid_id}", json={"unit_price": 750.0})
    assert patched.status_code == 200
    assert patched.json()["unit_price"] == 750.0

    assert client.delete(f"/api/v1/bids/{bid_id}").status_code == 204
    assert client.get(f"/api/v1/bids/{bid_id}").status_code == 404


def test_deleting_event_cascades_to_bids(client: TestClient) -> None:
    event_id, supplier_id = _seed_event_and_supplier(client)
    bid_id = client.post(
        "/api/v1/bids", json=_bid_payload(event_id, supplier_id)
    ).json()["id"]

    assert client.delete(f"/api/v1/events/{event_id}").status_code == 204
    assert client.get(f"/api/v1/bids/{bid_id}").status_code == 404
