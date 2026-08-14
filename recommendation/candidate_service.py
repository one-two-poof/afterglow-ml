"""Compatibility imports; use :mod:`app.rule.candidate_service`."""

from app.repositories.csv_place_repository import CsvPlaceRepository
from app.rule.candidate_service import CandidateService

__all__ = ["CandidateService", "CsvPlaceRepository"]
