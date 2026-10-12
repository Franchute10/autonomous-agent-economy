"""Database configuration and SQLAlchemy engine construction."""

from __future__ import annotations

from dataclasses import dataclass
import os

from sqlalchemy import Engine, create_engine as sqlalchemy_create_engine


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Small environment boundary; credentials never belong in source."""

    url: str
    echo: bool = False

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        url = os.environ.get("AEOS_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "AEOS_DATABASE_URL (or DATABASE_URL) must configure PostgreSQL"
            )
        return cls(url=url, echo=os.environ.get("AEOS_SQL_ECHO", "0") == "1")


def create_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create a synchronous SQLAlchemy engine for the configured PostgreSQL DSN."""
    resolved = settings or DatabaseSettings.from_environment()
    return sqlalchemy_create_engine(resolved.url, echo=resolved.echo, future=True)
