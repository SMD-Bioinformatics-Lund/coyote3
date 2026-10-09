"""Transport contracts for the private administrative demonstration installer."""

from pydantic import BaseModel


class DemoSampleStatus(BaseModel):
    """A bundled synthetic manifest and its installation state."""

    key: str
    name: str
    installed: bool


class DemoInstallationPlan(BaseModel):
    """Configuration counts and sample states for the packaged demonstration bundle."""

    configuration: dict[str, int]
    configuration_installed: bool
    samples: list[DemoSampleStatus]


class DemoInstallResult(BaseModel):
    """Successful single-operation result; failures use the standard error envelope."""

    status: str
