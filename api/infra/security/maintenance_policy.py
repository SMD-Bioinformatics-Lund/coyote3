"""Fixed authorization capability for the trusted maintenance worker host."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class MaintenanceWorkerIdentity(BaseModel):
    """Maintenance execution identity independent of interactive user sessions."""

    model_config = ConfigDict(frozen=True)

    username: Literal["celery-maintenance"] = "celery-maintenance"
    fullname: str = "Maintenance worker"
    is_superuser: Literal[False] = False
    must_change_password: Literal[False] = False


class MaintenanceWorkerPolicy:
    """Grant only fixed maintenance execution, without clinical or account administration."""

    def permission_allowed(
        self, user: Any, permission_id: str, *, context: dict[str, Any] | None = None
    ) -> bool:
        """Allow maintenance only for the host's fixed identity and without resource scope."""
        return (
            isinstance(user, MaintenanceWorkerIdentity)
            and permission_id == "app.maintenance:run"
            and not context
        )

    def scope_allowed(self, user: Any, context: dict[str, Any] | None) -> bool:
        """Deny sample-scoped application operations for the maintenance identity."""
        return False
