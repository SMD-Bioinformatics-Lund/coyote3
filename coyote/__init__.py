"""Initialize Flask app."""

from flask import Flask
from flask_cors import CORS

import config
from . import extensions


def init_app(testing: bool = False) -> Flask:
    """Create Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Allows cross-origin requests for CDM/api
    # /trends needs this to work.
    CORS(app)

    if testing:
        app.logger.info("Testing mode ON.")
        app.logger.info("Loading config.TestConfig")
        app.config.from_object(config.TestConfig())

    elif app.debug:
        app.logger.debug(
            "Debug mode ON. "
            "(Jag ropar ut mitt innersta hav, jag ropar ut all min skit och allt mitt skav!)"
        )
        app.logger.info("Loading config.DevelopmentConfig")
        app.config.from_object(config.DevelopmentConfig())

    else:
        app.logger.info("Loading config.DefaultConfig")
        app.config.from_object(config.DefaultConfig())  # Note initialization of Config

    app.logger.info("Initializing app extensions + blueprints:")
    with app.app_context():
        init_login_manager(app)
        init_db(app)
        init_store(app)
        register_blueprints(app)
        init_ldap(app)

    app.logger.info("App initialization finished. Returning app.")
    return app


def init_db(app) -> None:
    app.logger.info("Initializing MongoDB")
    # TODO: Add connection checks
    app.logger.info("Initializing mongodb at: " f"{app.config['MONGO_URI']}")
    extensions.mongo.init_app(app)


def init_store(app) -> None:
    app.logger.info("Initializing MongoAdapter at: " f"{app.config['MONGO_URI']}")
    extensions.store.init_from_app(app)


def register_blueprints(app) -> None:
    app.logger.info("Initializing blueprints")

    def bp_debug_msg(msg):
        app.logger.debug(f"Blueprint registered: {msg}")

    # Coyote main:
    bp_debug_msg("main_bp")
    from coyote.blueprints.main import main_bp

    app.register_blueprint(main_bp)

    # Login stuff
    bp_debug_msg("login_bp")
    from coyote.blueprints.login import login_bp

    app.register_blueprint(login_bp)

    # Show Case Variants
    bp_debug_msg("varaints_bp")
    from coyote.blueprints.variants import variants_bp

    app.register_blueprint(variants_bp)


def init_login_manager(app) -> None:
    app.logger.debug("Initializing login_manager")
    extensions.login_manager.init_app(app)
    extensions.login_manager.login_view = "login_bp.login"


def init_ldap(app):
    app.logger.debug("Initializing ldap login_manager")
    extensions.ldap_manager.init_app(app)
