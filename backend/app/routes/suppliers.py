"""CRUD endpoints for Supplier."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.schemas import SupplierCreate, SupplierRead, SupplierUpdate
from app.services import supplier_service

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate, session: Session = Depends(get_session)
) -> SupplierRead:
    return supplier_service.create(session, payload)  # type: ignore[return-value]


@router.get("", response_model=list[SupplierRead])
def list_suppliers(session: Session = Depends(get_session)) -> list[SupplierRead]:
    return supplier_service.list_all(session)  # type: ignore[return-value]


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: int, session: Session = Depends(get_session)
) -> SupplierRead:
    supplier = supplier_service.get(session, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return supplier  # type: ignore[return-value]


@router.patch("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    session: Session = Depends(get_session),
) -> SupplierRead:
    updated = supplier_service.update(session, supplier_id, payload)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return updated  # type: ignore[return-value]


@router.delete(
    "/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_supplier(supplier_id: int, session: Session = Depends(get_session)):
    if not supplier_service.delete(session, supplier_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
