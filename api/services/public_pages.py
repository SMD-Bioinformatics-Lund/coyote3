"""Public product and contact pages composed by the standalone web application."""

from collections.abc import Mapping
from typing import Any

from api.config.application_metadata import APPLICATION_DESCRIPTION
from api.config.contact import application_integration_links
from coyote3.application.operations.public import PublicApplication
from coyote3.config.policy import get_runtime_environment


class PublicPages:
    """Combine deployment metadata with public clinical reference operations."""

    def __init__(self, config: Mapping[str, Any], references: PublicApplication) -> None:
        """Bind explicit public deployment configuration and reference operations.

        Args:
            config: Host settings from which only allowlisted public fields are returned.
            references: Read-only clinical reference and version operations.
        """
        self._config, self._references = config, references

    def contact(self) -> dict[str, Any]:
        """Return center-owned public contact and support metadata."""
        return dict(self.contact_payload())

    def about(self) -> dict[str, Any]:
        """Return public application, support, and reference-version metadata."""
        payload = self.contact_payload()
        payload.update(
            {
                "application": {
                    "name": "Coyote3",
                    "version": self._config.get("APP_VERSION"),
                    "environment": get_runtime_environment(self._config),
                    "script_name": self._config.get("SCRIPT_NAME"),
                    "description": APPLICATION_DESCRIPTION,
                },
                "software": self._references.software_versions(),
                "references": self._references.reference_versions(),
                "databases": {
                    "primary": self._config.get("COYOTE3_DB"),
                    "identity": self._config.get("IDENTITY_DB"),
                    "knowledgebase": self._config.get("KNOWLEDGEBASE_DB"),
                    "bam_service": self._config.get("BAM_DB"),
                    "knowledgebases": {
                        "oncokb_public": self._config.get("ONCOKB_BASE_URL"),
                        "clinpgx_public": self._config.get("CLINPGX_BASE_URL"),
                    },
                },
                "software_links": application_integration_links(self._config),
                "knowledgebase_status": self._references.knowledgebase_status(),
            }
        )
        return dict(payload)

    def contact_payload(self) -> dict[str, Any]:
        """Build center-owned public contact and support metadata."""
        contact = self._config.get("CONTACT") or {}
        organization = dict(contact.get("organization") or {})
        organization.setdefault("name", self._config.get("ORGANIZATION_NAME") or "Coyote3")
        payload = {
            "organization": organization,
            "support": dict(contact.get("support") or {}),
            "codebase": dict(contact.get("codebase") or {}),
            "contacts": list(contact.get("contacts") or []),
            "links": list(contact.get("links") or []),
            "hours": list(contact.get("hours") or []),
            "meta": dict(contact.get("meta") or {}),
        }
        return dict(payload)
