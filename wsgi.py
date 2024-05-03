"""Application entry point."""
from coyote import init_app

app = init_app()

if __name__ != "__main__":
    print("Setting up Gunicorn logging.")
    import logging

    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    app.run(host="0.0.0.0")
