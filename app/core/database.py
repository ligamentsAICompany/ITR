"""Persistence helpers for local development and future database backends."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings

SQLITE_TABLES = {
    "validation_reports",
    "tax_computations",
    "filing_packages",
    "filing_package_artifacts",
    "audit_events",
}


def persistence_backend() -> str:
    settings = get_settings()
    if settings.database_url:
        if settings.database_url.startswith("sqlite:///"):
            return "sqlite"
        if settings.database_url.startswith(("postgres://", "postgresql://")):
            return "postgres"
    backend = settings.persistence_backend
    if backend not in {"memory", "sqlite", "postgres"}:
        raise ValueError("Invalid PERSISTENCE_BACKEND")
    if backend == "postgres" and not settings.database_url:
        raise ValueError("DATABASE_URL is required for postgres persistence")
    return backend


def sqlite_path() -> Path:
    settings = get_settings()
    if settings.database_url and settings.database_url.startswith("sqlite:///"):
        return Path(settings.database_url.replace("sqlite:///", "", 1)).resolve()
    return (Path(settings.persistence_storage_dir).resolve() / "itr_persistence.sqlite3")


@contextmanager
def sqlite_connection() -> Iterator[sqlite3.Connection]:
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        ensure_sqlite_schema(connection)
        yield connection
        connection.commit()
    finally:
        connection.close()


def ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    for table in SQLITE_TABLES:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def save_json_record(table: str, record_id: str, payload: dict, created_at: str, updated_at: str) -> None:
    _validate_table(table)
    backend = persistence_backend()
    if backend == "memory":
        return
    if backend == "postgres":
        raise NotImplementedError("PostgreSQL persistence requires migrations before production client use")
    with sqlite_connection() as connection:
        connection.execute(
            f"""
            INSERT INTO {table} (id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (record_id, json.dumps(payload, sort_keys=True), created_at, updated_at),
        )


def get_json_record(table: str, record_id: str) -> dict | None:
    _validate_table(table)
    backend = persistence_backend()
    if backend == "memory":
        return None
    if backend == "postgres":
        raise NotImplementedError("PostgreSQL persistence requires migrations before production client use")
    with sqlite_connection() as connection:
        row = connection.execute(f"SELECT payload FROM {table} WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        return None
    return json.loads(row["payload"])


def _validate_table(table: str) -> None:
    if table not in SQLITE_TABLES:
        raise ValueError("Unknown persistence table")
