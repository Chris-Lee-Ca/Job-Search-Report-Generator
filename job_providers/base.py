from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class JobProvider(ABC):
    """Abstract interface for job-listing sources."""

    @abstractmethod
    def setup(self) -> None:
        """One-time interactive setup (e.g. browser login)."""

    @abstractmethod
    def fetch_jobs(self, search_urls: List[dict]) -> List[dict]:
        """
        Scrape jobs from the given search URL entries.
        Each entry: {"label": str, "url": str, "remote_only": bool}
        Returns raw job dicts: {id, title, company, location, url, description, employment_type, _remote_only}
        """

    @abstractmethod
    def fetch_jobs_from_ids(self, ids_path: str) -> List[dict]:
        """Resume a fetch from a previously-saved job IDs JSON file."""
