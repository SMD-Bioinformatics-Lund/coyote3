"""Local FastAPI runner for Coyote3 API service."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("api.app:app", host="0.0.0.0", port=8001, reload=True)
