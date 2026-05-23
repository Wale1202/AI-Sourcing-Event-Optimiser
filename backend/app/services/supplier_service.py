"""Persistence logic for Supplier."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import Supplier
from app.schemas import SupplierCreate, SupplierUpdate


def create(session: Session, payload: SupplierCreate) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier


def list_all(session: Session) -> list[Supplier]:
    return list(session.exec(select(Supplier).order_by(Supplier.id)).all())


def get(session: Session, supplier_id: int) -> Supplier | None:
    return session.get(Supplier, supplier_id)


def update(
    session: Session, supplier_id: int, payload: SupplierUpdate
) -> Supplier | None:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, key, value)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier


def delete(session: Session, supplier_id: int) -> bool:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        return False
    session.delete(supplier)
    session.commit()
    return True
