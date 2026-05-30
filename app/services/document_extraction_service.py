"""Document extraction coordinator for Phase 1 intake."""

from io import BytesIO, StringIO
from pathlib import Path

from app.models.document import ExtractionResult
from app.services.document_mapping_service import DocumentMappingService
from app.services.storage_service import LocalStorageService


class DocumentExtractionService:
    def __init__(
        self,
        storage: LocalStorageService,
        mapping_service: DocumentMappingService | None = None,
    ) -> None:
        self.storage = storage
        self.mapping_service = mapping_service or DocumentMappingService()

    def extract(self, document_id: str) -> ExtractionResult:
        record = self.storage.get(document_id)
        suffix = Path(record.safe_filename).suffix.lower()
        if suffix == ".csv":
            rows = self._read_csv(self.storage.read_bytes(document_id))
            result = ExtractionResult(
                document_id=document_id,
                status="completed",
                fields=self.mapping_service.map_tabular_rows(document_id, rows),
            )
        elif suffix in {".xls", ".xlsx"}:
            rows = self._read_excel(self.storage.read_bytes(document_id))
            result = ExtractionResult(
                document_id=document_id,
                status="completed",
                fields=self.mapping_service.map_tabular_rows(document_id, rows),
            )
        elif suffix == ".pdf":
            result = self._extract_pdf(document_id, record.storage_path)
        elif suffix == ".txt":
            text = self.storage.read_bytes(document_id).decode("utf-8", errors="ignore")
            result = ExtractionResult(
                document_id=document_id,
                status="completed",
                fields=self.mapping_service.map_text(document_id, text),
            )
        else:
            result = ExtractionResult(
                document_id=document_id,
                status="rejected",
                warnings=["Unsupported file type for extraction"],
            )

        self.storage.update(record.model_copy(update={"status": "extracted" if result.status == "completed" else "rejected"}))
        return result.model_copy(
            update={
                "owner_user_id": record.owner_user_id,
                "organization_id": record.organization_id,
                "created_by": record.created_by,
            }
        )

    def _read_csv(self, content: bytes) -> list[dict[str, object]]:
        import pandas as pd

        return pd.read_csv(StringIO(content.decode("utf-8-sig"))).fillna("").to_dict(orient="records")

    def _read_excel(self, content: bytes) -> list[dict[str, object]]:
        import pandas as pd

        return pd.read_excel(BytesIO(content)).fillna("").to_dict(orient="records")

    def _extract_pdf(self, document_id: str, storage_path: str) -> ExtractionResult:
        try:
            from pdfminer.pdfdocument import PDFDocument, PDFPasswordIncorrect
            from pdfminer.pdfparser import PDFParser
            import pdfplumber
        except ImportError:
            return ExtractionResult(
                document_id=document_id,
                status="warning",
                warnings=["PDF extraction dependency is unavailable; OCR is not configured in Phase 1."],
            )

        try:
            with open(storage_path, "rb") as pdf_file:
                PDFDocument(PDFParser(pdf_file))
        except PDFPasswordIncorrect:
            return ExtractionResult(
                document_id=document_id,
                status="rejected",
                warnings=["Encrypted PDFs are not supported in Phase 1."],
            )
        except Exception:
            # Let pdfplumber produce the user-facing extraction warning below.
            pass

        try:
            with pdfplumber.open(storage_path) as pdf:
                if getattr(pdf, "is_encrypted", False):
                    return ExtractionResult(
                        document_id=document_id,
                        status="rejected",
                        warnings=["Encrypted PDFs are not supported in Phase 1."],
                    )
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            message = str(exc).lower()
            if "encrypt" in message or "decrypt" in message or "password" in message:
                return ExtractionResult(
                    document_id=document_id,
                    status="rejected",
                    warnings=["Encrypted PDFs are not supported in Phase 1."],
                )
            return ExtractionResult(
                document_id=document_id,
                status="warning",
                warnings=["PDF text extraction failed; OCR fallback is not configured in Phase 1."],
            )

        return ExtractionResult(
            document_id=document_id,
            status="completed",
            fields=self.mapping_service.map_text(document_id, text),
            warnings=[] if text.strip() else ["No text was extractable; OCR fallback is not configured in Phase 1."],
        )
