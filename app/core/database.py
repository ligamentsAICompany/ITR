"""Persistence helpers for local development and PostgreSQL-backed production."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.config import get_settings

SQLITE_TABLES = {
    "documents",
    "extraction_results",
    "validation_reports",
    "tax_computations",
    "filing_packages",
    "filing_package_artifacts",
    "audit_events",
}

TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    id TEXT PRIMARY KEY,
    payload {payload_type} NOT NULL,
    owner_user_id TEXT,
    organization_id TEXT,
    document_id TEXT,
    package_id TEXT,
    validation_run_id TEXT,
    computation_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

INDEX_COLUMNS = (
    "owner_user_id",
    "organization_id",
    "created_at",
    "document_id",
    "package_id",
    "validation_run_id",
    "computation_id",
)


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
        connection.execute(TABLE_DDL.format(table=table, payload_type="TEXT"))
        existing_columns = {
            row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column in INDEX_COLUMNS:
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        for column in INDEX_COLUMNS:
            connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_{column} ON {table} ({column})")


def init_database() -> None:
    backend = persistence_backend()
    if backend == "memory":
        return
    if backend == "sqlite":
        with sqlite_connection():
            return
    ensure_postgres_schema()


def ensure_postgres_schema() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise ValueError("DATABASE_URL is required for postgres persistence")
    with postgres_connection() as connection:
        with connection.cursor() as cursor:
            for table in SQLITE_TABLES:
                cursor.execute(TABLE_DDL.format(table=table, payload_type="JSONB"))
                for column in INDEX_COLUMNS:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_{column} ON {table} ({column})")


def save_json_record(table: str, record_id: str, payload: dict, created_at: str, updated_at: str) -> None:
    _validate_table(table)
    backend = persistence_backend()
    if backend == "memory":
        return
    if backend == "postgres":
        save_postgres_json_record(table, record_id, payload, created_at, updated_at)
        return
    metadata = _record_metadata(payload, table)
    with sqlite_connection() as connection:
        connection.execute(
            f"""
            INSERT INTO {table} (
                id, payload, owner_user_id, organization_id, document_id, package_id,
                validation_run_id, computation_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                owner_user_id = excluded.owner_user_id,
                organization_id = excluded.organization_id,
                document_id = excluded.document_id,
                package_id = excluded.package_id,
                validation_run_id = excluded.validation_run_id,
                computation_id = excluded.computation_id,
                updated_at = excluded.updated_at
            """,
            (
                record_id,
                json.dumps(payload, sort_keys=True),
                metadata["owner_user_id"],
                metadata["organization_id"],
                metadata["document_id"],
                metadata["package_id"],
                metadata["validation_run_id"],
                metadata["computation_id"],
                created_at,
                updated_at,
            ),
        )


def get_json_record(table: str, record_id: str) -> dict | None:
    _validate_table(table)
    backend = persistence_backend()
    if backend == "memory":
        return None
    if backend == "postgres":
        return get_postgres_json_record(table, record_id)
    with sqlite_connection() as connection:
        row = connection.execute(f"SELECT payload FROM {table} WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        return None
    return json.loads(row["payload"])


@contextmanager
def postgres_connection() -> Iterator[Any]:
    settings = get_settings()
    if not settings.database_url:
        raise ValueError("DATABASE_URL is required for postgres persistence")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
    with psycopg.connect(settings.database_url) as connection:
        yield connection


def save_postgres_json_record(table: str, record_id: str, payload: dict, created_at: str, updated_at: str) -> None:
    metadata = _record_metadata(payload, table)
    with postgres_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {table} (
                    id, payload, owner_user_id, organization_id, document_id, package_id,
                    validation_run_id, computation_id, created_at, updated_at
                )
                VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    owner_user_id = excluded.owner_user_id,
                    organization_id = excluded.organization_id,
                    document_id = excluded.document_id,
                    package_id = excluded.package_id,
                    validation_run_id = excluded.validation_run_id,
                    computation_id = excluded.computation_id,
                    updated_at = excluded.updated_at
                """,
                (
                    record_id,
                    json.dumps(payload, sort_keys=True),
                    metadata["owner_user_id"],
                    metadata["organization_id"],
                    metadata["document_id"],
                    metadata["package_id"],
                    metadata["validation_run_id"],
                    metadata["computation_id"],
                    created_at,
                    updated_at,
                ),
            )


def get_postgres_json_record(table: str, record_id: str) -> dict | None:
    with postgres_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT payload FROM {table} WHERE id = %s", (record_id,))
            row = cursor.fetchone()
    if row is None:
        return None
    payload = row[0]
    if isinstance(payload, str):
        return json.loads(payload)
    return dict(payload)


def _validate_table(table: str) -> None:
    if table not in SQLITE_TABLES:
        raise ValueError("Unknown persistence table")


def _record_metadata(payload: dict, table: str) -> dict[str, str | None]:
    return {
        "owner_user_id": _string_or_none(payload.get("owner_user_id") or payload.get("actor_user_id")),
        "organization_id": _string_or_none(payload.get("organization_id")),
        "document_id": _string_or_none(payload.get("document_id")),
        "package_id": _string_or_none(payload.get("package_id") or _package_id_from_artifact(payload, table)),
        "validation_run_id": _string_or_none(payload.get("validation_run_id")),
        "computation_id": _string_or_none(payload.get("computation_id")),
    }


def _package_id_from_artifact(payload: dict, table: str) -> str | None:
    if table != "filing_package_artifacts":
        return None
    return payload.get("package_id")


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
