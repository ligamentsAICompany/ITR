"""Deterministic database initialization entrypoint.

Run with:
    python -m app.db.init_db
"""

from app.core.database import init_database, persistence_backend


def main() -> None:
    backend = persistence_backend()
    init_database()
    print(f"Initialized {backend} persistence schema")


if __name__ == "__main__":
    main()
