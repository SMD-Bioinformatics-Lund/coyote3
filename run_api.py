# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Local FastAPI development entrypoint.

The React UI is started independently from ``frontend/`` with Vite.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "coyote_api.app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=["api/src", "core/src", "adapters/mongo/src"],
    )
