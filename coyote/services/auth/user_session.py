from flask_login import UserMixin
from coyote.models.user import UserModel
from coyote.extensions import roles_model
from coyote.services.permissions import PermissionService


class User(UserMixin):
    def __init__(self, user_model: UserModel):
        self.user_model = user_model

    def get_id(self):
        return self.user_model.id

    def __getattr__(self, item):
        # Proxy everything else to the user_model
        return getattr(self.user_model, item)

    def to_dict(self):
        return self.user_model.dict(by_alias=True)

    @property
    def last_login(self):
        return self.user_model.last_login

    @property
    def formatted_last_login(self):
        return self.user_model.formatted_last_login()

    def get_permission_service(self):
        return PermissionService(self, roles_model)

    def can(self, permission: str) -> bool:
        return self.get_permission_service().can(permission)

    def has_min_role(self, required_role: str) -> bool:
        return self.get_permission_service().has_min_role(required_role)
