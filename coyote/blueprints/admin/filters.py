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

from flask import current_app as app
from coyote.util.misc import EnhancedJSONEncoder
from markupsafe import Markup
import json
from datetime import datetime


@app.template_filter("now")
def now_filter(dummy=None, format="%Y-%m-%d %H:%M:%S"):
    return datetime.utcnow().strftime(format)


@app.template_filter("prettyjson")
def pretty_json_filter(value):
    return Markup(
        json.dumps(
            value, indent=2, ensure_ascii=False, cls=EnhancedJSONEncoder
        )
    )
