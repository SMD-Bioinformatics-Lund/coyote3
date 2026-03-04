"""FastAPI API entrypoint.

This launcher runs only the backend API runtime (`api.app:app`).
Use `run.py` for Flask UI runtime.
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("api.app:app", host="0.0.0.0", port=8001, reload=True)
