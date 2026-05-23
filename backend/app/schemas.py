"""Pydantic DTOs for request validation and response serialisation.

These are kept distinct from the SQLModel tables so we can evolve API shapes
independently of storage (e.g. omit ``created_at`` from create requests, add
computed fields on read).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- SourcingEvent ----------


class SourcingEventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    total_demand: int = Field(gt=0)
    max_suppliers: int = Field(gt=0)
    min_quality_score: float = Field(ge=0, le=100)
    max_average_risk: float = Field(ge=0, le=1)


class SourcingEventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    total_demand: int | None = Field(default=None, gt=0)
    max_suppliers: int | None = Field(default=None, gt=0)
    min_quality_score: float | None = Field(default=None, ge=0, le=100)
    max_average_risk: float | None = Field(default=None, ge=0, le=1)


class SourcingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    total_demand: int
    max_suppliers: int
    min_quality_score: float
    max_average_risk: float
    created_at: datetime


# ---------- Supplier ----------


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(min_length=1, max_length=100)
    risk_score: float = Field(ge=0, le=1)
    sustainability_score: float = Field(ge=0, le=100)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    sustainability_score: float | None = Field(default=None, ge=0, le=100)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    risk_score: float
    sustainability_score: float


# ---------- Bid ----------


class BidCreate(BaseModel):
    event_id: int
    supplier_id: int
    unit_price: float = Field(gt=0)
    capacity: int = Field(gt=0)
    lead_time_days: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=100)


class BidUpdate(BaseModel):
    # event_id/supplier_id are immutable once a bid exists — re-create instead.
    unit_price: float | None = Field(default=None, gt=0)
    capacity: int | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    quality_score: float | None = Field(default=None, ge=0, le=100)


class BidRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    supplier_id: int
    unit_price: float
    capacity: int
    lead_time_days: int
    quality_score: float


# ---------- OptimisationResult (read-only for now) ----------


class OptimisationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    total_cost: float
    average_quality: float
    average_risk: float
    explanation: str
    created_at: datetime
