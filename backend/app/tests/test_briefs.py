"""Tests for POST /briefs/parse — the Sourcing Brief Assistant.

Three briefs of increasing sparsity so the suite documents what the parser
will and will not pull out.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_parse_full_brief(client: TestClient) -> None:
    """The canonical example from the spec. Every field should be picked up."""
    brief = (
        "We need 1000 laptops for Q3. Prioritise low cost, but avoid "
        "high-risk suppliers. I want at most 3 suppliers and quality "
        "should be at least 75."
    )

    response = client.post("/api/v1/briefs/parse", json={"text": brief})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["original_text"] == brief
    assert body["total_demand"]["value"] == 1000
    assert body["category"]["value"].lower() == "laptops"
    assert body["max_suppliers"]["value"] == 3
    assert body["min_quality_score"]["value"] == 75
    assert body["risk_preference"]["value"] == "avoid_high_risk"
    assert body["cost_priority"]["value"] == "high"
    # Buyer still has to confirm fields the brief cannot supply.
    assert "max_average_risk" in body["missing_fields"]
    assert "event_name" in body["missing_fields"]
    # confidence_notes should contain one human-readable line per extracted field.
    assert any("total_demand=1000" in note for note in body["confidence_notes"])


def test_parse_multi_word_category_and_risk_tolerant(client: TestClient) -> None:
    """Different phrasing, multi-word category, and the opposite risk stance."""
    brief = (
        "Procuring 500 office chairs by end of year. Quality is critical — "
        "minimum 85. Maximum 2 vendors. We're risk-tolerant and willing to "
        "pay more for reliability."
    )

    response = client.post("/api/v1/briefs/parse", json={"text": brief})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total_demand"]["value"] == 500
    assert body["category"]["value"].lower() == "office chairs"
    assert body["max_suppliers"]["value"] == 2
    assert body["min_quality_score"]["value"] == 85
    assert body["risk_preference"]["value"] == "risk_tolerant"
    assert body["cost_priority"]["value"] == "low"


def test_parse_sparse_brief_reports_missing_fields(client: TestClient) -> None:
    """A short brief with only demand + category. Everything else should be
    reported as missing — the buyer needs to fill those in before any
    sourcing event is created."""
    brief = "Need 2000 widgets."

    response = client.post("/api/v1/briefs/parse", json={"text": brief})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total_demand"]["value"] == 2000
    assert body["category"]["value"].lower() == "widgets"

    # The parser must not invent values it cannot ground in the text.
    assert body["max_suppliers"] is None
    assert body["min_quality_score"] is None
    assert body["risk_preference"] is None
    assert body["cost_priority"] is None

    missing = set(body["missing_fields"])
    for required in (
        "max_suppliers", "min_quality_score",
        "risk_preference", "cost_priority",
        "max_average_risk", "event_name",
    ):
        assert required in missing, f"expected {required} in missing_fields"
