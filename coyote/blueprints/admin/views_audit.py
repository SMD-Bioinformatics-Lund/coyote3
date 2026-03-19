"""Admin audit-log routes."""

import json
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app as app
from flask import render_template
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util


@admin_bp.route("/audit")
@login_required
def audit():
    """Render the audit-log page from structured audit log files."""
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

    def _parse_line(line: str) -> dict:
        """Parse line.

        Args:
                line: Line.

        Returns:
                The  parse line result.
        """
        entry = {
            "raw": line,
            "timestamp": datetime.min,
            "level": "INFO",
            "log": None,
        }
        try:
            parts = line.split(" - ", 7)
            if len(parts) == 8:
                first_part = parts[0].strip("[] ")
                entry["level"] = parts[3].strip("[] ") or "INFO"
                if first_part:
                    if "," in first_part and "T" not in first_part:
                        entry["timestamp"] = datetime.strptime(first_part, "%Y-%m-%d %H:%M:%S,%f")
                    else:
                        ts = first_part.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(ts)
                        if dt.tzinfo is not None:
                            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                        entry["timestamp"] = dt
                entry["log"] = json.loads(parts[7])
        except Exception:
            pass
        return entry

    parsed_logs = sorted(
        (_parse_line(line) for line in logs_data), key=lambda item: item["timestamp"], reverse=True
    )
    return render_template("audit/audit.html", logs=parsed_logs)
