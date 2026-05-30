"""Build official-schema-validated ITR export artifacts."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.models.filing_package import safe_filename
from app.models.itr_export import ItrExportArtifact, ItrExportArtifactType, public_export_payload


class ItrExportArtifactService:
    def build_json_artifact(
        self,
        *,
        export_id: str,
        candidate_itr: str,
        payload: dict[str, Any],
    ) -> tuple[ItrExportArtifact, bytes]:
        content_payload = public_export_payload(payload)
        content = json.dumps(content_payload, sort_keys=True, indent=2, default=str).encode("utf-8")
        filename = safe_filename(f"{candidate_itr.lower()}_official_schema_export_{export_id[:8]}.json")
        artifact = ItrExportArtifact(
            artifact_type=ItrExportArtifactType.OFFICIAL_ITR_JSON,
            filename=filename,
            mime_type="application/json",
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            created_at=datetime.now(UTC),
        )
        return artifact, content
