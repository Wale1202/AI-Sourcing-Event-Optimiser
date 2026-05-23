"""Idempotent sample-data seeder.

Inserts one realistic sourcing event with five suppliers and five bids if (and
only if) the database has no events yet. Useful so a fresh clone has something
to look at in /docs immediately.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.database import engine
from app.models import Bid, SourcingEvent, Supplier


def seed_if_empty() -> None:
    with Session(engine) as session:
        if session.exec(select(SourcingEvent)).first() is not None:
            return

        event = SourcingEvent(
            name="Laptop Procurement Q3",
            category="IT Hardware",
            total_demand=1000,
            max_suppliers=3,
            min_quality_score=70.0,
            max_average_risk=0.4,
        )
        session.add(event)
        session.flush()  # populate event.id without committing

        suppliers = [
            Supplier(name="Acme Computers", country="Ireland",
                     risk_score=0.15, sustainability_score=85.0),
            Supplier(name="Globex Tech", country="Germany",
                     risk_score=0.25, sustainability_score=78.0),
            Supplier(name="Initech Devices", country="USA",
                     risk_score=0.35, sustainability_score=90.0),
            Supplier(name="Umbrella Systems", country="China",
                     risk_score=0.55, sustainability_score=70.0),
            Supplier(name="Soylent Hardware", country="Vietnam",
                     risk_score=0.45, sustainability_score=60.0),
        ]
        for s in suppliers:
            session.add(s)
        session.flush()

        # (supplier index, unit_price, capacity, lead_time_days, quality_score)
        bid_rows = [
            (0, 820.0, 400, 14, 88.0),
            (1, 790.0, 500, 21, 82.0),
            (2, 760.0, 350, 30, 92.0),
            (3, 700.0, 800, 45, 72.0),
            (4, 730.0, 600, 35, 65.0),
        ]
        for idx, price, cap, lead, quality in bid_rows:
            session.add(
                Bid(
                    event_id=event.id,  # type: ignore[arg-type]
                    supplier_id=suppliers[idx].id,  # type: ignore[arg-type]
                    unit_price=price,
                    capacity=cap,
                    lead_time_days=lead,
                    quality_score=quality,
                )
            )

        session.commit()
