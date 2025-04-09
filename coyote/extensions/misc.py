# -*- coding: utf-8 -*-
# Miscellaneous utilities for Coyote


import json
from datetime import datetime


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()  # or use obj.strftime(...) for a custom format
        return super().default(obj)
