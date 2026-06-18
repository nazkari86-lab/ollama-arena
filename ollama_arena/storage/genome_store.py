"""Genome store wrapper — re-exports GenomeStore for storage layer consumers."""
from ..genome.db import GenomeStore

__all__ = ["GenomeStore"]
