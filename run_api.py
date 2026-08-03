"""Local FastAPI development entrypoint.

The React UI is started independently from ``frontend/`` with Vite.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.app.main:app", host="0.0.0.0", port=8001, reload=True)
