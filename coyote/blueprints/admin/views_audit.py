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

"""Admin audit-log routes."""

from datetime import datetime, timezone
from pathlib import Path

from flask import current_app as app
from flask import render_template

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.auth.decorators import require


@admin_bp.route("/audit")
@require("view_audit_logs", min_role="admin", min_level=99999)
def audit():
    logs_path = Path(app.config["LOGS"], "audit")
    cutoff_ts = util.common.utc_now().timestamp() - (30 * 24 * 60 * 60)

    log_files = sorted(
        [f for f in logs_path.glob("*.log*") if f.stat().st_mtime >= cutoff_ts],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    logs_data = []
    for file in log_files:
        with file.open() as f:
            logs_data.extend([line.strip() for line in f])

    def _parse_log_timestamp(line: str) -> datetime:
        try:
            first_part = line.split(" - ", 1)[0].strip("[] ")
            if not first_part:
                return datetime.min

            if "," in first_part and "T" not in first_part:
                return datetime.strptime(first_part, "%Y-%m-%d %H:%M:%S,%f")

            ts = first_part.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return datetime.min

    logs_data = sorted(logs_data, key=lambda line: _parse_log_timestamp(line), reverse=True)
    return render_template("audit/audit.html", logs=logs_data)
