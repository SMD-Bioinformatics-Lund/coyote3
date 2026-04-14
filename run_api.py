"""FastAPI API entrypoint.

This launcher runs only the backend API runtime (`api.main:app`).
Use `run.py` for the Flask UI runtime.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
