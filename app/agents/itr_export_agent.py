"""Agent wrapper that delegates export work to deterministic services only."""

from app.models.itr_export import ItrExport, ItrExportExplanation
from app.services.itr_export_service import ItrExportService


class ItrExportAgent:
    def __init__(self, service: ItrExportService | None = None) -> None:
        self.service = service or ItrExportService()

    def generate_export(self, **kwargs) -> ItrExport:
        return self.service.generate(**kwargs)

    def explain(self, export: ItrExport) -> ItrExportExplanation:
        return self.service.explain(export)
