#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

from flask_login import UserMixin
from coyote.models.user import UserModel


class User(UserMixin):
    def __init__(self, user_model: UserModel):
        self.user_model = user_model

    def get_id(self):
        return self.user_model.id

    def __getattr__(self, name):
        return getattr(self.user_model, name)

    def to_dict(self):
        return self.user_model.to_dict()

    @property
    def access_level(self):
        return self.user_model.access_level
