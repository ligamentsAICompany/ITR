"""Generate deterministic JSON artifact content for filing packages."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.models.filing_package import FilingPackageArtifact, FilingPackageArtifactType, safe_filename


class FilingPackageArtifactService:
    def build_json_artifact(
        self,
        *,
        artifact_type: FilingPackageArtifactType,
        filename: str,
        payload: dict[str, Any],
    ) -> tuple[FilingPackageArtifact, bytes]:
        content = json.dumps(payload, sort_keys=True, indent=2, default=str).encode("utf-8")
        artifact = FilingPackageArtifact(
            artifact_type=artifact_type,
            filename=safe_filename(filename),
            mime_type="application/json",
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            created_at=datetime.now(UTC),
        )
        return artifact, content
