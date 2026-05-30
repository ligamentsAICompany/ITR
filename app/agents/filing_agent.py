"""Filing package agent constrained to deterministic package assembly."""

from app.models.decision import ITRDecisionResponse
from app.models.document import PublicDocumentMetadata
from app.models.filing_package import FilingPackage, FilingPackageExplanation
from app.models.tax_computation import TaxComputationResult
from app.models.tax_profile import CanonicalTaxProfile
from app.models.validation import ValidationReport
from app.services.filing_package_service import FilingPackageService


class FilingAgent:
    """Explains and assembles packages without deciding ITR, computing tax, or filing."""

    def __init__(self, service: FilingPackageService | None = None) -> None:
        self.service = service or FilingPackageService()

    def generate_package(
        self,
        *,
        profile: CanonicalTaxProfile,
        candidate_itr: ITRDecisionResponse,
        validation_report: ValidationReport,
        tax_computation_result: TaxComputationResult,
        documents: list[PublicDocumentMetadata],
        owner_user_id: str | None = None,
        organization_id: str | None = None,
        created_by: str | None = None,
    ) -> FilingPackage:
        payload = {
            "profile": profile,
            "candidate_itr": candidate_itr,
            "validation_report": validation_report,
            "tax_computation_result": tax_computation_result,
            "documents": documents,
        }
        if owner_user_id is not None or organization_id is not None or created_by is not None:
            payload.update(
                owner_user_id=owner_user_id,
                organization_id=organization_id,
                created_by=created_by,
            )
        return self.service.generate(**payload)

    def explain(self, package: FilingPackage) -> FilingPackageExplanation:
        return self.service.explain(package)
