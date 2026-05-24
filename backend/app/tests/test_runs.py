"""Tests for the scenario-comparison flow:
    POST /events/{id}/optimise   (now with optional label + overrides)
    GET  /events/{id}/runs
    GET  /runs/{run_id}
    DELETE /runs/{run_id}
"""

from __future__ import annotations

from fastapi.testclient import TestClient

EVENT = {
    "name": "Scenario Event",
    "category": "IT Hardware",
    "total_demand": 100,
    "max_suppliers": 10,
    "min_quality_score": 0.0,
    "max_average_risk": 1.0,
}
SUPPLIER_A = {
    "name": "Acme",
    "country": "IE",
    "risk_score": 0.1,
    "sustainability_score": 90.0,
}
SUPPLIER_B = {
    "name": "Globex",
    "country": "DE",
    "risk_score": 0.3,
    "sustainability_score": 70.0,
}


def _seed_minimal_event(client: TestClient) -> tuple[int, int, int]:
    event_id = client.post("/api/v1/events", json=EVENT).json()["id"]
    sa = client.post("/api/v1/suppliers", json=SUPPLIER_A).json()["id"]
    sb = client.post("/api/v1/suppliers", json=SUPPLIER_B).json()["id"]
    client.post(
        "/api/v1/bids",
        json={
            "event_id": event_id,
            "supplier_id": sa,
            "unit_price": 10.0,
            "capacity": 60,
            "lead_time_days": 14,
            "quality_score": 80.0,
        },
    )
    client.post(
        "/api/v1/bids",
        json={
            "event_id": event_id,
            "supplier_id": sb,
            "unit_price": 20.0,
            "capacity": 80,
            "lead_time_days": 14,
            "quality_score": 80.0,
        },
    )
    return event_id, sa, sb


def test_optimise_with_overrides_does_not_mutate_event(client: TestClient) -> None:
    """Per-run overrides apply only to the run — the event row stays intact."""
    event_id, _, _ = _seed_minimal_event(client)

    body = {
        "label": "Single-supplier scenario",
        "overrides": {"max_suppliers": 1},
    }
    response = client.post(f"/api/v1/events/{event_id}/optimise", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "infeasible"  # A alone can't cover demand of 100
    assert payload["constraints_used"]["max_suppliers"] == 1
    assert payload["label"] == "Single-supplier scenario"

    # Event itself is unchanged.
    event = client.get(f"/api/v1/events/{event_id}").json()
    assert event["max_suppliers"] == 10


def test_structured_explanation_breaks_down_decision(client: TestClient) -> None:
    """The structured explanation should name selected, rejected, binding and trade-offs."""
    event_id, sa, sb = _seed_minimal_event(client)

    response = client.post(f"/api/v1/events/{event_id}/optimise", json={"label": "Baseline"})
    assert response.status_code == 200
    body = response.json()
    structured = body["structured_explanation"]
    assert structured is not None

    # Selected: Acme (cheapest) and Globex (fills rest).
    selected_ids = {s["supplier_id"] for s in structured["selected"]}
    assert {sa, sb} == selected_ids

    # Lowest-price tag on Acme.
    acme = next(s for s in structured["selected"] if s["supplier_id"] == sa)
    assert "lowest_price" in acme["reason_codes"]

    # Binding includes demand (always) and bid_capacity (Acme capped at 60).
    binding_names = {c["name"] for c in structured["binding_constraints"]}
    assert "demand" in binding_names
    assert "bid_capacity" in binding_names

    # primary_constraint must be one of the binding ones.
    assert structured["primary_constraint"] is not None
    assert structured["primary_constraint"]["name"] in binding_names

    # At least one trade-off mentions Acme being at full capacity.
    assert any(
        "Acme" in t["summary"] and "capacity" in t["summary"].lower()
        for t in structured["trade_offs"]
    )


def test_runs_history_and_comparison(client: TestClient) -> None:
    """Run twice, list runs, then compare via /runs/{id}."""
    event_id, _, _ = _seed_minimal_event(client)

    r1 = client.post(
        f"/api/v1/events/{event_id}/optimise",
        json={"label": "Baseline"},
    ).json()
    r2 = client.post(
        f"/api/v1/events/{event_id}/optimise",
        json={"label": "Tighter quality", "overrides": {"min_quality_score": 95}},
    ).json()
    assert r1["status"] == "optimal"
    assert r2["status"] == "infeasible"  # both bids have quality 80, below 95

    # List shows both, newest first.
    history = client.get(f"/api/v1/events/{event_id}/runs").json()
    assert len(history) == 2
    assert history[0]["label"] == "Tighter quality"
    assert history[1]["label"] == "Baseline"
    # Comparison-table fields are populated even for infeasible runs.
    assert history[1]["total_cost"] == r1["total_cost"]
    assert history[0]["total_cost"] == 0.0
    assert history[0]["constraints_used"]["min_quality_score"] == 95

    # Detail endpoint hydrates allocations + structured explanation from the snapshot.
    detail = client.get(f"/api/v1/runs/{r1['result_id']}").json()
    assert detail["allocations"] == r1["allocations"]
    assert detail["structured_explanation"] is not None


def test_run_delete_only_affects_that_scenario(client: TestClient) -> None:
    event_id, _, _ = _seed_minimal_event(client)
    r1 = client.post(f"/api/v1/events/{event_id}/optimise", json={"label": "A"}).json()
    r2 = client.post(f"/api/v1/events/{event_id}/optimise", json={"label": "B"}).json()

    assert client.delete(f"/api/v1/runs/{r1['result_id']}").status_code == 204
    remaining = client.get(f"/api/v1/events/{event_id}/runs").json()
    assert [r["id"] for r in remaining] == [r2["result_id"]]
    assert client.get(f"/api/v1/runs/{r1['result_id']}").status_code == 404


def test_sustainability_is_quantity_weighted(client: TestClient) -> None:
    """Avg sustainability = (60*90 + 40*70) / 100 = 82.0."""
    event_id, _, _ = _seed_minimal_event(client)
    body = client.post(f"/api/v1/events/{event_id}/optimise", json={}).json()
    assert body["status"] == "optimal"
    assert body["average_sustainability"] == 82.0
