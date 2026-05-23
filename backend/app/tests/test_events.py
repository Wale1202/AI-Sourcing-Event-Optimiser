from __future__ import annotations

from fastapi.testclient import TestClient


VALID_EVENT = {
    "name": "Q4 Office Chairs",
    "category": "Furniture",
    "total_demand": 500,
    "max_suppliers": 2,
    "min_quality_score": 60.0,
    "max_average_risk": 0.5,
}


def test_create_event(client: TestClient) -> None:
    response = client.post("/api/v1/events", json=VALID_EVENT)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == VALID_EVENT["name"]
    assert "created_at" in body


def test_create_event_rejects_invalid(client: TestClient) -> None:
    bad = {**VALID_EVENT, "total_demand": 0}  # must be > 0
    response = client.post("/api/v1/events", json=bad)
    assert response.status_code == 422


def test_list_events_empty(client: TestClient) -> None:
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    assert response.json() == []


def test_get_event_404(client: TestClient) -> None:
    assert client.get("/api/v1/events/999").status_code == 404


def test_event_full_lifecycle(client: TestClient) -> None:
    created = client.post("/api/v1/events", json=VALID_EVENT).json()
    event_id = created["id"]

    fetched = client.get(f"/api/v1/events/{event_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == VALID_EVENT["name"]

    patched = client.patch(
        f"/api/v1/events/{event_id}", json={"max_suppliers": 5}
    )
    assert patched.status_code == 200
    assert patched.json()["max_suppliers"] == 5
    assert patched.json()["name"] == VALID_EVENT["name"]  # unchanged

    deleted = client.delete(f"/api/v1/events/{event_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404
