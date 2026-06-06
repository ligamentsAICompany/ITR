"""Persistence repository for filing packages and generated artifacts."""

from datetime import UTC, datetime

from app.core.database import get_json_record, save_json_record
from app.models.filing_package import FilingPackage

FILING_PACKAGE_CACHE: dict[str, FilingPackage] = {}
FILING_PACKAGE_ARTIFACT_CACHE: dict[tuple[str, str], bytes] = {}


class FilingPackageRepository:
    package_table = "filing_packages"
    artifact_table = "filing_package_artifacts"

    def save(self, package: FilingPackage) -> FilingPackage:
        FILING_PACKAGE_CACHE[package.package_id] = package
        save_json_record(
            self.package_table,
            package.package_id,
            package.model_dump(mode="json"),
            package.created_at.isoformat(),
            package.updated_at.isoformat(),
        )
        return package

    def get(self, package_id: str) -> FilingPackage | None:
        cached = FILING_PACKAGE_CACHE.get(package_id)
        if cached is not None:
            return cached
        payload = get_json_record(self.package_table, package_id)
        if payload is None:
            return None
        package = FilingPackage.model_validate(payload)
        FILING_PACKAGE_CACHE[package.package_id] = package
        return package

    def save_artifact_content(self, package_id: str, artifact_id: str, content: bytes) -> None:
        FILING_PACKAGE_ARTIFACT_CACHE[(package_id, artifact_id)] = content
        now = datetime.now(UTC).isoformat()
        save_json_record(
            self.artifact_table,
            artifact_record_id(package_id, artifact_id),
            {"package_id": package_id, "artifact_id": artifact_id, "content": content.decode("utf-8")},
            now,
            now,
        )

    def get_artifact_content(self, package_id: str, artifact_id: str) -> bytes | None:
        cached = FILING_PACKAGE_ARTIFACT_CACHE.get((package_id, artifact_id))
        if cached is not None:
            return cached
        payload = get_json_record(self.artifact_table, artifact_record_id(package_id, artifact_id))
        if payload is None:
            return None
        content = str(payload["content"]).encode("utf-8")
        FILING_PACKAGE_ARTIFACT_CACHE[(package_id, artifact_id)] = content
        return content


def artifact_record_id(package_id: str, artifact_id: str) -> str:
    return f"{package_id}:{artifact_id}"
