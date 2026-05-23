"""POST /briefs/parse — Sourcing Brief Assistant.

Turns a natural-language sourcing brief into a draft set of structured event
fields. The buyer must review and confirm before anything is persisted.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import BriefParseRequest, BriefParseResponse
from app.services.brief_parser import parse_brief

router = APIRouter(prefix="/api/v1/briefs", tags=["briefs"])


@router.post("/parse", response_model=BriefParseResponse)
def parse(request: BriefParseRequest) -> BriefParseResponse:
    return parse_brief(request.text)
