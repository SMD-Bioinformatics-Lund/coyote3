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

from flask import jsonify, render_template, request
from .exceptions import AppError


def register_error_handlers(app):
    """Register error handlers for the application."""
    from coyote.integrations.api.api_client import ApiRequestError

    def is_api_request() -> bool:
        path = request.path or ""
        app_root = app.config.get("APPLICATION_ROOT", "")
        if app_root and path.startswith(app_root):
            path = path[len(app_root) :] or "/"
        return path == "/api" or path.startswith("/api/")

    def error_response(status_code: int, error: str, details: str):
        if is_api_request():
            return jsonify({"status": status_code, "error": error, "details": details}), status_code
        return (
            render_template(
                "error.html",
                error=error,
                details=details,
            ),
            status_code,
        )

    @app.errorhandler(AppError)
    def handle_app_error(error):
        """Handles custom application errors."""
        return error_response(error.status_code, error.message, error.details)

    @app.errorhandler(ApiRequestError)
    def handle_api_request_error(error):
        """Handles upstream API client failures from web routes."""
        status_code = error.status_code or 502
        return error_response(status_code, "API request failed.", str(error))

    @app.errorhandler(400)
    def handle_400_error(error):
        """Handles 400 Bad Request."""
        return error_response(
            400,
            "Bad Request: The server could not understand your request.",
            "Check the request parameters and try again.",
        )

    @app.errorhandler(401)
    def handle_401_error(error):
        """Handles 401 Unauthorized."""
        return error_response(
            401,
            "Unauthorized: Access is denied.",
            "You need to log in to access this resource.",
        )

    @app.errorhandler(403)
    def handle_403_error(error):
        """Handles 403 Forbidden."""
        return error_response(
            403,
            "Forbidden: You do not have permission to access this resource.",
            "If you believe this is an error, contact support.",
        )

    @app.errorhandler(404)
    def handle_404_error(error):
        """Handles 404 Not Found."""
        return error_response(
            404,
            "The requested resource was not found.",
            "Ensure the URL is correct or try a different resource.",
        )

    @app.errorhandler(405)
    def handle_405_error(error):
        """Handles 405 Method Not Allowed."""
        return error_response(
            405,
            "Method Not Allowed: The HTTP method is not supported for this route.",
            "Check the request method and try again.",
        )

    @app.errorhandler(408)
    def handle_408_error(error):
        """Handles 408 Request Timeout."""
        return error_response(
            408,
            "Request Timeout: The server timed out waiting for your request.",
            "Try submitting the request again.",
        )

    @app.errorhandler(409)
    def handle_409_error(error):
        """Handles 409 Conflict."""
        return error_response(
            409,
            "Conflict: A conflict occurred with the current state of the resource.",
            "Resolve the conflict and try again.",
        )

    @app.errorhandler(500)
    def handle_500_error(error):
        """Handles 500 Internal Server Error."""
        return error_response(
            500,
            "An internal server error occurred.",
            "Please try again later. If the issue persists, contact support.",
        )

    @app.errorhandler(502)
    def handle_502_error(error):
        """Handles 502 Bad Gateway."""
        return error_response(
            502,
            "Bad Gateway: The server received an invalid response from the upstream server.",
            "Try again later. If the issue persists, contact support.",
        )

    @app.errorhandler(503)
    def handle_503_error(error):
        """Handles 503 Service Unavailable."""
        return error_response(
            503,
            "Service Unavailable: The server is temporarily unable to handle your request.",
            "Try again later.",
        )

    @app.errorhandler(504)
    def handle_504_error(error):
        """Handles 504 Gateway Timeout."""
        return error_response(
            504,
            "Gateway Timeout: The server did not receive a response from the upstream server.",
            "Try again later. If the issue persists, contact support.",
        )

    app.logger.info("Error handlers registered.")
