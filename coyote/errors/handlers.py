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

from flask import render_template

from .exceptions import AppError


def register_error_handlers(app):
    """Register error handlers for the application."""

    @app.errorhandler(AppError)
    def handle_app_error(error):
        """Handles custom application errors."""
        return (
            render_template(
                "error.html",
                error=error.message,
                details=error.details,
            ),
            error.status_code,
        )

    @app.errorhandler(400)
    def handle_400_error(error):
        """Handles 400 Bad Request."""
        return (
            render_template(
                "error.html",
                error="Bad Request: The server could not understand your request.",
                details="Check the request parameters and try again.",
            ),
            400,
        )

    @app.errorhandler(401)
    def handle_401_error(error):
        """Handles 401 Unauthorized."""
        return (
            render_template(
                "error.html",
                error="Unauthorized: Access is denied.",
                details="You need to log in to access this resource.",
            ),
            401,
        )

    @app.errorhandler(403)
    def handle_403_error(error):
        """Handles 403 Forbidden."""
        return (
            render_template(
                "error.html",
                error="Forbidden: You do not have permission to access this resource.",
                details="If you believe this is an error, contact support.",
            ),
            403,
        )

    @app.errorhandler(404)
    def handle_404_error(error):
        """Handles 404 Not Found."""
        return (
            render_template(
                "error.html",
                error="The requested resource was not found.",
                details="Ensure the URL is correct or try a different resource.",
            ),
            404,
        )

    @app.errorhandler(405)
    def handle_405_error(error):
        """Handles 405 Method Not Allowed."""
        return (
            render_template(
                "error.html",
                error="Method Not Allowed: The HTTP method is not supported for this route.",
                details="Check the request method and try again.",
            ),
            405,
        )

    @app.errorhandler(408)
    def handle_408_error(error):
        """Handles 408 Request Timeout."""
        return (
            render_template(
                "error.html",
                error="Request Timeout: The server timed out waiting for your request.",
                details="Try submitting the request again.",
            ),
            408,
        )

    @app.errorhandler(409)
    def handle_409_error(error):
        """Handles 409 Conflict."""
        return (
            render_template(
                "error.html",
                error="Conflict: A conflict occurred with the current state of the resource.",
                details="Resolve the conflict and try again.",
            ),
            409,
        )

    @app.errorhandler(500)
    def handle_500_error(error):
        """Handles 500 Internal Server Error."""
        return (
            render_template(
                "error.html",
                error="An internal server error occurred.",
                details="Please try again later. If the issue persists, contact support.",
            ),
            500,
        )

    @app.errorhandler(502)
    def handle_502_error(error):
        """Handles 502 Bad Gateway."""
        return (
            render_template(
                "error.html",
                error="Bad Gateway: The server received an invalid response from the upstream server.",
                details="Try again later. If the issue persists, contact support.",
            ),
            502,
        )

    @app.errorhandler(503)
    def handle_503_error(error):
        """Handles 503 Service Unavailable."""
        return (
            render_template(
                "error.html",
                error="Service Unavailable: The server is temporarily unable to handle your request.",
                details="Try again later.",
            ),
            503,
        )

    @app.errorhandler(504)
    def handle_504_error(error):
        """Handles 504 Gateway Timeout."""
        return (
            render_template(
                "error.html",
                error="Gateway Timeout: The server did not receive a response from the upstream server.",
                details="Try again later. If the issue persists, contact support.",
            ),
            504,
        )

    app.logger.info("Error handlers registered.")
