"""Recommendation snapshot repository."""

from __future__ import annotations

from app.models.recommendation import RecommendationSnapshot
from app.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository[RecommendationSnapshot]):
    model = RecommendationSnapshot
