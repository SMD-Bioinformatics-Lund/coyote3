"""Read individual allowed metadata fields for service integrations."""

from typing import Any, get_args

from coyote3.contracts.resource_fields import (
    AssayField,
    ConfigurationField,
    DiagnosisField,
    GeneListField,
    GroupField,
    SampleField,
)
from coyote3.contracts.resource_metadata import (
    AssayMetadata,
    ConfigurationMetadata,
    DiagnosisMetadata,
    GeneListMetadata,
    GroupMetadata,
    SampleMetadata,
)
from coyote3.domain.common.errors import api_error


class ResourceFieldService:
    """Return one allowed resource value after the caller's permission checks."""

    @classmethod
    def from_store(cls, store: Any) -> "ResourceFieldService":
        """Bind the existing governed resource repositories.

        Args:
            store: Repository container for the application database.

        Returns:
            A service for individual metadata lookups.
        """
        return cls(
            panels=store.assay_panel_repository,
            configurations=store.assay_configuration_repository,
            groups=store.assay_group_repository,
            diagnoses=store.assay_diagnosis_repository,
            gene_lists=store.gene_list_repository,
        )

    def __init__(
        self, *, panels: Any, configurations: Any, groups: Any, diagnoses: Any, gene_lists: Any
    ) -> None:
        """Bind repositories for assays, configurations, groups, diagnoses and gene lists."""
        self.panels = panels
        self.configurations = configurations
        self.groups = groups
        self.diagnoses = diagnoses
        self.gene_lists = gene_lists

    @staticmethod
    def _value(document: dict[str, Any] | None, field: str, allowed: Any) -> Any:
        """Validate an allowed key and return its value, preserving absent values as null.

        Args:
            document: Resource record, or None when not found.
            field: One supported metadata key.
            allowed: Literal type defining the resource's permitted keys.

        Returns:
            The field value, including null for optional absent metadata.

        Raises:
            AppError: If the key is unsupported (422) or the resource is missing (404).
        """
        if field not in get_args(allowed):
            raise api_error(422, "Unsupported resource field")
        if document is None:
            raise api_error(404, "Resource not found")
        return document.get(field)

    def sample_field(self, sample: dict[str, Any], field: SampleField) -> Any:
        """Return one metadata value from an already authorized sample.

        Args:
            sample: Sample returned by the standard sample scope authorization lookup.
            field: Allowed sample metadata key.

        Returns:
            One value; missing group metadata is resolved from the assay.
        """
        value = self._value(sample, field, SampleField)
        if field == "asp_group" and value is None:
            return (self.panels.get_asp(sample["asp_id"]) or {}).get("asp_group")
        return value

    def assay_field(self, asp_id: str, field: AssayField) -> Any:
        """Read one allowed value from the active assay definition.

        Args:
            asp_id: Assay business identifier.
            field: Allowed assay metadata key.

        Returns:
            The requested value, or null for absent optional metadata.

        Raises:
            AppError: For a missing assay or unsupported key.
        """
        return self._value(self.panels.get_asp(asp_id), field, AssayField)

    def configuration_field(self, aspc_id: str, field: ConfigurationField) -> Any:
        """Read one active configuration value, including nested report sections.

        Args:
            aspc_id: Configuration business identifier including diagnosis and environment.
            field: Allowed configuration metadata key.

        Returns:
            The requested value; missing report sections produce an empty list.

        Raises:
            AppError: For a missing configuration or unsupported key.
        """
        document = self.configurations.get_aspc_with_id(aspc_id)
        value = self._value(document, field, ConfigurationField)
        if field == "report_sections":
            return ((document or {}).get("reporting") or {}).get("report_sections", [])
        return value

    def group_field(self, group_id: str, field: GroupField) -> Any:
        """Read one biological group identity, hierarchy or availability value.

        Args:
            group_id: Biological group business identifier.
            field: Allowed group metadata key.

        Returns:
            The requested value, or null for absent optional metadata.

        Raises:
            AppError: For a missing group or unsupported key.
        """
        return self._value(self.groups.get(group_id), field, GroupField)

    def diagnosis_field(self, diagnosis_id: str, field: DiagnosisField) -> Any:
        """Read one shared diagnosis value or its associated assay identifiers.

        Args:
            diagnosis_id: Shared diagnosis business identifier.
            field: Allowed diagnosis metadata key.

        Returns:
            The requested value; assay identifiers are sorted alphabetically.

        Raises:
            AppError: For a missing diagnosis or unsupported key.
        """
        document = next(
            (
                row
                for row in self.diagnoses.list_definitions()
                if row["diagnosis_id"] == diagnosis_id
            ),
            None,
        )
        value = self._value(document, field, DiagnosisField)
        if field == "asp_ids":
            return sorted(self.diagnoses.assays_by_diagnosis().get(diagnosis_id, []))
        return value

    def gene_list_field(self, isgl_id: str, field: GeneListField) -> Any:
        """Read one gene-list metadata value or its gene count.

        Args:
            isgl_id: Gene-list business identifier.
            field: Allowed gene-list metadata key.

        Returns:
            The requested value; gene_count counts entries without returning gene content.

        Raises:
            AppError: For a missing gene list or unsupported key.
        """
        document = self.gene_lists.get_isgl(isgl_id, is_active=None)
        value = self._value(document, field, GeneListField)
        if field == "gene_count":
            return len((document or {}).get("genes") or [])
        return value

    @staticmethod
    def _metadata(document: dict[str, Any] | None, fields: Any) -> dict[str, Any]:
        """Project an existing document onto the permitted metadata keys.

        Args:
            document: Resource document, or None when lookup failed.
            fields: Literal contract defining allowed metadata keys.

        Returns:
            All allowed keys, with null for missing values.

        Raises:
            AppError: If the resource does not exist.
        """
        if document is None:
            raise api_error(404, "Resource not found")
        return {key: document.get(key) for key in get_args(fields)}

    def sample_metadata(self, sample: dict[str, Any]) -> SampleMetadata:
        """Project an authorized sample, resolving its group by the existing field rule.

        Args:
            sample: Sample already checked for the caller's access and scope.

        Returns:
            Permitted metadata without clinical content or file paths.
        """
        values = self._metadata(sample, SampleField)
        values["asp_group"] = self.sample_field(sample, "asp_group")
        return SampleMetadata.model_validate(values)

    def assay_metadata(self, asp_id: str) -> AssayMetadata:
        """Fetch permitted metadata from one active assay revision.

        Args:
            asp_id: Assay business identifier.

        Returns:
            Metadata using one repository lookup; a missing assay raises 404.
        """
        return AssayMetadata.model_validate(self._metadata(self.panels.get_asp(asp_id), AssayField))

    def configuration_metadata(self, aspc_id: str) -> ConfigurationMetadata:
        """Fetch one active configuration, projecting its nested report section names.

        Args:
            aspc_id: Configuration business identifier.

        Returns:
            Permitted metadata; a missing configuration raises 404.
        """
        document = self.configurations.get_aspc_with_id(aspc_id)
        values = self._metadata(document, ConfigurationField)
        values["report_sections"] = ((document or {}).get("reporting") or {}).get(
            "report_sections", []
        )
        return ConfigurationMetadata.model_validate(values)

    def group_metadata(self, group_id: str) -> GroupMetadata:
        """Fetch biological group metadata with one lookup.

        Args:
            group_id: Biological group business identifier.

        Returns:
            Permitted metadata; a missing group raises 404.
        """
        return GroupMetadata.model_validate(self._metadata(self.groups.get(group_id), GroupField))

    def diagnosis_metadata(self, diagnosis_id: str) -> DiagnosisMetadata:
        """Fetch shared diagnosis metadata with its linked assay identifiers.

        Args:
            diagnosis_id: Shared diagnosis business identifier.

        Returns:
            Permitted metadata with sorted assay identifiers; a missing diagnosis raises 404.
        """
        document = next(
            (
                row
                for row in self.diagnoses.list_definitions()
                if row["diagnosis_id"] == diagnosis_id
            ),
            None,
        )
        values = self._metadata(document, DiagnosisField)
        values["asp_ids"] = sorted(self.diagnoses.assays_by_diagnosis().get(diagnosis_id, []))
        return DiagnosisMetadata.model_validate(values)

    def gene_list_metadata(self, isgl_id: str) -> GeneListMetadata:
        """Fetch permitted gene-list metadata without exposing gene content.

        Args:
            isgl_id: Gene-list business identifier.

        Returns:
            Metadata with the computed gene count; a missing gene list raises 404.
        """
        document = self.gene_lists.get_isgl(isgl_id, is_active=None)
        values = self._metadata(document, GeneListField)
        values["gene_count"] = len((document or {}).get("genes") or [])
        return GeneListMetadata.model_validate(values)
