"""Role and ownership checks for protected MVP resources."""

from typing import Protocol

from app.models.auth import AccessDecision, SessionContext, UserRole


class OwnedResource(Protocol):
    owner_user_id: str | None
    organization_id: str | None


class AuthorizationService:
    def can_read_document(self, session: SessionContext, resource: OwnedResource) -> AccessDecision:
        return self._can_access(session, resource)

    def can_write_document(self, session: SessionContext, resource: OwnedResource) -> AccessDecision:
        return self._can_access(session, resource)

    def can_read_validation_report(self, session: SessionContext, resource: OwnedResource) -> AccessDecision:
        return self._can_access(session, resource)

    def can_read_tax_computation(self, session: SessionContext, resource: OwnedResource) -> AccessDecision:
        return self._can_access(session, resource)

    def can_read_filing_package(self, session: SessionContext, resource: OwnedResource) -> AccessDecision:
        return self._can_access(session, resource)

    def can_download_artifact(self, session: SessionContext, resource: OwnedResource) -> AccessDecision:
        return self._can_access(session, resource)

    def _can_access(self, session: SessionContext, resource: OwnedResource) -> AccessDecision:
        if not resource.organization_id or not resource.owner_user_id:
            return AccessDecision(allowed=False, reason="missing_owner")
        if resource.organization_id != session.organization_id:
            return AccessDecision(allowed=False, reason="cross_organization")
        if session.role == UserRole.SERVICE:
            return AccessDecision(allowed=True, reason="service_internal")
        if session.role in {UserRole.REVIEWER, UserRole.ADMIN}:
            return AccessDecision(allowed=True, reason="organization_scoped")
        if session.role == UserRole.TAXPAYER and resource.owner_user_id == session.user_id:
            return AccessDecision(allowed=True, reason="owner")
        return AccessDecision(allowed=False, reason="not_owner")
