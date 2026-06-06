"""Validation for document intake uploads."""

from pathlib import Path

from app.models.document import DocumentType


ALLOWED_EXTENSIONS = {".csv", ".xls", ".xlsx", ".pdf", ".txt"}
EXTENSION_MIME_TYPES = {
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
    ".xls": {"application/vnd.ms-excel"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
}


class DocumentValidationService:
    def __init__(self, max_size_bytes: int) -> None:
        self.max_size_bytes = max_size_bytes

    def validate(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        document_type: DocumentType,
    ) -> None:
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported file type")
        if size_bytes <= 0:
            raise ValueError("Uploaded file is empty")
        if size_bytes > self.max_size_bytes:
            raise ValueError("Uploaded file exceeds the configured size limit")
        allowed_mimes = EXTENSION_MIME_TYPES[suffix]
        normalized_content_type = (content_type or "application/octet-stream").split(";")[0].lower()
        if normalized_content_type not in allowed_mimes:
            raise ValueError("Uploaded file MIME type does not match its extension")
        if document_type not in set(DocumentType):
            raise ValueError("Unsupported document type")
