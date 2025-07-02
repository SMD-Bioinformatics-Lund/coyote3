import json
from datetime import datetime

from flask import current_app as app
from markupsafe import Markup

from coyote.util.misc import EnhancedJSONEncoder


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
