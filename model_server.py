"""Backward-compatible application entry point.

New deployments should use ``app.model_server:app``.
"""

from app.model_server import app
from app.rule.inference import resolve_anchor, resolve_treatments
from app.schemas.recommendation import PlaceRecommendationRequest, RecommendationRequest

__all__ = [
    "app",
    "PlaceRecommendationRequest",
    "RecommendationRequest",
    "resolve_anchor",
    "resolve_treatments",
]
