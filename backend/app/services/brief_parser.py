"""Sourcing Brief Assistant — turns natural-language sourcing briefs into a
draft of structured event fields.

This is an *assistant*, not an agent:
  - it never creates or runs anything on its own
  - everything it extracts is shown back to the buyer with the matched text
  - fields it could not extract are returned in ``missing_fields`` so the UI
    can prompt for them before any sourcing event is created.

The implementation is a deterministic, dependency-free, rule-based parser. It
intentionally targets the most common phrasings a procurement buyer uses
("at most N suppliers", "quality at least N", "avoid high-risk", etc.) — when
it cannot match, it returns nothing for that field rather than guess.

Why no LLM right now?
  - free to run, deterministic, easy to test, easy to defend in interviews
  - matches the brief that exists in this repo's milestones

How to add an LLM later:
  - implement the ``BriefParser`` protocol with a class like
    ``LlmBriefParser`` that calls a model API and returns the same
    ``BriefParseResponse`` shape
  - swap the default parser in ``parse_brief`` (or wire it through DI)
  - existing tests still pass because they target the protocol's behaviour,
    not the rule-based internals
"""

from __future__ import annotations

import re
from typing import Protocol

from app.schemas import BriefParseResponse, ExtractedField


# ---------- public protocol ----------


class BriefParser(Protocol):
    """Anything that can turn free-text into a draft sourcing event."""

    def parse(self, text: str) -> BriefParseResponse: ...


def parse_brief(text: str, parser: BriefParser | None = None) -> BriefParseResponse:
    """Convenience entry point. Defaults to the rule-based parser."""
    return (parser or RuleBasedBriefParser()).parse(text)


# ---------- rule-based implementation ----------


# Words that should never be treated as the category noun, e.g. for
# "at most 3 suppliers" we don't want category="suppliers".
_STOP_NOUNS_AFTER_NUMBER = {
    "supplier", "suppliers",
    "vendor", "vendors",
    "quality", "score", "scores",
    "risk", "risks",
    "percent", "%",
}

# Words that terminate a category noun phrase (function words / prepositions).
_CATEGORY_TERMINATORS = {
    "for", "by", "with", "at", "to", "in", "on", "from", "into", "of",
    "and", "or", "but", "that", "which", "when", "if", "because", "so",
    "the", "a", "an", "this", "these", "those",
}

# A field is "required to create an event" but cannot be parsed from text.
# We always list these so the UI prompts for them.
_ALWAYS_CONFIRM = ("max_average_risk", "event_name")


class RuleBasedBriefParser:
    """Regex + keyword parser. Order of extractors does not matter."""

    def parse(self, text: str) -> BriefParseResponse:
        response = BriefParseResponse(original_text=text)

        # Run each extractor; record both the field and a human-readable note.
        demand_field, category_field = _extract_demand_and_category(text)
        if demand_field is not None:
            response.total_demand = demand_field
            response.confidence_notes.append(
                f"total_demand={demand_field.value} "
                f"(matched '{demand_field.matched_text}', {demand_field.confidence} confidence)"
            )
        if category_field is not None:
            response.category = category_field
            response.confidence_notes.append(
                f"category='{category_field.value}' "
                f"(matched '{category_field.matched_text}', {category_field.confidence} confidence)"
            )

        max_suppliers_field = _extract_max_suppliers(text)
        if max_suppliers_field is not None:
            response.max_suppliers = max_suppliers_field
            response.confidence_notes.append(
                f"max_suppliers={max_suppliers_field.value} "
                f"(matched '{max_suppliers_field.matched_text}', "
                f"{max_suppliers_field.confidence} confidence)"
            )

        quality_field = _extract_min_quality(text)
        if quality_field is not None:
            response.min_quality_score = quality_field
            response.confidence_notes.append(
                f"min_quality_score={quality_field.value} "
                f"(matched '{quality_field.matched_text}', {quality_field.confidence} confidence)"
            )

        risk_field = _extract_risk_preference(text)
        if risk_field is not None:
            response.risk_preference = risk_field
            response.confidence_notes.append(
                f"risk_preference='{risk_field.value}' "
                f"(matched '{risk_field.matched_text}', {risk_field.confidence} confidence)"
            )

        cost_field = _extract_cost_priority(text)
        if cost_field is not None:
            response.cost_priority = cost_field
            response.confidence_notes.append(
                f"cost_priority='{cost_field.value}' "
                f"(matched '{cost_field.matched_text}', {cost_field.confidence} confidence)"
            )

        response.missing_fields = _missing_fields(response)
        return response


# ---------- extractors ----------


def _extract_demand_and_category(
    text: str,
) -> tuple[ExtractedField | None, ExtractedField | None]:
    """Find the first ``<number> <noun phrase>`` pattern where the noun is
    not a structural word like 'suppliers' or 'quality'."""
    pattern = re.compile(
        r"(\d{1,3}(?:,\d{3})+|\d+)\s+(?:units?\s+of\s+)?([a-zA-Z][\w\-]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        head_noun = match.group(2)
        if head_noun.lower() in _STOP_NOUNS_AFTER_NUMBER:
            continue
        category_words = [head_noun]
        cursor = match.end()
        # Allow up to two extra words (e.g. "office chairs", "high-grade steel")
        # so multi-word categories survive.
        for _ in range(2):
            tail = re.match(r"\s+([a-zA-Z][\w\-]+)", text[cursor:])
            if tail is None:
                break
            word = tail.group(1)
            if word.lower() in _CATEGORY_TERMINATORS:
                break
            category_words.append(word)
            cursor += tail.end()

        demand_value = int(match.group(1).replace(",", ""))
        matched_text = text[match.start(): cursor].strip()
        return (
            ExtractedField(
                value=demand_value,
                confidence="high",
                matched_text=matched_text,
            ),
            ExtractedField(
                value=" ".join(category_words).strip(),
                confidence="medium",  # category guess is fuzzier than the number
                matched_text=matched_text,
            ),
        )
    return None, None


def _extract_max_suppliers(text: str) -> ExtractedField | None:
    patterns = [
        r"(?:at most|maximum of|max(?:imum)?|no more than|up to)\s+(\d+)\s+(?:suppliers?|vendors?)",
        r"(\d+)\s+(?:suppliers?|vendors?)\s+(?:max(?:imum)?|or fewer|or less)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return ExtractedField(
                value=int(match.group(1)),
                confidence="high",
                matched_text=match.group(0),
            )
    return None


def _extract_min_quality(text: str) -> ExtractedField | None:
    # Direct patterns: "quality" sits immediately next to the qualifier+number.
    direct_patterns = [
        # "quality should be at least 75", "quality of 80", "quality at least 90"
        r"quality(?:\s+score)?\s+(?:should be\s+)?(?:at least|minimum|min|of|>=?\s*|≥\s*)\s*(\d{1,3})",
        # "minimum quality 85", "min quality of 70"
        r"(?:minimum|min)\s+quality(?:\s+score)?\s+(?:of\s+)?(\d{1,3})",
    ]
    for pattern in direct_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            if 0 <= value <= 100:
                return ExtractedField(
                    value=value, confidence="high", matched_text=match.group(0)
                )

    # Sentence-scoped fallback: phrases like "Quality is critical — minimum 85."
    # require us to link "quality" to a nearby "minimum N" within the same
    # sentence (no full stop between). Lower confidence because the link is
    # inferential, not lexical.
    fallback = re.search(
        r"quality[^.]{0,80}?\b(?:minimum|min|at least|>=?\s*|≥\s*)\s*(\d{1,3})\b",
        text,
        re.IGNORECASE,
    )
    if fallback:
        value = int(fallback.group(1))
        if 0 <= value <= 100:
            return ExtractedField(
                value=value, confidence="medium", matched_text=fallback.group(0)
            )
    return None


def _extract_risk_preference(text: str) -> ExtractedField | None:
    """Map natural-language risk signals to one of three buckets."""
    low_risk_phrases = (
        "avoid high-risk", "avoid high risk", "low risk", "low-risk",
        "minimise risk", "minimize risk", "risk-averse", "risk averse",
    )
    high_risk_phrases = (
        "risk-tolerant", "risk tolerant", "accept higher risk",
        "willing to take risk", "high risk is fine", "we're risk-tolerant",
    )
    lowered = text.lower()
    for phrase in low_risk_phrases:
        if phrase in lowered:
            return ExtractedField(
                value="avoid_high_risk", confidence="high", matched_text=phrase
            )
    for phrase in high_risk_phrases:
        if phrase in lowered:
            return ExtractedField(
                value="risk_tolerant", confidence="high", matched_text=phrase
            )
    return None


def _extract_cost_priority(text: str) -> ExtractedField | None:
    """Map cost-related signals to low / medium / high."""
    high_cost_priority = (
        "prioritise low cost", "prioritize low cost",
        "minimise cost", "minimize cost",
        "cheapest", "cost is critical", "cost is key",
        "low-cost", "cost-conscious", "lowest cost",
    )
    low_cost_priority = (
        "cost flexible", "cost is secondary", "willing to pay more",
        "cost-tolerant", "premium",
    )
    lowered = text.lower()
    for phrase in high_cost_priority:
        if phrase in lowered:
            return ExtractedField(
                value="high", confidence="high", matched_text=phrase
            )
    for phrase in low_cost_priority:
        if phrase in lowered:
            return ExtractedField(
                value="low", confidence="high", matched_text=phrase
            )
    return None


def _missing_fields(response: BriefParseResponse) -> list[str]:
    """Fields the buyer must confirm before a sourcing event can be created."""
    missing: list[str] = []
    if response.category is None:
        missing.append("category")
    if response.total_demand is None:
        missing.append("total_demand")
    if response.max_suppliers is None:
        missing.append("max_suppliers")
    if response.min_quality_score is None:
        missing.append("min_quality_score")
    # risk_preference / cost_priority shape future multi-objective weights —
    # absence is acceptable but worth surfacing.
    if response.risk_preference is None:
        missing.append("risk_preference")
    if response.cost_priority is None:
        missing.append("cost_priority")
    # Always-confirm fields are never parseable from a brief.
    missing.extend(_ALWAYS_CONFIRM)
    return missing
